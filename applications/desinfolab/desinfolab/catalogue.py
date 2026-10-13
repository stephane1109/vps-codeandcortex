"""Lecture publique, recherche SQL et sérialisation des fiches validées."""

from datetime import date, datetime
from sqlalchemy import and_, func, or_, select
from .modeles import Compte, Contenu, Plateforme, Reference, Source, Tag
from .securite import ErreurMetier
from .validation import Filtres, SAISIES

MODELES = {"source": Source, "compte": Compte, "contenu": Contenu, "tag": Tag}


def references_fiche(session, entite, identifiant):
    return list(
        session.scalars(
            select(Reference).where(getattr(Reference, f"{entite}_id") == identifiant).order_by(Reference.id)
        )
    )


def dictionnaire(objet):
    return {
        c.name: (v.isoformat() if isinstance(v := getattr(objet, c.name), (date, datetime)) else v)
        for c in objet.__table__.columns
    }


def serialiser(session, entite, objet):
    resultat = dictionnaire(objet)
    resultat.pop("url_canonique", None)
    resultat.pop("cle", None)
    resultat["entite"] = entite
    resultat["references"] = [
        {
            k: v
            for k, v in dictionnaire(r).items()
            if k not in {"source_id", "contenu_id", "compte_id", "tag_id"}
        }
        for r in references_fiche(session, entite, objet.id)
    ]
    if entite in {"source", "contenu"}:
        resultat["tags"] = [
            {"id": t.id, "nom": t.nom, "nature": t.nature, "parent_id": t.parent_id}
            for t in sorted(objet.tags, key=lambda t: t.nom)
        ]
        resultat["qualifications"] = [t["nom"] for t in resultat["tags"] if t["nature"] == "qualification"]
    if entite != "tag":
        resultat["plateforme"] = objet.plateforme.nom
    if entite in {"compte", "contenu"}:
        resultat["source"] = objet.source.nom
        resultat["pays"] = objet.source.pays
        resultat["langue"] = objet.source.langue
    return resultat


def obtenir_fiche(session, entite, identifiant, liens=True):
    modele = MODELES.get(entite)
    if modele is None:
        raise ErreurMetier("Type de fiche inconnu.")
    objet = session.get(modele, identifiant)
    if objet is None:
        raise ErreurMetier("Fiche introuvable.")
    fiche = serialiser(session, entite, objet)
    if liens and entite == "source":
        fiche["comptes"] = [serialiser(session, "compte", c) for c in objet.comptes]
        fiche["contenus"] = [serialiser(session, "contenu", c) for c in objet.contenus]
    return fiche


def donnees_editables(session, entite, identifiant):
    fiche = obtenir_fiche(session, entite, identifiant, liens=False)
    champs = SAISIES[entite].model_fields
    donnees = {k: v for k, v in fiche.items() if k in champs}
    if "tags" in donnees:
        donnees["tags"] = [t["id"] for t in donnees["tags"]]
    for reference in donnees["references"]:
        reference.pop("id", None)
    return donnees


def groupes_tags(session, identifiants, descendants=True):
    tags = list(session.scalars(select(Tag)))
    connus = {t.id for t in tags}
    groupes = []
    for identifiant in dict.fromkeys(identifiants):
        if identifiant not in connus:
            raise ErreurMetier(f"Tag {identifiant} introuvable.")
        groupe = {identifiant}
        if descendants:
            while True:
                nouveau = groupe | {t.id for t in tags if t.parent_id in groupe}
                if nouveau == groupe:
                    break
                groupe = nouveau
        groupes.append(groupe)
    return groupes


