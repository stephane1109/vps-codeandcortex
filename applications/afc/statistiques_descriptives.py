"""Calculs descriptifs sur un échantillon de publications, sans tests inférentiels."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from traitement_csv import VALEURS_VRAIES


# Les noms issus de ScrapTikTok sont prioritaires, puis leurs équivalents usuels.
CHAMPS_ENGAGEMENT = {
    "Vues": ("vues", "view_count", "play_count", "views", "nb_vues"),
    "Likes": ("likes", "like_count", "digg_count", "nb_likes"),
    "Commentaires": ("commentaires", "comment_count", "comments", "nb_commentaires"),
    "Partages": ("partages", "share_count", "shares", "nb_partages"),
    "Favoris": ("favoris", "collect_count", "favorite_count", "favorites", "saves"),
    "Abonnés": ("follower_count", "abonnes", "abonnés", "followers"),
    "Taux d'engagement (%)": (
        "taux_engagement", "engagement_rate", "taux_d_engagement",
    ),
}

CHAMPS_CLASSES = (
    "vues_classe", "likes_classe", "commentaires_classe",
    "partages_classe", "favoris_classe", "classe_taux_engagement",
    "classe_abonnes",
)

CHAMPS_GROUPES = (
    "type_media", "media", "region_code", "is_verified",
    "langue_detection", "type_violence", "violence", "auteur",
)

CHAMPS_DATES = (
    "date_publication", "created_at", "create_time", "date",
    "date_video", "published_at", "date_collecte",
)


def preparer_echantillon_descriptif(
    donnees: pd.DataFrame,
    uniquement_retenues: bool = True,
    dedoublonner: bool = False,
    variable_filtre: str | None = None,
    modalites_filtre: list[str] | None = None,
) -> pd.DataFrame:
    """Appliquer les mêmes règles de retenue et de doublon que l'AFC."""
    echantillon = donnees.copy()
    if uniquement_retenues and "retenue" in echantillon:
        retenues = echantillon["retenue"].astype(str).str.strip().str.lower()
        echantillon = echantillon.loc[retenues.isin(VALEURS_VRAIES)]
    if variable_filtre is not None:
        if variable_filtre not in echantillon:
            raise ValueError("La variable de filtrage n'existe pas dans le CSV.")
        if modalites_filtre is not None:
            echantillon = echantillon.loc[
                echantillon[variable_filtre].isin(modalites_filtre)
            ]
    if dedoublonner and "publication_id" in echantillon:
        identifiants = echantillon["publication_id"].fillna("").astype(str).str.strip()
        echantillon = echantillon.loc[
            identifiants.eq("") | ~identifiants.duplicated()
        ]
    if echantillon.empty:
        raise ValueError("Aucune publication ne correspond aux filtres descriptifs.")
    return echantillon.copy()


def convertir_nombres(
    valeurs: pd.Series, pourcentage: bool = False
) -> pd.Series:
    """Convertir les métriques françaises et internationales sans inventer de valeurs."""
    def convertir(valeur: object) -> float:
        if pd.isna(valeur):
            return np.nan
        texte = str(valeur).strip().replace("\u00a0", "").replace("\u202f", "")
        texte = re.sub(r"\s+", "", texte).replace("%", "")
        if not texte or texte.casefold() in {
            "nan", "na", "null", "none", "n/a", "indisponible", "nonrenseigné",
        }:
            return np.nan
        if "," in texte and "." in texte:
            separateur_decimal = "," if texte.rfind(",") > texte.rfind(".") else "."
            separateur_milliers = "." if separateur_decimal == "," else ","
            texte = texte.replace(separateur_milliers, "")
            texte = texte.replace(separateur_decimal, ".")
        elif "," in texte:
            if not pourcentage and re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+", texte):
                texte = texte.replace(",", "")
            else:
                texte = texte.replace(",", ".")
        elif "." in texte and not pourcentage:
            if re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+", texte):
                texte = texte.replace(".", "")
        try:
            nombre = float(texte)
        except ValueError:
            return np.nan
        return nombre if np.isfinite(nombre) and nombre >= 0 else np.nan

    return pd.to_numeric(valeurs.map(convertir), errors="coerce").astype(float)


