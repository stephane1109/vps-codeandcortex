"""Interface Streamlit de classification zero-shot pour corpus en sciences humaines."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import threading
import zipfile
from dataclasses import replace

import pandas as pd
import streamlit as st

from detection_langue import detecter_langues
from lecture_commentaires import analyser_commentaires_csv
from lecture_iramuteq import analyser_corpus, exporter_csv, tableau_documents
from moteur_zero_shot import (
    MODELE_DEFAUT,
    charger_classifieur,
    classifier_textes,
    exporter_documents_iramuteq,
    identifiant_categorie,
    preparer_categories,
    verifier_hypothese,
)
from stockage_resultats import enregistrer_resultat, recuperer_resultats

st.set_page_config(
    page_title="Zero-shot — classification des corpus", layout="wide"
)


def authentifier() -> None:
    """Protéger les corpus et le modèle par le secret défini dans Coolify."""
    secret = os.getenv("APP_PASSWORD", "")
    if not secret:
        st.error("Définir APP_PASSWORD dans les variables Coolify.")
        st.stop()
    mot_de_passe = st.text_input("Mot de passe de l'application", type="password")
    if not hmac.compare_digest(mot_de_passe.encode(), secret.encode()):
        st.stop()


@st.cache_resource(show_spinner=False)
def obtenir_classifieur():
    """Ne charger qu'un exemplaire du modèle dans le processus Streamlit."""
    return charger_classifieur(MODELE_DEFAUT)


@st.cache_resource(show_spinner=False)
def verrou_inference():
    """Limiter l'inférence simultanée pour protéger la RAM du VPS."""
    return threading.Lock()


@st.cache_data(show_spinner=False, max_entries=3)
def classifier_langues_cache(textes: tuple[str, ...]) -> list[dict]:
    """Éviter de refaire la détection de langue à chaque interaction."""
    return detecter_langues(list(textes))


def importer_fichiers(fichiers):
    """Lire les fichiers CSV et TXT sans supprimer leurs métadonnées."""
    documents = []
    informations = {}
    empreinte = hashlib.sha256()
    for fichier in fichiers:
        contenu = fichier.getvalue()
        nom = fichier.name
        empreinte.update(len(nom.encode("utf-8")).to_bytes(8, "big"))
        empreinte.update(nom.encode("utf-8"))
        empreinte.update(len(contenu).to_bytes(8, "big"))
        empreinte.update(contenu)

        if nom.lower().endswith(".csv"):
            nouveaux, details = analyser_commentaires_csv(
                contenu, numero_depart=len(documents)
            )
            documents.extend(nouveaux)
            for numero, donnees in details.items():
                informations[int(numero)] = {
                    **donnees,
                    "fichier_source": nom,
                    "format_source": "csv_commentaires",
                }
        else:
            nouveaux = analyser_corpus(contenu)
            depart = len(documents)
            for position, document in enumerate(nouveaux, start=1):
                nouveau = replace(document, numero=depart + position)
                documents.append(nouveau)
                informations[nouveau.numero] = {
                    "nom_affiche": "",
                    "ligne_csv": "",
                    "fichier_source": nom,
                    "format_source": "iramuteq",
                }
    if not documents:
        raise ValueError("Aucun document importé.")

    tableau = tableau_documents(documents)
    for nom_colonne in (
        "nom_affiche", "ligne_csv", "fichier_source", "format_source"
    ):
        tableau[nom_colonne] = [
            informations.get(int(numero), {}).get(nom_colonne, "")
            for numero in tableau["numero_document"]
        ]
    return documents, tableau, empreinte.hexdigest()


def preparer_tableau(
    corpus: pd.DataFrame, categories: list[str], cle_analyse: str
) -> pd.DataFrame:
    """Créer une ligne de résultats par document, même s'il est vide."""
    tableau = corpus.copy().reset_index(drop=True)
    tableau["cle_analyse"] = cle_analyse
    tableau["statut_analyse"] = "non_traite"
    tableau["categorie_principale"] = ""
    tableau["categorie_mieux_classee"] = ""
    tableau["score_maximum"] = pd.Series(
        [pd.NA] * len(tableau), dtype="Float64"
    )
    tableau["categories_retenues"] = ""
    tableau["erreur_analyse"] = ""
    for position, _ in enumerate(categories, start=1):
        tableau[f"score_{position:02d}"] = pd.Series(
            [pd.NA] * len(tableau), dtype="Float64"
        )
        tableau[f"classe_{position:02d}"] = pd.Series(
            [pd.NA] * len(tableau), dtype="boolean"
        )
    tableau.loc[
        tableau["texte"].fillna("").astype(str).str.strip().eq(""),
        "statut_analyse",
    ] = "vide"
    return tableau


