################################################
# Stéphane Meurisse
# www.codeandcortex.fr
# version beta 1.1
# 28 juillet 2025
################################################

# python -m streamlit run main.py

# ##########
# pip install streamlit pandas spacy matplotlib pyvis scipy wordcloud
# python -m spacy download fr_core_news_md
############

# ================================
# IMPORTS
# ================================
import itertools
import html  # pour html.escape
import math
import pandas as pd
import streamlit as st
from wordcloud import WordCloud
import spacy
import networkx as nx
from pyvis.network import Network
from streamlit.components.v1 import html as st_html
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors  # <-- IMPORT AJOUTÉ
from scipy.stats import chi2  # pour la p-valeur du test (df=1)
from collections import Counter
import io
import re

# ================================
# CHARGEMENT SPACY (FR)
# ================================
@st.cache_resource(show_spinner=False)
def charger_modele_spacy():
    try:
        modele = spacy.load("fr_core_news_md")
    except Exception as exc:
        raise RuntimeError(
            "Le modèle spaCy 'fr_core_news_md' n'est pas installé.\n"
            "Installez-le avec :\n"
            "pip install -U spacy && python -m spacy download fr_core_news_md"
        ) from exc

    # Garantit la disponibilité de doc.sents sans recharger le pipeline à chaque rerun.
    if "senter" not in modele.pipe_names and "sentencizer" not in modele.pipe_names:
        modele.add_pipe("sentencizer", config={"punct_chars": [".", "!", "?", "…"]})

    return modele

nlp = charger_modele_spacy()

# ================================
# STOPWORDS
# ================================
def construire_stopwords(appliquer_stop: bool):
    return set(nlp.Defaults.stop_words) if appliquer_stop else set()

# ================================
# SEGMENTATION PARAGRAPHES
# ================================
def segmenter_paragraphes(texte: str):
    norm = texte.replace("\r\n", "\n").replace("\r", "\n")
    blocs = re.split(r"\n\s*\n+", norm)
    return [b.strip() for b in blocs if b.strip()]

# ================================
# NORMALISATION (APOSTROPHES & FORMES)
# ================================
APOS = {"'", "’"}

def normaliser_apostrophe_joint(token_text: str) -> str:
    if "'" in token_text or "’" in token_text:
        parts = re.split(r"[’']", token_text, maxsplit=1)
        if len(parts) == 2:
            return parts[1]
    return token_text

def iter_tokens_norm_et_carte_global(doc, stopset, exclure_nombres: bool, exclure_monolettre: bool):
    norm_list, spans_list = [], []
    toks = list(doc)
    i, n = 0, len(toks)
    while i < n:
        tok = toks[i]
        raw = tok.text
        low = raw.lower()

        if low.isalpha() and i + 2 < n and toks[i+1].text in APOS:
            droite = toks[i+2].text.lower()
            mot = droite
            if mot.isalnum() and not (exclure_nombres and mot.isdigit()) and not (exclure_monolettre and len(mot) == 1):
                if mot not in stopset:
                    norm_list.append(mot); spans_list.append((i, i+3))
            i += 3
            continue

        if ("'" in raw) or ("’" in raw):
            mot = normaliser_apostrophe_joint(raw).lower()
        else:
            mot = low

        if mot.isalnum() and not (exclure_nombres and mot.isdigit()) and not (exclure_monolettre and len(mot) == 1):
            if mot not in stopset:
                norm_list.append(mot); spans_list.append((i, i+1))
        i += 1

    return norm_list, spans_list

def iter_tokens_normalises_global(doc, stopset, exclure_nombres: bool, exclure_monolettre: bool):
    norm, _ = iter_tokens_norm_et_carte_global(doc, stopset, exclure_nombres, exclure_monolettre)
    return norm

# ================================
# FENÊTRES GLOBALES (SANS PIVOT)
# ================================
def fenetres_globales_mots(doc, k: int, stopset, exclure_nombres: bool, exclure_monolettre: bool):
    seq = iter_tokens_normalises_global(doc, stopset, exclure_nombres, exclure_monolettre)
    fenetres = []
    for i in range(len(seq)):
        d = max(0, i - k); f = min(len(seq), i + k + 1)
        S = set(seq[d:f])
        if S:
            fenetres.append(S)
    return fenetres

def fenetres_globales_phrases(doc, stopset, exclure_nombres: bool, exclure_monolettre: bool):
    fenetres = []
    for sent in doc.sents:
        seq = iter_tokens_normalises_global(sent, stopset, exclure_nombres, exclure_monolettre)
        if seq:
            fenetres.append(set(seq))
    return fenetres

def fenetres_globales_paragraphes(texte: str, stopset, exclure_nombres: bool, exclure_monolettre: bool):
    fenetres = []
    for pa in segmenter_paragraphes(texte):
        d = nlp(pa)
        seq = iter_tokens_normalises_global(d, stopset, exclure_nombres, exclure_monolettre)
        if seq:
            fenetres.append(set(seq))
    return fenetres

# ================================
# COOCURRENCES (FRÉQUENCE)
# ================================
def compter_cooc_globales(fenetres):
    compteur = Counter()
    for S in fenetres:
        if len(S) < 2:
            continue
        for a, b in itertools.combinations(sorted(S), 2):
            compteur[(a, b)] += 1
    return compteur

def poids_noeuds_depuis_aretes(paires_freq: dict):
    deg = Counter()
    for (a, b), w in paires_freq.items():
        deg[a] += w
        deg[b] += w
    return deg

def filtrer_par_frequence_au_moins(paires_freq: dict, n: int):
    return {e: w for e, w in paires_freq.items() if w >= n}

# ================================
# PYVIS — GRAPHE GLOBAL & LLR (repris du script qui fonctionne)
# ================================
def _scale_linear(v, vmin, vmax, out_min, out_max):
    if vmax == vmin:
        return (out_min + out_max) / 2.0
    return out_min + (out_max - out_min) * ((v - vmin) / (vmax - vmin))

