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
    effectif_avant_exclusion_modalites: int | None = None
    modalites_exclues_lignes: tuple[str, ...] = ()
    modalites_exclues_colonnes: tuple[str, ...] = ()
    modalites_vides_lignes: tuple[str, ...] = ()
    modalites_vides_colonnes: tuple[str, ...] = ()


def exclure_modalites_contingence(
    preparation: PreparationAFC,
    lignes_a_exclure: list[str] | tuple[str, ...] = (),
    colonnes_a_exclure: list[str] | tuple[str, ...] = (),
) -> PreparationAFC:
    """Retirer des modalités du tableau avant un nouveau calcul FactoMineR.

    Les observations associées aux lignes ou colonnes exclues ne sont plus
    comptées. Le tableau initial reste inchangé et les marges nulles créées
    par l'exclusion disparaissent, car elles ne sont pas utilisables en AFC.
    """
    from dataclasses import replace

    initial = preparation.tableau
    lignes = tuple(dict.fromkeys(lignes_a_exclure))
    colonnes = tuple(dict.fromkeys(colonnes_a_exclure))
    inconnues_lignes = set(lignes).difference(initial.index)
    inconnues_colonnes = set(colonnes).difference(initial.columns)
    if inconnues_lignes or inconnues_colonnes:
        raise ValueError(
            "Une ou plusieurs modalités à supprimer sont absentes "
            "du tableau de contingence."
        )

    tableau = initial.drop(index=list(lignes), columns=list(colonnes))
    # Une ligne ou colonne sans observation doit également être retirée.
    lignes_vides = tuple(tableau.index[tableau.sum(axis=1).eq(0)].tolist())
    colonnes_vides = tuple(tableau.columns[tableau.sum(axis=0).eq(0)].tolist())
    tableau = tableau.drop(
        index=list(lignes_vides), columns=list(colonnes_vides)
    )
    if tableau.shape[0] < 2 or tableau.shape[1] < 2:
        raise ValueError(
            "L'AFC nécessite au moins deux modalités actives en lignes "
            "et deux en colonnes. Rétablissez une modalité supprimée."
        )

    # Les effectifs sont comptés dans le tableau effectivement transmis à R,
    # sans réimputation ni nouveau calcul statistique.
    return replace(
        preparation,
        tableau=tableau,
        effectif_final=int(tableau.to_numpy().sum()),
        effectif_avant_exclusion_modalites=preparation.effectif_final,
        modalites_exclues_lignes=lignes,
        modalites_exclues_colonnes=colonnes,
        modalites_vides_lignes=lignes_vides,
        modalites_vides_colonnes=colonnes_vides,
    )


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



def preparer_tableau_inerties(contenu: bytes) -> pd.DataFrame:
    """Présenter sans recalcul les inerties des axes produites par FactoMineR."""
    if not contenu:
        raise ValueError("Le tableau des inerties FactoMineR est vide.")
    try:
        inerties = pd.read_csv(
            io.BytesIO(contenu), sep=";", decimal=",", encoding="utf-8-sig"
        )
    except (ValueError, pd.errors.ParserError, UnicodeError) as erreur:
        raise ValueError(
            "Impossible de lire le tableau des inerties FactoMineR."
        ) from erreur
    # FactoMineR::CA retourne, dans cet ordre : valeur propre,
    # pourcentage d'inertie et pourcentage cumulé.
    if inerties.empty or inerties.shape[1] < 4:
        raise ValueError("Le tableau des inerties FactoMineR est incomplet.")
    valeurs = inerties.iloc[:, 1:4].apply(
        pd.to_numeric, errors="coerce"
    )
    if valeurs.isna().any().any():
        raise ValueError("Certaines valeurs d'inertie FactoMineR sont invalides.")
    return pd.DataFrame({
        "Axe": [f"Axe {numero}" for numero in range(1, len(valeurs) + 1)],
        "Valeur propre": valeurs.iloc[:, 0].round(4).to_numpy(),
        "Inertie (%)": valeurs.iloc[:, 1].round(2).to_numpy(),
        "Inertie cumulée (%)": valeurs.iloc[:, 2].round(2).to_numpy(),
    })


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
    # Aucun test statistique dans Python : FactoMineR réalise l'analyse
    # et évalue l'inertie à partir du tableau de contingence complet.
    return PreparationAFC(
        tableau=tableau,
        effectif_initial=effectif_initial,
        effectif_apres_filtre=effectif_apres_filtre,
        effectif_apres_dedoublonnage=effectif_apres_dedoublonnage,
        effectif_final=int(tableau.to_numpy().sum()),
    )