def renseigner_resultat(
    tableau: pd.DataFrame,
    indice: int,
    resultat: dict,
    categories: list[str],
) -> None:
    """Mettre à jour le tableau avec les scores effectivement calculés."""
    for colonne in (
        "statut_analyse",
        "categorie_principale",
        "categorie_mieux_classee",
        "score_maximum",
        "erreur_analyse",
    ):
        if colonne in resultat:
            tableau.at[indice, colonne] = resultat[colonne]
    if "categories_retenues" in resultat:
        selection = resultat["categories_retenues"]
        if isinstance(selection, list):
            tableau.at[indice, "categories_retenues"] = " | ".join(selection)
        else:
            tableau.at[indice, "categories_retenues"] = str(selection)
    scores = resultat.get("scores", {})
    for position, categorie in enumerate(categories, start=1):
        if categorie in scores:
            tableau.at[indice, f"score_{position:02d}"] = float(scores[categorie])
            retenues = resultat.get("categories_retenues", [])
            tableau.at[indice, f"classe_{position:02d}"] = categorie in retenues


def recuperer_tableau(
    corpus: pd.DataFrame, categories: list[str], cle_analyse: str,
    filtre_francais: bool,
) -> pd.DataFrame:
    """Reprendre automatiquement les résultats déjà présents en SQLite."""
    tableau = preparer_tableau(corpus, categories, cle_analyse)
    if filtre_francais:
        with st.spinner("Identification des langues du corpus"):
            langues = classifier_langues_cache(tuple(tableau["texte"].tolist()))
        for colonne in (
            "langue_detectee", "statut_langue",
            "confiance_langue", "ecart_langue",
        ):
            tableau[colonne] = [ligne[colonne] for ligne in langues]
        tableau.loc[
            tableau["statut_analyse"].eq("non_traite")
            & tableau["statut_langue"].eq("hors_francais"),
            "statut_analyse",
        ] = "exclu_langue"

    anciens = recuperer_resultats(cle_analyse)
    correspondance = {
        int(numero): indice
        for indice, numero in tableau["numero_document"].items()
    }
    for numero, resultat in anciens.items():
        indice = correspondance.get(int(numero))
        if indice is not None and tableau.at[indice, "statut_analyse"] != "vide":
            renseigner_resultat(tableau, indice, resultat, categories)
    return tableau