def pyvis_reseau_global_html_couleur(paires_freq: dict, edge_label_size: int = 10):
    """Réseau global pondéré par fréquence (physics ON, solver forceAtlas2Based)."""
    if not paires_freq:
        return "<div>Aucune cooccurrence globale à afficher (filtre trop strict ?).</div>"

    deg = Counter()
    for (a, b), w in paires_freq.items():
        deg[a] += float(w); deg[b] += float(w)
    deg_vals = list(deg.values()) or [1.0]
    dmin, dmax = min(deg_vals), max(deg_vals)

    wvals = [float(w) for w in paires_freq.values()] or [1.0]
    wmin, wmax = min(wvals), max(wvals)

    net = Network(height="900px", width="100%", directed=False, notebook=False, cdn_resources="in_line")
    net.set_options("""{
      "interaction": {"dragNodes": true, "dragView": true, "zoomView": true},
      "physics": {"enabled": true, "solver": "forceAtlas2Based",
        "forceAtlas2Based": {"gravitationalConstant": -50,"centralGravity": 0.005,"springLength": 150,"springConstant": 0.08,"avoidOverlap": 1.0},
        "stabilization": {"enabled": true, "iterations": 300, "fit": true, "updateInterval": 25}
      },
      "edges": {"smooth": false},
      "nodes": {"shape": "dot", "scaling": {"min": 8, "max": 60}}
    }""")

    vus = set()
    for (a, b), _w in paires_freq.items():
        for n_ in (a, b):
            if n_ in vus:
                continue
            vus.add(n_)
            taille = _scale_linear(deg[n_], dmin, dmax, 10, 58)
            t = 0.0 if dmax == dmin else (deg[n_] - dmin) / (dmax - dmin)
            col = mcolors.to_hex(cm.viridis(t))
            net.add_node(n_, label=n_, title=f"{n_} (degré pondéré={deg[n_]:.0f})", size=taille, color=col)

    for (a, b), w in paires_freq.items():
        w = float(w)
        width = _scale_linear(w, wmin, wmax, 1.2, 6.5)
        t = 0.0 if wmax == wmin else (w - wmin) / (wmax - wmin)
        ecol = mcolors.to_hex(cm.plasma(t))
        net.add_edge(a, b, value=w, width=width, color=ecol, label=str(int(w)),
                     title=f"fréquence={int(w)}", font={"size": edge_label_size})

    return net.generate_html()

def pyvis_graphe_likelihood_html(llr_scores: dict, pvals: dict, seuil_llr: float = 0.0, alpha: float = None, edge_label_size: int = 10):
    """Graphe PyVis pondéré par G², avec filtre p-valeur optionnel (physics ON)."""
    data = {e: s for e, s in llr_scores.items() if float(s) >= float(seuil_llr)}
    if alpha is not None:
        data = {e: s for e, s in data.items() if float(pvals.get(e, 1.0)) <= float(alpha)}
    if not data:
        return "<div>Aucune arête après application des seuils.</div>"

    deg = Counter()
    for (a, b), s in data.items():
        deg[a] += s; deg[b] += s
    dmin, dmax = (min(deg.values()), max(deg.values()))
    smin, smax = (min(data.values()), max(data.values()))

    net = Network(height="900px", width="100%", directed=False, notebook=False, cdn_resources="in_line")
    net.set_options("""{
      "interaction": {"dragNodes": true, "dragView": true, "zoomView": true},
      "physics": {"enabled": true, "solver": "forceAtlas2Based",
        "forceAtlas2Based": {"gravitationalConstant": -50,"centralGravity": 0.005,"springLength": 150,"springConstant": 0.08,"avoidOverlap": 1.0},
        "stabilization": {"enabled": true, "iterations": 300, "fit": true, "updateInterval": 25}
      },
      "edges": {"smooth": false},
      "nodes": {"shape": "dot", "scaling": {"min": 8, "max": 60}}
    }""")

    vus = set()
    for (a, b), _ in data.items():
        for n_ in (a, b):
            if n_ in vus:
                continue
            vus.add(n_)
            taille = _scale_linear(deg[n_], dmin, dmax, 10, 58)
            t = 0.0 if dmax == dmin else (deg[n_] - dmin) / (dmax - dmin)
            col = mcolors.to_hex(cm.viridis(t))
            net.add_node(n_, label=n_, title=f"{n_} (somme Log-likelihood={deg[n_]:.2f})", size=taille, color=col)

    for (a, b), s in data.items():
        width = _scale_linear(s, smin, smax, 1.2, 6.5)
        p = float(pvals.get((a, b), 1.0))
        ecol = mcolors.to_hex(cm.inferno(_scale_linear(s, smin, smax, 0.0, 1.0)))
        net.add_edge(a, b, value=s, width=width, color=ecol,
                     label=f"{s:.2f}",
                     title=f"Log-Likelihood={s:.2f} ; p={p:.3g}",
                     font={"size": edge_label_size})

    return net.generate_html()

# ================================
# CONCORDANCIERS (FONCTIONS)
# ================================
def surligner_phrase_paire(sent, w1: str, w2: str):
    toks = list(sent)
    out = []
    css = (
        "<style>"
        ".kwic-sent{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans','Helvetica Neue',Arial;"
        "line-height:1.6;margin:6px 0}"
        ".w1{background:#e63946;color:#fff;border-radius:3px;padding:0 3px}"
        ".w2{background:#1d3557;color:#fff;border-radius:3px;padding:0 3px}"
        "</style>"
    )
    for tok in toks:
        surf = html.escape(tok.text_with_ws)
        norm = normaliser_apostrophe_joint(tok.text).lower()
        if norm == w1:
            out.append(f"<span class='w1'>{surf}</span>")
        elif norm == w2:
            out.append(f"<span class='w2'>{surf}</span>")
        else:
            out.append(surf)
    return css + f"<div class='kwic-sent'>{''.join(out).strip()}</div>"

def kwic_mots_pm_k(doc, stopset, exclure_nombres, exclure_monolettre, w1: str, w2: str, k: int, marge: int = 5):
    norm, spans = iter_tokens_norm_et_carte_global(doc, stopset, exclure_nombres, exclure_monolettre)
    toks = list(doc)
    pos_w1 = [i for i, w in enumerate(norm) if w == w1]
    pos_w2 = [i for i, w in enumerate(norm) if w == w2]
    if not pos_w1 or not pos_w2:
        return []

    deja = set()
    lignes = []

    for i in pos_w1:
        for j in pos_w2:
            if abs(i - j) <= k:
                t_start = min(spans[i][0], spans[j][0])
                t_end   = max(spans[i][1], spans[j][1])
                s = max(0, t_start - marge)
                e = min(len(toks), t_end + marge)
                key = (s, e)
                if key in deja:
                    continue
                deja.add(key)

                head_i = max(spans[i][1]-1, spans[i][0])
                head_j = max(spans[j][1]-1, spans[j][0])

                css = (
                    "<style>"
                    ".kwic-sent{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans','Helvetica Neue',Arial;"
                    "line-height:1.6;margin:6px 0}"
                    ".w1{background:#e63946;color:#fff;border-radius:3px;padding:0 3px}"
                    ".w2{background:#1d3557;color:#fff;border-radius:3px;padding:0 3px}"
                    "</style>"
                )
                out = []
                for idx in range(s, e):
                    surf = html.escape(toks[idx].text_with_ws)
                    if idx == head_i:
                        out.append(f"<span class='w1'>{surf}</span>")
                    elif idx == head_j:
                        out.append(f"<span class='w2'>{surf}</span>")
                    else:
                        out.append(surf)
                lignes.append(css + f"<div class='kwic-sent'>{''.join(out).strip()}</div>")
    return lignes

