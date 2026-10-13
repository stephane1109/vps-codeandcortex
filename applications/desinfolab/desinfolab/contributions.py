"""Soumission anonyme, contrôle documentaire et modération transactionnelle."""

import hashlib
import json
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from .base import transaction
from .catalogue import MODELES, donnees_editables, obtenir_fiche, serialiser
from .modeles import Compte, Contribution, Historique, Plateforme, Quota, Reference, Source, Tag, maintenant
from .securite import ErreurMetier, exiger_admin, verifier_defi
from .validation import SAISIES, canonicaliser_url, cle_texte


def valider_donnees(session, entite, donnees, cible_id=None):
    if entite not in SAISIES:
        raise ErreurMetier("Type de contribution inconnu.")
    try:
        saisie = SAISIES[entite].model_validate(donnees)
    except ValidationError as erreur:
        raise ErreurMetier(
            " ; ".join(f"{'.'.join(map(str, e['loc']))} : {e['msg']}" for e in erreur.errors())
        ) from None
    d = saisie.model_dump(mode="json")
    for champ, modele in (("plateforme_id", Plateforme), ("source_id", Source), ("compte_id", Compte)):
        if d.get(champ) and session.get(modele, d[champ]) is None:
            raise ErreurMetier(f"{champ} ne désigne aucune fiche validée.")
    if entite == "contenu" and d["compte_id"]:
        compte = session.get(Compte, d["compte_id"])
        if compte.source_id != d["source_id"] or compte.plateforme_id != d["plateforme_id"]:
            raise ErreurMetier("Le compte, sa source et sa plateforme doivent correspondre.")
    tags = [session.get(Tag, i) for i in set(d.get("tags", []))]
    if any(t is None for t in tags):
        raise ErreurMetier("Un tag n'est pas encore validé.")
    if "tags" in d:
        d["tags"] = sorted(set(d["tags"]))
    qualifications = {t.id for t in tags if t.nature == "qualification"}
    justifiees = {r["qualification_tag_id"] for r in d["references"] if r["qualification_tag_id"]}
    if not qualifications <= justifiees:
        raise ErreurMetier(
            "Chaque qualification factuelle exige une référence qui la justifie explicitement."
        )
    if justifiees - qualifications:
        raise ErreurMetier("Une référence justifie un tag qui n'est pas une qualification sélectionnée.")
    if entite == "tag":
        if d["nature"] == "qualification" and not d["references"]:
            raise ErreurMetier("Définir une qualification factuelle nécessite une référence documentaire.")
        vus = {cible_id} if cible_id else set()
        parent_id = d["parent_id"]
        while parent_id:
            if parent_id in vus:
                raise ErreurMetier("Un tag ne peut pas créer de cycle dans la hiérarchie.")
            vus.add(parent_id)
            parent = session.get(Tag, parent_id)
            if not parent or parent.nature != d["nature"]:
                raise ErreurMetier("Le parent doit être un tag validé de même nature.")
            parent_id = parent.parent_id
        if cible_id and session.get(Tag, cible_id).nature != d["nature"]:
            raise ErreurMetier(
                "La nature d'un tag publié est stable ; proposer un nouveau tag pour la changer."
            )
    if entite == "compte" and cible_id:
        ancien = session.get(Compte, cible_id)
        if (
            ancien.source_id != d["source_id"] or ancien.plateforme_id != d["plateforme_id"]
        ) and ancien.contenus:
            raise ErreurMetier(
                "Réaffecter d'abord les contenus liés avant de changer la source ou la plateforme du compte."
            )
    return d