def analyser_documents(
    tableau: pd.DataFrame, indices: list[int],
    categories: list[str], hypothese: str,
    multilabel: bool, seuil: float, cle_analyse: str,
) -> tuple[int, int, bool]:
    """Exécuter automatiquement la classification et sauvegarder chaque résultat."""
    try:
        with st.spinner(
            "Chargement du modèle multilingue sur CPU. "
            "Au premier lancement, ses poids sont téléchargés."
        ):
            classifieur = obtenir_classifieur()
    except Exception as erreur:
        st.error(
            f"Impossible de charger le modèle : {type(erreur).__name__} : {erreur}"
        )
        return 0, 0, True

    progres = st.progress(0, text="Classification en cours")
    compteurs = st.empty()
    reussites = 0
    erreurs = 0
    consecutives = 0
    interrompu = False
    total = len(indices)

    # Ces groupes internes économisent le temps CPU ; aucun clic répété n'est requis.
    for debut in range(0, total, 4):
        groupe = indices[debut:debut + 4]
        textes = [str(tableau.at[indice, "texte"]) for indice in groupe]
        try:
            with verrou_inference():
                sorties = classifier_textes(
                    classifieur, textes, categories, hypothese, multilabel, seuil
                )
            if len(sorties) != len(groupe):
                raise RuntimeError("Nombre de réponses du modèle incorrect.")
            decisions = [("ok", resultat) for resultat in sorties]
        except Exception as erreur:
            # En cas d'échec d'un groupe, réessayer individuellement afin
            # d'isoler le commentaire en cause sans perdre les autres.
            decisions = []
            for texte in textes:
                try:
                    with verrou_inference():
                        sortie = classifier_textes(
                            classifieur, [texte], categories,
                            hypothese, multilabel, seuil,
                        )[0]
                    decisions.append(("ok", sortie))
                except Exception as erreur_individuelle:
                    decisions.append((
                        "erreur",
                        {
                            "erreur_analyse": (
                                f"{type(erreur_individuelle).__name__}: "
                                f"{str(erreur_individuelle)[:800]}"
                            )
                        },
                    ))
        for indice, (statut, sortie) in zip(groupe, decisions):
            numero = int(tableau.at[indice, "numero_document"])
            resultat = {"statut_analyse": statut, **sortie}
            renseigner_resultat(tableau, indice, resultat, categories)
            enregistrer_resultat(cle_analyse, numero, statut, sortie)
            if statut == "ok":
                reussites += 1
                consecutives = 0
            else:
                erreurs += 1
                consecutives += 1
            progression = reussites + erreurs
            progres.progress(
                min(100, round((debut + progression - (reussites + erreurs - len(groupe))) * 100 / max(1, total))),
                text=f"Commentaires examinés : {min(total, debut + groupe.index(indice) + 1)} / {total}",
            )
            compteurs.caption(
                f"Réussites : {reussites} ; erreurs : {erreurs}. "
                "Chaque résultat est enregistré sur le volume Docker."
            )
            if consecutives >= 3:
                interrompu = True
                break
        if interrompu:
            break
    progres.empty()
    compteurs.empty()
    return reussites, erreurs, interrompu


def restaurer_csv(
    tableau: pd.DataFrame, fichier, categories: list[str],
    cle_analyse: str,
) -> int:
    """Restaurer les données validées sans mélanger corpus et paramètres."""
    anciens = pd.read_csv(
        io.BytesIO(fichier.getvalue()), sep=";", encoding="utf-8-sig",
        dtype={
            "cle_analyse": "string", "numero_document": "Int64",
            "texte": "string", "statut_analyse": "string",
        },
        keep_default_na=False,
    )
    necessaires = {
        "cle_analyse", "numero_document", "texte", "statut_analyse",
        "categorie_principale", "score_maximum", "categories_retenues",
    }
    if not necessaires.issubset(anciens.columns):
        raise ValueError("Ce CSV n'est pas un export compatible avec Zero-shot.")
    if (
        len(anciens) != len(tableau)
        or not anciens["cle_analyse"].eq(cle_analyse).all()
        or anciens["numero_document"].astype(int).tolist()
        != tableau["numero_document"].astype(int).tolist()
        or anciens["texte"].fillna("").astype(str).tolist()
        != tableau["texte"].fillna("").astype(str).tolist()
    ):
        raise ValueError("Le CSV de reprise ne correspond pas au corpus et aux catégories.")
    compteur = 0
    for indice, ligne in anciens.iterrows():
        statut = str(ligne["statut_analyse"])
        if statut not in ("ok", "erreur"):
            continue
        scores = {}
        for position, categorie in enumerate(categories, start=1):
            valeur = pd.to_numeric(ligne.get(f"score_{position:02d}"), errors="coerce")
            if pd.notna(valeur):
                scores[categorie] = float(valeur)
        if statut == "ok" and len(scores) != len(categories):
            raise ValueError(
                f"Scores incomplets au document {int(ligne['numero_document'])}."
            )
        selection = str(ligne["categories_retenues"]).split(" | ") if ligne["categories_retenues"] else []
        resultat = {
            "statut_analyse": statut,
            "categorie_principale": str(ligne["categorie_principale"]),
            "categorie_mieux_classee": str(ligne.get("categorie_mieux_classee", "")),
            "score_maximum": (
                float(ligne["score_maximum"])
                if pd.notna(pd.to_numeric(ligne["score_maximum"], errors="coerce"))
                else None
            ),
            "categories_retenues": selection,
            "scores": scores,
            "erreur_analyse": str(ligne.get("erreur_analyse", "")),
        }
        renseigner_resultat(tableau, indice, resultat, categories)
        enregistrer_resultat(
            cle_analyse, int(ligne["numero_document"]), statut, resultat
        )
        compteur += 1
    return compteur