def surligner_paragraphe_paire(pa_texte: str, w1: str, w2: str):
    d = nlp(pa_texte)
    toks = list(d)
    out = []
    css = (
        "<style>"
        ".kwic-sent{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans','Helvetica Neue',Arial;"
        "line-height:1.6;margin:6px 0}"
        ".w1{background:#e63946;color:#fff;border-radius:3px;padding:0 3px}"
        ".w2{background:#1d3557;color:#fff;border-radius:3px;padding:0 3px}"
        "</style>"
    )
    for tok in toks:
        surf = html.escape(tok.text_with_ws)
        norm = normaliser_apostrophe_joint(tok.text).lower()
        if norm == w1:
            out.append(f"<span class='w1'>{surf}</span>")
        elif norm == w2:
            out.append(f"<span class='w2'>{surf}</span>")
        else:
            out.append(surf)
    return css + f"<div class='kwic-sent'>{''.join(out).strip()}</div>"

def document_html_kwic(titre: str, sections_html):
    style = (
        "<style>"
        "body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans','Helvetica Neue',Arial;line-height:1.6;padding:12px}"
        "h2{margin:18px 0 8px 0}"
        ".kwic-sent{margin:6px 0}"
        "</style>"
    )
    corps = "\n".join(sections_html)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(titre)}</title>{style}</head><body>"
        f"<h1>{html.escape(titre)}</h1>"
        f"{corps}</body></html>"
    )

# ================================
# OUTILS
# ================================
def generer_csv(df: pd.DataFrame):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf

def generer_nuage_mots(degre_pondere: dict, titre: str):
    freq_pos = {w: float(v) for w, v in degre_pondere.items() if v and v > 0}
    if not freq_pos:
        st.info("Nuage non généré : aucune valeur strictement positive.")
        return
    wc = WordCloud(width=900, height=450, background_color="white").generate_from_frequencies(freq_pos)
    fig = plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation="bilinear"); plt.axis("off"); plt.title(titre)
    st.pyplot(fig)
    buf_png = io.BytesIO()
    wc.to_image().save(buf_png, format="PNG")
    buf_png.seek(0)
    st.session_state["nuage_png"] = buf_png.getvalue()

def generer_png_graphe_stat(paires_freq: dict, largeur_px: int = 1600, hauteur_px: int = 1000, dpi: int = 100) -> bytes:
    if not paires_freq:
        return b""
    G = nx.Graph()
    for (a, b), w in paires_freq.items():
        G.add_edge(a, b, weight=float(w))

    deg_p = {n: float(sum(d["weight"] for _u, _v, d in G.edges(n, data=True))) for n in G.nodes()}
    if not deg_p:
        return b""

    n = max(G.number_of_nodes(), 1)
    k_dist = 1.2 / (n ** 0.5)
    pos = nx.spring_layout(G, weight="weight", seed=42, k=k_dist, iterations=200)

    dvals = list(deg_p.values())
    dmin, dmax = min(dvals), max(dvals)
    def scale(val, vmin, vmax, out_min, out_max):
        if vmax == vmin:
            return (out_min + out_max) / 2.0
        return out_min + (out_max - out_min) * ((val - vmin) / (vmax - vmin))

    fig_w = largeur_px / dpi
    fig_h = hauteur_px / dpi
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.axis("off")

    ncolors = [cm.viridis(scale(deg_p[n], dmin, dmax, 0.0, 1.0)) for n in G.nodes()]
    nsizes = [scale(deg_p[n], dmin, dmax, 300, 3000) for n in G.nodes()]

    wvals = [d["weight"] for _u, _v, d in G.edges(data=True)]
    wmin, wmax = (min(wvals), max(wvals)) if wvals else (1.0, 1.0)
    ewidths = [scale(w, wmin, wmax, 0.8, 5.0) for w in wvals]
    ecolors = [cm.plasma(scale(w, wmin, wmax, 0.0, 1.0)) for w in wvals]

    nx.draw_networkx_edges(G, pos, ax=ax, width=ewidths, edge_color=ecolors, alpha=0.9)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=nsizes, node_color=ncolors)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=14)

    buf = io.BytesIO()
    fig.tight_layout(pad=0)
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

# ================================
# LOGLIKELIHOOD (DUNNING) + p-VALEUR
# ================================
def compter_presence_par_fenetre(fenetres):
    c = Counter()
    for S in fenetres:
        for w in S:
            c[w] += 1
    return c

def tableau_contingence(a: str, b: str, pres_counts: dict, k11: int, N: int):
    k12 = pres_counts.get(a, 0) - k11
    k21 = pres_counts.get(b, 0) - k11
    k22 = N - k11 - k12 - k21
    k12 = max(0, k12); k21 = max(0, k21); k22 = max(0, k22)
    return k11, k12, k21, k22

def _xlogx(x: float) -> float:
    return x * math.log(x) if x > 0 else 0.0

def log_likelihood(k11, k12, k21, k22) -> float:
    row1 = k11 + k12
    row2 = k21 + k22
    col1 = k11 + k21
    col2 = k12 + k22
    N = row1 + row2
    return 2.0 * (
        _xlogx(k11) + _xlogx(k12) + _xlogx(k21) + _xlogx(k22)
        - _xlogx(row1) - _xlogx(row2) - _xlogx(col1) - _xlogx(col2)
        + _xlogx(N)
    )

def p_value_chi2_df1(g2: float) -> float:
    if g2 < 0 or not math.isfinite(g2):
        return 1.0
    return float(chi2.sf(g2, df=1))

def calculer_llr_et_pval(paires_freq: dict, fenetres):
    if not paires_freq:
        return {}, {}
    pres = compter_presence_par_fenetre(fenetres)
    N = len(fenetres)
    g2 = {}
    pvals = {}
    for (a, b), k11 in paires_freq.items():
        k11 = int(k11)
        k11, k12, k21, k22 = tableau_contingence(a, b, pres, k11, N)
        g = log_likelihood(k11, k12, k21, k22)
        g2[(a, b)] = g
        pvals[(a, b)] = p_value_chi2_df1(g)
    return g2, pvals

# ================================
# INTERFACE — PARAMÈTRES ET EXPLICATIONS
# ================================
st.set_page_config(page_title="Cooccurrences globales (sans mot pivot) — Graphe, Likelihood, Nuage, Concordancier")

st.markdown("<h1 style='color:#e63946'>Cooccurrences globales (sans mot pivot)</h1>", unsafe_allow_html=True)
st.caption("Stéphane Meurisse — version beta 1.1 - 26/07/2025 \\- [www.codeandcortex.fr](https://www.codeandcortex.fr)")
st.markdown("---")

st.markdown(
    "Cette application calcule des cooccurrences **sans mot pivot**. "
    "Fenêtres possibles : « Mots (±k) » (glissante), « Phrase » (spaCy) et « Paragraphe » (séparés par une ligne vide)."
)
st.markdown(
    "Le **filtrage par fréquence N** conserve les paires vues **au moins N fois**. "
    "**Log-likelihood** : mesure l'écart à l'indépendance entre deux mots. "
    "La **p-valeur** évalue la significativité (plus petite = plus significatif). "
)

