"""Interface publique française et espace de modération."""

import json
import os
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from .base import transaction
from .catalogue import (
    MODELES,
    dictionnaire,
    donnees_editables,
    iterer_resultats,
    lister_plateformes,
    lister_tags,
    obtenir_fiche,
    rechercher,
    statistiques,
)
from .contributions import (
    ajouter_plateforme,
    enregistrer_tag,
    modifier_plateforme,
    supprimer_plateforme,
    moderer,
    reviser_proposition,
    soumettre,
    trouver_doublons,
)
from .exports import MIMES, exporter
from .modeles import Compte, Contribution, Historique, Source
from .securite import ErreurMetier, connecter_admin, creer_defi, exiger_admin
from .validation import ENTITES, Filtres, MEDIAS, NATURES

PAGES = [
    "Accueil et statistiques",
    "Recherche et exploration",
    "Fiches sources et contenus",
    "Soumettre une contribution",
    "Explorer les tags",
    "Administration",
]


def aller_page(page, entite=None, identifiant=None):
    st.session_state.page = page
    if entite:
        st.session_state.fiche_entite = entite
    if identifiant:
        st.session_state.fiche_id = identifiant


def avis(message):
    st.session_state.avis = message
    st.rerun()


def proposer_modification(entite, identifiant):
    st.session_state.modifier_cible = (entite, identifiant)
    aller_page(PAGES[3])


def choix(label, objets, champ="nom", courant=None, vide=False, key=None):
    noms = {o["id"]: o[champ] for o in objets}
    options = ([None] if vide else []) + list(noms)
    if not options:
        st.info(f"Aucune option disponible pour « {label} ».")
        return None
    index = options.index(courant) if courant in options else 0
    return st.selectbox(
        label, options, index=index, format_func=lambda i: "—" if i is None else f"{noms[i]} · #{i}", key=key
    )


def afficher_liens(fiche):
    if fiche.get("url"):
        st.link_button("Ouvrir l'URL originale ↗", fiche["url"])
        st.code(fiche["url"], language=None)
        st.caption("Utilisez l'icône de copie du bloc ci-dessus pour copier l'URL.")


def telechargements(lignes, prefixe):
    colonnes = st.columns(3)
    for colonne, format_export in zip(colonnes, MIMES):
        colonne.download_button(
            f"Télécharger {format_export.upper()}",
            exporter(lignes, format_export),
            f"desinfolab-{prefixe}.{format_export}",
            mime=MIMES[format_export],
            key=f"export-{prefixe}-{format_export}",
        )


def accueil():
    st.caption("OBSERVATOIRE COLLABORATIF · SCIENCES HUMAINES ET SOCIALES")
    st.title("Documenter les sources.\nConstituer des corpus.")
    st.write(
        "Explorez des sources et des contenus multimédias, consultez leurs références et réunissez les URL utiles à vos recherches."
    )
    with transaction() as session:
        stats = statistiques(session)
    for colonne, (nom, total) in zip(st.columns(4), stats.items()):
        colonne.metric(nom, total)
    st.info(
        "Le référencement d'une source ne la qualifie pas comme source de désinformation. "
        "Les qualifications factuelles sont explicites, documentées et validées par l'administration."
    )
    gauche, droite = st.columns(2)
    with gauche, st.container(border=True):
        st.subheader("Explorer l'observatoire")
        st.write(
            "Croisez les plateformes, dates, pays, médias et tags. Exportez vos résultats en TXT, CSV ou JSON."
        )
        st.button("Rechercher des contenus", type="primary", on_click=aller_page, args=(PAGES[1],))
    with droite, st.container(border=True):
        st.subheader("Contribuer sans compte")
        st.write(
            "Proposez une source, un compte, un contenu ou une correction. Chaque proposition fait l'objet d'une validation humaine."
        )
        st.button("Soumettre une contribution", on_click=aller_page, args=(PAGES[3],))
    with st.expander("Méthode et confidentialité"):
        st.write(
            "Les références servent à situer les qualifications dans leur contexte. Elles ne constituent pas une notation automatique des sources."
        )
        st.write(
            "L'application ne demande ni nom, ni adresse électronique, ni compte contributeur. "
            "N'incluez aucune donnée personnelle dans les champs libres. Les contenus publiquement référencés peuvent, eux, nommer des auteurs."
        )
        st.write(
            "L'hébergeur, le proxy et les sites ouverts peuvent voir votre adresse IP. L'anonymat absolu n'est donc pas garanti. "
            "Aucun service de CAPTCHA tiers ni outil d'analyse d'audience n'est intégré."
        )
    api = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    st.link_button("Documentation de l'API publique", api + "/docs")


