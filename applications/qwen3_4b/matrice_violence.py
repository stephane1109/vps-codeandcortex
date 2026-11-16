"""Construction des unités textuelles et de la matrice thématique comparative."""
from __future__ import annotations

import csv
from collections import defaultdict

import pandas as pd

from codage_multithemes import codes_themes, valider_themes
from lecture_commentaires import identifiant_auteur, ouvrir_lecteur_csv
from lecture_iramuteq import Document

SOURCES_TEXTE = (
    "texte_ia", "texte_auteur", "voice_to_text", "commentaire",
)
SOURCES_IMPORT = (*SOURCES_TEXTE, "texte_libre")

LIBELLES_SOURCES = {
    "texte_ia": "Texte généré par TikTok",
    "texte_auteur": "Publication de l'auteur",
    "voice_to_text": "Parole transcrite de la vidéo",
    "commentaire": "Commentaire",
    "source_inconnue": "Source non renseignée",
    "texte_libre": "Texte ou commentaire (source libre)",
}

LIBELLES_THEMES = {
    "theme_denonciation": "Dénonciation",
    "theme_indignation": "Indignation",
    "theme_persecuteur": "Persécuteur désigné",
}


def analyser_sources_csv(
    contenu: bytes | str,
    colonnes_sources: dict[str, str],
    colonne_id_video: str | None = None,
    colonne_auteur: str | None = None,
    numero_depart: int = 0,
) -> tuple[list[Document], dict[int, dict[str, str]]]:
    """Créer une unité par source non vide, en conservant la ligne d'origine."""
    lecteur, colonnes = ouvrir_lecteur_csv(contenu)
    if not colonnes_sources or any(
        source not in SOURCES_IMPORT or col not in colonnes
        for source, col in colonnes_sources.items()
    ):
        raise ValueError("Sélection des colonnes textuelles invalide.")
    if len(set(colonnes_sources.values())) != len(colonnes_sources):
        raise ValueError("Une colonne CSV ne doit correspondre qu'à une source.")
    if colonne_id_video is not None and colonne_id_video not in colonnes:
        raise ValueError("La colonne identifiant vidéo est absente.")
    if colonne_auteur is not None and colonne_auteur not in colonnes:
        raise ValueError("La colonne auteur est absente.")

    documents: list[Document] = []
    metadonnees: dict[int, dict[str, str]] = {}
    colonnes_meta = [
        col for col in colonnes
        if col not in colonnes_sources.values()
        and col not in (colonne_id_video, colonne_auteur)
    ]
    try:
        for position, ligne in enumerate(lecteur, start=1):
            if None in ligne:
                raise ValueError(f"Ligne CSV {position+1} : champs en excès.")
            id_video = str(ligne.get(colonne_id_video) or "") if colonne_id_video else ""
            auteur = str(ligne.get(colonne_auteur) or "") if colonne_auteur else ""
            for source, colonne in colonnes_sources.items():
                texte = str(ligne.get(colonne) or "")
                if not texte.strip():
                    continue
                numero = numero_depart + len(documents) + 1
                tokens = (
                    "source_commentaires_csv",
                    f"ligne_{position + 1}",
                    f"source_texte_{source}",
                    f"auteur_{identifiant_auteur(auteur)}",
                )
                entete = "**** " + " ".join("*" + token for token in tokens)
                documents.append(Document(
                    numero=numero, entete=entete,
                    variables=tokens, texte=texte,
                ))
                meta = {
                    "nom_affiche": auteur,
                    "id_video": id_video,
                    "source_texte": source,
                    "ligne_csv": str(position + 1),
                    "colonne_texte_source": colonne,
                    "colonne_auteur_source": colonne_auteur or "",
                }
                # Les colonnes de texte non sélectionnées ne sont pas
                # dupliquées pour chaque annotation du même document.
                for col in colonnes_meta:
                    meta["csv_" + col] = str(ligne.get(col) or "")
                metadonnees[numero] = meta
    except csv.Error as erreur:
        raise ValueError(f"Erreur de lecture du CSV : {erreur}") from erreur
    if not documents:
        raise ValueError("Les colonnes sélectionnées ne contiennent aucun texte.")
    return documents, metadonnees


def extraire_source_iramuteq(document: Document) -> tuple[str, str]:
    """Rechercher la source et l'ID vidéo dans les variables étoilées."""
    marqueurs = set(document.variables)
    source = "source_inconnue"
    if "texte_auteur" in marqueurs or "source_original" in marqueurs:
        source = "texte_auteur"
    if "texte_ia" in marqueurs or "source_ia" in marqueurs:
        source = "texte_ia"
    if "texte_voicetotext" in marqueurs or "texte_voice_to_text" in marqueurs:
        source = "voice_to_text"
    if "texte_commentaire" in marqueurs or "source_commentaire" in marqueurs:
        source = "commentaire"
    id_video = next(
        (token[3:] for token in document.variables if token.startswith("id_")),
        "",
    )
    return source, id_video


def initialiser_annotations_matrice(
    tableau: pd.DataFrame,
    themes: list[dict[str, str]],
) -> pd.DataFrame:
    """Préparer les colonnes des thèmes du chercheur, sans grille imposée."""
    for code in codes_themes(themes):
        tableau[code] = pd.Series(
            [pd.NA] * len(tableau), index=tableau.index, dtype="boolean"
        )
        tableau["manuel_" + code] = pd.Series(
            [pd.NA] * len(tableau), index=tableau.index, dtype="boolean"
        )
        tableau["indice_" + code] = ""
    for champ in ("validation_humaine", "note_humaine", "justification"):
        tableau[champ] = ""
    tableau["incertitude_interpretation"] = pd.Series(
        [pd.NA] * len(tableau), index=tableau.index, dtype="boolean"
    )
    tableau["nombre_segments"] = 0
    tableau["segments_traites"] = 0
    return tableau


