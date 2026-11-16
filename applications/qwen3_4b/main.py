"""Application Streamlit Qwen3-4B : prompt libre et codage structuré optionnel."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import time
import zipfile
from dataclasses import replace

import pandas as pd
import requests
import streamlit as st

from configuration_qwen import (
    MODELE as MODELE_CONFIGURATION, MODELES_PROPOSES, LIBELLES_MODELES,
    MODELES_SPECIALISES, CONTEXTE_MAXIMUM, URL_OLLAMA, verifier_service,
)
from codage_multithemes import (
    PROMPT_MATRICE_DEFAUT, NOMBRE_THEMES_MAXIMUM,
    proposer_themes_depuis_prompt, extraire_themes_explicites,
    valider_themes, codes_themes, coder_multithemes,
)
from matrice_thematique import (
    SOURCES_TEXTE, LIBELLES_SOURCES,
    analyser_sources_csv, extraire_source_iramuteq,
    initialiser_annotations_matrice, construire_matrice,
    construire_bilan_sources, comparer_sources_par_video,
    exporter_iramuteq_matrice,
)
from analyse_specialisee import interroger_encodeur_specialise
from lecture_commentaires import obtenir_apercu_csv
from preparation_analyse import evaluer_commandes_analyse
from lecture_iramuteq import analyser_corpus, exporter_csv, tableau_documents

st.set_page_config(page_title="Qwen — analyse de corpus", layout="wide")

# Harmoniser en rouge tous les titres de section de niveau 3.
# Les autres niveaux de titre et le contenu des tableaux restent inchangés.
st.markdown(
    """
    <style>
        .stApp h3 {
            color: #C62828 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def authentifier() -> None:
    """Empêcher l'accès non autorisé à l'inférence sur le VPS."""
    secret = os.getenv("APP_PASSWORD", "")
    if not secret:
        if os.getenv("APP_ALLOW_PUBLIC", "0") != "1":
            st.error("Définir APP_PASSWORD dans Coolify avant de lancer l'application.")
            st.stop()
        st.warning("Mode public activé explicitement par APP_ALLOW_PUBLIC=1.")
        return
    saisie = st.text_input("Mot de passe de l'application", type="password")
    if not hmac.compare_digest(saisie.encode("utf-8"), secret.encode("utf-8")):
        st.stop()


def est_vrai(valeur: object) -> bool:
    """Lire des booléens provenant de l'interface ou d'un CSV de reprise."""
    if pd.isna(valeur):
        return False
    if isinstance(valeur, str):
        return valeur.strip().lower() in ("true", "vrai", "1", "oui")
    return bool(valeur)


def archive_resultats(
    tableau: pd.DataFrame,
    documents,
    signature: str,
    parametres: dict[str, object],
) -> bytes:
    """Préparer le ZIP unique avec matrice, sous-corpus et métadonnées."""
    themes = valider_themes(parametres["themes"])
    codes = codes_themes(themes)
    matrice = construire_matrice(tableau, themes)
    iramuteq = exporter_iramuteq_matrice(documents, matrice, themes)
    reponses = tableau.reindex(columns=[
        "numero_document", "id_video", "source_texte",
        "nom_affiche", "texte", "reponse_qwen",
        "erreur_codage", *codes,
        *("indice_" + code for code in codes),
        *("probabilite_" + code for code in codes),
        "probabilite_incertitude", "justification",
    ])
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "codage_commentaires.csv",
            exporter_csv(tableau.drop(columns=["type_source"], errors="ignore")),
        )
        archive.writestr("reponses_qwen.csv", exporter_csv(reponses))
        archive.writestr("corpus_qwen_iramuteq.txt", iramuteq)
        archive.writestr(
            "matrice_annotations_qwen.csv",
            exporter_csv(matrice.drop(columns=["statut_codage", "type_source"])),
        )
        archive.writestr(
            "comparaison_videos_qwen.csv",
            exporter_csv(comparer_sources_par_video(matrice, themes)),
        )
        archive.writestr(
            "bilan_sources_themes_qwen.csv",
            exporter_csv(
                construire_bilan_sources(matrice, themes)
                .drop(columns=["type_source"])
            ),
        )
        archive.writestr(
            "grille_themes_qwen.json",
            json.dumps({"themes": themes}, ensure_ascii=False, indent=2),
        )
        for code in codes:
            extraits = matrice.loc[
                matrice["statut_codage"].eq("ok")
                & matrice["final_" + code].eq(True).fillna(False)
            ]
            archive.writestr(
                f"textes_{code}_qwen.csv",
                exporter_csv(extraits.drop(columns=["statut_codage", "type_source"])),
            )
        archive.writestr(
            "parametres.json",
            json.dumps(
                {**parametres, "signature": signature},
                ensure_ascii=False, indent=2,
            ),
        )
    return tampon.getvalue()


def initialiser_tableau(
    tableau: pd.DataFrame,
    signature: str,
    cle_configuration: str = "",
) -> pd.DataFrame:
    """Conserver les textes et métadonnées en initialisant les résultats."""
    donnees = tableau.copy(deep=False).reset_index(drop=True)
    donnees["signature_corpus"] = signature
    donnees["cle_configuration"] = cle_configuration
    donnees["statut_codage"] = "non_traite"
    for champ in ("erreur_codage", "reponse_qwen", "mode_analyse"):
        donnees[champ] = ""
    for champ in ("texte_tronque", "contexte_tronque"):
        donnees[champ] = pd.Series(
            [pd.NA] * len(donnees), index=donnees.index, dtype="boolean"
        )
    donnees.loc[
        donnees["texte"].fillna("").astype(str).str.strip().eq(""),
        "statut_codage",
    ] = "vide"
    return donnees


def restaurer_checkpoint(
    donnees: pd.DataFrame,
    anciens: pd.DataFrame,
    signature: str,
    cle_configuration: str,
    themes: list[dict[str, str]],
) -> pd.DataFrame:
    """Restaurer des annotations seulement si corpus et prompt concordent."""
    indispensables = (
        "numero_document", "signature_corpus", "texte",
        "statut_codage", "cle_configuration",
    )
    if any(champ not in anciens.columns for champ in indispensables):
        raise ValueError("Le CSV de reprise ne contient pas les champs nécessaires.")
    if (
        len(anciens) != len(donnees)
        or anciens["signature_corpus"].nunique() != 1
        or anciens["signature_corpus"].iloc[0] != signature
        or anciens["cle_configuration"].nunique() != 1
        or anciens["cle_configuration"].iloc[0] != cle_configuration
        or not anciens["numero_document"].equals(donnees["numero_document"])
        or not anciens["texte"].fillna("").equals(donnees["texte"].fillna(""))
    ):
        raise ValueError(
            "Le corpus, le prompt, les thèmes ou leurs paramètres diffèrent "
            "du fichier de reprise."
        )
    codes = codes_themes(themes)
    champs_boolean = [
        *codes, *("manuel_" + code for code in codes),
        "incertitude_interpretation", "texte_tronque", "contexte_tronque",
    ]
    champs_texte = [
        "statut_codage", "erreur_codage", "reponse_qwen", "mode_analyse",
        *("indice_" + code for code in codes),
        "justification", "validation_humaine", "note_humaine",
    ]
    restauration = donnees.copy()
    for champ in champs_boolean:
        if champ in anciens.columns:
            restauration[champ] = pd.Series(
                [
                    pd.NA if pd.isna(valeur) or str(valeur).strip() == ""
                    else est_vrai(valeur)
                    for valeur in anciens[champ]
                ],
                index=restauration.index, dtype="boolean",
            )
    for champ in champs_texte:
        if champ in anciens.columns:
            restauration[champ] = (
                anciens[champ].fillna("").astype(str).reset_index(drop=True)
            )
    for champ in ("nombre_segments", "segments_traites"):
        if champ in anciens.columns:
            restauration[champ] = pd.to_numeric(
                anciens[champ], errors="coerce"
            ).fillna(0).astype(int).to_numpy()
    # Les anciens checkpoints ne comportent pas de scores : ils restent vides.
    for champ in (
        *("probabilite_" + code for code in codes),
        "probabilite_incertitude",
    ):
        if champ in anciens.columns:
            valeurs = pd.to_numeric(anciens[champ], errors="coerce")
            if valeurs.dropna().lt(0).any() or valeurs.dropna().gt(1).any():
                raise ValueError(f"Score hors de [0, 1] : {champ}.")
            restauration[champ] = pd.Series(
                valeurs.to_numpy(), index=restauration.index, dtype="Float64"
            )
    # Restaurer séparément les similarités d'encodeurs non génératifs.
    for champ in ("similarite_" + code for code in codes):
        if champ in anciens.columns:
            valeurs = pd.to_numeric(anciens[champ], errors="coerce")
            if valeurs.dropna().lt(-1).any() or valeurs.dropna().gt(1).any():
                raise ValueError(f"Similarité hors de [-1, 1] : {champ}.")
            restauration[champ] = pd.Series(
                valeurs.to_numpy(), index=restauration.index, dtype="Float64"
            )
    return restauration