def champs_filtres(tags, plateformes):
    with st.expander("Filtres de recherche", expanded=True):
        a, b, c = st.columns(3)
        with a:
            texte = st.text_input("Nom, titre ou pseudonyme")
            plateforme = choix("Plateforme", plateformes, vide=True)
            pays = st.text_input("Pays", help="Correspondance exacte, sans distinction de majuscules.")
        with b:
            url = st.text_input("URL contenant")
            media = st.selectbox(
                "Type de média", [None] + list(MEDIAS), format_func=lambda x: MEDIAS.get(x, "Tous")
            )
            langue = st.text_input("Langue")
        with c:
            thematique = choix("Thématique", [t for t in tags if t["nature"] == "thematique"], vide=True)
            debut = st.date_input("Date de publication · début", value=None)
            fin = st.date_input("Date de publication · fin", value=None)
        noms = {t["id"]: f"{NATURES[t['nature']]} / {t['nom']}" for t in tags}
        selection = st.multiselect("Tags (saisissez pour rechercher)", list(noms), format_func=noms.get)
        a, b = st.columns(2)
        operateur = a.radio("Croisement des tags", ["ET", "OU"], horizontal=True)
        descendants = b.checkbox("Inclure les descendants des tags", value=True)
    return Filtres(
        texte=texte,
        url=url,
        plateforme_id=plateforme,
        type_media=media,
        pays=pays,
        langue=langue,
        tags=selection,
        operateur=operateur,
        descendants=descendants,
        thematique_id=thematique,
        date_debut=debut,
        date_fin=fin,
    )


def tableau(lignes, cle):
    donnees = [
        {
            "ID": r["id"],
            "Nom / titre": r.get("nom") or r.get("titre") or r.get("pseudonyme"),
            "Plateforme": r.get("plateforme", ""),
            "Date": r.get("date"),
            "URL originale": r.get("url", ""),
            "Tags": ", ".join(t["nom"] for t in r.get("tags", [])),
            "Fiche": f"?fiche={r['entite']}&id={r['id']}",
        }
        for r in lignes
    ]
    return st.dataframe(
        donnees,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="multi-row",
        column_config={
            "URL originale": st.column_config.LinkColumn("URL originale"),
            "Fiche": st.column_config.LinkColumn("Fiche", display_text="Consulter"),
        },
        key=cle,
    )