# ---------- Widgets d'entrée ----------
uploaded = st.file_uploader("Fichiers texte (.txt)", type=["txt"], key="file", accept_multiple_files=True)
texte_libre = st.text_area("Ou collez votre texte ici", height=220,
                           placeholder="Collez votre corpus ici…", key="texte")

st.subheader("Fenêtre de contexte")
fenetre = st.selectbox("Type de fenêtre", ["Mots (±k)", "Phrase", "Paragraphe"], key="fenetre")
k = 5
if fenetre == "Mots (±k)":
    k = st.number_input("Paramètre k (taille de la fenêtre en mots)",
                        min_value=1, max_value=10000, value=5, step=1, key="k")

mode_document = st.checkbox("Analyser chaque fichier séparément (mode Document)", value=False, key="mode_doc")

st.markdown(f"<div style='color:#e63946;margin-top:6px'><strong>Fenêtre sélectionnée :</strong> {fenetre}</div>", unsafe_allow_html=True)
if mode_document:
    st.markdown("<div style='color:#1d3557'>Mode Document activé : chaque fichier est analysé séparément, puis affiché l’un après l’autre.</div>", unsafe_allow_html=True)

st.subheader("Options de nettoyage")
appliquer_stop = st.checkbox("Appliquer les stopwords (spaCy)", value=True, key="stop")
exclure_nombres = st.checkbox("Exclure les nombres", value=True, key="nonum")
exclure_monolettre = st.checkbox("Exclure les mots d’une seule lettre", value=True, key="mono1")

st.subheader("Filtrage par fréquence")
n_filtre = st.number_input("Fréquence minimale N (au moins N)", min_value=1, max_value=100000,
                           value=2, step=1, key="nmin")

st.subheader("Paramètres likelihood")
seuil_llr_graphe = st.number_input("Seuil minimal log-likelihood pour le graphe (arêtes ≥ seuil)",
                                   min_value=0.0, max_value=1e9, value=5.0, step=1.0, key="seuil_llr")
st.markdown("**log-likelihood ratio.** Filtre visuel : seules les arêtes avec **log-likelihood ≥ seuil** sont dessinées.")
activer_filtre_p = st.checkbox("Activer le filtre par p-valeur", value=True, key="filtre_p")
alpha = st.number_input("Seuil α (p ≤ α)", min_value=0.0001, max_value=1.0,
                        value=0.05, step=0.01, key="alpha")

top_k_llr_cloud  = st.number_input("Top K cooccurrences (nuage log-likelihood)", min_value=1, max_value=5000, value=10, step=5, key="topk_llr_pairs")
top_k_freq_pairs = st.number_input("Top K cooccurrences (nuage fréquence)",      min_value=1, max_value=5000, value=10, step=5, key="topk_freq_pairs")

# ================================
# CALCUL
# ================================
if st.button("Calculer les cooccurrences", key="btn_calc"):
    textes_list, noms_list = [], []

    if uploaded:
        for f in uploaded:
            try:
                contenus = f.read().decode("utf-8", errors="ignore")
            except Exception:
                contenus = f.read().decode("latin-1", errors="ignore")
            if contenus and contenus.strip():
                textes_list.append(contenus)
                noms_list.append(getattr(f, "name", f"doc_{len(noms_list)+1}.txt"))

    if texte_libre and texte_libre.strip():
        textes_list.append(texte_libre)
        noms_list.append("texte_libre.txt")

    if not textes_list:
        st.error("Veuillez fournir un texte.")
        st.stop()

    stopset = construire_stopwords(appliquer_stop)

    if mode_document:
        docs_results = []
        for txt, nom in zip(textes_list, noms_list):
            ddoc = nlp(txt)
            if fenetre == "Mots (±k)":
                fens = fenetres_globales_mots(ddoc, int(k), stopset, exclure_nombres, exclure_monolettre)
            elif fenetre == "Phrase":
                fens = fenetres_globales_phrases(ddoc, stopset, exclure_nombres, exclure_monolettre)
            else:
                fens = fenetres_globales_paragraphes(txt, stopset, exclure_nombres, exclure_monolettre)

            p_all = compter_cooc_globales(fens)
            p_freq = filtrer_par_frequence_au_moins(p_all, int(n_filtre))
            g2_scores, pvals = calculer_llr_et_pval(p_all, fens)

            freq_all = {(a, b): int(w) for (a, b), w in p_all.items()}
            df_paires = pd.DataFrame(
                [(a, b, int(w)) for (a, b), w in sorted(p_freq.items(), key=lambda x: x[1], reverse=True)],
                columns=["mot1", "mot2", "frequence"]
            )
            df_llr_all = pd.DataFrame(
                [(a, b, freq_all.get((a, b), 0), float(g2_scores[(a, b)]), float(pvals[(a, b)]))
                 for (a, b) in g2_scores.keys()],
                columns=["mot1", "mot2", "frequence", "log_likelihood", "p_value"]
            )

            docs_results.append({
                "nom": nom,
                "texte": txt,
                "doc": ddoc,
                "fenetres": fens,
                "paires_all": p_all,
                "paires_freq": p_freq,
                "df_paires": df_paires,
                "g2_scores": g2_scores,
                "pvals": pvals,
                "df_llr_all": df_llr_all,
            })

        texte_concat = "\n\n".join(textes_list)
        doc_concat = nlp(texte_concat)

        st.session_state["res"] = {
            "mode_document": True,
            "docs": docs_results,
            "texte": texte_concat,
            "doc": doc_concat,
            "fenetre": fenetre,
            "k": int(k),
            "stopset": stopset,
            "exclure_nombres": exclure_nombres,
            "exclure_monolettre": exclure_monolettre,
        }
    else:
        texte = "\n\n".join(textes_list)
        doc = nlp(texte)
        if fenetre == "Mots (±k)":
            fenetres_calc = fenetres_globales_mots(doc, int(k), stopset, exclure_nombres, exclure_monolettre)
        elif fenetre == "Phrase":
            fenetres_calc = fenetres_globales_phrases(doc, stopset, exclure_nombres, exclure_monolettre)
        else:
            fenetres_calc = fenetres_globales_paragraphes(texte, stopset, exclure_nombres, exclure_monolettre)

        paires_all = compter_cooc_globales(fenetres_calc)
        paires_freq = filtrer_par_frequence_au_moins(paires_all, int(n_filtre))
        g2_scores, pvals = calculer_llr_et_pval(paires_all, fenetres_calc)

        freq_all = {(a, b): int(w) for (a, b), w in paires_all.items()}
        df_paires = pd.DataFrame(
            [(a, b, int(w)) for (a, b), w in sorted(paires_freq.items(), key=lambda x: x[1], reverse=True)],
            columns=["mot1", "mot2", "frequence"]
        )
        df_llr_all = pd.DataFrame(
            [(a, b, freq_all.get((a, b), 0), float(g2_scores[(a, b)]), float(pvals[(a, b)]))
             for (a, b) in g2_scores.keys()],
            columns=["mot1", "mot2", "frequence", "log_likelihood", "p_value"]
        )

        st.session_state["res"] = {
            "mode_document": False,
            "texte": texte,
            "fenetre": fenetre,
            "k": int(k),
            "stopset": stopset,
            "exclure_nombres": exclure_nombres,
            "exclure_monolettre": exclure_monolettre,
            "doc": doc,
            "fenetres": fenetres_calc,
            "paires_all": paires_all,
            "paires_freq": paires_freq,
            "df_paires": df_paires,
            "g2_scores": g2_scores,
            "pvals": pvals,
            "df_llr_all": df_llr_all,
        }

    st.success("Calcul terminé. Vous pouvez ajuster les seuils / Top-K sans recalculer.")