def demander_arret_analyse() -> None:
    """Demander l'arrêt sans effacer les annotations déjà enregistrées."""
    st.session_state["qwen_arret_demande"] = True
    st.session_state["qwen_message"] = (
        "Arrêt demandé. Les annotations déjà produites sont conservées. "
        "Les textes restants pourront être analysés ultérieurement."
    )


def lancer_analyse(
    donnees: pd.DataFrame,
    indices: list[int],
    prompt: str,
    themes: list[dict[str, str]],
    contexte_general: str,
    contexte_variables: list[str],
    temperature: float,
    modele: str,
) -> tuple[int, int, bool]:
    """Analyser automatiquement toutes les lignes sélectionnées, sans lots visibles."""
    nombre_total = len(indices)
    barre = st.progress(0, text="Préparation de l'analyse")
    information = st.empty()
    termines = 0
    erreurs = 0
    erreurs_consecutives = 0
    interruption_service = False

    with requests.Session() as session:
        for position, indice in enumerate(indices, start=1):
            # Une demande d'arrêt n'efface aucun résultat.
            # L'arrêt est vérifié entre deux requêtes vers Ollama.
            if st.session_state.get("qwen_arret_demande", False):
                break
            ligne = donnees.loc[indice]
            details = "\n".join(
                f"{colonne}: {ligne[colonne]}"
                for colonne in contexte_variables
                if pd.notna(ligne.get(colonne))
            )
            contexte = (contexte_general + "\n" + details).strip()
            try:
                resultat = coder_multithemes(
                    texte=str(ligne["texte"]),
                    themes=themes,
                    contexte=contexte,
                    temperature=temperature,
                    session=session,
                    consigne=prompt,
                    modele=modele,
                )
                for champ, valeur in resultat.items():
                    donnees.at[indice, champ] = valeur
                donnees.at[indice, "statut_codage"] = "ok"
                donnees.at[indice, "erreur_codage"] = ""
                termines += 1
                erreurs_consecutives = 0
            except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError) as erreur:
                type_erreur = (
                    "erreur_service" if isinstance(erreur, requests.RequestException)
                    else "sortie_invalide"
                )
                donnees.at[indice, "statut_codage"] = type_erreur
                # Inclure la configuration réellement demandée au serveur
                # pour que chaque erreur exportée soit interprétable.
                details_erreur = str(erreur)
                if "Modèle sollicité :" not in details_erreur:
                    details_erreur = (
                        f"Modèle sollicité : {modele} ; "
                        f"Contexte demandé : {CONTEXTE_MAXIMUM} tokens ; "
                        + details_erreur
                    )
                donnees.at[indice, "erreur_codage"] = (
                    f"{type(erreur).__name__}: {details_erreur[:900]}"
                )
                erreurs += 1
                # Interrompre immédiatement si le système a tué le moteur d'inférence.
                erreurs_consecutives = (
                    3 if (
                        "signal: killed" in str(erreur).lower()
                        or "unexpected eof" in str(erreur).lower()
                    ) else erreurs_consecutives + 1
                )
            barre.progress(
                round(position * 100 / max(1, nombre_total)),
                text=f"Textes examinés : {position} / {nombre_total}",
            )
            information.caption(
                f"Analyses abouties : {termines} ; erreurs : {erreurs}. "
                "Les résultats déjà obtenus sont conservés dans la session."
            )
            st.session_state["qwen_donnees"] = donnees
            if erreurs_consecutives >= 3:
                interruption_service = True
                break
    barre.empty()
    information.empty()
    return termines, erreurs, interruption_service


authentifier()

st.title("Qwen — analyser un corpus avec votre prompt")
# La mention de version reste sous le titre, avec le modèle réellement sélectionné.
mention_version = st.empty()
# Un seul parcours : le même prompt et la même matrice pour les commentaires
# courts et pour les documents longs. Aucun choix de méthode n'est nécessaire.
mode_analyse = "matrice"
# Migrer uniquement l'ancien texte générique ; conserver tout prompt personnalisé.
PROMPT_GENERIQUE_PRECEDENT = "Analyse un corpus de sciences humaines et sociales.\nRepère les thèmes pertinents pour la question de recherche formulée ici.\nPour chaque texte, applique la grille validée sans créer de nouvelles catégories.\nPlusieurs thèmes peuvent être présents dans un même texte.\nDistingue les indices textuels explicites des interprétations incertaines.\nRespecte les formulations SMS, les commentaires courts et les textes longs.\nN'invente pas de fait, de citation ni d'intention non exprimée."
# Migrer les deux anciens prompts par défaut sans écraser une consigne personnelle.
PROMPT_VIOLENCE_LONG_PRECEDENT = "Analyse les textes et commentaires de ce corpus de sciences humaines et sociales sous l'angle des discours sur la violence.\n\nConstruis une grille de codage comportant exactement trois thèmes.\n\nDénonciation de la violence : le texte condamne ou critique explicitement des actes de violence, leurs auteurs ou leurs conséquences.\n\nIndignation face à la violence : le texte manifeste explicitement une réaction de colère, de révolte, de consternation ou un sentiment d'injustice devant des violences.\n\nDétermination d'un persécuteur face à la violence : le texte désigne explicitement une personne, un groupe ou une institution comme responsable de violences, de persécutions ou d'oppression envers une cible. Cette désignation constitue une attribution de responsabilité dans le discours, et non une culpabilité établie.\n\nAnnote chaque unité textuelle selon ces trois thèmes non exclusifs. Un même texte peut relever simultanément de plusieurs thèmes. Ne force pas l'attribution d'une catégorie lorsque les indices textuels sont insuffisants.\n\nPour chaque thème présent, relève un extrait littéral du texte et justifie brièvement l'annotation. Signale les interprétations incertaines. N'invente aucun fait, aucune citation, aucune émotion ni aucune intention qui ne soit exprimée dans le texte.\n\nApplique les mêmes critères aux commentaires courts, aux formulations SMS, aux publications des auteurs, aux transcriptions vocales, aux textes descriptifs longs et aux textes générés par l'IA.\n\nConserve les formulations originales. Les textes longs peuvent être segmentés, mais leurs annotations doivent être regroupées au niveau du document initial.\n\nPrésente les résultats dans une matrice comportant une ligne par texte, une colonne binaire pour chacun des trois thèmes, les indices textuels justificatifs et une indication d'incertitude. Cette matrice doit permettre une validation ou une correction manuelle ultérieure."
if st.session_state.get("qwen_prompt_matrice") in (
    PROMPT_GENERIQUE_PRECEDENT,
    PROMPT_VIOLENCE_LONG_PRECEDENT,
):
    st.session_state["qwen_prompt_matrice"] = PROMPT_MATRICE_DEFAUT
prompt = st.text_area(
    "Prompt d'annotation des textes et commentaires",
    value=PROMPT_MATRICE_DEFAUT,
    key="qwen_prompt_matrice",
    height=260,
    help=(
        "Le prompt initial traite trois thèmes de la violence. Vous pouvez "
        "modifier librement ces thèmes et leurs définitions. "
        "Qwen propose une grille à valider avant le codage. Les textes longs "
        "sont segmentés ; les résultats restent corrigeables et exportables."
    ),
)
st.caption(
    "Même analyse pour les commentaires courts, les textes IA, "
    "les publications et les transcriptions longues. "
    "La segmentation automatique ne change ni le prompt ni les thèmes."
)
if not prompt.strip():
    st.error("Vous devez saisir un prompt avant de lancer l'analyse.")

fichiers = st.file_uploader(
    "Importer un ou plusieurs fichiers : commentaires CSV ou corpus IRaMuTeQ TXT",
    type=["csv", "txt"], accept_multiple_files=True,
    help=(
        "CSV : choisissez librement la colonne des commentaires et, "
        "si elle existe, celle des auteurs. Séparateurs : point-virgule, "
        "virgule ou tabulation. TXT : en-têtes IRaMuTeQ ****."
    ),
)
# Réunir les modèles génératifs Ollama et les encodeurs français dans un menu.
# Le choix initial suit la configuration Coolify, sans modifier ses variables.
if "qwen_modele_selectionne" not in st.session_state:
    st.session_state["qwen_modele_selectionne"] = (
        MODELE_CONFIGURATION
        if MODELE_CONFIGURATION in MODELES_PROPOSES
        else MODELES_PROPOSES[0]
    )