def recherche():
    st.title("Recherche et exploration")
    st.caption("Seules les fiches validées sont visibles. Les dates portent sur la publication des contenus.")
    entite = (
        st.segmented_control(
            "Rechercher dans",
            ["contenu", "source", "compte"],
            format_func=ENTITES.get,
            default="contenu",
            key="recherche_entite",
        )
        or "contenu"
    )
    with transaction() as session:
        tags, plateformes = lister_tags(session), lister_plateformes(session)
    filtres = champs_filtres(tags, plateformes)
    if entite == "compte":
        st.caption("Les filtres de tags des comptes portent sur leur source associée.")
    signature = entite + filtres.model_dump_json()
    if st.session_state.get("signature_recherche") != signature:
        st.session_state.page_resultats = 1
        st.session_state.signature_recherche = signature
        st.session_state.pop("export_filtre", None)
    a, b = st.columns([1, 3])
    page = a.number_input("Page", min_value=1, step=1, key="page_resultats")
    taille = b.selectbox("Résultats par page", [25, 50, 100, 200])
    with transaction() as session:
        resultat = rechercher(session, entite, filtres, int(page), taille)
    st.write(
        f"**{resultat['total']} résultat(s)** · page {page} / {max(1, (resultat['total'] + taille - 1) // taille)}"
    )
    lignes = resultat["resultats"]
    panier = st.session_state.setdefault("panier", {})
    if lignes:
        selection = tableau(lignes, f"resultats-{signature}-{page}-{taille}")
        retenus = [lignes[i] for i in selection.selection.rows]
        if st.button(f"Ajouter la sélection au corpus ({len(retenus)})", disabled=not retenus):
            for r in retenus:
                panier[f"{r['entite']}:{r['id']}"] = (r["entite"], r["id"])
            avis(f"{len(retenus)} fiche(s) ajoutée(s) au corpus.")
        choisi = choix(
            "Ouvrir une fiche de cette page",
            [{"id": r["id"], "nom": r.get("nom") or r.get("titre") or r.get("pseudonyme")} for r in lignes],
        )
        st.button("Afficher la fiche", on_click=aller_page, args=(PAGES[2], entite, choisi))
    else:
        st.info("Aucun résultat pour ces critères.")
    with st.expander(f"Mon corpus · {len(panier)} URL sélectionnée(s)", expanded=bool(panier)):
        if panier:
            with transaction() as session:
                corpus = [obtenir_fiche(session, e, i, liens=False) for e, i in panier.values()]
            st.code("\n".join(r["url"] for r in corpus), language=None)
            telechargements(corpus, "selection")
            if st.button("Vider la sélection"):
                st.session_state.panier = {}
                st.rerun()
        else:
            st.caption(
                "Sélectionnez des lignes puis ajoutez-les au corpus. La sélection reste disponible d'une page à l'autre pendant cette session."
            )
    st.subheader("Exporter tous les résultats filtrés")
    if st.button("Préparer les exports complets", disabled=resultat["total"] == 0):
        with st.spinner("Préparation du corpus…"), transaction() as session:
            st.session_state.export_filtre = list(iterer_resultats(session, entite, filtres))
    if "export_filtre" in st.session_state:
        st.caption(
            f"{len(st.session_state.export_filtre)} fiches dans l'export préparé. Relancez la préparation pour actualiser le corpus."
        )
        telechargements(st.session_state.export_filtre, "resultats")


def afficher_references(fiche):
    st.subheader("Références documentaires")
    noms = {t["id"]: t["nom"] for t in fiche.get("tags", [])}
    if not fiche["references"]:
        st.caption("Aucune référence documentaire associée. Cette fiche constitue un simple référencement.")
    for r in fiche["references"]:
        with st.container(border=True):
            st.text(r["titre"])
            st.caption(r["type_reference"].replace("_", " "))
            if r.get("qualification_tag_id"):
                st.write(
                    "Qualification justifiée : "
                    + noms.get(r["qualification_tag_id"], str(r["qualification_tag_id"]))
                )
            if r.get("citation"):
                st.text(r["citation"])
            st.link_button("Consulter la référence ↗", r["url"])


def fiches():
    st.title("Fiches sources et contenus")
    entite = st.selectbox("Type de fiche", list(ENTITES), format_func=ENTITES.get, key="fiche_entite")
    identifiant = st.number_input("Identifiant de la fiche", min_value=1, step=1, key="fiche_id")
    with transaction() as session:
        fiche = obtenir_fiche(session, entite, int(identifiant))
    st.subheader(fiche.get("nom") or fiche.get("titre") or fiche.get("pseudonyme"))
    st.caption(
        f"Fiche #{fiche['id']} · version {fiche['version']} · validée le / mise à jour le {fiche['modifie_le'][:10]}"
    )
    if fiche.get("description"):
        st.text(fiche["description"])
    details = {
        k: fiche[k]
        for k in ["plateforme", "pays", "langue", "date", "type_media", "source", "identifiant", "nature"]
        if fiche.get(k)
    }
    if details:
        st.dataframe([details], hide_index=True, width="stretch")
    afficher_liens(fiche)
    if entite in {"source", "contenu"}:
        if fiche["qualifications"]:
            st.warning("Qualifications documentées : " + " · ".join(fiche["qualifications"]))
        else:
            st.info("Simple référencement : aucune qualification factuelle attribuée à cette fiche.")
        if fiche["tags"]:
            st.write("Tags : " + " · ".join(t["nom"] for t in fiche["tags"]))
    afficher_references(fiche)
    for relation in ("comptes", "contenus"):
        if relation in fiche:
            st.subheader(f"{relation.capitalize()} référencés ({len(fiche[relation])})")
            if fiche[relation]:
                tableau(fiche[relation], f"fiche-{relation}")
                telechargements(fiche[relation], f"source-{relation}")
    if entite != "tag":
        st.button(
            "Proposer une modification de cette fiche",
            on_click=proposer_modification,
            args=(entite, fiche["id"]),
        )