def archive_resultats(
    tableau: pd.DataFrame, documents, parametres: dict,
    categories: list[str],
) -> bytes:
    """Rassembler toutes les données et les métadonnées dans un ZIP unique."""
    reponses = [
        "numero_document", "nom_affiche", "texte",
        "fichier_source", "statut_analyse", "categorie_principale",
        "score_maximum", "categories_retenues", "erreur_analyse",
    ]
    reponses += [
        f"score_{position:02d}" for position in range(1, len(categories) + 1)
    ]
    bilan = pd.DataFrame([
        {
            "categorie": categorie,
            "colonne_score": f"score_{position:02d}",
            "colonne_presence": f"classe_{position:02d}",
            "variable_iramuteq": f"zs_{identifiant_categorie(categorie)}_oui",
            "documents_attribues": int(
                tableau[f"classe_{position:02d}"].fillna(False).sum()
            ),
        }
        for position, categorie in enumerate(categories, start=1)
    ])
    statuts = (
        tableau["statut_analyse"].value_counts(dropna=False)
        .rename_axis("statut").reset_index(name="nombre")
    )
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("codage_zero_shot.csv", exporter_csv(tableau))
        archive.writestr(
            "scores_zero_shot.csv",
            exporter_csv(tableau[[col for col in reponses if col in tableau]]),
        )
        archive.writestr("bilan_categories.csv", exporter_csv(bilan))
        archive.writestr("bilan_statuts.csv", exporter_csv(statuts))
        if "statut_langue" in tableau.columns:
            langues = (
                tableau["statut_langue"].value_counts(dropna=False)
                .rename_axis("statut_langue").reset_index(name="nombre")
            )
            archive.writestr("bilan_langues.csv", exporter_csv(langues))
        archive.writestr(
            "corpus_zero_shot_iramuteq.txt",
            exporter_documents_iramuteq(documents, tableau, categories),
        )
        archive.writestr(
            "parametres.json",
            json.dumps(parametres, ensure_ascii=False, indent=2),
        )
    return tampon.getvalue()


authentifier()
st.title("Classification zero-shot des corpus")
st.caption(
    "Classification multilingue par MiniLM sur CPU, sans Ollama. "
    "Vous définissez vos catégories ; aucun sujet n'est imposé."
)
st.info(
    "Zero-shot attribue des catégories et des scores aux textes. "
    "Contrairement à Qwen, il ne rédige pas d'interprétation libre. "
    "Les scores ne garantissent pas que le classement soit correct."
)

with st.expander("Catégories et paramètres de classification", expanded=True):
    categories_brutes = st.text_area(
        "Catégories à rechercher (une par ligne)",
        value=(
            "politique\néducation\nsanté\nenvironnement\n"
            "tourisme\néconomie\nculture"
        ),
        height=180,
        help="Vous pouvez remplacer entièrement ces exemples. Maximum 30 catégories.",
    )
    mode = st.radio(
        "Une ou plusieurs catégories par commentaire ?",
        ["Plusieurs catégories possibles", "Une catégorie principale"],
        horizontal=True,
    )
    multilabel = mode == "Plusieurs catégories possibles"
    hypothese = st.text_input(
        "Phrase d'hypothèse du modèle",
        value="Ce commentaire évoque {}.",
        help="Le texte {} est remplacé par chaque catégorie. Ce n'est pas un prompt génératif.",
    )
    seuil = st.slider(
        "Score minimum pour attribuer une catégorie",
        min_value=0.0, max_value=1.0, value=0.65, step=0.05,
        help=(
            "Si aucune catégorie n'atteint le seuil, la décision est indéterminée. "
            "Un score de 0,90 ne garantit pas 90 % de réponses correctes."
        ),
    )
    filtrer_francais = st.checkbox(
        "Exclure les commentaires identifiés comme non français",
        value=False,
        help=(
            "Le modèle est multilingue. Si ce filtre est activé, les textes "
            "courts ou ambigus restent analysables ; les autres langues "
            "clairement identifiées sont exclues des calculs, mais pas des exports."
        ),
    )
