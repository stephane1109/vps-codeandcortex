"""Construction des unités textuelles et de la matrice thématique comparative."""
from __future__ import annotations

import csv
from collections import defaultdict

import pandas as pd

from codage_multithemes import CHAMPS_THEMES
from lecture_commentaires import identifiant_auteur, ouvrir_lecteur_csv
from lecture_iramuteq import Document

SOURCES_TEXTE = (
    "texte_ia", "texte_auteur", "voice_to_text", "commentaire",
)

LIBELLES_SOURCES = {
    "texte_ia": "Texte généré par TikTok",
    "texte_auteur": "Publication de l'auteur",
    "voice_to_text": "Parole transcrite de la vidéo",
    "commentaire": "Commentaire",
    "source_inconnue": "Source non renseignée",
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
        source not in SOURCES_TEXTE or col not in colonnes
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


def initialiser_annotations_matrice(tableau: pd.DataFrame) -> pd.DataFrame:
    """Ajouter les résultats sans remplacer les annotations historiques."""
    for theme in CHAMPS_THEMES:
        tableau[theme] = pd.Series(
            [pd.NA] * len(tableau), index=tableau.index, dtype="boolean",
        )
        tableau["manuel_" + theme] = pd.Series(
            [pd.NA] * len(tableau), index=tableau.index, dtype="boolean",
        )
    for champ in (
        "indice_denonciation", "indice_indignation", "indice_persecuteur",
        "acteur_designe", "validation_humaine", "note_humaine",
    ):
        tableau[champ] = ""
    tableau["incertitude_interpretation"] = pd.Series(
        [pd.NA] * len(tableau), index=tableau.index, dtype="boolean"
    )
    tableau["nombre_segments"] = 0
    tableau["segments_traites"] = 0
    return tableau


def construire_matrice(tableau: pd.DataFrame) -> pd.DataFrame:
    """Construire la matrice unitaire, avec valeurs finales corrigées."""
    colonnes = [
        "numero_document", "id_video", "source_texte", "fichier_source",
        "ligne_csv", "nom_affiche", "texte", "statut_codage",
        *CHAMPS_THEMES,
        "indice_denonciation", "indice_indignation", "indice_persecuteur",
        "acteur_designe", "incertitude_interpretation",
        "validation_humaine", "note_humaine",
        "nombre_segments", "segments_traites",
    ]
    donnees = tableau.reindex(columns=colonnes).copy()
    for theme in CHAMPS_THEMES:
        manuel = "manuel_" + theme
        valeurs = tableau[theme].copy()
        mask = tableau[manuel].notna()
        valeurs.loc[mask] = tableau.loc[mask, manuel]
        donnees["final_" + theme] = valeurs.astype("boolean")
        donnees[manuel] = tableau[manuel].copy()
    return donnees


def construire_bilan_sources(tableau: pd.DataFrame) -> pd.DataFrame:
    """Compter les annotations positives et négatives par provenance."""
    valide = tableau.loc[tableau["statut_codage"].eq("ok")]
    lignes: list[dict[str, object]] = []
    for source, groupe in valide.groupby("source_texte", dropna=False):
        for theme in CHAMPS_THEMES:
            valeurs = groupe["final_" + theme]
            lignes.append({
                "source_texte": source,
                "theme": LIBELLES_THEMES[theme],
                "effectif_textes": len(groupe),
                "presence": int(valeurs.eq(True).sum()),
                "absence": int(valeurs.eq(False).sum()),
                "indetermine": int(valeurs.isna().sum()),
            })
    return pd.DataFrame(lignes, columns=[
        "source_texte", "theme", "effectif_textes",
        "presence", "absence", "indetermine",
    ])


def comparer_sources_par_video(tableau: pd.DataFrame) -> pd.DataFrame:
    """Comparer les sources appariées par vidéo sans confondre absence et manque."""
    valides = tableau.loc[
        tableau["statut_codage"].eq("ok")
        & tableau["id_video"].fillna("").astype(str).str.strip().ne("")
    ]
    groupes: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for ligne in valides.to_dict("records"):
        groupes[str(ligne["id_video"])][str(ligne["source_texte"])].append(ligne)
    resultats: list[dict[str, object]] = []
    for id_video, sources in groupes.items():
        for theme in CHAMPS_THEMES:
            enregistrement: dict[str, object] = {
                "id_video": id_video,
                "theme": LIBELLES_THEMES[theme],
            }
            for source in SOURCES_TEXTE:
                lignes = sources.get(source, [])
                valeurs = [ligne["final_" + theme] for ligne in lignes]
                if not lignes:
                    code = "non_disponible"
                elif any(
                    pd.notna(valeur) and bool(valeur) for valeur in valeurs
                ):
                    code = "oui"
                elif all(
                    pd.notna(valeur) and not bool(valeur)
                    for valeur in valeurs
                ):
                    code = "non"
                else:
                    code = "indetermine"
                enregistrement[source] = code
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
        "id_video", "theme", *SOURCES_TEXTE,
        "discordance_ia_auteur", "discordance_ia_voix",
    ])


def exporter_iramuteq_matrice(
    documents: list[Document], tableau: pd.DataFrame
) -> bytes:
    """Ajouter les indicateurs multiples à chaque en-tête sans toucher au texte."""
    annotations = {
        int(ligne["numero_document"]): ligne
        for ligne in tableau.to_dict("records")
    }
    textes = []
    for document in documents:
        ligne = annotations.get(document.numero)
        suffixes: list[str] = []
        if ligne and ligne.get("statut_codage") == "ok":
            for theme in CHAMPS_THEMES:
                champ = "final_" + theme
                valeur = ligne.get(champ, pd.NA)
                if pd.notna(valeur):
                    suffixes.append(
                        "*" + theme + "_" + ("oui" if bool(valeur) else "non")
                    )
            source = str(ligne.get("source_texte") or "")
            if (
                source in SOURCES_TEXTE
                and "source_texte_" + source not in document.variables
            ):
                suffixes.append("*source_texte_" + source)
        texte = document.entete + (
            " " + " ".join(suffixes) if suffixes else ""
        ) + "\n" + document.texte
        textes.append(texte)
    return ("\n\n".join(textes) + "\n").encode("utf-8")