@dataclass
class PreparationACM:
    """Conserve les observations catégorielles destinées à FactoMineR::MCA."""

    donnees: pd.DataFrame
    effectif_initial: int
    effectif_apres_filtre: int
    effectif_apres_dedoublonnage: int
    effectif_final: int
    effectif_avant_exclusion_modalites: int
    modalites_exclues: dict[str, list[str]]


def preparer_acm(
    donnees: pd.DataFrame,
    variables: list[str],
    uniquement_retenues: bool = True,
    dedoublonner: bool = False,
    exclure_indeterminees: bool = True,
    inclure_manquantes: bool = False,
    maximum_modalites: int = 40,
    variable_filtre: str | None = None,
    modalites_filtre: list[str] | None = None,
    modalites_a_exclure: dict[str, list[str]] | None = None,
) -> PreparationACM:
    """Préparer au moins trois variables qualitatives sans calcul statistique.

    Les exclusions retirent des observations ; elles ne suppriment ni une
    colonne de la source ni les modalités présentes dans le fichier importé.
    """
    if len(variables) < 3 or len(set(variables)) != len(variables):
        raise ValueError(
            "L'ACM exige au moins trois variables catégorielles distinctes."
        )
    inconnues = [nom for nom in variables if nom not in donnees.columns]
    if inconnues:
        raise ValueError("Variables absentes du CSV : " + ", ".join(inconnues))

    observations = donnees
    effectif_initial = len(observations)
    if uniquement_retenues and "retenue" in observations.columns:
        observations = observations.loc[
            observations["retenue"].str.lower().isin(VALEURS_VRAIES)
        ]
    if variable_filtre:
        if variable_filtre not in observations.columns:
            raise ValueError("La variable de filtrage est absente du CSV.")
        if modalites_filtre is not None:
            observations = observations.loc[
                observations[variable_filtre].isin(modalites_filtre)
            ]
    effectif_apres_filtre = len(observations)
    if dedoublonner and "publication_id" in observations.columns:
        identifiants = observations["publication_id"]
        observations = observations.loc[
            identifiants.eq("") | ~identifiants.duplicated()
        ]
    effectif_apres_dedoublonnage = len(observations)
    categories = observations.loc[:, variables].copy()
    for nom in variables:
        if inclure_manquantes:
            categories[nom] = categories[nom].replace(
                "", "Valeur manquante"
            )
        if exclure_indeterminees:
            categories = categories.loc[
                ~categories[nom].str.contains(MOTIFS_INDETERMINES, na=False)
            ]
    if not inclure_manquantes:
        categories = categories.loc[categories[variables].ne("").all(axis=1)]
    effectif_avant_exclusion_modalites = len(categories)

    exclusions = modalites_a_exclure or {}
    if set(exclusions).difference(variables):
        raise ValueError(
            "Une variable exclue n'appartient pas aux variables actives de l'ACM."
        )
    exclusions_validees = {}
    for nom in variables:
        modalites = list(dict.fromkeys(exclusions.get(nom, [])))
        if modalites:
            inconnues_modalites = set(modalites).difference(
                categories[nom].unique()
            )
            if inconnues_modalites:
                raise ValueError(
                    f"Certaines modalités à supprimer sont absentes de {nom}."
                )
            categories = categories.loc[~categories[nom].isin(modalites)]
        exclusions_validees[nom] = modalites

    if categories.empty:
        raise ValueError("Aucune observation ne subsiste pour l'ACM.")
    for nom in variables:
        nombre = int(categories[nom].nunique())
        if nombre < 2:
            raise ValueError(
                f"ACM impossible : la variable '{nom}' ne possède plus "
                "au moins deux modalités actives."
            )
        if nombre > maximum_modalites:
            raise ValueError(
                f"ACM impossible : '{nom}' possède {nombre} modalités "
                f"(maximum : {maximum_modalites})."
            )
    return PreparationACM(
        donnees=categories.reset_index(drop=True),
        effectif_initial=effectif_initial,
        effectif_apres_filtre=effectif_apres_filtre,
        effectif_apres_dedoublonnage=effectif_apres_dedoublonnage,
        effectif_final=len(categories),
        effectif_avant_exclusion_modalites=effectif_avant_exclusion_modalites,
        modalites_exclues=exclusions_validees,
    )