try:
    categories = preparer_categories(categories_brutes, multilabel)
    hypothese = verifier_hypothese(hypothese)
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

fichiers = st.file_uploader(
    "Importer un ou plusieurs fichiers CSV (nom_affiche, texte) ou IRaMuTeQ TXT",
    type=["csv", "txt"],
    accept_multiple_files=True,
)
if not fichiers:
    st.caption("Importez un corpus pour commencer.")
    st.stop()

try:
    documents, corpus, signature = importer_fichiers(fichiers)
except (ValueError, UnicodeError) as erreur:
    st.error(f"Import impossible : {erreur}")
    st.stop()

parametres = {
    "modele": MODELE_DEFAUT,
    "signature_corpus": signature,
    "categories": categories,
    "hypothese": hypothese,
    "multilabel": multilabel,
    "seuil": float(seuil),
    "filtrer_francais": bool(filtrer_francais),
}
cle_analyse = hashlib.sha256(
    json.dumps(parametres, sort_keys=True, ensure_ascii=False).encode("utf-8")
).hexdigest()
parametres["cle_analyse"] = cle_analyse

if st.session_state.get("zs_cle") != cle_analyse:
    st.session_state["zs_cle"] = cle_analyse
    st.session_state["zs_message"] = ""
    try:
        st.session_state["zs_tableau"] = recuperer_tableau(
            corpus, categories, cle_analyse, filtrer_francais
        )
    except Exception as erreur:
        st.error(
            f"Impossible de charger les données sauvegardées : "
            f"{type(erreur).__name__} : {erreur}"
        )
        st.stop()
tableau = st.session_state["zs_tableau"]

non_traites = tableau.index[
    tableau["statut_analyse"].eq("non_traite")
].tolist()
indices_erreur = tableau.index[tableau["statut_analyse"].eq("erreur")].tolist()
nombre_ok = int(tableau["statut_analyse"].eq("ok").sum())
nombre_vides = int(tableau["statut_analyse"].eq("vide").sum())
nombre_exclus = int(tableau["statut_analyse"].eq("exclu_langue").sum())

st.write(
    f"**{len(tableau)} documents importés** ; "
    f"{nombre_ok} classés ; {len(non_traites)} à traiter ; "
    f"{len(indices_erreur)} en erreur ; {nombre_vides} vides ; "
    f"{nombre_exclus} exclus par le filtre linguistique."
)

with st.expander("Aperçu des documents importés", expanded=False):
    st.dataframe(
        corpus[
            [col for col in (
                "numero_document", "nom_affiche", "texte", "fichier_source"
            ) if col in corpus]
        ].head(30),
        hide_index=True, use_container_width=True,
    )

fichier_reprise = st.file_uploader(
    "Reprendre depuis un précédent codage_zero_shot.csv (facultatif)",
    type=["csv"], key="zs_reprise",
)
if fichier_reprise is not None and st.button("Restaurer le CSV de reprise"):
    try:
        quantite = restaurer_csv(
            tableau, fichier_reprise, categories, cle_analyse
        )
        st.success(f"{quantite} résultats restaurés et enregistrés.")
        st.rerun()
    except (ValueError, KeyError, TypeError) as erreur:
        st.error(f"Reprise refusée : {erreur}")

if st.session_state.get("zs_message"):
    st.info(st.session_state["zs_message"])

st.subheader("Lancer la classification")
st.caption(
    "Le premier test charge le modèle si nécessaire. L'analyse complète "
    "fonctionne automatiquement ; chaque résultat est sauvegardé après calcul."
)
col_test, col_lancer, col_reprise = st.columns([1, 2, 1])
tester = col_test.button(
    "Tester 3 commentaires", disabled=not non_traites
)
lancer = col_lancer.button(
    "Classifier tous les commentaires restants",
    type="primary", disabled=not non_traites,
)
reessayer = col_reprise.button(
    "Réessayer les erreurs", disabled=not indices_erreur
)
if tester or lancer or reessayer:
    selection = (
        non_traites[:3] if tester
        else non_traites if lancer
        else indices_erreur
    )
    reussites, erreurs, interrompu = analyser_documents(
        tableau, selection, categories, hypothese,
        multilabel, float(seuil), cle_analyse,
    )
    if interrompu:
        dernieres = tableau.loc[
            tableau["statut_analyse"].eq("erreur"), "erreur_analyse"
        ].tail(1).tolist()
        detail = dernieres[0] if dernieres else "Voir les journaux du serveur."
        st.session_state["zs_message"] = (
            f"Traitement interrompu : {reussites} réussite(s), "
            f"{erreurs} erreur(s). Dernière erreur : {detail}"
        )
    else:
        st.session_state["zs_message"] = (
            f"{reussites} commentaire(s) classé(s), "
            f"{erreurs} erreur(s). Résultats sauvegardés."
        )
    st.rerun()