def empreinte_contribution(entite, operation, cible_id, donnees, version_cible=None):
    texte = json.dumps(
        [entite, operation, cible_id, version_cible, donnees], sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(texte.encode()).hexdigest()


def trouver_doublons(session, entite, donnees, exclure=None):
    modele = MODELES[entite]
    critere = (
        ((Tag.cle == cle_texte(donnees["nom"])) & (Tag.nature == donnees["nature"]))
        if entite == "tag"
        else (modele.url_canonique == canonicaliser_url(donnees["url"]))
    )
    requete = select(modele).where(critere)
    if exclure:
        requete = requete.where(modele.id != exclure)
    return [serialiser(session, entite, objet) for objet in session.scalars(requete)]


def soumettre(entite, donnees, jeton_defi, reponse, champ_piege="", cible_id=None, version_cible=None):
    verifier_defi(jeton_defi, reponse, champ_piege)
    try:
        with transaction() as session:
            operation = "modification" if cible_id else "ajout"
            if cible_id:
                objet = session.get(MODELES.get(entite), cible_id) if entite in MODELES else None
                if not objet:
                    raise ErreurMetier("La fiche à modifier n'existe pas.")
                if version_cible != objet.version:
                    raise ErreurMetier(
                        "Cette fiche a évolué. Rechargez-la avant de proposer votre modification."
                    )
            d = valider_donnees(session, entite, donnees, cible_id)
            empreinte = empreinte_contribution(entite, operation, cible_id, d, version_cible)
            if session.scalar(
                select(Contribution.id).where(
                    Contribution.empreinte == empreinte, Contribution.statut == "en_attente"
                )
            ):
                raise ErreurMetier("Une proposition identique attend déjà une validation.")
            doublons = trouver_doublons(session, entite, d, cible_id)
            contribution = Contribution(
                entite=entite,
                operation=operation,
                cible_id=cible_id,
                version_cible=version_cible,
                donnees=d,
                empreinte=empreinte,
            )
            session.add(contribution)
            session.flush()
            session.add(
                Historique(
                    contribution_id=contribution.id,
                    entite=entite,
                    entite_id=cible_id,
                    action="soumission",
                    apres=d,
                )
            )
            return {"id": contribution.id, "doublons": [o["id"] for o in doublons]}
    except IntegrityError:
        raise ErreurMetier("Une proposition identique vient d'être enregistrée. Rechargez la page.") from None


def verrouiller_moderation(session):
    # Verrou global court : rend aussi atomiques les changements de hiérarchie des tags.
    session.scalar(select(Quota).where(Quota.nom == "moderation").with_for_update())


def verifier_contribution(session, identifiant, empreinte_attendue):
    contribution = session.scalar(
        select(Contribution).where(Contribution.id == identifiant).with_for_update()
    )
    if not contribution or contribution.statut != "en_attente":
        raise ErreurMetier("Cette contribution n'est plus en attente.")
    if contribution.empreinte != empreinte_attendue:
        raise ErreurMetier("La proposition a été révisée par une autre session. Rechargez-la.")
    return contribution


def reviser_proposition(jeton_admin, identifiant, donnees, empreinte_attendue, motif, rebaser=False):
    exiger_admin(jeton_admin)
    if not motif.strip():
        raise ErreurMetier("Indiquer le motif de la révision.")
    try:
        with transaction() as session:
            verrouiller_moderation(session)
            c = verifier_contribution(session, identifiant, empreinte_attendue)
            d = valider_donnees(session, c.entite, donnees, c.cible_id)
            session.add(
                Historique(
                    contribution_id=c.id,
                    entite=c.entite,
                    entite_id=c.cible_id,
                    action="revision",
                    avant=c.donnees,
                    apres=d,
                    motif=motif[:5000],
                )
            )
            c.donnees = d
            if rebaser and c.cible_id:
                c.version_cible = session.get(MODELES[c.entite], c.cible_id).version
            c.empreinte = empreinte_contribution(c.entite, c.operation, c.cible_id, d, c.version_cible)
    except IntegrityError:
        raise ErreurMetier("Cette révision correspond à une autre proposition en attente.") from None


def appliquer(session, entite, donnees, objet=None):
    saisie = SAISIES[entite].model_validate(donnees)
    champs = saisie.model_dump(exclude={"references", "tags"})
    if entite == "tag":
        champs["cle"] = cle_texte(champs["nom"])
    else:
        champs["url_canonique"] = canonicaliser_url(champs["url"])
    if objet is None:
        objet = MODELES[entite](**champs)
        session.add(objet)
    else:
        for nom, valeur in champs.items():
            setattr(objet, nom, valeur)
        objet.version += 1
    if "tags" in donnees:
        objet.tags = [session.get(Tag, i) for i in donnees["tags"]]
    session.flush()
    # Une nouvelle liste de références est historisée intégralement avant remplacement.
    anciennes = session.scalars(select(Reference).where(getattr(Reference, f"{entite}_id") == objet.id)).all()
    for reference in anciennes:
        session.delete(reference)
    for reference in donnees["references"]:
        session.add(Reference(**reference, **{f"{entite}_id": objet.id}))
    session.flush()
    return objet


def moderer(jeton_admin, identifiant, decision, empreinte_attendue, motif, fusion_id=None):
    exiger_admin(jeton_admin)
    if decision not in {"valider", "refuser", "fusionner"} or not motif.strip():
        raise ErreurMetier("Choisir une décision et indiquer sa justification.")
    try:
        with transaction() as session:
            verrouiller_moderation(session)
            c = verifier_contribution(session, identifiant, empreinte_attendue)
            avant, apres, resultat_id = None, None, None
            if decision == "refuser":
                c.statut = "refusee"
            else:
                cible_id = fusion_id if decision == "fusionner" else c.cible_id
                if decision == "fusionner" and (not fusion_id or c.operation != "ajout"):
                    raise ErreurMetier(
                        "La fusion concerne un ajout et exige une fiche existante de même type."
                    )
                objet = session.get(MODELES[c.entite], cible_id) if cible_id else None
                if cible_id and not objet:
                    raise ErreurMetier("La fiche cible n'existe pas.")
                if decision == "valider" and objet and objet.version != c.version_cible:
                    raise ErreurMetier(
                        "Conflit de version : comparez la fiche actuelle et révisez la proposition."
                    )
                d = dict(c.donnees)
                if objet:
                    avant = obtenir_fiche(session, c.entite, objet.id, liens=False)
                if decision == "fusionner":
                    # Conserver les champs de la fiche cible, enrichir ses tags et ses références.
                    existant = donnees_editables(session, c.entite, objet.id)
                    if "tags" in existant:
                        existant["tags"] = sorted(set(existant["tags"]) | set(d.get("tags", [])))
                    refs = {
                        json.dumps(r, sort_keys=True): r for r in existant["references"] + d["references"]
                    }
                    existant["references"] = list(refs.values())
                    d = existant
                d = valider_donnees(session, c.entite, d, cible_id)
                doublons = trouver_doublons(session, c.entite, d, cible_id)
                if doublons:
                    raise ErreurMetier(
                        f"Doublon publié : fiche {doublons[0]['id']}. Utilisez la fusion ou corrigez l'URL."
                    )
                objet = appliquer(session, c.entite, d, objet)
                resultat_id = objet.id
                apres = obtenir_fiche(session, c.entite, objet.id, liens=False)
                c.statut = "fusionnee" if decision == "fusionner" else "validee"
            c.motif, c.traite_le, c.resultat_id = motif.strip()[:5000], maintenant(), resultat_id
            session.add(
                Historique(
                    contribution_id=c.id,
                    entite=c.entite,
                    entite_id=resultat_id or c.cible_id,
                    action=c.statut,
                    avant=avant,
                    apres=apres,
                    motif=c.motif,
                )
            )
            return resultat_id
    except IntegrityError:
        raise ErreurMetier("Conflit de données : un doublon ou une relation empêche la validation.") from None


def ajouter_plateforme(jeton_admin, nom):
    exiger_admin(jeton_admin)
    nom = nom.strip()
    if not nom or len(nom) > 100:
        raise ErreurMetier("Le nom de plateforme doit contenir 1 à 100 caractères.")
    with transaction() as session:
        verrouiller_moderation(session)
        if session.scalar(select(Plateforme).where(func.lower(Plateforme.nom) == nom.lower())):
            raise ErreurMetier("Cette plateforme existe déjà.")
        p = Plateforme(nom=nom)
        session.add(p)
        session.flush()
        session.add(Historique(entite="plateforme", entite_id=p.id, action="creation", apres={"nom": nom}))
        return p.id