def construire_matrice(
    tableau: pd.DataFrame,
    themes: list[dict[str, str]],
) -> pd.DataFrame:
    """Une ligne par unité textuelle et une colonne par thème non exclusif."""
    codes = codes_themes(themes)
    colonnes = [
        "numero_document", "id_video", "source_texte", "fichier_source",
        "ligne_csv", "nom_affiche", "texte", "statut_codage",
        *codes, *("indice_" + code for code in codes),
        "incertitude_interpretation", "justification",
        "validation_humaine", "note_humaine",
        "nombre_segments", "segments_traites",
    ]
    donnees = tableau.reindex(columns=colonnes).copy()
    for code in codes:
        manuel = "manuel_" + code
        valeurs = tableau[code].copy()
        mask = tableau[manuel].notna()
        valeurs.loc[mask] = tableau.loc[mask, manuel]
        donnees["final_" + code] = valeurs.astype("boolean")
        donnees[manuel] = tableau[manuel].copy()
    return donnees


def construire_bilan_sources(
    matrice: pd.DataFrame,
    themes: list[dict[str, str]],
) -> pd.DataFrame:
    """Établir les fréquences des thèmes dans chaque source textuelle."""
    colonnes = [
        "source_texte", "code_theme", "theme", "effectif_textes",
        "presence", "absence", "indetermine",
    ]
    valides = matrice.loc[matrice["statut_codage"].eq("ok")]
    lignes: list[dict[str, object]] = []
    for source, groupe in valides.groupby("source_texte", dropna=False):
        for code, theme in zip(codes_themes(themes), valider_themes(themes)):
            valeurs = groupe["final_" + code]
            lignes.append({
                "source_texte": source,
                "code_theme": code,
                "theme": theme["titre"],
                "effectif_textes": len(groupe),
                "presence": int(valeurs.eq(True).sum()),
                "absence": int(valeurs.eq(False).sum()),
                "indetermine": int(valeurs.isna().sum()),
            })
    return pd.DataFrame(lignes, columns=colonnes)


def comparer_sources_par_video(
    matrice: pd.DataFrame,
    themes: list[dict[str, str]],
) -> pd.DataFrame:
    """Comparer les sources associées à une même vidéo sans inventer d'absences."""
    disponibles = matrice.loc[
        matrice["id_video"].fillna("").astype(str).str.strip().ne("")
    ]
    groupes: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for ligne in disponibles.to_dict("records"):
        groupes[str(ligne["id_video"])][str(ligne["source_texte"])].append(ligne)
    resultats: list[dict[str, object]] = []
    for id_video, sources in groupes.items():
        for code, theme in zip(codes_themes(themes), valider_themes(themes)):
            enregistrement: dict[str, object] = {
                "id_video": id_video,
                "code_theme": code,
                "theme": theme["titre"],
            }
            for source in SOURCES_TEXTE:
                lignes = sources.get(source, [])
                annotees = [
                    ligne for ligne in lignes
                    if ligne["statut_codage"] == "ok"
                ]
                valeurs = [ligne["final_" + code] for ligne in annotees]
                if not lignes:
                    etat = "non_disponible"
                elif not annotees:
                    etat = "non_traite"
                elif any(pd.notna(v) and bool(v) for v in valeurs):
                    etat = "oui"
                elif len(annotees) == len(lignes) and all(
                    pd.notna(v) and not bool(v) for v in valeurs
                ):
                    etat = "non"
                else:
                    etat = "partiel"
                enregistrement[source] = etat
            enregistrement["discordance_ia_auteur"] = (
                enregistrement["texte_ia"] != enregistrement["texte_auteur"]
                if enregistrement["texte_ia"] in ("oui", "non")
                and enregistrement["texte_auteur"] in ("oui", "non")
                else pd.NA
            )
            enregistrement["discordance_ia_voix"] = (
                enregistrement["texte_ia"] != enregistrement["voice_to_text"]
                if enregistrement["texte_ia"] in ("oui", "non")
                and enregistrement["voice_to_text"] in ("oui", "non")
                else pd.NA
            )
            resultats.append(enregistrement)
    return pd.DataFrame(resultats, columns=[
        "id_video", "code_theme", "theme", *SOURCES_TEXTE,
        "discordance_ia_auteur", "discordance_ia_voix",
    ])


def exporter_iramuteq_matrice(
    documents: list[Document],
    matrice: pd.DataFrame,
    themes: list[dict[str, str]],
) -> bytes:
    """Conserver les en-têtes et enrichir les textes de variables thématiques."""
    annotations = {
        int(ligne["numero_document"]): ligne
        for ligne in matrice.to_dict("records")
    }
    contenus: list[str] = []
    for document in documents:
        ligne = annotations.get(document.numero)
        variables: list[str] = []
        if ligne and ligne.get("statut_codage") == "ok":
            for code in codes_themes(themes):
                valeur = ligne.get("final_" + code, pd.NA)
                if pd.notna(valeur):
                    variables.append(
                        f"*{code}_{'oui' if bool(valeur) else 'non'}"
                    )
            source = str(ligne.get("source_texte") or "")
            if (
                source in SOURCES_IMPORT
                and "source_texte_" + source not in document.variables
            ):
                variables.append("*source_texte_" + source)
        entete = document.entete + (
            " " + " ".join(variables) if variables else ""
        )
        contenus.append(entete + "\n" + document.texte)
    return ("\n\n".join(contenus) + "\n").encode("utf-8")