def editeur_references(references, tags, key):
    st.markdown("**Références justificatives**")
    st.caption(
        "Ajoutez une ligne par référence. Pour chaque qualification factuelle, sélectionnez le tag justifié dans une référence."
    )
    noms = {t["id"]: f"{t['nom']} · #{t['id']}" for t in tags if t["nature"] == "qualification"}
    inverse = {v: k for k, v in noms.items()}
    lignes = [
        {
            "Titre": r["titre"],
            "URL": r["url"],
            "Type": r["type_reference"],
            "Extrait / justification": r["citation"],
            "Qualification justifiée": noms.get(r.get("qualification_tag_id"), "—"),
        }
        for r in references
    ]
    df = pd.DataFrame(
        lignes, columns=["Titre", "URL", "Type", "Extrait / justification", "Qualification justifiée"]
    )
    donnees = st.data_editor(
        df,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=key,
        column_config={
            "Titre": st.column_config.TextColumn(required=True),
            "URL": st.column_config.TextColumn(required=True),
            "Type": st.column_config.SelectboxColumn(
                options=["article", "scientifique", "fact_checking", "autre"],
                default="article",
                required=True,
            ),
            "Qualification justifiée": st.column_config.SelectboxColumn(
                options=["—"] + list(noms.values()), default="—"
            ),
        },
    )
    donnees = donnees.fillna("")
    return [
        {
            "titre": r["Titre"],
            "url": r["URL"],
            "type_reference": r["Type"] or "article",
            "citation": r["Extrait / justification"],
            "qualification_tag_id": inverse.get(r["Qualification justifiée"]),
        }
        for r in donnees.to_dict("records")
        if any(r.values())
    ]