# ================================
# AFFICHAGE À PARTIR DE LA SESSION
# ================================
res = st.session_state.get("res")
if not res:
    st.info("Configurez vos paramètres puis cliquez sur **Calculer les cooccurrences**.")
    st.stop()

fenetre_saved   = res["fenetre"]
k_saved         = res.get("k", 5)
stopset_saved   = res.get("stopset", set())
excl_num_saved  = res.get("exclure_nombres", True)
excl_mono_saved = res.get("exclure_monolettre", True)

# ---------------------------------------------------------
# MODE DOCUMENT
# ---------------------------------------------------------
if res.get("mode_document", False):
    st.markdown(f"<h2 style='color:#e63946'>Mode Document — Fenêtre : {fenetre_saved}</h2>", unsafe_allow_html=True)

    for i, docres in enumerate(res["docs"], start=1):
        nom = docres["nom"]
        doc_saved = docres["doc"]
        paires_all = docres["paires_all"]
        paires_freq = docres["paires_freq"]
        df_paires = docres["df_paires"]
        g2_scores = docres["g2_scores"]
        pvals = docres["pvals"]
        df_llr_all = docres["df_llr_all"]
        texte = docres["texte"]

        st.markdown(
            f"<div style='background:#1d3557;color:#ffffff;padding:10px 14px;border-radius:8px;margin:14px 0;font-weight:600'>"
            f"Document {i} — {html.escape(nom)}</div>",
            unsafe_allow_html=True
        )

        # ---------- FRÉQUENCE ----------
        st.markdown(f"<h4 style='color:#e63946'>Table des cooccurrences retenues (fréquence) — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        st.dataframe(df_paires.head(3000), use_container_width=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", nom)
        st.download_button("Télécharger le CSV (paires filtrées)",
                           data=generer_csv(df_paires).getvalue(),
                           file_name=f"cooccurrences_filtrees_{safe_name}.csv",
                           mime="text/csv",
                           key=f"dl_csv_pairs_{i}")

        noeuds = set()
        for (a, b) in paires_freq.keys():
            noeuds.add(a); noeuds.add(b)
        E = len(paires_freq); V = len(noeuds)
        densite = 0.0 if V < 2 else (2 * E) / (V * (V - 1))
        st.write(f"Nœuds : {V} — Arêtes : {E} — Densité ≈ {densite:.3f}")

        st.markdown(f"<h4 style='color:#e63946'>Graphe global (pondéré par la fréquence) — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        html_global = pyvis_reseau_global_html_couleur(paires_freq, edge_label_size=10)
        st_html(html_global, height=900, scrolling=True)
        st.download_button("Télécharger le graphe (HTML)",
                           data=html_global.encode("utf-8"),
                           file_name=f"graphe_cooccurrences_{safe_name}.html",
                           mime="text/html",
                           key=f"dl_graph_freq_html_{i}")

        png_graphe = generer_png_graphe_stat(paires_freq, largeur_px=1600, hauteur_px=1000, dpi=100)
        if png_graphe:
            st.download_button("Télécharger le graphe (PNG 1600px)",
                               data=png_graphe,
                               file_name=f"graphe_cooccurrences_{safe_name}.png",
                               mime="image/png",
                               key=f"dl_graph_freq_png_{i}")

        # === Nuage fréquence ===
        st.markdown(f"<h4 style='color:#e63946'>Nuage des cooccurrences (fréquence) — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        pairs_freq_for_cloud = {f"{a}_{b}": int(w) for (a, b), w in paires_all.items()}
        pairs_freq_for_cloud = {k: v for k, v in pairs_freq_for_cloud.items() if v > 0}
        if pairs_freq_for_cloud:
            items_pairs = sorted(pairs_freq_for_cloud.items(), key=lambda x: x[1], reverse=True)[:int(top_k_freq_pairs)]
            generer_nuage_mots(dict(items_pairs), f"Top {int(top_k_freq_pairs)} — cooccurrences par fréquence — Fenêtre : {fenetre_saved} — {nom}")
            if st.session_state.get("nuage_png"):
                st.download_button(
                    label="Télécharger le nuage cooccurrences (fréquence) — PNG",
                    data=st.session_state["nuage_png"],
                    file_name=f"nuage_cooccurrences_paires_frequence_{safe_name}.png",
                    mime="image/png",
                    key=f"dl_cloud_freq_{i}"
                )
        else:
            st.info("Nuage non généré (aucune paire).")

        # ---------- CONCORDANCIER (FRÉQUENCE) ----------
        st.markdown(f"<h4 style='color:#e63946'>Concordancier global (fréquence) — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        st.markdown("Aperçu limité aux **10 premières phrases** (toutes paires confondues).")

        sections_full = []
        all_lines_for_preview = []
        paires_triees = sorted(paires_freq.items(), key=lambda x: x[1], reverse=True)

        if fenetre_saved == "Phrase":
            sent_infos = [(sent, set(iter_tokens_normalises_global(sent, stopset_saved, excl_num_saved, excl_mono_saved)))
                          for sent in doc_saved.sents]
            for (w1, w2), w in paires_triees:
                titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (f={int(w)})"
                lignes = []
                for sent, sset in sent_infos:
                    if w1 in sset and w2 in sset:
                        h = surligner_phrase_paire(sent, w1, w2)
                        lignes.append(h)
                        all_lines_for_preview.append((titre_pair, h))
                if lignes:
                    sections_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

        elif fenetre_saved == "Mots (±k)":
            for (w1, w2), w in paires_triees:
                titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (f={int(w)})"
                lignes = kwic_mots_pm_k(doc_saved, stopset_saved, excl_num_saved, excl_mono_saved,
                                        w1=w1, w2=w2, k=int(k_saved), marge=5)
                for h in lignes:
                    all_lines_for_preview.append((titre_pair, h))
                if lignes:
                    sections_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

        else:  # Paragraphe
            paras = segmenter_paragraphes(texte)
            para_infos = []
            for pa in paras:
                d = nlp(pa)
                sset = set(iter_tokens_normalises_global(d, stopset_saved, excl_num_saved, excl_mono_saved))
                para_infos.append((pa, sset))
            for (w1, w2), w in paires_triees:
                titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (f={int(w)})"
                lignes = []
                for pa, sset in para_infos:
                    if w1 in sset and w2 in sset:
                        h = surligner_paragraphe_paire(pa, w1, w2)
                        lignes.append(h)
                        all_lines_for_preview.append((titre_pair, h))
                if lignes:
                    sections_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

        if not all_lines_for_preview:
            st.info("Aucun extrait trouvé pour le concordancier avec les options actuelles.")
        else:
            apercu_parts = []
            for titre_pair, ligne in all_lines_for_preview[:10]:
                apercu_parts.append(f"<h3>{titre_pair}</h3>{ligne}")
            st.markdown("\n".join(apercu_parts), unsafe_allow_html=True)

            st.markdown("&nbsp;", unsafe_allow_html=True)
            doc_html_freq = document_html_kwic(f"Concordancier — cooccurrences (fréquence) — Fenêtre : {fenetre_saved} — {nom}", sections_full)
            st.download_button("Télécharger le concordancier complet (HTML)",
                               data=doc_html_freq.encode("utf-8"),
                               file_name=f"concordancier_frequence_complet_{safe_name}.html",
                               mime="text/html",
                               key=f"dl_kwic_freq_{i}")

        # ---------- LIKELIHOOD ----------
        st.markdown(f"<h4 style='color:#e63946'>Approche par log-likelihood — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        st.markdown("Filtrer par p ≤ α si nécessaire.")

        df_llr = df_llr_all.copy()
        if activer_filtre_p:
            df_llr = df_llr[df_llr["p_value"] <= float(alpha)]
        info_filtre = f"(filtré p ≤ {alpha})" if activer_filtre_p else "(sans filtre p)"
        df_llr.sort_values(["log_likelihood", "frequence"], ascending=[False, False], inplace=True)

        st.markdown(f"Table des paires triées par **log-likelihood décroissant** {info_filtre}.")
        df_llr_display = df_llr.copy()
        df_llr_display["p_value"] = df_llr_display["p_value"].apply(lambda p: "< 0.000001" if p < 1e-6 else f"{p:.6f}")
        st.dataframe(df_llr_display.head(3000), use_container_width=True)

        st.download_button("Télécharger le CSV (log-likelihood + p-valeur)",
                           data=generer_csv(df_llr).getvalue(),
                           file_name=f"cooccurrences_likelihood_p_{safe_name}.csv",
                           mime="text/csv",
                           key=f"dl_llr_csv_{i}")

        llr_for_graph = {(r.mot1, r.mot2): float(r.log_likelihood) for _, r in df_llr.iterrows()}
        p_for_graph   = {(r.mot1, r.mot2): float(r.p_value)        for _, r in df_llr.iterrows()}
        alpha_used = float(alpha) if activer_filtre_p else None

        html_llr = pyvis_graphe_likelihood_html(llr_for_graph, p_for_graph, seuil_llr=float(seuil_llr_graphe), alpha=alpha_used)
        st.markdown(f"<h4 style='color:#e63946'>Graphe basé sur le likelihood — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        st_html(html_llr, height=900, scrolling=True)
        st.download_button("Télécharger le graphe likelihood (HTML)",
                           data=html_llr.encode("utf-8"),
                           file_name=f"graphe_likelihood_{safe_name}.html",
                           mime="text/html",
                           key=f"dl_llr_html_{i}")

        # === Nuage LLR ===
        st.markdown(f"<h4 style='color:#e63946'>Nuage des cooccurrences (log-likelihood) — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        pairs_llr_for_cloud = {f"{a}_{b}": float(g2_scores[(a, b)]) for (a, b) in g2_scores.keys()}
        pairs_llr_for_cloud = {k: v for k, v in pairs_llr_for_cloud.items() if v > 0}
        if pairs_llr_for_cloud:
            items_pairs_llr = sorted(pairs_llr_for_cloud.items(), key=lambda x: x[1], reverse=True)[:int(top_k_llr_cloud)]
            generer_nuage_mots(dict(items_pairs_llr), f"Top {int(top_k_llr_cloud)} — cooccurrences par loglikelihood (non filtré) — Fenêtre : {fenetre_saved} — {nom}")
            if st.session_state.get("nuage_png"):
                st.download_button(
                    label="Télécharger le nuage cooccurrences (log-likelihood) — PNG",
                    data=st.session_state["nuage_png"],
                    file_name=f"nuage_cooccurrences_paires_loglikelihood_{safe_name}.png",
                    mime="image/png",
                    key=f"dl_cloud_llr_{i}"
                )
        else:
            st.info("Nuage non généré : tous les log-likelihood sont nuls.")

        # ---------- CONCORDANCIER (LLR) ----------
        st.markdown(f"<h4 style='color:#e63946'>Concordancier — meilleures associations (log-likelihood) — Fenêtre : {fenetre_saved}</h4>", unsafe_allow_html=True)
        st.markdown("Aperçu limité aux **10 premières phrases** (toutes paires confondues).")

        sections_llr_full = []
        all_lines_llr_preview = []
        pairs_llr_sorted = [((r.mot1, r.mot2), float(r.log_likelihood), float(r.p_value)) for _, r in df_llr.iterrows()]
        pairs_llr_sorted.sort(key=lambda x: x[1], reverse=True)

        if fenetre_saved == "Phrase":
            sent_infos = [(sent, set(iter_tokens_normalises_global(sent, stopset_saved, excl_num_saved, excl_mono_saved)))
                          for sent in doc_saved.sents]
            for (w1, w2), s, p in pairs_llr_sorted:
                p_txt = "< 0.000001" if p < 1e-6 else f"{p:.6f}"
                titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (log-likelihood={s:.6f}; p={p_txt})"
                lignes = []
                for sent, sset in sent_infos:
                    if w1 in sset and w2 in sset:  # <-- FIX and (pas "et")
                        h = surligner_phrase_paire(sent, w1, w2)
                        lignes.append(h)
                        all_lines_llr_preview.append((titre_pair, h))
                if lignes:
                    sections_llr_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

        elif fenetre_saved == "Mots (±k)":
            for (w1, w2), s, p in pairs_llr_sorted:
                p_txt = "< 0.000001" if p < 1e-6 else f"{p:.6f}"
                titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (log-likelihood={s:.6f}; p={p_txt})"
                lignes = kwic_mots_pm_k(doc_saved, stopset_saved, excl_num_saved, excl_mono_saved,
                                        w1=w1, w2=w2, k=int(k_saved), marge=5)
                for h in lignes:
                    all_lines_llr_preview.append((titre_pair, h))
                if lignes:
                    sections_llr_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

        else:  # Paragraphe
            paras = segmenter_paragraphes(texte)
            para_infos = []
            for pa in paras:
                d = nlp(pa)
                sset = set(iter_tokens_normalises_global(d, stopset_saved, excl_num_saved, excl_mono_saved))
                para_infos.append((pa, sset))
            for (w1, w2), s, p in pairs_llr_sorted:
                p_txt = "< 0.000001" if p < 1e-6 else f"{p:.6f}"
                titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (log-likelihood={s:.6f}; p={p_txt})"
                lignes = []
                for pa, sset in para_infos:
                    if w1 in sset and w2 in sset:
                        h = surligner_paragraphe_paire(pa, w1, w2)
                        lignes.append(h)
                        all_lines_llr_preview.append((titre_pair, h))
                if lignes:
                    sections_llr_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

        if not all_lines_llr_preview:
            st.info("Aucun extrait trouvé pour le concordancier likelihood avec les options actuelles.")
        else:
            apercu_llr = []
            for titre_pair, ligne in all_lines_llr_preview[:10]:
                apercu_llr.append(f"<h3>{titre_pair}</h3>{ligne}")
            st.markdown("\n".join(apercu_llr), unsafe_allow_html=True)

            st.markdown("&nbsp;", unsafe_allow_html=True)
            doc_html_llr = document_html_kwic(f"Concordancier — log-likelihood (complet) — Fenêtre : {fenetre_saved} — {nom}", sections_llr_full)
            st.download_button("Télécharger le concordancier likelihood complet (HTML)",
                               data=doc_html_llr.encode("utf-8"),
                               file_name=f"concordancier_likelihood_complet_{safe_name}.html",
                               mime="text/html",
                               key=f"dl_kwic_llr_{i}")

# ---------------------------------------------------------
# MODE CLASSIQUE
# ---------------------------------------------------------
else:
    texte        = res["texte"]
    doc_saved    = res["doc"]
    fenetres     = res["fenetres"]
    paires_all   = res["paires_all"]
    paires_freq  = res["paires_freq"]
    df_paires    = res["df_paires"]
    g2_scores    = res["g2_scores"]
    pvals        = res["pvals"]
    df_llr_all   = res["df_llr_all"]

    st.markdown(f"<h3 style='color:#e63946'>Table des cooccurrences retenues (fréquence) — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    st.dataframe(df_paires.head(3000), use_container_width=True)
    st.download_button("Télécharger le CSV (paires filtrées)", data=generer_csv(df_paires).getvalue(),
                       file_name="cooccurrences_filtrees.csv", mime="text/csv")

    noeuds = set()
    for (a, b) in paires_freq.keys():
        noeuds.add(a); noeuds.add(b)
    E = len(paires_freq); V = len(noeuds)
    densite = 0.0 if V < 2 else (2 * E) / (V * (V - 1))
    st.write(f"Nœuds : {V} — Arêtes : {E} — Densité ≈ {densite:.3f}")

    st.markdown(f"<h3 style='color:#e63946'>Graphe global (pondéré par la fréquence) — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    html_global = pyvis_reseau_global_html_couleur(paires_freq, edge_label_size=10)
    st_html(html_global, height=900, scrolling=True)
    st.download_button("Télécharger le graphe (HTML)", data=html_global.encode("utf-8"),
                       file_name="graphe_cooccurrences.html", mime="text/html")

    png_graphe = generer_png_graphe_stat(paires_freq, largeur_px=1600, hauteur_px=1000, dpi=100)
    if png_graphe:
        st.download_button("Télécharger le graphe (PNG 1600px)", data=png_graphe,
                           file_name="graphe_cooccurrences.png", mime="image/png")

    st.markdown(f"<h3 style='color:#e63946'>Nuage des cooccurrences (fréquence) — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    pairs_freq_for_cloud = {f"{a}_{b}": int(w) for (a, b), w in paires_all.items()}
    pairs_freq_for_cloud = {k: v for k, v in pairs_freq_for_cloud.items() if v > 0}
    if pairs_freq_for_cloud:
        items_pairs = sorted(pairs_freq_for_cloud.items(), key=lambda x: x[1], reverse=True)[:int(top_k_freq_pairs)]
        generer_nuage_mots(dict(items_pairs), f"Top {int(top_k_freq_pairs)} — cooccurrences par fréquence — Fenêtre : {fenetre_saved}")
        if st.session_state.get("nuage_png"):
            st.download_button(
                label="Télécharger le nuage cooccurrences (fréquence) — PNG",
                data=st.session_state["nuage_png"],
                file_name="nuage_cooccurrences_paires_frequence.png",
                mime="image/png"
            )
    else:
        st.info("Nuage non généré (aucune paire).")

    st.markdown(f"<h3 style='color:#e63946'>Concordancier global (fréquence) — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    st.markdown("Aperçu limité aux **10 premières phrases** (toutes paires confondues).")

    sections_full = []
    all_lines_for_preview = []
    paires_triees = sorted(paires_freq.items(), key=lambda x: x[1], reverse=True)

    if fenetre_saved == "Phrase":
        sent_infos = [(sent, set(iter_tokens_normalises_global(sent, stopset_saved, excl_num_saved, excl_mono_saved)))
                      for sent in doc_saved.sents]
        for (w1, w2), w in paires_triees:
            titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (f={int(w)})"
            lignes = []
            for sent, sset in sent_infos:
                if w1 in sset and w2 in sset:
                    h = surligner_phrase_paire(sent, w1, w2)
                    lignes.append(h)
                    all_lines_for_preview.append((titre_pair, h))
            if lignes:
                sections_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

    elif fenetre_saved == "Mots (±k)":
        for (w1, w2), w in paires_triees:
            titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (f={int(w)})"
            lignes = kwic_mots_pm_k(doc_saved, stopset_saved, excl_num_saved, excl_mono_saved,
                                    w1=w1, w2=w2, k=int(k_saved), marge=5)
            for h in lignes:
                all_lines_for_preview.append((titre_pair, h))
            if lignes:
                sections_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

    else:  # Paragraphe
        paras = segmenter_paragraphes(texte)
        para_infos = []
        for pa in paras:
            d = nlp(pa)
            sset = set(iter_tokens_normalises_global(d, stopset_saved, excl_num_saved, excl_mono_saved))
            para_infos.append((pa, sset))
        for (w1, w2), w in paires_triees:
            titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (f={int(w)})"
            lignes = []
            for pa, sset in para_infos:
                if w1 in sset and w2 in sset:
                    h = surligner_paragraphe_paire(pa, w1, w2)
                    lignes.append(h)
                    all_lines_for_preview.append((titre_pair, h))
            if lignes:
                sections_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

    if not all_lines_for_preview:
        st.info("Aucun extrait trouvé pour le concordancier avec les options actuelles.")
    else:
        apercu_parts = []
        for titre_pair, ligne in all_lines_for_preview[:10]:
            apercu_parts.append(f"<h3>{titre_pair}</h3>{ligne}")
        st.markdown("\n".join(apercu_parts), unsafe_allow_html=True)

        st.markdown("&nbsp;", unsafe_allow_html=True)
        doc_html_freq = document_html_kwic(f"Concordancier global — cooccurrences (fréquence) — Fenêtre : {fenetre_saved}", sections_full)
        st.download_button("Télécharger le concordancier complet (HTML)",
                           data=doc_html_freq.encode("utf-8"),
                           file_name="concordancier_frequence_complet.html",
                           mime="text/html")

    # ---------- LIKELIHOOD ----------
    st.markdown(f"<h3 style='color:#e63946'>Approche par log-likelihood — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    df_llr = df_llr_all.copy()
    if activer_filtre_p:
        df_llr = df_llr[df_llr["p_value"] <= float(alpha)]
    info_filtre = f"(filtré p ≤ {alpha})" if activer_filtre_p else "(sans filtre p)"
    df_llr.sort_values(["log_likelihood", "frequence"], ascending=[False, False], inplace=True)

    st.markdown(f"Table des paires triées par **log-likelihood décroissant** {info_filtre}.")
    df_llr_display = df_llr.copy()
    df_llr_display["p_value"] = df_llr_display["p_value"].apply(lambda p: "< 0.000001" if p < 1e-6 else f"{p:.6f}")
    st.dataframe(df_llr_display.head(3000), use_container_width=True)

    st.download_button("Télécharger le CSV (log-likelihood + p-valeur)",
                       data=generer_csv(df_llr).getvalue(),
                       file_name="cooccurrences_likelihood_p.csv",
                       mime="text/csv")

    llr_for_graph = {(r.mot1, r.mot2): float(r.log_likelihood) for _, r in df_llr.iterrows()}
    p_for_graph   = {(r.mot1, r.mot2): float(r.p_value)        for _, r in df_llr.iterrows()}
    alpha_used = float(alpha) if activer_filtre_p else None

    html_llr = pyvis_graphe_likelihood_html(llr_for_graph, p_for_graph, seuil_llr=float(seuil_llr_graphe), alpha=alpha_used)
    st.markdown(f"<h3 style='color:#e63946'>Graphe basé sur le likelihood — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    st_html(html_llr, height=900, scrolling=True)
    st.download_button("Télécharger le graphe likelihood (HTML)",
                       data=html_llr.encode("utf-8"),
                       file_name="graphe_likelihood.html",
                       mime="text/html")

    # === Nuage LLR ===
    st.markdown(f"<h3 style='color:#e63946'>Nuage des cooccurrences (log-likelihood) — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    pairs_llr_for_cloud = {f"{a}_{b}": float(g2_scores[(a, b)]) for (a, b) in g2_scores.keys()}
    pairs_llr_for_cloud = {k: v for k, v in pairs_llr_for_cloud.items() if v > 0}
    if pairs_llr_for_cloud:
        items_pairs_llr = sorted(pairs_llr_for_cloud.items(), key=lambda x: x[1], reverse=True)[:int(top_k_llr_cloud)]
        generer_nuage_mots(dict(items_pairs_llr), f"Top {int(top_k_llr_cloud)} — cooccurrences par loglikelihood (non filtré) — Fenêtre : {fenetre_saved}")
        if st.session_state.get("nuage_png"):
            st.download_button(
                label="Télécharger le nuage cooccurrences (log-likelihood) — PNG",
                data=st.session_state["nuage_png"],
                file_name="nuage_cooccurrences_paires_loglikelihood.png",
                mime="image/png"
            )
    else:
        st.info("Nuage non généré : tous les log-likelihood sont nuls.")

    # ---------- CONCORDANCIER (LLR) ----------
    st.markdown(f"<h3 style='color:#e63946'>Concordancier — meilleures associations (log-likelihood) — Fenêtre : {fenetre_saved}</h3>", unsafe_allow_html=True)
    sections_llr_full = []
    all_lines_llr_preview = []
    pairs_llr_sorted = [((r.mot1, r.mot2), float(r.log_likelihood), float(r.p_value)) for _, r in df_llr.iterrows()]
    pairs_llr_sorted.sort(key=lambda x: x[1], reverse=True)

    if fenetre_saved == "Phrase":
        sent_infos = [(sent, set(iter_tokens_normalises_global(sent, stopset_saved, excl_num_saved, excl_mono_saved)))
                      for sent in doc_saved.sents]
        for (w1, w2), s, p in pairs_llr_sorted:
            p_txt = "< 0.000001" if p < 1e-6 else f"{p:.6f}"
            titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (log-likelihood={s:.6f}; p={p_txt})"
            lignes = []
            for sent, sset in sent_infos:
                if w1 in sset and w2 in sset:  # <-- FIX and
                    h = surligner_phrase_paire(sent, w1, w2)
                    lignes.append(h)
                    all_lines_llr_preview.append((titre_pair, h))
            if lignes:
                sections_llr_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

    elif fenetre_saved == "Mots (±k)":
        for (w1, w2), s, p in pairs_llr_sorted:
            p_txt = "< 0.000001" if p < 1e-6 else f"{p:.6f}"
            titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (log-likelihood={s:.6f}; p={p_txt})"
            lignes = kwic_mots_pm_k(doc_saved, stopset_saved, excl_num_saved, excl_mono_saved,
                                    w1=w1, w2=w2, k=int(k_saved), marge=5)
            for h in lignes:
                all_lines_llr_preview.append((titre_pair, h))
            if lignes:
                sections_llr_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

    else:  # Paragraphe
        paras = segmenter_paragraphes(texte)
        para_infos = []
        for pa in paras:
            d = nlp(pa)
            sset = set(iter_tokens_normalises_global(d, stopset_saved, excl_num_saved, excl_mono_saved))
            para_infos.append((pa, sset))
        for (w1, w2), s, p in pairs_llr_sorted:
            p_txt = "< 0.000001" if p < 1e-6 else f"{p:.6f}"
            titre_pair = f"{html.escape(w1)} — {html.escape(w2)} (log-likelihood={s:.6f}; p={p_txt})"
            lignes = []
            for pa, sset in para_infos:
                if w1 in sset and w2 in sset:
                    h = surligner_paragraphe_paire(pa, w1, w2)
                    lignes.append(h)
                    all_lines_llr_preview.append((titre_pair, h))
            if lignes:
                sections_llr_full.append(f"<h2>{titre_pair}</h2>" + "\n".join(lignes))

    if not all_lines_llr_preview:
        st.info("Aucun extrait trouvé pour le concordancier likelihood avec les options actuelles.")
    else:
        apercu_llr = []
        for titre_pair, ligne in all_lines_llr_preview[:10]:
            apercu_llr.append(f"<h3>{titre_pair}</h3>{ligne}")
        st.markdown("\n".join(apercu_llr), unsafe_allow_html=True)

        st.markdown("&nbsp;", unsafe_allow_html=True)
        doc_html_llr = document_html_kwic(f"Concordancier — log-likelihood — Fenêtre : {fenetre_saved}", sections_llr_full)
        st.download_button("Télécharger le concordancier likelihood complet (HTML)",
                           data=doc_html_llr.encode("utf-8"),
                           file_name="concordancier_likelihood_complet.html",
                           mime="text/html")