st.subheader("Résultats de la classification")
classements = tableau.loc[tableau["statut_analyse"].eq("ok")].copy()
if classements.empty:
    st.warning(
        "Aucun commentaire n'a encore été classé par le modèle. "
        "Le tableau original importé n'est pas un résultat de classification."
    )
else:
    colonnes = [
        "numero_document", "nom_affiche", "texte",
        "categorie_principale", "score_maximum",
        "categories_retenues",
    ]
    colonnes += [
        f"score_{position:02d}" for position in range(1, len(categories) + 1)
    ]
    st.dataframe(
        classements[[col for col in colonnes if col in classements]].head(1000),
        hide_index=True, use_container_width=True, height=400,
    )
    if len(classements) > 1000:
        st.caption(
            "Seules 1 000 lignes sont affichées. Tous les résultats "
            "figurent dans les fichiers exportés."
        )
    choix = st.selectbox(
        "Examiner un commentaire classé",
        classements["numero_document"].astype(int).tolist(),
    )
    selection = classements.loc[
        classements["numero_document"].eq(choix)
    ].iloc[0]
    st.text_area(
        "Texte original", value=str(selection["texte"]),
        height=120, disabled=True,
    )
    scores_detail = pd.DataFrame([
        {
            "Catégorie": categorie,
            "Score": float(selection[f"score_{position:02d}"]),
            "Attribuée": bool(selection[f"classe_{position:02d}"]),
        }
        for position, categorie in enumerate(categories, start=1)
    ]).sort_values("Score", ascending=False)
    st.dataframe(
        scores_detail, hide_index=True, use_container_width=True,
    )
    st.subheader("Répartition des catégories")
    valeurs = pd.DataFrame([
        {
            "Catégorie": categorie,
            "Commentaires attribués": int(
                classements[f"classe_{position:02d}"].fillna(False).sum()
            ),
        }
        for position, categorie in enumerate(categories, start=1)
    ])
    st.bar_chart(
        valeurs.set_index("Catégorie"),
        x_label="Catégorie", y_label="Nombre de commentaires",
    )
    st.caption(
        "En mode multilabel, un commentaire peut compter "
        "dans plusieurs catégories."
    )

erreurs_tableau = tableau.loc[tableau["statut_analyse"].eq("erreur")]
if not erreurs_tableau.empty:
    st.subheader("Erreurs du modèle")
    st.error(
        f"{len(erreurs_tableau)} commentaire(s) sans classification valide. "
        "Les détails sont affichés ci-dessous."
    )
    st.dataframe(
        erreurs_tableau[
            [
                col for col in (
                    "numero_document", "nom_affiche", "texte",
                    "erreur_analyse",
                )
                if col in erreurs_tableau
            ]
        ].head(200),
        hide_index=True, use_container_width=True,
    )

with st.expander(
    "Tableau complet et métadonnées du corpus", expanded=False
):
    st.dataframe(
        tableau.head(1000), hide_index=True, use_container_width=True
    )

st.subheader("Exporter et reprendre les résultats")
archive = archive_resultats(tableau, documents, parametres, categories)
st.download_button(
    "Télécharger tous les résultats (ZIP unique)",
    data=archive,
    file_name="resultats_zero_shot.zip",
    mime="application/zip",
)
st.download_button(
    "Télécharger le CSV complet pour reprise",
    data=exporter_csv(tableau),
    file_name="codage_zero_shot.csv",
    mime="text/csv",
)
st.caption(
    "Le modèle et les résultats sont conservés dans deux volumes Docker "
    "distincts. Ne supprimez pas ces volumes dans Coolify."
)
