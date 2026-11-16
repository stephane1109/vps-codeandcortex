"""Application Streamlit Qwen3-4B : prompt libre et codage structuré optionnel."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import zipfile
from dataclasses import replace

import pandas as pd
import requests
import streamlit as st

from codage_qwen import (
    CHAMPS_BOOLEENS,
    MODELE,
    PROMPT_LIBRE_DEFAUT,
    PROMPT_VIOLENCE_DEFAUT,
    PROMPT_THESES_DEFAUT,
    THESES_INITIALES,
    proposer_trois_theses,
    valider_theses,
    CONTEXTE_MAXIMUM,
    URL_OLLAMA,
    coder_commentaire,
    verifier_service,
)
from lecture_commentaires import analyser_commentaires_csv, obtenir_apercu_csv
from codage_multithemes import (
    CHAMPS_THEMES, PROMPT_MATRICE_DEFAUT, coder_multithemes,
)
from matrice_violence import (
    SOURCES_TEXTE, LIBELLES_SOURCES, LIBELLES_THEMES,
    analyser_sources_csv, extraire_source_iramuteq,
    initialiser_annotations_matrice, construire_matrice,
    construire_bilan_sources, comparer_sources_par_video,
    exporter_iramuteq_matrice,
)
from preparation_analyse import evaluer_commandes_analyse
from lecture_iramuteq import (
    analyser_corpus,
    exporter_csv,
    exporter_iramuteq,
    tableau_documents,
)

st.set_page_config(page_title=f"Qwen {MODELE} — analyse de corpus", layout="wide")


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


def categorie_document(ligne, mode_analyse: str) -> str:
    """Conserver les anciennes catégories, ou signaler une analyse libre."""
    if ligne.statut_codage != "ok":
        return "indetermine"
    if mode_analyse == "libre":
        return "analyse_libre"
    if mode_analyse == "theses":
        # Conserver un code IRaMuTeQ stable malgré l'édition des intitulés.
        resultat = str(getattr(ligne, "theme_retenu", "")) or str(
            getattr(ligne, "these_retenue", "indetermine")
        ).replace("these_", "theme_")
        return resultat.removeprefix("theme_") if resultat else "indetermine"
    if est_vrai(ligne.interpretation_indeterminee):
        return "indetermine"
    if est_vrai(ligne.violence_justifiee) and est_vrai(ligne.violence_denoncee):
        return "ambivalent"
    if est_vrai(ligne.violence_justifiee):
        return "justification"
    if est_vrai(ligne.violence_denoncee):
        return "denonciation"
    if est_vrai(ligne.violence_minimisee):
        return "minimisation"
    if est_vrai(ligne.violence_evoquee):
        return "evocation"
    return "hors_violence"


def archive_resultats(
    tableau: pd.DataFrame,
    documents,
    signature: str,
    parametres: dict[str, object],
) -> bytes:
    """Créer une archive ZIP unique incluant toutes les lignes et le prompt."""
    mode_analyse = str(parametres["mode_analyse"])
    if mode_analyse == "matrice":
        matrice = construire_matrice(tableau)
        texte = exporter_iramuteq_matrice(documents, matrice)
    else:
        categories = {
            int(ligne.numero_document): categorie_document(ligne, mode_analyse)
            for ligne in tableau.itertuples(index=False)
        }
        nom_variable = "qwen_theme" if mode_analyse == "theses" else "qwen_position"
        texte = exporter_iramuteq(documents, categories, nom_variable)
    colonnes_reponses = [
        "numero_document", "nom_affiche", "texte", "fichier_source",
        "ligne_csv", "colonne_texte_source", "colonne_auteur_source",
        "reponse_qwen", "statut_codage", "erreur_codage", "mode_analyse",
        "theme_retenu", "theme_intitule", "indice_textuel", "justification",
        "these_retenue", "these_intitule",
        "id_video", "source_texte", *CHAMPS_THEMES,
        "indice_denonciation", "indice_indignation", "indice_persecuteur",
        "acteur_designe", "incertitude_interpretation",
        "validation_humaine", "note_humaine",
    ]
    reponses = tableau[[col for col in colonnes_reponses if col in tableau]].copy()
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("codage_commentaires.csv", exporter_csv(tableau))
        archive.writestr("reponses_qwen.csv", exporter_csv(reponses))
        archive.writestr("corpus_qwen_iramuteq.txt", texte)
        if mode_analyse == "matrice":
            archive.writestr("matrice_annotations_qwen.csv", exporter_csv(matrice))
            archive.writestr(
                "comparaison_videos_qwen.csv",
                exporter_csv(comparer_sources_par_video(matrice)),
            )
            archive.writestr(
                "bilan_sources_themes_qwen.csv",
                exporter_csv(construire_bilan_sources(matrice)),
            )
        if mode_analyse == "theses" and parametres.get("theses") is not None:
            grille = valider_theses(parametres.get("theses"))
            bilans = pd.DataFrame([
                {
                    "code": f"theme_{indice}",
                    "theme": theme["titre"],
                    "definition": theme["definition"],
                    "nombre_commentaires": int(
                        (
                            tableau["theme_retenu"].eq(f"theme_{indice}")
                            & tableau["statut_codage"].eq("ok")
                        ).sum()
                    ),
                }
                for indice, theme in enumerate(grille, start=1)
            ])
            bilans.loc[len(bilans)] = {
                "code": "indetermine",
                "theme": "Indéterminé / hors des trois thèmes",
                "definition": "Aucun thème n'est suffisamment étayé",
                "nombre_commentaires": int((
                    tableau["theme_retenu"].eq("indetermine")
                    & tableau["statut_codage"].eq("ok")
                ).sum()),
            }
            archive.writestr("bilan_themes_qwen.csv", exporter_csv(bilans))
            archive.writestr(
                "grille_themes_qwen.json",
                json.dumps({"themes": grille}, ensure_ascii=False, indent=2),
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
    """Initialiser les résultats en conservant les textes et les métadonnées."""
    # Réutiliser les colonnes sources sans les dupliquer en mémoire.
    # Les colonnes produites par Qwen sont créées séparément.
    donnees = tableau.copy(deep=False).reset_index(drop=True)
    donnees["signature_corpus"] = signature
    donnees["cle_configuration"] = cle_configuration
    donnees["statut_codage"] = "non_traite"
    for champ in CHAMPS_BOOLEENS:
        donnees[champ] = pd.Series(
            [pd.NA] * len(donnees), index=donnees.index, dtype="boolean"
        )
    for champ in (
        "acteur_cible", "indice_textuel", "justification",
        "erreur_codage", "reponse_qwen", "mode_analyse",
        "these_retenue", "these_intitule",
        "theme_retenu", "theme_intitule",
    ):
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
    autoriser_ancien_format: bool = False,
) -> pd.DataFrame:
    """Restaurer sans mélanger les corpus et les prompts différents."""
    colonnes_indispensables = (
        "numero_document", "signature_corpus", "texte", "statut_codage"
    )
    if any(col not in anciens.columns for col in colonnes_indispensables):
        raise ValueError("Colonnes de reprise incomplètes.")
    if (
        len(anciens) != len(donnees)
        or anciens["signature_corpus"].nunique() != 1
        or anciens["signature_corpus"].iloc[0] != signature
        or not anciens["numero_document"].equals(donnees["numero_document"])
        or not anciens["texte"].fillna("").equals(donnees["texte"].fillna(""))
    ):
        raise ValueError("Le CSV de reprise ne correspond pas au corpus actuel.")

    if "cle_configuration" in anciens.columns:
        if (
            anciens["cle_configuration"].nunique() != 1
            or anciens["cle_configuration"].iloc[0] != cle_configuration
        ):
            raise ValueError(
                "Le prompt, le mode ou les paramètres diffèrent de ceux de la reprise."
            )
    elif not autoriser_ancien_format:
        raise ValueError(
            "Cet ancien CSV n'enregistre pas le prompt utilisé. "
            "Reprise autorisée seulement avec la grille structurée historique."
        )

    restauration = donnees.copy()
    champs_restaurables = (
        "statut_codage", *CHAMPS_BOOLEENS, *CHAMPS_THEMES,
        *("manuel_" + theme for theme in CHAMPS_THEMES),
        "indice_denonciation", "indice_indignation", "indice_persecuteur",
        "acteur_designe", "incertitude_interpretation",
        "validation_humaine", "note_humaine",
        "nombre_segments", "segments_traites",
        "acteur_cible", "indice_textuel", "justification",
        "erreur_codage", "texte_tronque", "contexte_tronque",
        "reponse_qwen", "mode_analyse",
        "these_retenue", "these_intitule",
        "theme_retenu", "theme_intitule",
    )
    for champ in champs_restaurables:
        if champ in anciens.columns:
            valeurs = anciens[champ].reset_index(drop=True)
            if champ in (
                *CHAMPS_BOOLEENS, *CHAMPS_THEMES,
                *("manuel_" + theme for theme in CHAMPS_THEMES),
                "incertitude_interpretation",
                "texte_tronque", "contexte_tronque",
            ):
                def convertir_booleen(valeur):
                    if pd.isna(valeur) or str(valeur).strip() == "":
                        return pd.NA
                    return est_vrai(valeur)
                restauration[champ] = pd.Series(
                    [convertir_booleen(v) for v in valeurs], dtype="boolean"
                )
            elif champ in (
                "acteur_cible", "indice_textuel", "justification",
                "erreur_codage", "reponse_qwen", "mode_analyse",
                "these_retenue", "these_intitule",
                "theme_retenu", "theme_intitule",
                "indice_denonciation", "indice_indignation", "indice_persecuteur",
                "acteur_designe", "validation_humaine", "note_humaine",
            ):
                restauration[champ] = valeurs.fillna("").astype(str)
            else:
                restauration[champ] = valeurs
    return restauration


def lancer_analyse(
    donnees: pd.DataFrame,
    indices: list[int],
    mode_analyse: str,
    prompt: str,
    contexte_general: str,
    contexte_variables: list[str],
    temperature: float,
    theses: list[dict[str, str]] | None = None,
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
            ligne = donnees.loc[indice]
            details = "\n".join(
                f"{colonne}: {ligne[colonne]}"
                for colonne in contexte_variables
                if pd.notna(ligne.get(colonne))
            )
            contexte = (contexte_general + "\n" + details).strip()
            try:
                if mode_analyse == "matrice":
                    resultat = coder_multithemes(
                        texte=str(ligne["texte"]),
                        contexte=contexte,
                        temperature=temperature,
                        session=session,
                        consigne=prompt,
                    )
                else:
                    resultat = coder_commentaire(
                        texte=str(ligne["texte"]),
                        contexte=contexte,
                        temperature=temperature,
                        session=session,
                        consigne=prompt,
                        mode_analyse=mode_analyse,
                        theses=theses,
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
                        f"Modèle sollicité : {MODELE} ; "
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
                text=f"Commentaires examinés : {position} / {nombre_total}",
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
st.write(
    f"**Modèle sollicité par l'application : `{MODELE}`** "
    f"(contexte : {CONTEXTE_MAXIMUM} tokens)."
)
st.caption(
    "Ce nom provient de la configuration effective du conteneur Streamlit. "
    "Il est transmis à Ollama lors de chaque demande d'analyse. "
    "Le modèle traite chaque commentaire séparément et conserve le texte original."
)
mode_affichage = st.radio(
    "Type d'analyse",
    [
        "Analyse libre avec mon prompt",
        "Codage structuré sur la violence",
        "Classification en trois thèmes : discours sur la violence",
    "Matrice multithématique : comparer les sources textuelles",
    ],
    horizontal=True,
    index=3,
    help=(
        "Le mode libre conserve votre prompt. Le mode structuré conserve "
        "les catégories historiques. Le mode trois thèmes propose une grille "
        "commune à tout le corpus avant le classement des commentaires."
    ),
)
mode_analyse = (
    "libre" if mode_affichage.startswith("Analyse libre")
    else "theses" if mode_affichage.startswith("Classification")
    else "matrice" if mode_affichage.startswith("Matrice")
    else "structure"
)
prompt = st.text_area(
    "Prompt à transmettre à Qwen pour chaque commentaire",
    value=(
        PROMPT_LIBRE_DEFAUT if mode_analyse == "libre"
        else PROMPT_THESES_DEFAUT if mode_analyse == "theses"
        else PROMPT_MATRICE_DEFAUT if mode_analyse == "matrice"
        else PROMPT_VIOLENCE_DEFAUT
    ),
    key=f"qwen_prompt_{mode_analyse}",
    height=230,
    help=(
        "Modifiez librement les instructions. Dans le mode trois thèmes, "
        "le prompt sert à proposer la grille ; les trois définitions " 
        "validées servent ensuite au classement des commentaires. "
        "Les deux autres modes conservent leur fonctionnement."
    ),
)
if mode_analyse == "theses":
    st.info(
        "La grille distingue la dénonciation, l'indignation et la désignation "
        "d'un persécuteur face à la violence. Chaque commentaire reçoit "
        "un thème principal ou « indéterminé ». Les titres et définitions "
        "restent modifiables avant la classification."
    )
if mode_analyse == "matrice":
    st.info(
        "Codage non exclusif : chaque texte peut relever de la dénonciation, "
        "de l'indignation et de la désignation d'un persécuteur. "
        "Associez les colonnes IA TikTok, publication, voice-to-text et "
        "commentaires à leur source ; la comparaison se fait par ID vidéo. "
        "Les textes longs sont analysés par segments sans être éliminés. "
        "Les annotations peuvent être validées ou corrigées manuellement."
    )
if mode_analyse == "structure":
    st.info(
        "Le mode structuré conserve les colonnes historiques "
        "violence_evoquee, violence_denoncee, violence_justifiee, "
        "violence_minimisee et interpretation_indeterminee. "
        "Pour toute autre grille de lecture, choisissez Analyse libre."
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
    "Dans les modes historiques, sélectionnez la colonne de commentaires. "
    "Dans la matrice, associez les colonnes de textes à leur provenance ; "
    "une ligne CSV peut produire plusieurs unités textuelles distinctes. "
    "La colonne auteur reste facultative."
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
        if mode_analyse == "matrice":
            noms_suggeres = {
                "texte_ia": (
                    "texte_ia", "texte_genere_ia", "statut_resume_ia",
                    "resume_ia", "description_ia", "ai_generated_text",
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
                    "texte", "comment", "message", "content",
                ),
            }
            st.caption(
                f"Sources textuelles et identifiant vidéo — {fichier.name}. "
                "Choisissez « Aucune colonne » pour une source absente."
            )
            colonnes_sources = {}
            colonnes_g = st.columns(2)
            for i_source, source in enumerate(SOURCES_TEXTE):
                with colonnes_g[i_source % 2]:
                    defaut = proposer_colonne(
                        colonnes_csv, noms_suggeres[source]
                    )
                    choix_colonne = st.selectbox(
                        LIBELLES_SOURCES[source] + f" — {fichier.name}",
                        options=[None] + colonnes_csv,
                        index=(
                            0 if defaut is None
                            else colonnes_csv.index(defaut) + 1
                        ),
                        format_func=lambda valeur: (
                            "Aucune colonne" if valeur is None else valeur
                        ),
                        key=f"qwen_source_{source}_{cle_fichier}",
                    )
                    if choix_colonne is not None:
                        colonnes_sources[source] = choix_colonne
            if not colonnes_sources:
                st.warning(
                    "Sélectionnez au moins une colonne textuelle pour la matrice."
                )
                st.stop()
            if len(set(colonnes_sources.values())) != len(colonnes_sources):
                st.error(
                    "La même colonne ne peut pas être affectée à deux sources."
                )
                st.stop()
            colonnes_gauche, colonnes_droite = st.columns(2)
            with colonnes_gauche:
                identifiant_propose = proposer_colonne(
                    colonnes_csv,
                    ("id_video", "video_id", "idvideo", "videoid",
                     "aweme_id", "id_publication", "id"),
                )
                colonne_id_video = st.selectbox(
                    f"Identifiant vidéo pour l'appariement — {fichier.name}",
                    options=[None] + colonnes_csv,
                    index=(
                        0 if identifiant_propose is None else
                        colonnes_csv.index(identifiant_propose) + 1
                    ),
                    format_func=lambda valeur: (
                        "Aucune colonne : pas de comparaison par vidéo"
                        if valeur is None else valeur
                    ),
                    key=f"qwen_id_video_{cle_fichier}",
                )
            with colonnes_droite:
                auteur_propose = proposer_colonne(
                    colonnes_csv,
                    ("nom_affiche", "display_name", "auteur", "author",
                     "utilisateur", "username", "profil"),
                )
                auteur_choisi = st.selectbox(
                    f"Colonne auteur (facultative) — {fichier.name}",
                    options=[None] + colonnes_csv,
                    index=(
                        0 if auteur_propose is None else
                        colonnes_csv.index(auteur_propose) + 1
                    ),
                    format_func=lambda valeur: (
                        "Aucune colonne auteur" if valeur is None else valeur
                    ),
                    key=f"qwen_auteur_csv_{cle_fichier}",
                )
            correspondances_csv.append({
                "numero_fichier": numero_fichier,
                "nom_fichier": fichier.name,
                "colonne_texte": None,
                "colonne_auteur": auteur_choisi,
                "colonne_id_video": colonne_id_video,
                "colonnes_sources": colonnes_sources,
            })
        else:
            colonne_gauche, colonne_droite = st.columns(2)
            with colonne_gauche:
                texte_choisi = st.selectbox(
                    f"Colonne contenant les commentaires — {fichier.name}",
                    options=colonnes_csv,
                    index=colonnes_csv.index(defaut_texte),
                    key=f"qwen_texte_csv_{cle_fichier}",
                )
            with colonne_droite:
                choix_auteurs = [None] + [
                    nom for nom in colonnes_csv if nom != texte_choisi
                ]
                auteur_propose = proposer_colonne(
                    colonnes_csv,
                    ("nom_affiche", "display_name", "auteur", "author",
                     "utilisateur", "username", "profil"),
                )
                if auteur_propose not in choix_auteurs:
                    auteur_propose = None
                auteur_choisi = st.selectbox(
                    f"Colonne auteur (facultative) — {fichier.name}",
                    options=choix_auteurs,
                    index=choix_auteurs.index(auteur_propose),
                    format_func=lambda valeur: (
                        "Aucune colonne auteur" if valeur is None else valeur
                    ),
                    key=f"qwen_auteur_csv_{cle_fichier}",
                )
            correspondances_csv.append({
                "numero_fichier": numero_fichier,
                "nom_fichier": fichier.name,
                "colonne_texte": texte_choisi,
                "colonne_auteur": auteur_choisi,
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
selection_personnalisee = any(
    choix["colonne_texte"] != "texte"
    or choix["colonne_auteur"] != "nom_affiche"
    for choix in correspondances_csv
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
    f"commentaires non vides : **{int(tableau['texte'].str.strip().ne('').sum())}**."
)
with st.expander("Aperçu des textes et variables", expanded=False):
    st.dataframe(tableau.head(30), use_container_width=True, hide_index=True)

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

theses_validees: list[dict[str, str]] | None = None
source_grille = ""
if mode_analyse == "theses":
    st.subheader("Définir les trois thèmes")
    st.caption(
        "Les trois thèmes demandés sont préremplis. Cliquez sur "
        "« Affiner les définitions avec Qwen » pour proposer des précisions "
        "à partir du corpus sans remplacer les intitulés. "
        "Vous pouvez ensuite modifier les titres et les définitions."
    )
    identifiant_grille = hashlib.sha256(
        (signature + prompt).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("qwen_identifiant_grille") != identifiant_grille:
        st.session_state["qwen_identifiant_grille"] = identifiant_grille
        st.session_state["qwen_source_grille"] = "Grille initiale modifiable"
        for indice, these in enumerate(THESES_INITIALES, start=1):
            st.session_state[f"qwen_theme_titre_{indice}"] = these["titre"]
            st.session_state[f"qwen_theme_definition_{indice}"] = these["definition"]
    if st.button("Affiner les définitions avec Qwen"):
        try:
            grille_courante = valider_theses([
                {
                    "titre": st.session_state[f"qwen_theme_titre_{indice}"],
                    "definition": st.session_state[f"qwen_theme_definition_{indice}"],
                }
                for indice in range(1, 4)
            ])
            propositions = proposer_trois_theses(
                tableau["texte"].fillna("").astype(str).tolist(),
                consigne=prompt,
                themes_imposes=grille_courante,
            )
            for indice, theme in enumerate(propositions, start=1):
                st.session_state[f"qwen_theme_titre_{indice}"] = theme["titre"]
                st.session_state[f"qwen_theme_definition_{indice}"] = theme["definition"]
            st.session_state["qwen_source_grille"] = (
                "Définitions affinées par Qwen à partir d'un échantillon"
            )
            st.rerun()
        except (requests.RequestException, ValueError, json.JSONDecodeError) as erreur:
            st.error(
                f"Qwen n'a pas pu proposer trois thèmes avec {MODELE} : "
                f"{type(erreur).__name__} : {erreur}"
            )
    themes_modifiables = []
    st.write(
        "**Thèmes sélectionnés :** "
        + " ; ".join(
            st.session_state[f"qwen_theme_titre_{indice}"]
            for indice in range(1, 4)
        )
    )
    with st.expander("Modifier les intitulés et les définitions", expanded=False):
        for indice in range(1, 4):
            st.text_input(
                f"Thème {indice} — intitulé",
                key=f"qwen_theme_titre_{indice}",
            )
            st.text_area(
                f"Thème {indice} — définition",
                key=f"qwen_theme_definition_{indice}",
                height=80,
            )
    # Toujours recueillir les trois valeurs, même lorsque le panneau est fermé.
    for indice in range(1, 4):
        themes_modifiables.append({
            "titre": st.session_state[f"qwen_theme_titre_{indice}"],
            "definition": st.session_state[f"qwen_theme_definition_{indice}"],
        })
    source_grille = st.session_state.get(
        "qwen_source_grille", "Grille initiale modifiable"
    )
    st.caption(
        f"Origine de la grille : {source_grille}. "
        "Les définitions proposées par Qwen ne constituent pas une validation "
        "scientifique. La classification représente le discours des auteurs, "
        "sans établir la responsabilité réelle d'un persécuteur."
    )
    try:
        theses_validees = valider_theses(themes_modifiables)
    except ValueError as erreur:
        st.error(f"Grille invalide : {erreur}")

configuration = {
    "modele": MODELE,
    "mode_analyse": mode_analyse,
    "prompt": prompt,
    "temperature": float(temperature),
    "contexte_general": contexte_general,
    "contexte_variables": contexte_variables,
    "signature_corpus": signature,
}
if selection_personnalisee:
    configuration["correspondances_csv"] = correspondances_csv
if mode_analyse == "theses":
    configuration["theses"] = theses_validees
    configuration["source_grille"] = source_grille

cle = hashlib.sha256(
    json.dumps(configuration, sort_keys=True, ensure_ascii=False)
    .encode("utf-8")
).hexdigest()

if st.session_state.get("qwen_cle") != cle:
    st.session_state["qwen_cle"] = cle
    donnees_initiales = initialiser_tableau(tableau, signature, cle)
    if mode_analyse == "matrice":
        donnees_initiales = initialiser_annotations_matrice(donnees_initiales)
    st.session_state["qwen_donnees"] = donnees_initiales
    st.session_state["qwen_message"] = ""

checkpoint = st.file_uploader(
    "Reprendre une analyse : importer le CSV de résultats précédent (facultatif)",
    type=["csv"], key="checkpoint",
)
if checkpoint is not None and st.button("Restaurer les résultats enregistrés"):
    try:
        anciens = pd.read_csv(
            io.BytesIO(checkpoint.getvalue()),
            sep=";", encoding="utf-8-sig",
            dtype={"signature_corpus": str, "cle_configuration": str, "texte": str},
        )
        compatible_ancien = (
            mode_analyse == "structure" and prompt == PROMPT_VIOLENCE_DEFAUT
        )
        st.session_state["qwen_donnees"] = restaurer_checkpoint(
            st.session_state["qwen_donnees"],
            anciens,
            signature,
            cle,
            autoriser_ancien_format=compatible_ancien,
        )
        st.success("Résultats restaurés. Vous pouvez poursuivre les analyses restantes.")
        if "cle_configuration" not in anciens.columns:
            st.warning(
                "Cet ancien CSV ne contenait pas la consigne du modèle. "
                "La compatibilité exacte du prompt historique ne peut pas être vérifiée."
            )
    except (ValueError, pd.errors.ParserError) as erreur:
        st.error(f"Reprise impossible : {erreur}")

donnees = st.session_state["qwen_donnees"]
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
    "Le bouton de test traite un seul commentaire. Le bouton principal "
    "analyse ensuite les commentaires restants sans lots manuels."
)
etat_commandes = evaluer_commandes_analyse(
    nombre_restants=len(reste),
    nombre_erreurs=len(erreurs),
    prompt=prompt,
    mode_analyse=mode_analyse,
    grille_valide=(mode_analyse != "theses" or theses_validees is not None),
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
        f"{len(reste)} commentaire(s) prêt(s) pour l'analyse avec {MODELE}. "
        "La grille et le prompt sont renseignés."
    )
colonne_test, colonne_analyser, colonne_erreurs = st.columns([1, 2, 1])
tester = colonne_test.button(
    "Tester sur un commentaire",
    disabled=not etat_commandes["tester"],
)
lancer = colonne_analyser.button(
    "Analyser tous les commentaires restants",
    type="primary",
    disabled=not etat_commandes["lancer"],
)
relancer = colonne_erreurs.button(
    "Réessayer les commentaires en erreur",
    disabled=not etat_commandes["relancer"],
)
if tester or lancer or relancer:
    indices = reste[:1] if tester else (reste if lancer else erreurs)
    termines, nombre_erreurs, interrompu = lancer_analyse(
        donnees, indices, mode_analyse, prompt,
        contexte_general, contexte_variables, float(temperature),
        theses=theses_validees,
    )
    st.session_state["qwen_donnees"] = donnees
    if interrompu:
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
            "Utilisez « Tester sur un commentaire » pour vérifier "
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
    if mode_analyse == "structure":
        colonnes_principales += list(CHAMPS_BOOLEENS) + ["acteur_cible"]
    elif mode_analyse == "matrice":
        colonnes_principales = [
            "numero_document", "id_video", "source_texte", "texte",
            *CHAMPS_THEMES, "acteur_designe",
            "incertitude_interpretation", "statut_codage",
        ]
    elif mode_analyse == "theses":
        colonnes_principales += [
            "theme_retenu", "theme_intitule", "indice_textuel", "justification"
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
            "theme_retenu": st.column_config.TextColumn("Code du thème"),
            "theme_intitule": st.column_config.TextColumn("Thème retenu"),
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
                    "statut_codage", "erreur_codage",
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
    st.dataframe(vue.head(1000), hide_index=True, use_container_width=True)
    if len(vue) > 1000:
        st.caption(
            "Aperçu limité à 1 000 lignes. Le ZIP et le CSV "
            "contiennent toutes les lignes."
        )


if mode_analyse == "matrice":
    st.subheader("Matrice des annotations par texte et par thème")
    matrice_affichage = construire_matrice(donnees)
    colonnes_matrice = [
        "numero_document", "id_video", "source_texte", "texte",
        "statut_codage", *("final_" + theme for theme in CHAMPS_THEMES),
        "incertitude_interpretation", "acteur_designe",
        "validation_humaine",
    ]
    st.dataframe(
        matrice_affichage[colonnes_matrice].head(1000),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "Une ligne représente un texte ou un commentaire. Les trois colonnes "
        "thématiques sont indépendantes. Les valeurs manquantes correspondent "
        "aux textes non analysés, et non à une absence de thème. "
        "Le ZIP contient la matrice intégrale."
    )

    st.subheader("Fréquences des thèmes selon la source textuelle")
    bilan_sources = construire_bilan_sources(matrice_affichage)
    st.dataframe(
        bilan_sources, use_container_width=True, hide_index=True,
    )

    st.subheader("Comparaison des sources appariées par identifiant vidéo")
    comparaison = comparer_sources_par_video(matrice_affichage)
    if comparaison.empty:
        st.info(
            "Aucune vidéo appariée disponible. Choisissez la colonne ID vidéo "
            "dans le CSV pour comparer textes IA, auteurs et voix transcrites."
        )
    else:
        st.dataframe(
            comparaison.head(1000), use_container_width=True, hide_index=True
        )
        st.caption(
            "Une absence de source est notée non_disponible, jamais non. "
            "Les discordances IA-auteur et IA-voix ne sont calculées que "
            "lorsque les deux textes ont reçu une annotation exploitable."
        )

    st.subheader("Validation et correction manuelles des annotations")
    lignes_verifiables = donnees.loc[donnees["statut_codage"].eq("ok")]
    if lignes_verifiables.empty:
        st.info("Analysez au moins un texte pour activer la validation humaine.")
    else:
        identifiants_manuels = lignes_verifiables["numero_document"].astype(int).tolist()
        numero_validation = st.selectbox(
            "Texte à valider ou corriger",
            identifiants_manuels,
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
            "Texte original pour validation",
            value=str(ligne_validation["texte"]),
            height=180, disabled=True,
        )
        with st.form(
            key=f"qwen_form_validation_{numero_validation}",
            clear_on_submit=False,
        ):
            corrections = {}
            for theme in CHAMPS_THEMES:
                actuel = ligne_validation["manuel_" + theme]
                if pd.isna(actuel):
                    actuel = ligne_validation[theme]
                corrections[theme] = st.checkbox(
                    LIBELLES_THEMES[theme],
                    value=bool(actuel) if pd.notna(actuel) else False,
                )
            note_validation = st.text_area(
                "Observation du chercheur",
                value=str(ligne_validation["note_humaine"]),
                height=80,
            )
            enregistrer_validation = st.form_submit_button(
                "Enregistrer la validation ou la correction"
            )
        if enregistrer_validation:
            indice_validation = donnees.index[
                donnees["numero_document"].eq(numero_validation)
            ][0]
            correction_effective = any(
                bool(corrections[theme]) != bool(
                    donnees.at[indice_validation, theme]
                )
                for theme in CHAMPS_THEMES
            )
            for theme in CHAMPS_THEMES:
                donnees.at[
                    indice_validation, "manuel_" + theme
                ] = corrections[theme]
            donnees.at[indice_validation, "validation_humaine"] = (
                "corrige" if correction_effective else "valide"
            )
            donnees.at[indice_validation, "note_humaine"] = note_validation
            st.session_state["qwen_donnees"] = donnees
            st.success("Annotation humaine enregistrée dans la matrice.")
            st.rerun()

avec_resultat = donnees.loc[donnees["statut_codage"].eq("ok")]
if mode_analyse == "theses" and theses_validees is not None:
    st.subheader("Répartition des commentaires dans les trois thèmes")
    frequences_themes = avec_resultat["theme_retenu"].value_counts()
    repartition = pd.DataFrame([
        {
            "Thème": theme["titre"],
            "Code": f"theme_{indice}",
            "Commentaires": int(frequences_themes.get(f"theme_{indice}", 0)),
            "Définition": theme["definition"],
        }
        for indice, theme in enumerate(theses_validees, start=1)
    ] + [{
        "Thème": "Indéterminé / hors des trois thèmes",
        "Code": "indetermine",
        "Commentaires": int(frequences_themes.get("indetermine", 0)),
        "Définition": "Aucun thème suffisamment étayé par ce commentaire",
    }])
    st.dataframe(repartition, hide_index=True, use_container_width=True)
    if not avec_resultat.empty:
        st.bar_chart(
            repartition.set_index("Thème")["Commentaires"],
            x_label="Thème",
            y_label="Commentaires classés",
        )
if mode_analyse == "structure" and not avec_resultat.empty:
    frequences = pd.Series({
        champ: int(avec_resultat[champ].fillna(False).sum())
        for champ in CHAMPS_BOOLEENS
    })
    st.bar_chart(frequences, x_label="Catégorie", y_label="Commentaires codés")
    variables_disponibles = [
        col for col in donnees if col.startswith("variable_")
    ]
    if variables_disponibles:
        variable = st.selectbox(
            "Croiser un codage avec une variable du corpus",
            variables_disponibles,
        )
        categorie = st.selectbox(
            "Catégorie à croiser", list(CHAMPS_BOOLEENS)
        )
        st.dataframe(
            pd.crosstab(
                avec_resultat[variable].fillna("absent"),
                avec_resultat[categorie].astype(str),
            ),
            use_container_width=True,
        )

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
    return exporter_csv(donnees)


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
