"""Lecture, contrôle et préparation des tableaux de contingence pour l'AFC."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd


VALEURS_VRAIES = frozenset({"true", "1", "vrai", "oui", "yes"})
MOTIFS_INDETERMINES = re.compile(
    r"ind[eé]termin|indisponible|non[ _-]?[eé]valu|non[ _-]?renseign[eé]|"
    r"^inconnu(?:e)?$|^unknown$|^not[ _-]?available$",
    flags=re.IGNORECASE,
)
INDICATEURS_MEDIAS = {
    "presse_nationale": "Presse nationale",
    "presse_regio_dpt": "Presse régionale",
    "presse_indep": "Presse indépendante",
    "presse_autre": "Autres médias",
}


@dataclass
class PreparationAFC:
    """Stocke le tableau et les effectifs des étapes de préparation."""

    tableau: pd.DataFrame
    effectif_initial: int
    effectif_apres_filtre: int
    effectif_apres_dedoublonnage: int
    effectif_final: int
    effectifs_attendus: pd.DataFrame
    cellules_attendues_faibles: int
    inertie_nulle: bool


def detecter_encodage(contenu: bytes, choix: str = "Automatique") -> str:
    """Recherche un décodage valide en évitant toute substitution silencieuse."""
    correspondances = {
        "UTF-8": "utf-8-sig",
        "Windows-1252": "cp1252",
        "Latin-1": "latin-1",
    }
    if choix != "Automatique":
        if choix not in correspondances:
            raise ValueError("Encodage non reconnu.")
        encodage = correspondances[choix]
        contenu.decode(encodage)
        return encodage
    for encodage in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            contenu.decode(encodage)
            return encodage
        except UnicodeDecodeError:
            continue
    raise ValueError("L'encodage du CSV n'a pas pu être reconnu.")


def detecter_separateur(texte: str) -> str:
    """Détecte le séparateur avec repli sur le premier en-tête."""
    echantillon = texte[:12000]
    try:
        choix = csv.Sniffer().sniff(echantillon, delimiters=";,\t|").delimiter
        return choix
    except csv.Error:
        premiere_ligne = texte.splitlines()[0] if texte.splitlines() else ""
        return max((";", ",", "\t", "|"), key=premiere_ligne.count)


def lire_csv(
    contenu: bytes,
    separateur: str = "Automatique",
    encodage: str = "Automatique",
) -> pd.DataFrame:
    """Importe un CSV sans transformer les identifiants en nombres."""
    if not contenu:
        raise ValueError("Le fichier est vide.")
    codec = detecter_encodage(contenu, encodage)
    texte = contenu.decode(codec)
    separateurs = {"Point-virgule (;)": ";", "Virgule (, )": ",", "Tabulation": "\t", "Barre verticale (|)": "|"}
    sep = detecter_separateur(texte) if separateur == "Automatique" else separateurs.get(separateur)
    if sep is None:
        raise ValueError("Séparateur non reconnu.")
    try:
        donnees = pd.read_csv(
            io.BytesIO(contenu),
            sep=sep,
            encoding=codec,
            dtype=str,
            na_filter=False,
            low_memory=False,
            on_bad_lines="error",
        )
    except (pd.errors.ParserError, ValueError, UnicodeDecodeError) as erreur:
        raise ValueError(f"Impossible de lire le CSV : {erreur}") from erreur
    if donnees.empty:
        raise ValueError("Le CSV ne contient aucune observation.")
    if len(donnees.columns) < 2:
        raise ValueError("Une seule colonne détectée : vérifier le séparateur du CSV.")
    donnees.columns = [str(nom).lstrip("\ufeff").strip() for nom in donnees.columns]
    if any(not nom for nom in donnees.columns):
        raise ValueError("Une ou plusieurs colonnes ont un nom vide.")
    if donnees.columns.duplicated().any():
        raise ValueError("Le CSV contient des noms de colonnes identiques.")
    for nom in donnees.columns:
        donnees[nom] = donnees[nom].str.strip()
    return ajouter_type_media(donnees)


def ajouter_type_media(donnees: pd.DataFrame) -> pd.DataFrame:
    """Construit une variable catégorielle à partir des indicateurs médias disponibles."""
    if "type_media" in donnees.columns:
        return donnees
    presentes = [nom for nom in INDICATEURS_MEDIAS if nom in donnees.columns]
    if not presentes:
        return donnees
    donnees = donnees.copy()
    indicateurs = pd.DataFrame(
        {nom: donnees[nom].str.lower().isin(VALEURS_VRAIES) for nom in presentes},
        index=donnees.index,
    )
    codages = indicateurs.dot(np.power(2, np.arange(len(presentes), dtype=np.int64)))
    noms = {}
    for code in codages.unique():
        categories = [INDICATEURS_MEDIAS[nom] for i, nom in enumerate(presentes) if code & (1 << i)]
        noms[int(code)] = "Plusieurs catégories de médias" if len(categories) > 1 else (
            categories[0] if categories else "Non renseigné"
        )
    donnees["type_media"] = codages.map(noms)
    return donnees



def generer_donnees_simulees(effectif: int = 400, graine: int = 2026) -> pd.DataFrame:
    """Crée un corpus fictif pour éprouver la mécanique AFC, sans données réelles."""
    if effectif < 20:
        raise ValueError("Une simulation doit comporter au moins 20 observations.")
    generateur = np.random.default_rng(graine)
    classes_vues = ["Moins de 10k", "10k-100k", "100k-1M", "Plus de 1M"]
    classes_engagement = ["Moins de 1%", "1-3%", "3-5%", "Plus de 5%"]
    probabilites_vues = np.array([0.25, 0.35, 0.25, 0.15])
    probabilites_engagement = np.array([
        [0.20, 0.25, 0.30, 0.25],
        [0.25, 0.35, 0.25, 0.15],
        [0.38, 0.37, 0.18, 0.07],
        [0.48, 0.35, 0.13, 0.04],
    ])
    indices_vues = generateur.choice(4, size=effectif, p=probabilites_vues)
    indices_engagement = np.array([
        generateur.choice(4, p=probabilites_engagement[classe])
        for classe in indices_vues
    ])
    return pd.DataFrame({
        "publication_id": [f"SIMULATION_{indice}" for indice in range(1, effectif + 1)],
        "retenue": ["True"] * effectif,
        "vues_classe": np.array(classes_vues)[indices_vues],
        "classe_taux_engagement": np.array(classes_engagement)[indices_engagement],
        "type_media": generateur.choice(
            ["Presse nationale", "Presse régionale", "Presse indépendante", "Autres médias"],
            size=effectif,
        ),
        "violence_annotee": generateur.choice(["Violence", "Pacifique"], size=effectif, p=[0.4, 0.6]),
        "symboles_etat": generateur.choice(["Présents", "Absents"], size=effectif),
    }).astype(str)


def decrire_variables(donnees: pd.DataFrame, maximum_modalites: int = 40) -> pd.DataFrame:
    """Établit l'inventaire des colonnes et distingue les variables à recoder."""
    descriptions = []
    for nom in donnees.columns:
        valeurs = donnees[nom]
        presentes = valeurs[valeurs.ne("")]
        uniques = int(presentes.nunique())
        vides = int(len(valeurs) - len(presentes))
        proportion_numerique = 0.0
        if len(presentes):
            nombres = pd.to_numeric(presentes.str.replace(",", ".", regex=False), errors="coerce")
            proportion_numerique = float(nombres.notna().mean())
        numerique_continue = (proportion_numerique > 0.95 and uniques > max(12, int(len(presentes) * 0.1)))
        statut = (
            "À recoder (numérique)" if numerique_continue else
            "À regrouper (nombreuses modalités)" if uniques > maximum_modalites else
            "Insuffisante (< 2 modalités)" if uniques < 2 else
            "Catégorielle possible"
        )
        descriptions.append({
            "Variable": nom,
            "Modalités": uniques,
            "Valeurs absentes": vides,
            "Diagnostic": statut,
        })
    return pd.DataFrame(descriptions)