def soumission():
    st.title("Soumettre une contribution")
    st.write("Sans compte ni identification. Votre proposition restera privée jusqu'à sa validation.")
    st.caption(
        "N'indiquez pas vos coordonnées dans les champs libres. Une source doit être validée avant l'ajout de ses comptes ou contenus."
    )
    cible = st.session_state.get("modifier_cible")
    if cible and cible[0] == "tag":
        st.session_state.pop("modifier_cible", None)
        st.info("La création et la modification des tags sont réservées à l'administration.")
        return
    if cible:
        entite, cible_id = cible
        st.info(f"Modification proposée : {ENTITES[entite]} #{cible_id}")
        if st.button("Revenir à une nouvelle proposition"):
            st.session_state.pop("modifier_cible", None)
            st.rerun()
        snapshot_key = f"snapshot-{entite}-{cible_id}"
        if snapshot_key not in st.session_state:
            with transaction() as session:
                st.session_state[snapshot_key] = (
                    donnees_editables(session, entite, cible_id),
                    session.get(MODELES[entite], cible_id).version,
                )
        initial, version_cible = st.session_state[snapshot_key]
    else:
        entites_publiques = [e for e in ENTITES if e != "tag"]
        if st.session_state.get("nouvelle_entite") not in entites_publiques:
            st.session_state.pop("nouvelle_entite", None)
        entite = st.selectbox(
            "Type de proposition", entites_publiques, format_func=ENTITES.get, key="nouvelle_entite"
        )
        cible_id, initial, version_cible = None, {}, None
    cle = f"saisie-{entite}-{cible_id or 'nouvelle'}"
    with transaction() as session:
        tags, plateformes = lister_tags(session), lister_plateformes(session)
        sources = [{"id": s.id, "nom": s.nom} for s in session.scalars(select(Source).order_by(Source.nom))]
        comptes = [dictionnaire(c) for c in session.scalars(select(Compte).order_by(Compte.pseudonyme))]
    if entite in {"compte", "contenu"} and not sources:
        st.info(
            "Proposez d'abord une source et attendez sa validation pour lui associer un compte ou un contenu."
        )
        return
    d = {}
    # Les sélecteurs hors formulaire réagissent immédiatement (parents, comptes et qualifications).
    if entite in {"compte", "contenu"}:
        d["source_id"] = choix(
            "Source associée", sources, courant=initial.get("source_id"), key=cle + "-source"
        )
    if entite == "contenu":
        d["compte_id"] = choix(
            "Compte associé (facultatif)",
            [c for c in comptes if c["source_id"] == d["source_id"]],
            "pseudonyme",
            initial.get("compte_id"),
            vide=True,
            key=cle + "-compte",
        )
    if entite != "tag":
        compte = next((c for c in comptes if c["id"] == d.get("compte_id")), None)
        if compte:
            d["plateforme_id"] = compte["plateforme_id"]
            st.caption(
                "Plateforme héritée du compte : "
                + next(p["nom"] for p in plateformes if p["id"] == d["plateforme_id"])
            )
        else:
            d["plateforme_id"] = choix(
                "Plateforme", plateformes, courant=initial.get("plateforme_id"), key=cle + "-plateforme"
            )
    if entite in {"source", "contenu"}:
        noms = {t["id"]: f"{NATURES[t['nature']]} / {t['nom']}" for t in tags}
        d["tags"] = st.multiselect(
            "Tags validés · saisissez pour rechercher",
            list(noms),
            default=initial.get("tags", []),
            format_func=noms.get,
            key=cle + "-tags",
        )
        st.caption("Les tags sont créés et modifiés par l'administration.")
    if "defi" not in st.session_state:
        st.session_state.defi = creer_defi()
    with st.form(cle):
        champ_nom = {"source": "nom", "compte": "pseudonyme", "contenu": "titre", "tag": "nom"}[entite]
        d[champ_nom] = st.text_input(
            {"nom": "Nom", "pseudonyme": "Pseudonyme du compte", "titre": "Titre"}[champ_nom],
            value=initial.get(champ_nom, ""),
            max_chars=150 if entite == "tag" else 300,
        )
        if entite != "tag":
            d["url"] = st.text_input(
                "URL originale", value=initial.get("url", ""), max_chars=2048, placeholder="https://…"
            )
        if entite != "compte":
            d["description"] = st.text_area(
                "Description contextualisée", value=initial.get("description", ""), max_chars=10000
            )
        if entite == "source":
            a, b = st.columns(2)
            d["pays"] = a.text_input("Pays", value=initial.get("pays", ""), max_chars=100)
            d["langue"] = b.text_input("Langue", value=initial.get("langue", ""), max_chars=100)
        if entite == "compte":
            d["identifiant"] = st.text_input(
                "Identifiant public sur la plateforme (facultatif)",
                value=initial.get("identifiant", ""),
                max_chars=300,
            )
        if entite == "contenu":
            a, b = st.columns(2)
            d["type_media"] = a.selectbox(
                "Type de média",
                list(MEDIAS),
                format_func=MEDIAS.get,
                index=list(MEDIAS).index(initial.get("type_media", "video")),
            )
            d["date"] = b.date_input(
                "Date de publication (si connue)",
                value=date.fromisoformat(initial["date"]) if initial.get("date") else None,
            )
        d["references"] = editeur_references(initial.get("references", []), tags, cle + "-refs")
        st.divider()
        reponse = st.text_input(st.session_state.defi["question"], key=cle + "-reponse")
        piege = st.text_input(
            "Champ de contrôle · laisser vide", key=cle + "-piege", help="Ne renseignez pas ce champ."
        )
        envoyer = st.form_submit_button("Envoyer pour validation", type="primary")
    if envoyer:
        defi = st.session_state.pop("defi")
        resultat = soumettre(entite, d, defi["jeton"], reponse, piege, cible_id, version_cible)
        st.success(f"Proposition #{resultat['id']} enregistrée en attente de validation.")
        if resultat["doublons"]:
            st.info(
                "Une fiche similaire existe déjà. L'administration vérifiera si une fusion est appropriée."
            )
        st.session_state.pop(f"snapshot-{entite}-{cible_id}", None)