def preparer_mesures_engagement(
    echantillon: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Normaliser les mesures numériques sans modifier les colonnes originales."""
    noms_originaux = {nom.casefold(): nom for nom in echantillon.columns}
    mesures = pd.DataFrame(index=echantillon.index)
    origines: dict[str, str] = {}
    for indicateur, alias in CHAMPS_ENGAGEMENT.items():
        champ = next((noms_originaux[n.casefold()] for n in alias
                      if n.casefold() in noms_originaux), None)
        if champ is not None:
            mesures[indicateur] = convertir_nombres(
                echantillon[champ],
                pourcentage=indicateur == "Taux d'engagement (%)",
            )
            origines[indicateur] = champ

    # Calcul autorisé uniquement lorsque les quatre interactions sont connues.
    interactions = ("Likes", "Commentaires", "Partages", "Favoris")
    if "Vues" in mesures and all(nom in mesures for nom in interactions):
        somme = mesures.loc[:, list(interactions)].sum(axis=1, min_count=4)
        taux_calcule = (
            somme.div(mesures["Vues"].where(mesures["Vues"].gt(0))).mul(100)
        )
        if "Taux d'engagement (%)" in mesures:
            mesures["Taux d'engagement (%)"] = (
                mesures["Taux d'engagement (%)"].fillna(taux_calcule)
            )
            origines["Taux d'engagement (%)"] += " ; compléments calculés"
        else:
            mesures["Taux d'engagement (%)"] = taux_calcule
            origines["Taux d'engagement (%)"] = (
                "(likes + commentaires + partages + favoris) / vues × 100"
            )
    return mesures, origines


def resumer_engagement(
    mesures: pd.DataFrame, effectif_total: int
) -> pd.DataFrame:
    """Calculer les statistiques avec le dénominateur propre à chaque mesure."""
    lignes = []
    for nom in mesures:
        valides = mesures[nom].dropna()
        n = len(valides)
        lignes.append({
            "Indicateur": nom,
            "N valide": n,
            "N absent": int(effectif_total - n),
            "Absents (%)": round(100 * (effectif_total - n) / effectif_total, 2)
            if effectif_total else np.nan,
            "Zéros": int(valides.eq(0).sum()),
            "Somme": float(valides.sum()) if n else np.nan,
            "Moyenne": float(valides.mean()) if n else np.nan,
            "Médiane": float(valides.median()) if n else np.nan,
            "Écart-type": float(valides.std()) if n > 1 else np.nan,
            "Minimum": float(valides.min()) if n else np.nan,
            "Q1": float(valides.quantile(0.25)) if n else np.nan,
            "Q3": float(valides.quantile(0.75)) if n else np.nan,
            "P90": float(valides.quantile(0.90)) if n else np.nan,
            "P95": float(valides.quantile(0.95)) if n else np.nan,
            "Maximum": float(valides.max()) if n else np.nan,
        })
    return pd.DataFrame(lignes)


def produire_histogramme(
    valeurs: pd.Series, nombre_classes: int = 25, logarithmique: bool = False
) -> pd.DataFrame:
    """Produire les effectifs d'histogramme, avec transformation log1p optionnelle."""
    serie = pd.to_numeric(valeurs, errors="coerce").dropna()
    serie = serie.loc[np.isfinite(serie) & serie.ge(0)]
    if serie.empty:
        return pd.DataFrame(columns=["Classe", "Publications"])
    serie = np.log1p(serie) if logarithmique else serie
    if serie.nunique() == 1:
        valeur = float(serie.iloc[0])
        etiquette = f"{np.expm1(valeur) if logarithmique else valeur:,.3g}"
        return pd.DataFrame({"Classe": [etiquette], "Publications": [len(serie)]})
    effectifs, bornes = np.histogram(
        serie.to_numpy(dtype=float), bins=max(2, int(nombre_classes))
    )
    bornes_originales = np.expm1(bornes) if logarithmique else bornes
    return pd.DataFrame({
        "Classe": [
            f"{bornes_originales[i]:,.3g} – {bornes_originales[i+1]:,.3g}"
            for i in range(len(effectifs))
        ],
        "Publications": effectifs.astype(int),
    })


def repartir_modalites(
    echantillon: pd.DataFrame, variable: str
) -> pd.DataFrame:
    """Conserver les modalités observées, y compris les données absentes."""
    if variable not in echantillon:
        raise ValueError("Variable qualitative absente du CSV.")
    modalites = echantillon[variable].fillna("").astype(str).str.strip()
    modalites = modalites.mask(modalites.eq(""), "(Valeur absente)")
    effectifs = modalites.value_counts(dropna=False)
    return pd.DataFrame({
        "Modalité": effectifs.index.to_list(),
        "Effectif": effectifs.to_numpy(),
        "Proportion (%)": (effectifs.to_numpy() / len(echantillon) * 100).round(2),
    })


def comparer_groupes(
    echantillon: pd.DataFrame,
    mesures: pd.DataFrame,
    variable: str,
    indicateur: str,
    minimum_observations: int = 1,
    maximum_groupes: int = 20,
) -> pd.DataFrame:
    """Résumer un indicateur par groupe ; aucune inférence statistique."""
    if variable not in echantillon or indicateur not in mesures:
        raise ValueError("Variable de groupe ou mesure indisponible.")
    groupes = echantillon[variable].fillna("").astype(str).str.strip()
    groupes = groupes.mask(groupes.eq(""), "(Valeur absente)")
    tableau = pd.DataFrame({
        "Groupe": groupes,
        "Mesure": mesures[indicateur],
    }, index=echantillon.index)
    resultat = tableau.groupby("Groupe", dropna=False).agg(
        Publications=("Groupe", "size"),
        **{
            "N valide": ("Mesure", "count"),
            "Médiane": ("Mesure", "median"),
            "Moyenne": ("Mesure", "mean"),
        },
    ).reset_index()
    resultat = resultat.loc[
        resultat["Publications"].ge(minimum_observations)
        & resultat["N valide"].gt(0)
    ]
    return resultat.sort_values(
        ["Publications", "Groupe"], ascending=[False, True]
    ).head(maximum_groupes).reset_index(drop=True)


def convertir_dates(valeurs: pd.Series) -> pd.Series:
    """Lire ISO, date simple et epoch TikTok sans confondre date et identifiant."""
    texte = valeurs.fillna("").astype(str).str.strip()
    resultat = pd.to_datetime(texte, errors="coerce", utc=True, format="mixed")
    secondes = texte.str.fullmatch(r"\d{10}")
    millisecondes = texte.str.fullmatch(r"\d{13}")
    if secondes.any():
        resultat.loc[secondes] = pd.to_datetime(
            texte.loc[secondes].astype("int64"), unit="s", utc=True
        )
    if millisecondes.any():
        resultat.loc[millisecondes] = pd.to_datetime(
            texte.loc[millisecondes].astype("int64"), unit="ms", utc=True
        )
    return resultat


def produire_evolution(
    echantillon: pd.DataFrame,
    mesures: pd.DataFrame,
    variable_date: str,
    indicateur: str,
) -> pd.DataFrame:
    """Compter les publications et décrire la médiane par jour UTC."""
    if variable_date not in echantillon or indicateur not in mesures:
        raise ValueError("Variable temporelle ou indicateur indisponible.")
    dates = convertir_dates(echantillon[variable_date])
    tableau = pd.DataFrame({
        "Jour": dates.dt.floor("D"),
        "Mesure": mesures[indicateur],
    }, index=echantillon.index).dropna(subset=["Jour"])
    if tableau.empty:
        return pd.DataFrame(columns=["Jour", "Publications", "N valide", "Médiane"])
    return tableau.groupby("Jour", as_index=False).agg(
        Publications=("Jour", "size"),
        **{"N valide": ("Mesure", "count"), "Médiane": ("Mesure", "median")},
    )