def construire_requete(session, entite: str, filtres: Filtres):
    if entite not in {"source", "compte", "contenu"}:
        raise ErreurMetier("La recherche porte sur les sources, comptes ou contenus.")
    if filtres.date_debut and filtres.date_fin and filtres.date_debut > filtres.date_fin:
        raise ErreurMetier("La date de début doit précéder la date de fin.")
    modele = MODELES[entite]
    requete = select(modele)
    nom = {"source": Source.nom, "compte": Compte.pseudonyme, "contenu": Contenu.titre}[entite]
    if filtres.texte:
        requete = requete.where(nom.icontains(filtres.texte, autoescape=True))
    if filtres.url:
        requete = requete.where(modele.url.icontains(filtres.url, autoescape=True))
    if filtres.plateforme_id:
        if entite == "source":
            requete = requete.where(
                or_(
                    Source.plateforme_id == filtres.plateforme_id,
                    Source.comptes.any(Compte.plateforme_id == filtres.plateforme_id),
                    Source.contenus.any(Contenu.plateforme_id == filtres.plateforme_id),
                )
            )
        else:
            requete = requete.where(modele.plateforme_id == filtres.plateforme_id)
    if filtres.source_id:
        requete = requete.where((Source.id if entite == "source" else modele.source_id) == filtres.source_id)
    if filtres.compte_id:
        if entite == "contenu":
            requete = requete.where(Contenu.compte_id == filtres.compte_id)
        elif entite == "compte":
            requete = requete.where(Compte.id == filtres.compte_id)
        else:
            requete = requete.where(Source.comptes.any(Compte.id == filtres.compte_id))
    for champ in ("pays", "langue"):
        valeur = getattr(filtres, champ)
        if valeur:
            critere = func.lower(getattr(Source, champ)) == valeur.lower()
            requete = requete.where(critere if entite == "source" else modele.source.has(critere))
    contraintes_contenu = []
    if filtres.type_media:
        contraintes_contenu.append(Contenu.type_media == filtres.type_media)
    if filtres.date_debut:
        contraintes_contenu.append(Contenu.date >= filtres.date_debut)
    if filtres.date_fin:
        contraintes_contenu.append(Contenu.date <= filtres.date_fin)
    if contraintes_contenu:
        predicat = and_(*contraintes_contenu)
        requete = requete.where(predicat if entite == "contenu" else modele.contenus.any(predicat))

    def critere_tags(groupe):
        if entite == "contenu":
            return Contenu.tags.any(Tag.id.in_(groupe))
        if entite == "source":
            return Source.tags.any(Tag.id.in_(groupe))
        return Compte.source.has(Source.tags.any(Tag.id.in_(groupe)))

    groupes = groupes_tags(session, filtres.tags, filtres.descendants)
    if groupes:
        criteres = [critere_tags(g) for g in groupes]
        requete = requete.where(and_(*criteres) if filtres.operateur == "ET" else or_(*criteres))
    if filtres.thematique_id:
        tag = session.get(Tag, filtres.thematique_id)
        if not tag or tag.nature != "thematique":
            raise ErreurMetier("La thématique choisie est invalide.")
        requete = requete.where(critere_tags(groupes_tags(session, [tag.id], filtres.descendants)[0]))
    return requete.order_by(modele.id)


def rechercher(session, entite: str, filtres: Filtres, page=1, taille=25):
    if page < 1 or not 1 <= taille <= 200:
        raise ErreurMetier("Pagination invalide (1 à 200 lignes par page).")
    requete = construire_requete(session, entite, filtres)
    total = session.scalar(select(func.count()).select_from(requete.order_by(None).subquery()))
    objets = session.scalars(requete.offset((page - 1) * taille).limit(taille)).all()
    return {
        "total": total,
        "page": page,
        "taille": taille,
        "resultats": [serialiser(session, entite, o) for o in objets],
    }


def iterer_resultats(session, entite, filtres):
    # Pages par clé : mémoire bornée, sans troncature silencieuse des exports.
    dernier = 0
    requete = construire_requete(session, entite, filtres)
    modele = MODELES[entite]
    while objets := session.scalars(requete.where(modele.id > dernier).limit(200)).all():
        for objet in objets:
            yield serialiser(session, entite, objet)
        dernier = objets[-1].id


def statistiques(session):
    return {
        nom: session.scalar(select(func.count()).select_from(modele))
        for nom, modele in {"Sources": Source, "Comptes": Compte, "Contenus": Contenu, "Tags": Tag}.items()
    }


def lister_tags(session):
    return [serialiser(session, "tag", t) for t in session.scalars(select(Tag).order_by(Tag.nature, Tag.nom))]


def lister_plateformes(session):
    return [dictionnaire(p) for p in session.scalars(select(Plateforme).order_by(Plateforme.nom))]