def explorer_tags():
    st.title("Explorer les tags")
    st.write(
        "Un vocabulaire hiérarchisé : thématiques, types de discours, qualifications factuelles, catégories et mots-clés."
    )
    with transaction() as session:
        tags = lister_tags(session)
    nature = st.selectbox(
        "Famille de tags", [None] + list(NATURES), format_func=lambda x: NATURES.get(x, "Toutes")
    )
    terme = st.text_input("Rechercher un tag")
    noms = {t["id"]: t["nom"] for t in tags}
    selection = [
        t for t in tags if (not nature or t["nature"] == nature) and terme.casefold() in t["nom"].casefold()
    ]
    st.dataframe(
        [
            {
                "ID": t["id"],
                "Nom": t["nom"],
                "Famille": NATURES[t["nature"]],
                "Parent": noms.get(t["parent_id"], "—"),
                "Description": t["description"],
            }
            for t in selection
        ],
        hide_index=True,
        width="stretch",
    )
    if selection:
        identifiant = choix("Consulter le tag et ses références", selection)
        st.button("Afficher le tag", on_click=aller_page, args=(PAGES[2], "tag", identifiant))
    with st.expander("Hiérarchie complète", expanded=True):

        def branche(parent, niveau=0):
            for t in (t for t in tags if t["parent_id"] == parent and (not nature or t["nature"] == nature)):
                st.text("    " * niveau + ("↳ " if niveau else "") + t["nom"] + f" · {NATURES[t['nature']]}")
                branche(t["id"], niveau + 1)

        branche(None)


def administrer_tags(jeton):
    exiger_admin(jeton)
    with transaction() as session:
        tags = lister_tags(session)
    mode = st.radio("Gestion des tags", ["Créer un tag", "Modifier un tag"], horizontal=True)
    identifiant, version, initial = None, None, {}
    if mode == "Modifier un tag":
        if not tags:
            st.info("Aucun tag à modifier. Créez d'abord un tag.")
            return
        identifiant = choix("Tag à modifier", tags, key="admin-tag-selection")
        with transaction() as session:
            initial = donnees_editables(session, "tag", identifiant)
            version = session.get(MODELES["tag"], identifiant).version
    cle = f"admin-tag-{identifiant or 'nouveau'}-{version or 0}"
    nature = st.selectbox(
        "Famille du tag",
        list(NATURES),
        format_func=NATURES.get,
        index=list(NATURES).index(initial.get("nature", "thematique")),
        disabled=identifiant is not None,
        key=cle + "-nature",
    )
    if identifiant is not None:
        st.caption(
            "La famille d'un tag existant est conservée pour préserver les qualifications et la hiérarchie."
        )
    parent = choix(
        "Tag parent (facultatif)",
        [t for t in tags if t["nature"] == nature and t["id"] != identifiant],
        courant=initial.get("parent_id"),
        vide=True,
        key=cle + "-parent-" + nature,
    )
    with st.form(cle):
        nom = st.text_input("Nom du tag", value=initial.get("nom", ""), max_chars=150)
        description = st.text_area(
            "Description du tag", value=initial.get("description", ""), max_chars=10000
        )
        if nature == "qualification":
            st.caption("Une qualification factuelle nécessite au moins une référence documentaire.")
        references = editeur_references(initial.get("references", []), [], cle + "-references")
        motif = st.text_input("Motif de création ou de modification", max_chars=5000)
        enregistrer = st.form_submit_button(
            "Créer le tag" if identifiant is None else "Enregistrer le tag", type="primary"
        )
    if enregistrer:
        enregistrer_tag(
            jeton,
            {
                "nom": nom,
                "nature": nature,
                "description": description,
                "parent_id": parent,
                "references": references,
            },
            motif,
            identifiant,
            version,
        )
        avis("Tag créé." if identifiant is None else "Tag modifié.")