MODELE = st.selectbox(
    "Modèle d'analyse (Ollama ou Transformers)",
    options=MODELES_PROPOSES,
    format_func=lambda nom: LIBELLES_MODELES.get(nom, nom),
    key="qwen_modele_selectionne",
    help=(
        "Qwen, Gemma et Llama utilisent Ollama pour annoter les textes. "
        "JuriBERT et BERTweetFR utilisent Transformers pour calculer "
        "des similarités exploratoires, et non des classifications. "
        "Changer de modèle réinitialise les résultats de l'analyse en cours."
    ),
)
MODELE_EST_SPECIALISE = MODELE in MODELES_SPECIALISES
moteur = "Transformers" if MODELE_EST_SPECIALISE else "Ollama"
mention_version.caption(f"version 16-11-2026 - modèle : {MODELE} — {moteur}")
if MODELE_EST_SPECIALISE:
    st.caption(
        "JuriBERT et BERTweetFR produisent des similarités cosinus avec "
        "les définitions thématiques. Ces scores ne sont pas des "
        "probabilités de présence et ne remplacent pas une annotation humaine."
    )
if not fichiers:
    st.stop()


def proposer_colonne(colonnes: list[str], suggestions: tuple[str, ...]) -> str | None:
    """Trouver une colonne habituelle sans imposer son intitulé."""
    normalisees = {nom.strip().casefold(): nom for nom in colonnes}
    for suggestion in suggestions:
        if suggestion in normalisees:
            return normalisees[suggestion]
    return None


st.subheader("Choix des colonnes CSV")
st.caption(
    "Sélectionnez la colonne des textes à annoter, quelle que soit leur "
    "longueur. Vous pouvez aussi associer plusieurs sources textuelles "
    "à une même vidéo pour les comparer (facultatif). " 
    "Les dix premières lignes du CSV restent visibles."
)
correspondances_csv: list[dict[str, object]] = []
try:
    for numero_fichier, fichier in enumerate(fichiers):
        if not fichier.name.lower().endswith(".csv"):
            continue
        # Ne pas redécoder 22 Mo de CSV pour afficher les mêmes 10 lignes
        # après chaque modification d'un widget.
        empreinte_apercu = hashlib.sha256(fichier.getvalue()).hexdigest()
        cle_apercu = f"{numero_fichier}:{fichier.name}:{empreinte_apercu}"
        if st.session_state.get("qwen_apercu_cle_" + str(numero_fichier)) != cle_apercu:
            colonnes_csv, lignes_apercu = obtenir_apercu_csv(
                fichier.getvalue(), nombre_lignes=10
            )
            st.session_state["qwen_apercu_cle_" + str(numero_fichier)] = cle_apercu
            st.session_state["qwen_apercu_donnees_" + str(numero_fichier)] = (
                colonnes_csv, lignes_apercu
            )
        else:
            colonnes_csv, lignes_apercu = st.session_state[
                "qwen_apercu_donnees_" + str(numero_fichier)
            ]
        defaut_texte = proposer_colonne(
            colonnes_csv,
            ("texte", "commentaire", "commentaires", "comment", "text",
             "content", "message", "body", "description"),
        ) or colonnes_csv[0]
        cle_fichier = hashlib.sha256(
            f"{numero_fichier}:{fichier.name}:".encode("utf-8")
            + fichier.getvalue()
        ).hexdigest()[:16]
        noms_suggeres = {
            "texte_ia": (
                "texte_ia", "texte_genere_ia", "resume_ia",
                "description_ia", "ai_generated_text",
            ),
            "texte_auteur": (
                "texte_auteur", "texte_original", "caption", "legende",
                "description", "post", "texte_post",
            ),
            "voice_to_text": (
                "voice_to_text", "texte_voicetotext", "voicetotext",
                "transcription", "transcript", "sous_titres",
            ),
            "commentaire": (
                "commentaire", "commentaires", "texte_commentaire",
                "comment", "message", "content",
            ),
        }
        suggestions_tous_textes = (
            "texte", "commentaire", "commentaires", "message", "content",
            "texte_ia", "texte_auteur", "voice_to_text", "texte_voicetotext",
            "transcription", "description", "post", "avis", "texte_post",
        )
        defaut_texte = (
            proposer_colonne(colonnes_csv, suggestions_tous_textes)
            or colonnes_csv[0]
        )
        colonne_gauche, colonne_droite = st.columns(2)
        with colonne_gauche:
            texte_choisi = st.selectbox(
                f"Colonne contenant les textes ou commentaires — {fichier.name}",
                options=colonnes_csv,
                index=colonnes_csv.index(defaut_texte),
                key=f"qwen_texte_csv_{cle_fichier}",
            )
        with colonne_droite:
            auteur_propose = proposer_colonne(
                colonnes_csv,
                ("nom_affiche", "display_name", "auteur", "author",
                 "utilisateur", "username", "profil"),
            )
            auteurs_possibles = [None] + [
                colonne for colonne in colonnes_csv if colonne != texte_choisi
            ]
            auteur_choisi = st.selectbox(
                f"Colonne auteur (facultative) — {fichier.name}",
                options=auteurs_possibles,
                index=(
                    auteurs_possibles.index(auteur_propose)
                    if auteur_propose in auteurs_possibles else 0
                ),
                format_func=lambda valeur: (
                    "Aucune colonne auteur" if valeur is None else valeur
                ),
                key=f"qwen_auteur_csv_{cle_fichier}",
            )
        source_suggeree = next(
            (
                source for source, noms in noms_suggeres.items()
                if texte_choisi.casefold() in noms
            ),
            "texte_libre",
        )
        with st.expander(
            f"Sources et comparaison entre vidéos — {fichier.name} (facultatif)",
            expanded=False,
        ):
            st.caption(
                "Ces réglages décrivent la provenance des textes ; "
                "ils ne modifient ni le prompt ni le modèle d'analyse."
            )
            source_principale = st.selectbox(
                "Provenance du texte principal",
                options=["texte_libre", *SOURCES_TEXTE],
                index=["texte_libre", *SOURCES_TEXTE].index(source_suggeree),
                format_func=lambda source: LIBELLES_SOURCES[source],
                key=f"qwen_type_source_{cle_fichier}",
            )
            identifiant_propose = proposer_colonne(
                colonnes_csv,
                ("id_video", "video_id", "idvideo", "videoid",
                 "aweme_id", "id_publication", "id"),
            )
            colonne_id_video = st.selectbox(
                "Colonne identifiant vidéo (facultative)",
                options=[None] + colonnes_csv,
                index=(
                    0 if identifiant_propose is None else
                    colonnes_csv.index(identifiant_propose) + 1
                ),
                format_func=lambda valeur: (
                    "Aucune colonne" if valeur is None else valeur
                ),
                key=f"qwen_id_video_{cle_fichier}",
            )
            autres_sources = st.checkbox(
                "Comparer plusieurs colonnes textuelles de ce CSV",
                key=f"qwen_comparer_sources_{cle_fichier}",
                value=False,
            )
            colonnes_sources = {source_principale: texte_choisi}
            if autres_sources:
                for source in SOURCES_TEXTE:
                    if source == source_principale:
                        continue
                    colonnes_disponibles = [
                        col for col in colonnes_csv
                        if col != texte_choisi
                    ]
                    choix_colonne = st.selectbox(
                        LIBELLES_SOURCES[source],
                        options=[None] + colonnes_disponibles,
                        index=0,
                        format_func=lambda valeur: (
                            "Aucune colonne" if valeur is None else valeur
                        ),
                        key=f"qwen_autre_source_{source}_{cle_fichier}",
                    )
                    if choix_colonne is not None:
                        colonnes_sources[source] = choix_colonne
        if len(set(colonnes_sources.values())) != len(colonnes_sources):
            st.error("Une même colonne ne peut pas être affectée à deux sources.")
            st.stop()
        correspondances_csv.append({
            "numero_fichier": numero_fichier,
            "nom_fichier": fichier.name,
            "colonne_texte": texte_choisi,
            "colonne_auteur": auteur_choisi,
            "colonne_id_video": colonne_id_video,
            "colonnes_sources": colonnes_sources,
        })
        st.caption(
            f"Aperçu du CSV — {fichier.name} : "
            f"{len(lignes_apercu)} ligne(s) affichée(s), 10 au maximum."
        )
        st.dataframe(
            pd.DataFrame(lignes_apercu, columns=colonnes_csv),
            use_container_width=True,
            hide_index=True,
        )
except (ValueError, UnicodeError) as erreur:
    st.error(f"Impossible de lire les en-têtes CSV : {erreur}")
    st.stop()

