# tests.py
# Exploration interactive + TESTS AUTOMATIQUES sur DataFrames
# Toutes les fonctions en minuscules. Explications en français.

import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

try:
    from scipy import stats
    _scipy_ok = True
except Exception:
    _scipy_ok = False

# =========================
# utilitaires de typage et prétraitement
# =========================

def _inferer_types(df: pd.DataFrame, max_modalites: int = 10, min_non_nuls: int = 10):
    """sélectionner colonnes numériques et catégorielles raisonnables pour les tests."""
    if df is None or df.empty:
        return [], []
    cols_valides = [c for c in df.columns if df[c].notna().sum() >= min_non_nuls]
    num_cols = [c for c in cols_valides if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = []
    for c in cols_valides:
        if c in num_cols:
            continue
        k = int(df[c].nunique(dropna=True))
        if 2 <= k <= max_modalites:
            cat_cols.append(c)
    return num_cols, cat_cols

def _appliquer_filtre(df: pd.DataFrame, requete: str) -> pd.DataFrame:
    """appliquer un filtre pandas.query (optionnel)."""
    if not requete:
        return df
    try:
        return df.query(requete)
    except Exception as e:
        st.warning(f"Filtre ignoré (syntaxe invalide pour pandas.query) : {e}")
        return df

# =========================
# tailles d’effet et contrôles
# =========================

def _cramer_v(table_np: np.ndarray) -> float:
    """V de Cramer pour table de contingence."""
    if table_np.size == 0:
        return np.nan
    chi2 = stats.chi2_contingency(table_np, correction=False)[0]
    n = table_np.sum()
    r, c = table_np.shape
    if n == 0:
        return np.nan
    return float(np.sqrt(chi2 / (n * (min(r, c) - 1)))) if min(r, c) > 1 else np.nan

def _eta2_anova(groupes: list[np.ndarray]) -> float:
    """eta² pour ANOVA une voie."""
    try:
        data = np.concatenate(groupes)
        k = len(groupes)
        n = len(data)
        grand_m = np.mean(data)
        ssb = sum([len(g) * (np.mean(g) - grand_m)**2 for g in groupes])
        sst = np.sum((data - grand_m)**2)
        return float(ssb / sst) if sst > 0 else np.nan
    except Exception:
        return np.nan

# =========================
# tests automatiques
# =========================

def _tests_cat_cat(df: pd.DataFrame, cat_cols: list[str], alpha: float):
    """Chi² indépendance pour toutes les paires catégorielles (Fisher 2x2 si ill-conditionné)."""
    lignes = []
    for i in range(len(cat_cols)):
        for j in range(i + 1, len(cat_cols)):
            a, b = cat_cols[i], cat_cols[j]
            table = pd.crosstab(df[a], df[b])
            if table.empty or table.shape[0] < 2 or table.shape[1] < 2:
                lignes.append({"var_a": a, "var_b": b, "test": "Chi²", "stat": np.nan, "p_value": np.nan, "taille_effet": np.nan, "note": "table dégénérée"})
                continue
            try:
                chi2, p, dof, exp = stats.chi2_contingency(table.values, correction=False)
                note = ""
                if (exp < 5).sum() > 0:
                    note = "attention: effectifs attendus < 5"
                v = _cramer_v(table.values) if _scipy_ok else np.nan
                lignes.append({"var_a": a, "var_b": b, "test": "Chi² indépendance", "stat": float(chi2), "p_value": float(p), "taille_effet": v, "note": note})
            except Exception as e:
                # tentative Fisher si 2x2
                if table.shape == (2, 2):
                    try:
                        odds, p = stats.fisher_exact(table.values)
                        lignes.append({"var_a": a, "var_b": b, "test": "Fisher exact 2x2", "stat": float(odds), "p_value": float(p), "taille_effet": np.nan, "note": "Chi² non calculable"})
                        continue
                    except Exception:
                        pass
                lignes.append({"var_a": a, "var_b": b, "test": "Chi²", "stat": np.nan, "p_value": np.nan, "taille_effet": np.nan, "note": f"erreur: {e}"})
    res = pd.DataFrame(lignes) if lignes else pd.DataFrame(columns=["var_a","var_b","test","stat","p_value","taille_effet","note"])
    if not res.empty:
        res["significatif"] = res["p_value"] < alpha
    return res.sort_values("p_value", na_position="last")

def _tests_num_cat(df: pd.DataFrame, num_cols: list[str], cat_cols: list[str], alpha: float):
    """ANOVA une voie pour toutes les paires numérique×catégoriel (à partir de 2 groupes)."""
    lignes = []
    for y in num_cols:
        for g in cat_cols:
            groupes = [sub[y].dropna().values for _, sub in df.groupby(g)]
            k = len(groupes)
            tailles = [len(arr) for arr in groupes]
            if k < 2 or min(tailles) < 2:
                lignes.append({"var_num": y, "groupe": g, "test": "ANOVA", "stat": np.nan, "p_value": np.nan, "taille_effet": np.nan, "note": "groupes insuffisants"})
                continue
            try:
                f, p = stats.f_oneway(*groupes)
                eta2 = _eta2_anova(groupes) if _scipy_ok else np.nan
                note = ""
                if max(tailles) / max(1, min(tailles)) > 4:
                    note = "attention: tailles de groupes très inégales"
                lignes.append({"var_num": y, "groupe": g, "test": "ANOVA une voie", "stat": float(f), "p_value": float(p), "taille_effet": eta2, "note": note})
            except Exception as e:
                lignes.append({"var_num": y, "groupe": g, "test": "ANOVA", "stat": np.nan, "p_value": np.nan, "taille_effet": np.nan, "note": f"erreur: {e}"})
    res = pd.DataFrame(lignes) if lignes else pd.DataFrame(columns=["var_num","groupe","test","stat","p_value","taille_effet","note"])
    if not res.empty:
        res["significatif"] = res["p_value"] < alpha
    return res.sort_values("p_value", na_position="last")

def _tests_num_num(df: pd.DataFrame, num_cols: list[str], alpha: float):
    """corrélations Pearson et Spearman pour toutes les paires numériques."""
    lignes = []
    for i in range(len(num_cols)):
        for j in range(i + 1, len(num_cols)):
            x, y = num_cols[i], num_cols[j]
            s = df[[x, y]].dropna()
            if len(s) < 3:
                lignes.append({"x": x, "y": y, "test": "corrélations", "pearson_r": np.nan, "pearson_p": np.nan, "spearman_rho": np.nan, "spearman_p": np.nan, "n": len(s), "note": "échantillon insuffisant"})
                continue
            try:
                r, p = stats.pearsonr(s[x], s[y])
                rs, ps = stats.spearmanr(s[x], s[y])
                lignes.append({"x": x, "y": y, "test": "corrélations", "pearson_r": float(r), "pearson_p": float(p), "spearman_rho": float(rs), "spearman_p": float(ps), "n": int(len(s)), "note": ""})
            except Exception as e:
                lignes.append({"x": x, "y": y, "test": "corrélations", "pearson_r": np.nan, "pearson_p": np.nan, "spearman_rho": np.nan, "spearman_p": np.nan, "n": len(s), "note": f"erreur: {e}"})
    res = pd.DataFrame(lignes) if lignes else pd.DataFrame(columns=["x","y","test","pearson_r","pearson_p","spearman_rho","spearman_p","n","note"])
    return res.sort_values("pearson_p", na_position="last")

# =========================
# interface : tests auto + exploration manuelle existante
# =========================

def ui_tests_auto(dfs_disponibles: dict[str, pd.DataFrame]):
    """tests automatiques sur la table choisie, avec explications et restrictions."""
    st.header("Tests automatiques")
    if not _scipy_ok:
        st.error("scipy n’est pas installé. Installez-le : pip install scipy")
        return
    if not dfs_disponibles:
        st.info("Aucune table disponible. Lancez d’abord l’analyse dans l’onglet Données.")
        return

    nom_table = st.selectbox("Table pour tests automatiques", options=list(dfs_disponibles.keys()))
    df = dfs_disponibles.get(nom_table)
    if df is None or df.empty:
        st.warning("Table vide.")
        return

    with st.expander("Filtre optionnel (pandas.query)", expanded=False):
        st.caption("Exemples : locuteur == 'locuteur_1' ; present_brut > 0 and planification_brut >= 1")
        requete = st.text_input("Requête", value="", key=f"auto_query_{nom_table}")
        df_f = _appliquer_filtre(df, requete)

    colp = st.columns(4)
    with colp[0]:
        alpha = st.number_input("Seuil α", value=0.05, min_value=0.001, max_value=0.2, step=0.005, format="%.3f")
    with colp[1]:
        max_modalites = st.number_input("Modalités max (cat.)", value=10, min_value=2, max_value=50, step=1)
    with colp[2]:
        min_non_nuls = st.number_input("Observations min/colonne", value=10, min_value=3, max_value=1000, step=1)
    with colp[3]:
        lancer = st.button("Lancer les tests automatiques", type="primary")

    st.caption("Rappels : Chi² teste l’indépendance entre deux variables catégorielles. ANOVA compare les moyennes d’une variable numérique entre k groupes (k ≥ 2). Les corrélations évaluent l’association entre deux numériques. Les p-values sont indicatives et doivent être interprétées avec prudence (multiplicité des tests, hypothèses).")

    if not lancer:
        return

    num_cols, cat_cols = _inferer_types(df_f, max_modalites=int(max_modalites), min_non_nuls=int(min_non_nuls))

    st.subheader("Catégoriel × Catégoriel — Chi² d’indépendance")
    res_cc = _tests_cat_cat(df_f, cat_cols, alpha)
    if res_cc.empty:
        st.info("Aucune paire catégorielle testable avec les critères actuels.")
    else:
        st.dataframe(res_cc)
        st.download_button("Télécharger résultats Chi² (CSV)", res_cc.to_csv(index=False).encode("utf-8"), file_name=f"{nom_table}_chi2.csv", mime="text/csv")
        st.caption("Restriction : si des effectifs attendus < 5 sont fréquents, le Chi² peut être peu fiable. Dans ce cas, un test exact (Fisher) est préférable pour des tables 2×2.")

    st.subheader("Numérique × Catégoriel — ANOVA une voie")
    res_nc = _tests_num_cat(df_f, num_cols, cat_cols, alpha)
    if res_nc.empty:
        st.info("Aucune paire numérique×catégoriel testable avec les critères actuels.")
    else:
        st.dataframe(res_nc)
        st.download_button("Télécharger résultats ANOVA (CSV)", res_nc.to_csv(index=False).encode("utf-8"), file_name=f"{nom_table}_anova.csv", mime="text/csv")
        st.caption("Hypothèses : indépendance des observations, homoscédasticité approximative, résidus environ normaux. En cas de violation, privilégier des tests non paramétriques (non inclus ici par défaut).")

    st.subheader("Numérique × Numérique — Corrélations")
    res_nn = _tests_num_num(df_f, num_cols, alpha)
    if res_nn.empty:
        st.info("Aucune paire numérique×numérique testable.")
    else:
        st.dataframe(res_nn)
        st.download_button("Télécharger résultats corrélations (CSV)", res_nn.to_csv(index=False).encode("utf-8"), file_name=f"{nom_table}_correlations.csv", mime="text/csv")
        st.caption("Pearson suppose une relation linéaire et des distributions approximativement normales ; Spearman est une alternative de rangs plus robuste aux non-normalités et aux monotonicités non linéaires.")

# =========================
# UI exploratoire manuelle déjà fournie précédemment
# =========================

def _tableau_croise(df: pd.DataFrame, ligne: str, colonne: str, normaliser: str):
    dropna = False
    if normaliser == "aucune":
        t = pd.crosstab(df[ligne], df[colonne], dropna=dropna)
    elif normaliser == "lignes":
        t = pd.crosstab(df[ligne], df[colonne], normalize="index", dropna=dropna)
    elif normaliser == "colonnes":
        t = pd.crosstab(df[ligne], df[colonne], normalize="columns", dropna=dropna)
    else:
        t = pd.crosstab(df[ligne], df[colonne], normalize=True, dropna=dropna)
    return t

def _pivot_agrege(df: pd.DataFrame, index: str, colonnes: str, valeur: str, agg: str):
    if agg == "count":
        p = pd.pivot_table(df, index=index, columns=colonnes, aggfunc="count")
        if isinstance(p.columns, pd.MultiIndex) and valeur in p.columns.get_level_values(0):
            p = p[valeur]
        return p
    return pd.pivot_table(df, values=valeur, index=index, columns=colonnes, aggfunc=agg)

def _chart_heatmap(df: pd.DataFrame, titre: str = "Heatmap"):
    if df is None or df.empty:
        return None
    m = df.reset_index().melt(id_vars=df.index.name or "index", var_name="x", value_name="valeur")
    y_name = df.index.name or "index"
    return alt.Chart(m).mark_rect().encode(
        x=alt.X("x:N", title=df.columns.name or "colonnes"),
        y=alt.Y(f"{y_name}:N", title=y_name),
        color=alt.Color("valeur:Q", title="valeur"),
        tooltip=[alt.Tooltip(f"{y_name}:N"), alt.Tooltip("x:N"), alt.Tooltip("valeur:Q", format=".3f")]
    ).properties(title=titre, height=340)

def _chart_scatter(df: pd.DataFrame, x: str, y: str, couleur: str | None = None):
    enc = {"x": alt.X(f"{x}:Q", title=x), "y": alt.Y(f"{y}:Q", title=y), "tooltip": [x, y]}
    if couleur and couleur in df.columns:
        enc["color"] = alt.Color(f"{couleur}:N", title=couleur)
        enc["tooltip"].append(couleur)
    return alt.Chart(df).mark_circle(opacity=0.6).encode(**enc).properties(height=320)

def _resumer_groupby(df: pd.DataFrame, by: str, metriques: list[str], agg: str):
    if not metriques:
        return pd.DataFrame()
    if agg == "count":
        return df.groupby(by)[metriques].count()
    return getattr(df.groupby(by)[metriques], agg)()

def ui_tests_croises(dfs_disponibles: dict[str, pd.DataFrame]):
    """interface exploratoire manuelle (inchangée en esprit)."""
    st.header("Exploration manuelle")
    if not dfs_disponibles:
        st.info("Aucune table disponible pour le moment. Lancez d’abord l’analyse dans l’onglet Données.")
        return
    nom_table = st.selectbox("Table", options=list(dfs_disponibles.keys()))
    df = dfs_disponibles.get(nom_table)
    if df is None or df.empty:
        st.warning("Table vide.")
        return
    with st.expander("Filtre optionnel (pandas.query)", expanded=False):
        st.caption("Exemples : locuteur == 'locuteur_1' ; present_brut > 0 and planification_brut >= 1")
        requete = st.text_input("Requête", value="", key=f"query_{nom_table}")
        df_f = _appliquer_filtre(df, requete)
    num_cols = [c for c in df_f.columns if pd.api.types.is_numeric_dtype(df_f[c])]
    cat_cols = [c for c in df_f.columns if c not in num_cols]
    st.subheader("Tableau croisé")
    col1, col2, col3 = st.columns(3)
    with col1:
        var_ligne = st.selectbox("Ligne (cat.)", options=cat_cols or ["—"], key="tc_l")
    with col2:
        var_col = st.selectbox("Colonne (cat.)", options=cat_cols or ["—"], key="tc_c")
    with col3:
        normaliser = st.selectbox("Normalisation", options=["aucune","lignes","colonnes","toutes"], index=0)
    if var_ligne in df_f.columns and var_col in df_f.columns and var_ligne != var_col:
        t = _tableau_croise(df_f, var_ligne, var_col, normaliser)
        st.dataframe(t)
        ch = _chart_heatmap(t, titre="Tableau croisé")
        if ch is not None:
            st.altair_chart(ch, use_container_width=True)
    st.subheader("Nuage de points")
    cols = st.columns(3)
    with cols[0]:
        xnum = st.selectbox("X (num.)", options=num_cols or ["—"], key="sc_x")
    with cols[1]:
        ynum = st.selectbox("Y (num.)", options=num_cols or ["—"], key="sc_y")
    with cols[2]:
        colr = st.selectbox("Couleur (cat., optionnel)", options=["—"] + cat_cols, index=0, key="sc_c")
    if xnum in num_cols and ynum in num_cols and xnum != ynum:
        st.altair_chart(_chart_scatter(df_f, xnum, ynum, None if colr == "—" else colr), use_container_width=True)
    st.subheader("Statistiques par groupe")
    colg1, colg2 = st.columns(2)
    with colg1:
        by = st.selectbox("Grouper par (cat.)", options=cat_cols or ["—"], key="gb_by")
    with colg2:
        agg2 = st.selectbox("Agrégat", options=["mean","sum","count","median","std"], index=0, key="gb_agg")
    mets = st.multiselect("Métriques (num.)", options=num_cols, default=[c for c in num_cols[:3]])
    if by in df_f.columns and mets:
        st.dataframe(_resumer_groupby(df_f, by, mets, agg2))