def administration():
    st.title("Administration")
    jeton = st.session_state.get("admin")
    try:
        exiger_admin(jeton)
    except ErreurMetier:
        st.session_state.pop("admin", None)
        st.caption("Session limitée à 30 minutes. L'accès est réservé à l'administration de l'observatoire.")
        with st.form("connexion", clear_on_submit=True):
            mot_de_passe = st.text_input("Mot de passe administrateur", type="password", max_chars=1024)
            connexion = st.form_submit_button("Se connecter", type="primary")
        if connexion:
            st.session_state.admin = connecter_admin(mot_de_passe)
            st.rerun()
        return
    if st.button("Se déconnecter"):
        st.session_state.pop("admin", None)
        st.rerun()
    onglet = st.radio(
        "Espace de gestion", ["Contributions", "Tags", "Plateformes", "Historique"], horizontal=True
    )
    if onglet == "Tags":
        administrer_tags(jeton)
        return
    if onglet == "Plateformes":
        with transaction() as session:
            plateformes = lister_plateformes(session)
        st.dataframe(plateformes, hide_index=True, width="stretch")
        with st.form("plateforme"):
            nom = st.text_input("Nouvelle plateforme", max_chars=100)
            ajouter = st.form_submit_button("Ajouter la plateforme")
        if ajouter:
            ajouter_plateforme(jeton, nom)
            avis("Plateforme ajoutée.")
        if plateformes:
            st.divider()
            identifiant = choix("Plateforme à gérer", plateformes, key="plateforme-a-gerer")
            plateforme = next(p for p in plateformes if p["id"] == identifiant)
            with st.form(f"modifier-plateforme-{identifiant}-{plateforme['nom']}"):
                nouveau_nom = st.text_input("Nom de la plateforme", value=plateforme["nom"], max_chars=100)
                modifier = st.form_submit_button("Enregistrer les modifications")
            if modifier:
                modifier_plateforme(jeton, identifiant, nouveau_nom)
                avis("Plateforme modifiée.")
            st.caption(
                "La suppression est possible uniquement si aucune fiche publiée ni contribution en attente n'utilise cette plateforme."
            )
            confirmation = st.checkbox(
                f"Confirmer la suppression de « {plateforme['nom']} »",
                key=f"confirmer-suppression-plateforme-{identifiant}-{plateforme['nom']}",
            )
            if st.button("Supprimer la plateforme", disabled=not confirmation):
                supprimer_plateforme(jeton, identifiant)
                avis("Plateforme supprimée.")
        return
    if onglet == "Historique":
        contribution_id = st.number_input("Filtrer par contribution (0 = toutes)", min_value=0, step=1)
        page = st.number_input("Page d'historique", min_value=1, step=1)
        with transaction() as session:
            requete = select(Historique).order_by(Historique.id.desc())
            if contribution_id:
                requete = requete.where(Historique.contribution_id == contribution_id)
            lignes = [
                dictionnaire(h) for h in session.scalars(requete.offset((int(page) - 1) * 25).limit(25))
            ]
        for h in lignes:
            with st.expander(f"#{h['id']} · {h['action']} · {h['entite']} · {h['cree_le'][:19]}"):
                st.text(h["motif"])
                a, b = st.columns(2)
                a.json(h["avant"])
                b.json(h["apres"])
        return
    statut = st.selectbox("Statut", ["en_attente", "validee", "refusee", "fusionnee"])
    page = st.number_input("Page des contributions", min_value=1, step=1)
    with transaction() as session:
        total = session.scalar(
            select(func.count()).select_from(Contribution).where(Contribution.statut == statut)
        )
        propositions = [
            dictionnaire(c)
            for c in session.scalars(
                select(Contribution)
                .where(Contribution.statut == statut)
                .order_by(Contribution.id)
                .offset((int(page) - 1) * 25)
                .limit(25)
            )
        ]
    st.caption(f"{total} contribution(s) · 25 par page")
    if not propositions:
        st.info("Aucune contribution à afficher.")
        return
    identifiant = choix(
        "Contribution à examiner",
        [
            {
                "id": c["id"],
                "nom": f"{ENTITES[c['entite']]} · {c['operation']} · {c['donnees'].get('nom') or c['donnees'].get('titre') or c['donnees'].get('pseudonyme')}",
            }
            for c in propositions
        ],
    )
    c = next(c for c in propositions if c["id"] == identifiant)
    st.caption(
        "Les données ci-dessous sont une proposition non vérifiée. Consulter les références avant toute décision."
    )
    st.json(c["donnees"])
    with transaction() as session:
        doublons = trouver_doublons(session, c["entite"], c["donnees"], c["cible_id"])
        if c["cible_id"]:
            st.markdown("**Fiche publiée actuelle**")
            st.json(obtenir_fiche(session, c["entite"], c["cible_id"], liens=False))
    if doublons:
        st.warning("Doublons publiés possibles : " + ", ".join(str(d["id"]) for d in doublons))
    if statut != "en_attente":
        st.text(c["motif"])
        return
    with st.expander("Réviser la proposition avant décision"):
        st.caption(
            "Les identifiants de tags et de plateformes sont consultables dans les pages correspondantes. "
            "Une révision est enregistrée dans l'historique, sans publier la proposition."
        )
        with st.form(f"revision-{c['id']}-{c['empreinte']}"):
            texte = st.text_area(
                "Données proposées (JSON)", json.dumps(c["donnees"], indent=2, ensure_ascii=False), height=350
            )
            motif_revision = st.text_input("Motif de révision", max_chars=5000)
            rebaser = st.checkbox(
                "J'ai comparé avec la fiche actuelle : utiliser sa version pour cette proposition",
                disabled=not c["cible_id"],
            )
            reviser = st.form_submit_button("Enregistrer la révision")
        if reviser:
            try:
                donnees = json.loads(texte)
            except json.JSONDecodeError:
                raise ErreurMetier("Le JSON n'est pas valide.") from None
            reviser_proposition(jeton, c["id"], donnees, c["empreinte"], motif_revision, rebaser)
            avis("Révision enregistrée. La proposition attend toujours une décision.")
    with st.form(f"decision-{c['id']}-{c['empreinte']}"):
        decision = st.selectbox(
            "Décision", ["valider", "refuser"] + (["fusionner"] if c["operation"] == "ajout" else [])
        )
        fusion = st.number_input(
            "Fiche cible pour une fusion (même type)",
            min_value=0,
            value=doublons[0]["id"] if doublons else 0,
            step=1,
        )
        st.caption(
            "Une fusion conserve les champs de la fiche cible et ajoute les tags et références de la proposition. "
            "L'URL et les autres champs proposés restent dans l'historique."
        )
        motif = st.text_area("Justification de la décision", max_chars=5000)
        confirme = st.checkbox("J'ai vérifié les références et la portée des qualifications.")
        decider = st.form_submit_button("Appliquer la décision", type="primary")
    if decider:
        if not confirme:
            raise ErreurMetier("Confirmez la vérification documentaire avant d'appliquer la décision.")
        moderer(jeton, c["id"], decision, c["empreinte"], motif, int(fusion) or None)
        avis("Décision enregistrée et historique conservé.")