choix_par_fichier = {
    int(choix["numero_fichier"]): choix for choix in correspondances_csv
}

# Calculer la signature historique sans assembler un nouveau fichier géant.
empreinte_fichiers = hashlib.sha256()
for numero_fichier, fichier in enumerate(fichiers):
    if numero_fichier:
        empreinte_fichiers.update(b"\0")
    empreinte_fichiers.update(fichier.getvalue())
signature_fichiers = empreinte_fichiers.hexdigest()

# Réutiliser le corpus analysé tant que les fichiers et les colonnes
# sélectionnées ne changent pas, même si l'interface Streamlit se réexécute.
cle_importation = hashlib.sha256(
    json.dumps(
        {
            "signature": signature_fichiers,
            "fichiers": [fichier.name for fichier in fichiers],
            "colonnes": correspondances_csv,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()
if (
    st.session_state.get("qwen_cle_importation") == cle_importation
    and "qwen_documents_importes" in st.session_state
    and "qwen_tableau_importe" in st.session_state
):
    documents = st.session_state["qwen_documents_importes"]
    tableau = st.session_state["qwen_tableau_importe"]
else:
    try:
        documents = []
        metadonnees = {}
        for numero_fichier, fichier in enumerate(fichiers):
            nom_fichier = fichier.name
            if nom_fichier.lower().endswith(".csv"):
                choix = choix_par_fichier[numero_fichier]
                if mode_analyse == "matrice":
                    nouveaux, informations = analyser_sources_csv(
                        fichier.getvalue(),
                        colonnes_sources=choix["colonnes_sources"],
                        colonne_id_video=choix["colonne_id_video"],
                        colonne_auteur=choix["colonne_auteur"],
                        numero_depart=len(documents),
                    )
                else:
                    nouveaux, informations = analyser_commentaires_csv(
                        fichier.getvalue(),
                        numero_depart=len(documents),
                        colonne_texte=str(choix["colonne_texte"]),
                        colonne_auteur=choix["colonne_auteur"],
                    )
                documents.extend(nouveaux)
                for informations_document in informations.values():
                    # Éviter une deuxième copie du dictionnaire de chaque ligne.
                    informations_document["fichier_source"] = nom_fichier
                    informations_document["format_source"] = "csv_commentaires"
                metadonnees.update(informations)
            else:
                extraits = analyser_corpus(fichier.getvalue())
                depart = len(documents)
                documents.extend(
                    replace(doc, numero=depart + numero + 1)
                    for numero, doc in enumerate(extraits)
                )
                for doc in documents[depart:]:
                    source_texte, id_video = (
                        extraire_source_iramuteq(doc)
                        if mode_analyse == "matrice" else ("", "")
                    )
                    metadonnees[doc.numero] = {
                        "nom_affiche": "",
                        "ligne_csv": "",
                        "fichier_source": nom_fichier,
                        "format_source": "iramuteq",
                        "source_texte": source_texte,
                        "type_source": source_texte,
                        "id_video": id_video,
                    }

        tableau = tableau_documents(documents)
        colonnes_metadonnees = {
            "nom_affiche", "ligne_csv", "fichier_source", "format_source",
            "colonne_texte_source", "colonne_auteur_source",
        }
        for informations_document in metadonnees.values():
            colonnes_metadonnees.update(informations_document.keys())
        for colonne in sorted(colonnes_metadonnees):
            tableau[colonne] = [
                metadonnees.get(int(numero), {}).get(colonne, "")
                for numero in tableau["numero_document"]
            ]
    except (ValueError, UnicodeError) as erreur:
        st.error(str(erreur))
        st.stop()

    # Ne pas garder les grands dictionnaires CSV après construction.
    del metadonnees
    if "informations" in locals():
        del informations
    st.session_state["qwen_documents_importes"] = documents
    st.session_state["qwen_tableau_importe"] = tableau
    st.session_state["qwen_cle_importation"] = cle_importation
# Les importations historiques conservent leur signature pour les reprises.
# Inclure la provenance et l'appariement vidéo dans la signature.
# Deux configurations de colonnes différentes ne doivent jamais
# réutiliser les réponses d'une autre analyse.
selection_personnalisee = (
    bool(correspondances_csv) if mode_analyse == "matrice"
    else any(
        choix["colonne_texte"] != "texte"
        or choix["colonne_auteur"] != "nom_affiche"
        for choix in correspondances_csv
    )
)
signature = (
    hashlib.sha256(
        (signature_fichiers + json.dumps(
            correspondances_csv, ensure_ascii=False, sort_keys=True,
        )).encode("utf-8")
    ).hexdigest()
    if selection_personnalisee else signature_fichiers
)
st.write(
    f"Documents importés : **{len(documents)}** ; "
    f"textes non vides : **{int(tableau['texte'].str.strip().ne('').sum())}**."
)
with st.expander("Aperçu des textes et variables", expanded=False):
    st.dataframe(
        tableau.drop(columns=["type_source"], errors="ignore").head(30),
        use_container_width=True, hide_index=True,
    )

with st.expander("Paramètres complémentaires", expanded=False):
    temperature = st.slider(
        "Température du modèle", 0.0, 0.8, 0.2, 0.05
    )
    contexte_general = st.text_area(
        "Contexte analytique facultatif commun aux commentaires",
        height=100,
        help="Aucune vidéo, image ou donnée sonore n'est récupérée automatiquement.",
    )
    variables = [col for col in tableau if col.startswith("variable_")]
    contexte_variables = st.multiselect(
        "Variables étoilées incluses dans le contexte",
        variables,
        help="Les métadonnées ne remplacent pas les indices textuels.",
    )
    montrer_uniquement_valides = st.checkbox(
        "Afficher uniquement les analyses abouties", value=False
    )

st.subheader("Définir les thèmes à partir de votre prompt")
st.caption(
    (
        "Pour un modèle spécialisé, indiquez les thèmes entre guillemets "
        "dans le prompt ou définissez-les manuellement. "
        "JuriBERT et BERTweetFR ne génèrent pas de catégories."
        if MODELE_EST_SPECIALISE
        else "Qwen peut proposer une grille à partir de la consigne, sans thème ni "
        "nombre de catégories imposés. Vous pouvez aussi saisir ou modifier "
        "manuellement chaque titre et sa définition. Les catégories ne sont pas exclusives."
    )
)
identifiant_grille = hashlib.sha256(
    (signature + prompt).encode("utf-8")
).hexdigest()
if st.session_state.get("qwen_id_grille_libre") != identifiant_grille:
    st.session_state["qwen_id_grille_libre"] = identifiant_grille
    st.session_state["qwen_themes_proposes"] = []
    st.session_state["qwen_origine_grille"] = ""

if st.button(
    "Reprendre les thèmes nommés dans le prompt"
    if MODELE_EST_SPECIALISE
    else "Construire les thèmes avec Qwen à partir du prompt"
):
    try:
        if MODELE_EST_SPECIALISE:
            propositions = extraire_themes_explicites(prompt)
            if not propositions:
                raise ValueError(
                    "Aucun thème explicite détecté : utilisez des intitulés "
                    "entre guillemets après « thèmes : », ou ajoutez des "
                    "thèmes manuellement."
                )
        else:
            propositions = proposer_themes_depuis_prompt(
                prompt,
                tableau["texte"].fillna("").astype(str).head(20).tolist(),
                modele=MODELE,
            )
        st.session_state["qwen_themes_proposes"] = propositions
        st.session_state["qwen_origine_grille"] = (
            "Extraction depuis le prompt"
            if MODELE_EST_SPECIALISE else "Proposition de Qwen"
        )
        for indice, theme in enumerate(propositions, start=1):
            st.session_state[
                f"qwen_titre_libre_{identifiant_grille[:12]}_{indice}"
            ] = theme["titre"]
            st.session_state[
                f"qwen_definition_libre_{identifiant_grille[:12]}_{indice}"
            ] = theme["definition"]
        st.rerun()
    except (requests.RequestException, ValueError, json.JSONDecodeError) as erreur:
        st.error(
            f"La proposition de thèmes a échoué : "
            f"{type(erreur).__name__} : {erreur}"
        )

colonne_ajout, colonne_effacer = st.columns(2)
with colonne_ajout:
    if st.button("Ajouter un thème manuellement"):
        themes_actuels = st.session_state["qwen_themes_proposes"]
        if len(themes_actuels) < NOMBRE_THEMES_MAXIMUM:
            themes_actuels.append({"titre": "", "definition": ""})
            st.session_state["qwen_origine_grille"] = "Grille manuelle"
            st.rerun()
        else:
            st.warning(f"Maximum de {NOMBRE_THEMES_MAXIMUM} thèmes.")
with colonne_effacer:
    if st.button("Retirer le dernier thème"):
        themes_actuels = st.session_state["qwen_themes_proposes"]
        if themes_actuels:
            indice_supprime = len(themes_actuels)
            themes_actuels.pop()
            st.session_state.pop(
                f"qwen_titre_libre_{identifiant_grille[:12]}_{indice_supprime}",
                None,
            )
            st.session_state.pop(
                f"qwen_definition_libre_{identifiant_grille[:12]}_{indice_supprime}",
                None,
            )
            st.rerun()

themes_courants: list[dict[str, str]] = []
for indice, theme in enumerate(
    st.session_state["qwen_themes_proposes"], start=1
):
    cle_titre = f"qwen_titre_libre_{identifiant_grille[:12]}_{indice}"
    cle_definition = f"qwen_definition_libre_{identifiant_grille[:12]}_{indice}"
    if cle_titre not in st.session_state:
        st.session_state[cle_titre] = theme["titre"]
    if cle_definition not in st.session_state:
        st.session_state[cle_definition] = theme["definition"]
    gauche, droite = st.columns([1, 2])
    with gauche:
        titre = st.text_input(
            f"Thème {indice} — intitulé",
            key=cle_titre,
        )
    with droite:
        definition = st.text_area(
            f"Thème {indice} — définition",
            key=cle_definition,
            height=75,
        )
    themes_courants.append({"titre": titre, "definition": definition})

st.session_state["qwen_themes_proposes"] = themes_courants
themes_valides: list[dict[str, str]] | None = None
if not themes_courants:
    st.info(
        (
            "La grille n'est pas encore définie. Ajoutez des thèmes "
            "manuellement ou reprenez ceux nommés dans votre prompt."
            if MODELE_EST_SPECIALISE
            else "La grille n'est pas encore définie. Cliquez sur « Construire les "
            "thèmes avec Qwen à partir du prompt » ou ajoutez vos catégories."
        )
    )
else:
    try:
        themes_valides = valider_themes(themes_courants)
        st.success(
            f"Grille valide : {len(themes_valides)} thème(s) indépendant(s). "
            (
                "Vous pouvez calculer les similarités."
                if MODELE_EST_SPECIALISE
                else "Vous pouvez commencer à annoter les textes."
            )
        )
    except ValueError as erreur:
        st.error(f"Grille incomplète : {erreur}")

configuration = {
    "modele": MODELE,
    "mode_analyse": "matrice",
    "prompt": prompt,
    "themes": themes_valides,
    "temperature": float(temperature),
    "contexte_general": contexte_general,
    "contexte_variables": contexte_variables,
    "signature_corpus": signature,
    "correspondances_csv": correspondances_csv,
}
cle = hashlib.sha256(
    json.dumps(configuration, sort_keys=True, ensure_ascii=False)
    .encode("utf-8")
).hexdigest()
if st.session_state.get("qwen_cle") != cle:
    st.session_state["qwen_cle"] = cle
    tableau_initial = initialiser_tableau(tableau, signature, cle)
    if themes_valides is not None:
        tableau_initial = initialiser_annotations_matrice(
            tableau_initial, themes_valides
        )
    st.session_state["qwen_donnees"] = tableau_initial
    st.session_state["qwen_message"] = ""
    st.session_state.pop("qwen_test_rapide", None)


checkpoint = st.file_uploader(
    "Reprendre une analyse : importer le CSV de résultats précédent (facultatif)",
    type=["csv"], key="checkpoint",
)
if checkpoint is not None and st.button(
    "Restaurer les résultats enregistrés",
    disabled=themes_valides is None,
):
    try:
        anciens = pd.read_csv(
            io.BytesIO(checkpoint.getvalue()),
            sep=";", encoding="utf-8-sig",
            dtype={
                "signature_corpus": str, "cle_configuration": str,
                "texte": str,
            },
        )
        st.session_state["qwen_donnees"] = restaurer_checkpoint(
            st.session_state["qwen_donnees"],
            anciens, signature, cle, themes_valides,
        )
        st.success("Résultats restaurés. Vous pouvez poursuivre les analyses.")
    except (ValueError, pd.errors.ParserError) as erreur:
        st.error(f"Reprise impossible : {erreur}")

donnees = st.session_state["qwen_donnees"]
if MODELE_EST_SPECIALISE:
    st.subheader("Analyse textuelle avec le modèle spécialisé")
    st.caption(
        f"Modèle : {LIBELLES_MODELES[MODELE]}. "
        "Chaque valeur représente une similarité cosinus entre un texte "
        "et la définition d'un thème, pas une probabilité de présence. "
        "Les modèles ne produisent ni justification générée ni codage binaire."
    )
    etat_encodeurs = False
    try:
        adresse_encodeurs = os.getenv(
            "ENCODEURS_URL", "http://encodeurs:8502"
        ).rstrip("/")
        inventaire = requests.get(
            adresse_encodeurs + "/modeles", timeout=10
        )
        inventaire.raise_for_status()
        etat_encodeurs = MODELE in inventaire.json().get("modeles", {})
        if not etat_encodeurs:
            st.warning("Le modèle sélectionné n'est pas déclaré par le service.")
    except (requests.RequestException, ValueError) as erreur:
        st.warning(
            f"Vérification des encodeurs impossible : {erreur}. "
            "Vous pouvez tester un texte pour afficher le diagnostic précis."
        )

    lignes_restantes = donnees.index[
        donnees["statut_codage"].eq("non_traite")
    ].tolist()
    lignes_erreur = donnees.index[
        donnees["statut_codage"].isin(["erreur_service", "sortie_invalide"])
    ].tolist()
    lignes_traitees = donnees.index[
        donnees["statut_codage"].eq("similarite")
    ].tolist()
    st.write(
        f"Textes avec similarités : **{len(lignes_traitees)}** ; "
        f"restants : **{len(lignes_restantes)}** ; "
        f"erreurs : **{len(lignes_erreur)}**."
    )
    if st.session_state.get("qwen_message"):
        st.info(st.session_state["qwen_message"])
    if themes_valides is None:
        st.warning("Définissez et validez d'abord vos thèmes.")
    col_test, col_tous, col_reprise, col_stop = st.columns([1, 2, 1, 1])
    test_encodeur = col_test.button(
        "Tester sur un texte",
        disabled=not lignes_restantes or themes_valides is None,
    )
    tous_encodeur = col_tous.button(
        "Analyser tous les textes restants",
        type="primary",
        disabled=not lignes_restantes or themes_valides is None,
    )
    relancer_encodeur = col_reprise.button(
        "Réessayer les textes en erreur",
        disabled=not lignes_erreur or themes_valides is None,
    )
    col_stop.button(
        "Arrêter l'analyse",
        on_click=demander_arret_analyse,
        help="Arrêt entre deux textes, sans effacer les similarités calculées.",
    )
    if test_encodeur:
        indice = min(
            lignes_restantes[:200],
            key=lambda i: len(str(donnees.at[i, "texte"])),
        )
        texte_test = str(donnees.at[indice, "texte"])
        debut = time.perf_counter()
        try:
            resultat_test = interroger_encodeur_specialise(
                texte_test, themes_valides, MODELE, delai_lecture=60,
            )
            st.session_state["qwen_test_rapide"] = {
                "reussi": True,
                "modele": MODELE,
                "resultat": resultat_test,
                "duree_secondes": round(time.perf_counter() - debut, 2),
            }
            for champ, valeur in resultat_test.items():
                donnees.at[indice, champ] = valeur
            donnees.at[indice, "statut_codage"] = "similarite"
            donnees.at[indice, "erreur_codage"] = ""
            st.session_state["qwen_donnees"] = donnees
        except (requests.RequestException, ValueError, KeyError) as erreur:
            st.session_state["qwen_test_rapide"] = {
                "reussi": False,
                "modele": MODELE,
                "erreur": f"{type(erreur).__name__} : {erreur}",
                "duree_secondes": round(time.perf_counter() - debut, 2),
            }
        st.rerun()
    if tous_encodeur or relancer_encodeur:
        indices = lignes_restantes if tous_encodeur else lignes_erreur
        st.session_state["qwen_arret_demande"] = False
        avancement = st.progress(0, text="Calcul des similarités")
        nombre_reussites = 0
        nombre_erreurs = 0
        with requests.Session() as session:
            for position, indice in enumerate(indices, start=1):
                if st.session_state.get("qwen_arret_demande", False):
                    break
                try:
                    resultat = interroger_encodeur_specialise(
                        str(donnees.at[indice, "texte"]), themes_valides,
                        MODELE, session=session,
                    )
                    for champ, valeur in resultat.items():
                        donnees.at[indice, champ] = valeur
                    donnees.at[indice, "statut_codage"] = "similarite"
                    donnees.at[indice, "erreur_codage"] = ""
                    nombre_reussites += 1
                except (requests.RequestException, ValueError, KeyError) as erreur:
                    donnees.at[indice, "statut_codage"] = (
                        "erreur_service"
                        if isinstance(erreur, requests.RequestException)
                        else "sortie_invalide"
                    )
                    donnees.at[indice, "erreur_codage"] = (
                        f"{type(erreur).__name__} : {str(erreur)[:800]}"
                    )
                    nombre_erreurs += 1
                st.session_state["qwen_donnees"] = donnees
                avancement.progress(
                    position / max(1, len(indices)),
                    text=f"Textes examinés : {position}/{len(indices)}",
                )
                # Éviter les requêtes répétées si le service est indisponible.
                if nombre_erreurs >= 3 and nombre_reussites == 0:
                    break
        avancement.empty()
        st.session_state["qwen_message"] = (
            f"Similarités obtenues : {nombre_reussites} ; "
            f"erreurs : {nombre_erreurs}. "
            "Les textes non traités peuvent être repris."
        )
        st.rerun()

    retour_encodeur = st.session_state.get("qwen_test_rapide")
    if retour_encodeur:
        if retour_encodeur["reussi"]:
            st.success(
                f"Test réussi avec {retour_encodeur['modele']} "
                f"en {retour_encodeur['duree_secondes']} s."
            )
            resultat = retour_encodeur["resultat"]
            st.dataframe(
                pd.DataFrame([
                    {"theme": theme["titre"],
                     "similarite_cosinus": resultat["similarite_" + code]}
                    for code, theme in zip(codes_themes(themes_valides), themes_valides)
                ]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.error(
                f"Test échoué : {retour_encodeur['erreur']}. "
                "Aucun résultat n'a été inventé."
            )

    if lignes_traitees:
        st.subheader("Similarités par texte et par thème")
        codes = codes_themes(themes_valides)
        colonnes = [
            "numero_document", "id_video", "source_texte", "texte",
            *("similarite_" + code for code in codes), "texte_tronque",
        ]
        st.dataframe(
            donnees.loc[lignes_traitees].reindex(columns=colonnes).head(1000),
            hide_index=True, use_container_width=True,
            column_config={
                "similarite_" + code: st.column_config.NumberColumn(
                    theme["titre"], format="%.4f"
                )
                for code, theme in zip(codes, themes_valides)
            },
        )
        st.caption(
            "Le texte peut être tronqué à 256 tokens par l'encodeur. "
            "Ces valeurs exploratoires ne sont pas calibrées."
        )
    if lignes_erreur:
        st.subheader("Erreurs du modèle spécialisé")
        st.dataframe(
            donnees.loc[lignes_erreur, [
                "numero_document", "texte", "erreur_codage",
            ]].head(200),
            hide_index=True, use_container_width=True,
        )

    def generer_csv_specialise() -> bytes:
        """Exporter la totalité des lignes sans colonnes internes masquées."""
        colonnes = [
            "numero_document", "id_video", "source_texte", "texte",
            *("similarite_" + code for code in codes_themes(themes_valides or [])),
            "texte_tronque",
        ]
        return exporter_csv(donnees.reindex(columns=colonnes))

    def generer_checkpoint_specialise() -> bytes:
        """Conserver la reprise même si la source logique reste masquée."""
        return exporter_csv(
            donnees.drop(columns=["type_source"], errors="ignore")
        )

    def generer_archive_specialisee() -> bytes:
        """Fournir un ZIP avec les similarités, le corpus et les paramètres."""
        memoire = io.BytesIO()
        with zipfile.ZipFile(memoire, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "similarites_modeles_specialises.csv",
                generer_csv_specialise(),
            )
            archive.writestr(
                "codage_commentaires.csv", generer_checkpoint_specialise()
            )
            archive.writestr(
                "grille_themes.json",
                json.dumps(
                    {"themes": themes_valides}, ensure_ascii=False, indent=2,
                ),
            )
            archive.writestr(
                "parametres.json",
                json.dumps(
                    {**configuration, "signature": signature},
                    ensure_ascii=False, indent=2,
                ),
            )
        return memoire.getvalue()

    st.download_button(
        "Télécharger tous les résultats, même partiels (ZIP)",
        data=generer_archive_specialisee,
        file_name="resultats_" + MODELE + "_similarites.zip",
        mime="application/zip",
        on_click="ignore",
    )
    st.download_button(
        "Télécharger le CSV de reprise",
        data=generer_checkpoint_specialise,
        file_name="codage_commentaires.csv",
        mime="text/csv",
        on_click="ignore",
    )
    st.stop()

reste = donnees.index[donnees["statut_codage"].eq("non_traite")].tolist()
erreurs = donnees.index[
    donnees["statut_codage"].isin(["erreur_service", "sortie_invalide"])
].tolist()
aboutis = int(donnees["statut_codage"].eq("ok").sum())
vides = int(donnees["statut_codage"].eq("vide").sum())
st.write(
    f"Analyses réalisées : **{aboutis}** ; "
    f"à analyser : **{len(reste)}** ; "
    f"en erreur : **{len(erreurs)}** ; "
    f"textes vides : **{vides}**."
)
if st.session_state.get("qwen_message"):
    if erreurs:
        st.error(st.session_state["qwen_message"])
    else:
        st.info(st.session_state["qwen_message"])

if erreurs:
    if any(
        "unexpected eof" in str(valeur).lower()
        for valeur in donnees.loc[erreurs, "erreur_codage"]
    ):
        st.warning(
            "Ollama a perdu la connexion avec le processus d'inférence "
            "(unexpected EOF). Il faut consulter les journaux du conteneur "
            "ollama dans Coolify, au moment exact de l'échec. "
            "Une saturation mémoire, un plantage du moteur ou un problème "
            "de compatibilité sont possibles ; ce message seul ne permet "
            "pas de les départager. Le choix de la colonne CSV ne résout "
            "pas cette panne d'Ollama."
        )
    st.error(
        f"Échec de l'inférence Qwen pour {len(erreurs)} commentaire(s). "
        f"Modèle sollicité : {MODELE} ; "
        f"contexte demandé : {CONTEXTE_MAXIMUM} tokens. "
        "Voici les causes techniques renvoyées par Ollama :"
    )
    for numero_erreur, (_, ligne_erreur) in enumerate(
        donnees.loc[erreurs].head(3).iterrows(), start=1
    ):
        st.code(
            f"Commentaire {int(ligne_erreur['numero_document'])} — "
            f"{ligne_erreur['statut_codage']}\n"
            f"Modèle sollicité : {MODELE}\n"
            f"Contexte demandé : {CONTEXTE_MAXIMUM} tokens\n"
            f"{ligne_erreur['erreur_codage'] or 'Détail non fourni'}",
            language="text",
        )

# Lancer une analyse uniquement lorsque l'API répond ET que le modèle est présent.
service_disponible = False
try:
    informations = verifier_service()
    modeles_disponibles = [
        str(modele.get("name", "")) for modele in informations.get("models", [])
    ]
    service_disponible = any(
        nom == MODELE or nom.startswith(MODELE + ":")
        for nom in modeles_disponibles
    )
    if service_disponible:
        st.success(
            f"Modèle sollicité : {MODELE} — disponible dans Ollama. "
            "Cela confirme sa présence, mais pas sa capacité à terminer une inférence."
        )
    else:
        st.error(
            f"Ollama répond, mais le modèle {MODELE} est absent. "
            "Aucune analyse ne peut commencer : vérifiez le téléchargement "
            "des poids Qwen dans le service charger_modele de Coolify."
        )
except requests.RequestException as erreur:
    st.error(
        f"Impossible de joindre Ollama ({URL_OLLAMA}) : {type(erreur).__name__} : {erreur}. "
        "Vérifiez le service ollama dans Coolify ; les données CSV "
        "ne constituent pas un résultat d'analyse."
    )

st.subheader("Lancer l'analyse")
st.caption(
    "Le test vérifie l'inférence sur un texte court en un seul appel Ollama "
    "(au maximum 350 caractères, avec un délai de lecture limité à 60 secondes). "
    "Si le texte original est plus long, le test porte sur son début et "
    "ne valide pas l'ensemble du document. L'analyse complète reste inchangée."
)
etat_commandes = evaluer_commandes_analyse(
    nombre_restants=len(reste),
    nombre_erreurs=len(erreurs),
    prompt=prompt,
    mode_analyse=mode_analyse,
    grille_valide=themes_valides is not None,
    service_disponible=service_disponible,
)
for cause_blocage in etat_commandes["causes"]:
    st.warning(cause_blocage)
if etat_commandes["avertissement_service"]:
    st.warning(
        f"La disponibilité du modèle {MODELE} n'a pas été confirmée "
        "par la vérification d'Ollama. Vous pouvez néanmoins essayer "
        "une inférence ; le résultat ou l'erreur sera affiché explicitement. "
        "Cette vérification n'est pas une exécution du modèle."
    )
if etat_commandes["lancer"]:
    st.success(
        f"{len(reste)} texte(s) prêt(s) pour l'analyse avec {MODELE}. "
        "La grille et le prompt sont renseignés."
    )
colonne_test, colonne_analyser, colonne_erreurs, colonne_arret = st.columns(
    [1, 2, 1, 1]
)
tester = colonne_test.button(
    "Tester sur un texte",
    disabled=not etat_commandes["tester"],
)
lancer = colonne_analyser.button(
    "Analyser tous les textes restants",
    type="primary",
    disabled=not etat_commandes["lancer"],
)
relancer = colonne_erreurs.button(
    "Réessayer les textes en erreur",
    disabled=not etat_commandes["relancer"],
)
colonne_arret.button(
    "Arrêter l'analyse",
    on_click=demander_arret_analyse,
    help=(
        "Interrompt le traitement entre deux requêtes Qwen. "
        "La requête déjà envoyée peut devoir se terminer avant l'arrêt."
    ),
)
if tester:
    # Le bouton de test ne doit jamais parcourir un texte long segment après
    # segment. Retenir un texte court, ou seulement le début d'un texte long.
    indice_test = min(
        reste[:200],
        key=lambda indice: len(str(donnees.at[indice, "texte"])),
    )
    texte_original = str(donnees.at[indice_test, "texte"])
    texte_essai = texte_original[:350]
    extrait_uniquement = len(texte_original) > len(texte_essai)
    ligne_essai = donnees.loc[indice_test]
    details_essai = "\n".join(
        f"{colonne}: {ligne_essai[colonne]}"
        for colonne in contexte_variables
        if pd.notna(ligne_essai.get(colonne))
    )
    contexte_essai = (contexte_general + "\n" + details_essai).strip()
    debut_test = time.perf_counter()
    resultat_test = None
    erreur_test = ""
    with st.spinner(
        f"Test réel avec {MODELE} : une seule requête Ollama..."
    ):
        try:
            with requests.Session() as session:
                resultat_test = coder_multithemes(
                    texte=texte_essai,
                    themes=themes_valides,
                    contexte=contexte_essai,
                    temperature=float(temperature),
                    session=session,
                    consigne=prompt,
                    timeout_lecture=60,
                    modele=MODELE,
                )
        except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError) as erreur:
            erreur_test = f"{type(erreur).__name__} : {erreur}"
    duree_test = round(time.perf_counter() - debut_test, 2)
    st.session_state["qwen_test_rapide"] = {
        "reussi": resultat_test is not None,
        "numero_document": int(ligne_essai["numero_document"]),
        "duree_secondes": duree_test,
        "nombre_caracteres": len(texte_essai),
        "extrait_uniquement": extrait_uniquement,
        "modele": MODELE,
        "contexte_tokens": CONTEXTE_MAXIMUM,
        "erreur": erreur_test,
        "resultat": resultat_test,
    }
    if resultat_test is not None and not extrait_uniquement:
        # Un document intégralement testé est conservé comme auparavant.
        for champ, valeur in resultat_test.items():
            donnees.at[indice_test, champ] = valeur
        donnees.at[indice_test, "statut_codage"] = "ok"
        donnees.at[indice_test, "erreur_codage"] = ""
        st.session_state["qwen_donnees"] = donnees
    # Si un extrait a été testé, le document original reste non traité.
    st.rerun()

if lancer or relancer:
    st.session_state["qwen_arret_demande"] = False
    indices = reste if lancer else erreurs
    termines, nombre_erreurs, interrompu = lancer_analyse(
        donnees, indices, prompt, themes_valides,
        contexte_general, contexte_variables, float(temperature), MODELE,
    )
    st.session_state["qwen_donnees"] = donnees
    if st.session_state.get("qwen_arret_demande", False):
        st.session_state["qwen_message"] = (
            f"Analyse arrêtée à la demande : {termines} annotation(s) "
            f"supplémentaire(s) conservée(s), {nombre_erreurs} erreur(s). "
            "Les textes non traités restent disponibles pour la reprise."
        )
    elif interrompu:
        indice_derniere_erreur = indices[min(
            len(indices) - 1, termines + nombre_erreurs - 1
        )]
        detail_derniere_erreur = str(
            donnees.at[indice_derniere_erreur, "erreur_codage"]
        )
        panne_moteur = (
            "signal: killed" in detail_derniere_erreur.lower()
            or "unexpected eof" in detail_derniere_erreur.lower()
        )
        motif_arret = (
            "arrêt du moteur d'inférence Ollama"
            if panne_moteur else "trois erreurs consécutives"
        )
        st.session_state["qwen_message"] = (
            f"Analyse interrompue ({motif_arret}). "
            f"Modèle sollicité : {MODELE} ; "
            f"contexte demandé : {CONTEXTE_MAXIMUM} tokens ; "
            f"{termines} réussite(s), {nombre_erreurs} erreur(s). "
            f"Cause : {detail_derniere_erreur}. "
            "Les analyses abouties restent conservées."
        )
    elif nombre_erreurs:
        st.session_state["qwen_message"] = (
            f"{termines} analyse(s) aboutie(s), {nombre_erreurs} erreur(s). "
            "Les détails techniques sont visibles dans la rubrique Erreurs de Qwen."
        )
    else:
        st.session_state["qwen_message"] = (
            f"{termines} commentaire(s) analysé(s) avec succès. "
            "Les réponses sont affichées ci-dessous."
        )
    st.rerun()

retour_test = st.session_state.get("qwen_test_rapide")
if retour_test:
    if retour_test["reussi"]:
        portee = (
            "Extrait uniquement : le document complet reste à analyser."
            if retour_test["extrait_uniquement"]
            else "Document court intégralement analysé et enregistré."
        )
        st.success(
            f"Test Ollama réussi avec {retour_test['modele']} : "
            f"{retour_test['duree_secondes']} s, "
            f"{retour_test['nombre_caracteres']} caractères, un appel. "
            + portee
        )
        with st.expander("Consulter les annotations obtenues lors du test"):
            st.json(retour_test["resultat"])
    else:
        st.error(
            f"Test Ollama échoué avec {retour_test['modele']} "
            f"(contexte {retour_test['contexte_tokens']} tokens, "
            f"{retour_test['duree_secondes']} s). "
            f"Cause : {retour_test['erreur']}. "
            "Le document reste disponible : aucun résultat n'a été inventé."
        )

st.subheader("Réponses produites par Qwen")
reponses_valides = donnees.loc[
    donnees["statut_codage"].eq("ok")
    & donnees["reponse_qwen"].fillna("").astype(str).str.strip().ne("")
].copy()
tableau_erreurs = donnees.loc[
    donnees["statut_codage"].isin(["erreur_service", "sortie_invalide"])
].copy()
nombre_a_traiter = int(donnees["statut_codage"].eq("non_traite").sum())

if reponses_valides.empty:
    if not tableau_erreurs.empty:
        st.error(
            "Aucune réponse produite par Qwen : les tentatives ont rencontré "
            "des erreurs. Leur détail est affiché ci-dessous. "
            "Le tableau importé n'est PAS une analyse."
        )
    elif nombre_a_traiter:
        st.info(
            f"Aucune réponse Qwen pour le moment. "
            f"{nombre_a_traiter} commentaire(s) attendent une analyse. "
            "Utilisez « Tester sur un texte » pour vérifier "
            "le fonctionnement du modèle avant l'analyse du corpus entier."
        )
    else:
        st.warning(
            "Aucune réponse Qwen disponible. "
            "Consultez le statut des commentaires et les éventuelles erreurs."
        )
else:
    st.success(
        f"{len(reponses_valides)} réponse(s) effectivement générée(s) par le modèle."
    )
    colonnes_principales = [
        "numero_document", "nom_affiche", "texte", "reponse_qwen",
        "statut_codage",
    ]
    colonnes_principales = [
        "numero_document", "id_video", "source_texte",
        "texte", *(codes_themes(themes_valides) if themes_valides else []),
        *(
            "probabilite_" + code
            for code in (codes_themes(themes_valides) if themes_valides else [])
        ),
        "probabilite_incertitude",
    ]
    st.dataframe(
        reponses_valides[
            [col for col in colonnes_principales if col in reponses_valides]
        ].head(1000),
        hide_index=True,
        use_container_width=True,
        height=380,
        column_config={
            "texte": st.column_config.TextColumn("Commentaire", width="large"),
            "nom_affiche": st.column_config.TextColumn("Auteur"),
            "reponse_qwen": st.column_config.TextColumn(
                "Analyse produite par Qwen", width="large"
            ),
        },
    )
    if len(reponses_valides) > 1000:
        st.caption(
            "Aperçu limité à 1 000 réponses. Les exports contiennent toutes les lignes."
        )

    identifiants = reponses_valides["numero_document"].astype(int).tolist()
    descriptions = {
        int(ligne.numero_document): (
            f"{int(ligne.numero_document)} — "
            f"{str(ligne.nom_affiche) if str(ligne.nom_affiche).strip() else 'Sans pseudonyme'}"
        )
        for ligne in reponses_valides.itertuples(index=False)
    }
    commentaire_choisi = st.selectbox(
        "Lire intégralement une analyse",
        identifiants,
        format_func=lambda numero: descriptions.get(numero, str(numero)),
    )
    selection = reponses_valides.loc[
        reponses_valides["numero_document"].eq(commentaire_choisi)
    ].iloc[0]
    st.text_area(
        "Commentaire original",
        value=str(selection["texte"]),
        height=100,
        disabled=True,
    )
    st.text_area(
        "Réponse effective de Qwen",
        value=str(selection["reponse_qwen"]),
        height=260,
        disabled=True,
    )

if not tableau_erreurs.empty:
    st.subheader("Erreurs de Qwen")
    st.error(
        f"{len(tableau_erreurs)} commentaire(s) n'ont pas reçu de réponse valide. "
        "Une erreur HTTP, une indisponibilité d'Ollama ou une sortie invalide "
        "n'est pas un résultat d'analyse."
    )
    st.dataframe(
        tableau_erreurs[
            [
                col for col in (
                    "numero_document", "nom_affiche", "texte",
                    "erreur_codage",
                )
                if col in tableau_erreurs
            ]
        ].head(200),
        hide_index=True,
        use_container_width=True,
        column_config={
            "erreur_codage": st.column_config.TextColumn(
                "Cause technique (Ollama ou modèle)", width="large"
            ),
        },
    )

with st.expander("Tableau complet, métadonnées et variables du corpus", expanded=False):
    vue = (
        donnees.loc[donnees["statut_codage"].eq("ok")]
        if montrer_uniquement_valides else donnees
    )
    st.dataframe(
        vue.drop(columns=["type_source"], errors="ignore").head(1000),
        hide_index=True, use_container_width=True,
    )
    if len(vue) > 1000:
        st.caption(
            "Aperçu limité à 1 000 lignes. Le ZIP et le CSV "
            "contiennent toutes les lignes."
        )


if themes_valides is not None:
    st.subheader("Matrice des annotations par texte et par thème")
    matrice_affichage = construire_matrice(donnees, themes_valides)
    codes = codes_themes(themes_valides)
    colonnes_matrice = [
        "numero_document", "id_video", "source_texte",
        "texte", *("final_" + code for code in codes),
        *("probabilite_" + code for code in codes),
        "probabilite_incertitude", "validation_humaine",
    ]
    st.dataframe(
        matrice_affichage[colonnes_matrice].head(1000),
        use_container_width=True, hide_index=True,
        column_config={
            **{
                "probabilite_" + code: st.column_config.NumberColumn(
                    "Confiance " + theme["titre"], format="%.2f",
                )
                for code, theme in zip(codes, themes_valides)
            },
            "probabilite_incertitude": st.column_config.NumberColumn(
                "Incertitude (score)", format="%.2f",
            ),
        },
    )
    st.caption(
        "source_texte affiche le nom exact de la colonne CSV sélectionnée ; "
        ""
        "Les valeurs entre 0 et 1 sont des scores estimés par Qwen "
        "(non calibrés), distincts des annotations validées. "
        "Les exports conservent l'intégralité du corpus."
    )
    with st.expander("Consulter les textes regroupés par thème", expanded=False):
        panneaux = st.tabs([theme["titre"] for theme in themes_valides])
        for panneau, code, theme in zip(panneaux, codes, themes_valides):
            with panneau:
                sous_corpus = matrice_affichage.loc[
                    matrice_affichage["statut_codage"].eq("ok")
                    & matrice_affichage["final_" + code].eq(True).fillna(False)
                ]
                st.caption(
                    f"{len(sous_corpus)} texte(s) associé(s) à {theme['titre']}. "
                    "Le même texte peut relever de plusieurs catégories."
                )
                st.dataframe(
                    sous_corpus[
                        [
                            "numero_document", "id_video", "source_texte",
                            "texte",
                        ]
                    ].head(1000),
                    use_container_width=True, hide_index=True,
                )

    st.subheader("Répartition des thèmes selon la source textuelle")
    bilan_sources = construire_bilan_sources(matrice_affichage, themes_valides)
    st.dataframe(
        bilan_sources.drop(columns=["type_source"]),
        use_container_width=True, hide_index=True,
    )

    st.subheader("Comparaison des textes appariés par identifiant vidéo")
    comparaison = comparer_sources_par_video(matrice_affichage, themes_valides)
    if comparaison.empty:
        st.info(
            "Aucun appariement par identifiant vidéo disponible. "
            "Ce réglage reste facultatif pour l'annotation des corpus."
        )
    else:
        st.dataframe(
            comparaison.head(1000), use_container_width=True, hide_index=True
        )
        st.caption(
            "Une source absente est non_disponible ; une source non analysée "
            "est non_traite. Les discordances exigent deux annotations connues."
        )

    st.subheader("Validation et correction manuelles")
    lignes_verifiables = donnees.loc[donnees["statut_codage"].eq("ok")]
    if lignes_verifiables.empty:
        st.info("Analysez au moins un texte pour activer la correction manuelle.")
    else:
        identifiants = lignes_verifiables["numero_document"].astype(int).tolist()
        numero_validation = st.selectbox(
            "Texte à valider",
            identifiants,
            format_func=lambda numero: (
                f"{numero} — "
                + str(
                    donnees.loc[
                        donnees["numero_document"].eq(numero), "source_texte"
                    ].iloc[0]
                )
            ),
            key="qwen_numero_validation_matrice",
        )
        ligne_validation = donnees.loc[
            donnees["numero_document"].eq(numero_validation)
        ].iloc[0]
        st.text_area(
            "Texte original",
            value=str(ligne_validation["texte"]),
            height=180, disabled=True,
        )
        with st.form(
            key=f"qwen_form_validation_{numero_validation}",
            clear_on_submit=False,
        ):
            corrections = {}
            for code, theme in zip(codes, themes_valides):
                actuel = ligne_validation["manuel_" + code]
                if pd.isna(actuel):
                    actuel = ligne_validation[code]
                corrections[code] = st.checkbox(
                    theme["titre"],
                    value=bool(actuel) if pd.notna(actuel) else False,
                )
            note = st.text_area(
                "Observation du chercheur",
                value=str(ligne_validation["note_humaine"]),
                height=80,
            )
            enregistrer = st.form_submit_button(
                "Enregistrer la validation ou la correction"
            )
        if enregistrer:
            indice = donnees.index[
                donnees["numero_document"].eq(numero_validation)
            ][0]
            correction = any(
                bool(corrections[code]) != bool(donnees.at[indice, code])
                for code in codes
            )
            for code in codes:
                donnees.at[indice, "manuel_" + code] = corrections[code]
            donnees.at[indice, "validation_humaine"] = (
                "corrige" if correction else "valide"
            )
            donnees.at[indice, "note_humaine"] = note
            st.session_state["qwen_donnees"] = donnees
            st.success("Validation humaine enregistrée dans la matrice.")
            st.rerun()

# L'export des dizaines de milliers de lignes n'est pas exécuté
# lors de chaque affichage : Streamlit le prépare au clic uniquement.
parametres_export = {
    **configuration, "correspondances_csv": correspondances_csv
}


def generer_archive_au_telechargement() -> bytes:
    """Construire l'archive unique uniquement à la demande."""
    return archive_resultats(
        donnees, documents, signature, parametres_export
    )


def generer_csv_au_telechargement() -> bytes:
    """Produire le CSV de reprise uniquement à la demande."""
    return exporter_csv(
        donnees.drop(columns=["type_source"], errors="ignore")
    )


st.download_button(
    "Télécharger tous les résultats, même partiels (ZIP)",
    data=generer_archive_au_telechargement,
    file_name="resultats_qwen3_4b_iramuteq.zip",
    mime="application/zip",
    on_click="ignore",
)
st.download_button(
    "Télécharger le CSV de reprise",
    data=generer_csv_au_telechargement,
    file_name="codage_commentaires.csv",
    mime="text/csv",
    on_click="ignore",
)