def preparer_contingence(
    donnees: pd.DataFrame,
    variable_lignes: str,
    variable_colonnes: str,
    uniquement_retenues: bool = True,
    dedoublonner: bool = False,
    exclure_indeterminees: bool = True,
    inclure_manquantes: bool = False,
    maximum_modalites: int = 40,
    variable_filtre: str | None = None,
    modalites_filtre: list[str] | None = None,
) -> PreparationAFC:
    """Filtre une observation par ligne et prépare le tableau de contingence."""
    if variable_lignes == variable_colonnes:
        raise ValueError("Choisir deux variables distinctes pour l'AFC.")
    if variable_lignes not in donnees or variable_colonnes not in donnees:
        raise ValueError("Les variables sélectionnées sont absentes du CSV.")
    jeu = donnees
    effectif_initial = len(jeu)
    if uniquement_retenues and "retenue" in jeu.columns:
        jeu = jeu.loc[jeu["retenue"].str.lower().isin(VALEURS_VRAIES)]
    if variable_filtre:
        if variable_filtre not in jeu.columns:
            raise ValueError("La variable de filtrage est absente du CSV.")
        if modalites_filtre is not None:
            jeu = jeu.loc[jeu[variable_filtre].isin(modalites_filtre)]
    effectif_apres_filtre = len(jeu)
    if dedoublonner and "publication_id" in jeu.columns:
        identifiants = jeu["publication_id"]
        jeu = jeu.loc[identifiants.eq("") | ~identifiants.duplicated()]
    effectif_apres_dedoublonnage = len(jeu)

    colonnes = jeu.loc[:, [variable_lignes, variable_colonnes]].copy()
    for nom in colonnes.columns:
        if inclure_manquantes:
            colonnes[nom] = colonnes[nom].replace("", "Valeur manquante")
        if exclure_indeterminees:
            colonnes = colonnes.loc[~colonnes[nom].str.contains(MOTIFS_INDETERMINES, na=False)]
    if not inclure_manquantes:
        colonnes = colonnes.loc[colonnes[variable_lignes].ne("") & colonnes[variable_colonnes].ne("")]
    if colonnes.empty:
        raise ValueError("Aucune observation ne subsiste après application des filtres.")
    nombre_lignes = int(colonnes[variable_lignes].nunique())
    nombre_colonnes = int(colonnes[variable_colonnes].nunique())
    if min(nombre_lignes, nombre_colonnes) < 2:
        raise ValueError(
            f"AFC impossible : {nombre_lignes} modalité(s) en lignes et "
            f"{nombre_colonnes} en colonnes. Il faut au moins 2 modalités de chaque côté."
        )
    if max(nombre_lignes, nombre_colonnes) > maximum_modalites:
        raise ValueError(
            f"Trop de modalités : {nombre_lignes} × {nombre_colonnes} "
            f"(maximum autorisé : {maximum_modalites} par variable). "
            "Utiliser des classes ou regrouper les catégories."
        )
    tableau = pd.crosstab(
        colonnes[variable_lignes], colonnes[variable_colonnes],
        rownames=[variable_lignes], colnames=[variable_colonnes],
        dropna=False,
    )
    observés = tableau.to_numpy(dtype=float)
    attendus = np.outer(observés.sum(axis=1), observés.sum(axis=0)) / observés.sum()
    effectifs_attendus = pd.DataFrame(attendus, index=tableau.index, columns=tableau.columns)
    chi2 = float((np.square(observés - attendus) / attendus).sum())
    return PreparationAFC(
        tableau=tableau,
        effectif_initial=effectif_initial,
        effectif_apres_filtre=effectif_apres_filtre,
        effectif_apres_dedoublonnage=effectif_apres_dedoublonnage,
        effectif_final=int(tableau.to_numpy().sum()),
        effectifs_attendus=effectifs_attendus,
        cellules_attendues_faibles=int((attendus < 5).sum()),
        inertie_nulle=chi2 < 1e-12,
    )