def afficher_application():
    st.set_page_config(page_title="DésinfoLab · Observatoire collaboratif", page_icon="◈", layout="wide")
    st.markdown(
        """<style>
    .block-container {max-width: 1280px; padding-top: 4.5rem;}
    h1 {letter-spacing: -.035em; font-weight: 650 !important;}
    [data-testid="stSidebar"] {border-right: 1px solid #dbe4df;}
    [data-testid="stMetric"] {background: #eff4f1; border-radius: 12px; padding: 18px;}
    [data-testid="stSidebar"] h1 {font-size: 1.8rem;}
    </style>""",
        unsafe_allow_html=True,
    )
    if "page" not in st.session_state:
        st.session_state.page = PAGES[0]
        if st.query_params.get("fiche") in ENTITES:
            try:
                aller_page(PAGES[2], st.query_params["fiche"], max(1, int(st.query_params.get("id", 1))))
            except ValueError:
                pass
    with st.sidebar:
        st.title("◈ DésinfoLab")
        st.caption("SOURCES · CONTENUS · RÉFÉRENCES")
        st.radio("Navigation", PAGES, key="page", label_visibility="collapsed")
        st.divider()
        st.caption("Un observatoire pour la recherche.\nContributions anonymes, validation humaine.")
    if message := st.session_state.pop("avis", None):
        st.success(message)
    try:
        {
            PAGES[0]: accueil,
            PAGES[1]: recherche,
            PAGES[2]: fiches,
            PAGES[3]: soumission,
            PAGES[4]: explorer_tags,
            PAGES[5]: administration,
        }[st.session_state.page]()
    except ErreurMetier as erreur:
        st.error(str(erreur))
    except SQLAlchemyError:
        st.error(
            "La base est indisponible ou une opération concurrente a empêché l'enregistrement. Réessayez après actualisation."
        )
    st.divider()
    st.caption("DésinfoLab · Référencer ne vaut pas qualifier. Aucun téléchargement automatique de vidéos.")
