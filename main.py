################################################
# Stéphane Meurisse
# www.codeandcortex.fr
# Version beta 1.1
# Date : 27-07-2025
################################################

# python -m streamlit run main.py

# ##########
# pip install streamlit pandas matplotlib worldcloud pyvis scipy
# python -m spacy download fr_core_news_md
############

# Application Streamlit : Analyse des Cooccurrences par à partir d'un mot pivot
#     - 1. Fréquences
#     - 2. log-likelihood


# Log-likelihood : mesure la force des cooccurrences
# Le log-likelihood est une mesure statistique qui sert à tester l’indépendance entre deux mots.

# L'application utilise le modèle medium de SPACY pour traiter les stopsword, les Pos-tag...

# - Affichage des résultats par document : 1) Fréquences, 2) Log-likelihood

# - Choix des paramètres
# - Résultats en dessous (onglets Résultats, (Lexique, Explications = NON DEVELOPPé)).
# - 3 fenêtres au choix : Mots (±k), Phrase (ponctuation), Paragraphe (retour à la ligne).
# - 1 mode document : analyse séparement chaque fichier avec la fenetre "phrase"
# - Stopwords : option spaCy (sans ajout manuel). Nettoyage optionnel des nombres et des mots d’1 lettre.
# - Apostrophes : « c’est » -> « est », « l’homme » -> « homme »
# - le mot pivot n’est jamais filtré.
# - POS affichées dans les tableaux de cooccurrents.
# - Concordanciers : Fréquences et Log-likelihood.
# - Tout est téléchargeables en HTML, csv. png
# - Graphes PyVis : Fréquence Log-likelihood

# ================================
# IMPORTS
# ================================
import io
import re
import html
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from collections import Counter, defaultdict
from wordcloud import WordCloud
import spacy
from scipy.stats import power_divergence
from pyvis.network import Network
from streamlit.components.v1 import html as st_html
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from ticket_gate import enforce_streamlit_access

# ================================
# CHARGEMENT SPACY
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

    # La segmentation en phrases doit rester stable sur le VPS.
    if "sentencizer" not in modele.pipe_names:
        modele.add_pipe(
            "sentencizer",
            config={
                "punct_chars": [".", "!", "?", "…"],
                "overwrite": True,
            },
        )

    return modele


nlp = charger_modele_spacy()

# ================================
# STOPWORDS
# ================================
def construire_stopwords(appliquer_stop: bool):
    """Renvoie l’ensemble des stopwords spaCy si coché, sinon ensemble vide."""
    return set(nlp.Defaults.stop_words) if appliquer_stop else set()

# ================================
# SEGMENTATION PARAGRAPHES
# ================================
def segmenter_paragraphes(texte: str):
    """Paragraphe = bloc séparé par au moins une ligne vide."""
    norm = texte.replace("\r\n", "\n").replace("\r", "\n")
    blocs = re.split(r"\n\s*\n+", norm)
    return [b.strip() for b in blocs if b.strip()]

# ================================
# NORMALISATION (RÈGLE APOSTROPHE)
# ================================
APOS = {"'", "’"}

def normaliser_avec_apostrophe_joint(token_text: str) -> str:
    """Si le token contient une apostrophe, garder la partie à droite (ex. « l'homme » -> « homme »)."""
    if "'" in token_text or "’" in token_text:
        parts = re.split(r"[’']", token_text, maxsplit=1)
        if len(parts) == 2:
            return parts[1]
    return token_text

def iter_tokens_norm_et_carte(doc, stopset, pivot, exclure_nombres, exclure_monolettre):
    """
    Produit deux listes alignées :
      - norm_list : formes normalisées utilisées pour l’analyse,
      - spans_list : paires (start, end_excl) d’indices surface.
    Sert aux comptages et au repérage surface pour les concordanciers.
    """
    norm_list, spans_list = [], []
    toks = list(doc)
    i, n = 0, len(toks)
    while i < n:
        tok = toks[i]
        raw = tok.text
        low = raw.lower()

        # Cas "c ' est" -> garder "est"
        if low.isalpha() and i + 2 < n and toks[i+1].text in APOS:
            droite = toks[i+2].text.lower()
            mot = droite
            if mot == pivot:
                if mot.isalnum():
                    norm_list.append(mot); spans_list.append((i, i+3))
            else:
                if mot.isalnum() and not (exclure_nombres and mot.isdigit()) and not (exclure_monolettre and len(mot) == 1):
                    if mot not in stopset:
                        norm_list.append(mot); spans_list.append((i, i+3))
            i += 3
            continue

        # Cas "l'homme" -> "homme"
        mot = normaliser_avec_apostrophe_joint(raw).lower() if (("'" in raw) or ("’" in raw)) else low

        if mot == pivot:
            if mot.isalnum():
                norm_list.append(mot); spans_list.append((i, i+1))
        else:
            if mot.isalnum() and not (exclure_nombres and mot.isdigit()) and not (exclure_monolettre and len(mot) == 1):
                if mot not in stopset:
                    norm_list.append(mot); spans_list.append((i, i+1))
        i += 1
    return norm_list, spans_list

def iter_tokens_normalises(doc, stopset, pivot, exclure_nombres, exclure_monolettre):
    """Renvoie uniquement la liste normalisée (plus rapide pour les comptages)."""
    norm, _ = iter_tokens_norm_et_carte(doc, stopset, pivot, exclure_nombres, exclure_monolettre)
    return norm

# ================================
# FENÊTRES LINÉAIRES (FRÉQUENCES & LOGLIKE)
# ================================
def fenetres_mots(doc, pivot: str, k: int, stopset, exclure_nombres: bool, exclure_monolettre: bool):
    """Fenêtres ±k autour de chaque pivot (après normalisation/filtrage)."""
    seq = iter_tokens_normalises(doc, stopset, pivot, exclure_nombres, exclure_monolettre)
    indices = [i for i, w in enumerate(seq) if w == pivot]
    fenetres = []
    for idx in indices:
        d = max(0, idx - k); f = min(len(seq), idx + k + 1)
        fen = set(seq[d:f])
        if fen:
            fenetres.append(fen)
    return fenetres, seq

def fenetres_phrases(doc, stopset, pivot, exclure_nombres: bool, exclure_monolettre: bool):
    """Fenêtres = phrases spaCy (après normalisation/filtrage par phrase)."""
    fenetres = []
    for sent in doc.sents:
        seq = iter_tokens_normalises(sent, stopset, pivot, exclure_nombres, exclure_monolettre)
        if seq:
            fenetres.append(set(seq))
    return fenetres

def fenetres_paragraphes(texte: str, stopset, pivot, exclure_nombres: bool, exclure_monolettre: bool):
    """Fenêtres = paragraphes séparés par ligne vide (après normalisation/filtrage)."""
    fenetres = []
    for pa in segmenter_paragraphes(texte):
        d = nlp(pa)
        seq = iter_tokens_normalises(d, stopset, pivot, exclure_nombres, exclure_monolettre)
        if seq:
            fenetres.append(set(seq))
    return fenetres

# ================================
# LOG-LIKELIHOOD (statistique + p-valeur)
# ================================
def loglike_scipy_par_mot(T: int, F1: int, f2: int, a: int):
    """
    Calcule G² et la p-valeur pour une table 2×2 :
    a=O11, b=O12, c=O21, d=O22, avec
    b = F1 - a ; c = f2 - a ; d = T - a - b - c.
    Renvoie (G2, pval). Retourne (0.0, 1.0) si la table est invalide.
    """
    b = F1 - a
    c = f2 - a
    d = T - a - b - c
    if min(a, b, c, d) < 0:
        return 0.0, 1.0
    obs = np.array([[a, b], [c, d]], dtype=float)
    total = obs.sum()
    if total <= 0:
        return 0.0, 1.0
    row_sums = obs.sum(axis=1, keepdims=True)
    col_sums = obs.sum(axis=0, keepdims=True)
    exp = (row_sums @ col_sums) / total
    stat, pval = power_divergence(obs, f_exp=exp, lambda_="log-likelihood", axis=None)
    if not np.isfinite(stat) or not np.isfinite(pval):
        return 0.0, 1.0
    return float(max(stat, 0.0)), float(max(min(pval, 1.0), 0.0))

def compter_loglike_sur_fenetres(fenetres, pivot: str):
    """
    Calcule, pour chaque mot w, le couple (G², p) ainsi que T, F1, F12, F2.
    T = nombre de fenêtres ; F1 = fenêtres contenant le pivot ;
    F2[w] = fenêtres contenant w ; F12[w] = co-présences pivot–w.
    """
    T = len(fenetres)
    if T == 0:
        return {}, {}, 0, 0, {}, Counter()
    F1 = 0
    F2 = Counter()
    F12 = Counter()
    for S in fenetres:
        cp = pivot in S
        if cp:
            F1 += 1
        for w in S:
            F2[w] += 1
            if cp and w != pivot:
                F12[w] += 1
    scores = {}
    pvals = {}
    for w, f2 in F2.items():
        if w == pivot:
            continue
        a = F12[w]  # O11
        g2, p = loglike_scipy_par_mot(T, F1, f2, a)
        scores[w] = g2
        pvals[w] = p
    return scores, pvals, T, F1, dict(F12), F2

# ================================
# UTILITAIRES (POS, CSV, WordCloud, PyVis, Explications POS)
# ================================
def etiqueter_pos_corpus(textes, stopset, pivot, exclure_nombres: bool, exclure_monolettre: bool):
    """POS majoritaire par forme normalisée (cohérent avec l’analyse)."""
    pos_counts = defaultdict(Counter)
    for txt in textes:
        d = nlp(txt)
        norm_list, spans_list = iter_tokens_norm_et_carte(d, stopset, pivot, exclure_nombres, exclure_monolettre)
        toks = list(d)
        for norm, (s_i, _e_i) in zip(norm_list, spans_list):
            pos_counts[norm][toks[s_i].pos_] += 1
    return {w: ctr.most_common(1)[0][0] for w, ctr in pos_counts.items()}

def generer_csv(df):
    """Flux CSV téléchargeable."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf

def generer_wordcloud(freq_dict, titre):
    """Nuage de mots robuste (ignore valeurs ≤ 0)."""
    freq_pos = {w: float(v) for w, v in freq_dict.items() if v and v > 0}
    if not freq_pos:
        st.info("Nuage de mots non généré : aucune valeur strictement positive.")
        return
    wc = WordCloud(width=900, height=450, background_color="white").generate_from_frequencies(freq_pos)
    fig = plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation="bilinear"); plt.axis("off"); plt.title(titre)
    st.pyplot(fig)

def pyvis_reseau_html(pivot: str, poids_dict, titre: str, top_n: int = 30, syntaxique: bool = False, mode_label: str = "freq", edge_label_size: int = 10):
    """Construit un réseau centré sur le pivot et renvoie l'HTML PyVis."""
    net = Network(height="600px", width="100%", directed=False, notebook=False)
    net.barnes_hut()
    net.set_options("""{
      "edges": {"color": {"inherit": false}, "smooth": false},
      "nodes": {"shape": "dot", "scaling": {"min": 10, "max": 50}},
      "physics": {"stabilization": true}
    }""")

    net.add_node(pivot, label=pivot, color="#e63946", title=pivot, value=50)

    cmap = cm.get_cmap("tab10")
    couleurs = [mcolors.rgb2hex(cmap(i % 10)) for i in range(100)]

    items = sorted(poids_dict.items(), key=lambda x: x[1], reverse=True)[:max(1, int(top_n))]
    if not items:
        return "<div>Aucune arête.</div>"

    vals = [float(p) for (_k, p) in items]
    wmin, wmax = min(vals), max(vals)

    def width_scale(v):
        if wmax == wmin:
            return 2
        return 1 + 5 * ((v - wmin) / (wmax - wmin))

    for idx, (w, p) in enumerate(items):
        couleur = couleurs[idx % len(couleurs)]
        net.add_node(w, label=w, title=w, value=20, color=couleur)
        edge_label = f"{int(p)}" if mode_label == "freq" else f"{float(p):.1f}"
        net.add_edge(
            pivot, w,
            value=float(p),
            width=width_scale(float(p)),
            label=edge_label,
            title=edge_label,
            font={"size": edge_label_size}
        )

    return net.generate_html()

# ================================
# TABLE EXPLICATIVE — POS (spaCy/UD)
# ================================
def table_pos_explicative_fr_enrichie() -> pd.DataFrame:
    """POS spaCy/UD : label, définition synthétique (FR), exemple court."""
    data = [
        ("ADJ",   "adjectif modifiant un nom",                    "une hausse économique notable"),
        ("ADP",   "adposition (préposition, postposition)",       "hausse de la fréquentation"),
        ("ADV",   "adverbe modifiant verbe/adj./phrase",          "Paris attire fortement"),
        ("AUX",   "auxiliaire dans les périphrases verbales",     "a été annoncé"),
        ("CCONJ", "conjonction de coordination",                  "tourisme et économie"),
        ("SCONJ", "conjonction de subordination",                 "parce que la demande augmente"),
        ("DET",   "déterminant lié à un nom",                     "la fréquentation"),
        ("INTJ",  "interjection",                                 "oh, quelle affluence"),
        ("NOUN",  "nom commun",                                   "tourisme, fréquentation, hausse"),
        ("PROPN", "nom propre",                                   "Paris, Île-de-France"),
        ("NUM",   "numéral",                                      "plus de 10 millions"),
        ("PART",  "particule grammaticale",                       "ne ... pas"),
        ("PRON",  "pronom",                                       "ils augmentent"),
        ("PUNCT", "ponctuation",                                   "— , . ; :"),
        ("SYM",   "symbole",                                       "%, €"),
        ("VERB",  "verbe lexical",                                 "augmente, progresse"),
        ("X",     "autres/inconnu",                                "token hétéroclite"),
        ("SPACE", "espace (blanc)",                                "espacement")
    ]
    return pd.DataFrame(data, columns=["POS", "Définition (FR)", "Exemple"])

# ================================
# CONCORDANCIER SURFACE (HTML)
# ================================
def phrase_surface_html(sent, pivot, cible, stopset, exclure_nombres, exclure_monolettre):
    """Concordancier « phrase surface » : surlignage PIVOT et CIBLE."""
    toks = list(sent)
    norm_list, spans_list = iter_tokens_norm_et_carte(sent, stopset, pivot, exclure_nombres, exclure_monolettre)
    piv_idx = set(); cib_idx = set()
    for norm, (s_i, e_i) in zip(norm_list, spans_list):
        head = max(e_i - 1, s_i)
        if norm == pivot:
            piv_idx.add(head)
        if cible and norm == cible:
            cib_idx.add(head)
    css = (
        "<style>"
        ".pivot-badge{background:#e63946;color:#fff;border-radius:4px;padding:0 4px}"
        ".cible-badge{background:#1d3557;color:#fff;border-radius:3px;padding:0 2px}"
        ".kwic-sent{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans','Helvetica Neue',Arial;"
        "line-height:1.6;margin:6px 0}"
        "</style>"
    )
    out = []
    for i, tok in enumerate(toks):
        text = html.escape(tok.text_with_ws)
        if i in piv_idx:
            out.append(f"<span class='pivot-badge'>{text}</span>")
        elif i in cib_idx:
            out.append(f"<span class='cible-badge'>{text}</span>")
        else:
            out.append(text)
    return css + f"<div class='kwic-sent'>{''.join(out).strip()}</div>"

def document_html_kwic(titre: str, lignes_html):
    """Document HTML pour téléchargement d’un concordancier."""
    style = (
        "<style>"
        "body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,'Noto Sans','Helvetica Neue',Arial;line-height:1.6;padding:12px}"
        "h3{margin-top:0}"
        ".pivot-badge{background:#e63946;color:#fff;border-radius:4px;padding:0 4px}"
        ".cible-badge{background:#1d3557;color:#fff;border-radius:3px;padding:0 2px}"
        ".kwic-sent{margin:6px 0}"
        ".ligne-phrase{margin:8px 0 4px 0;white-space:nowrap;overflow-x:auto}"
        ".grille-tokens{display:inline-flex;gap:12px;align-items:flex-start}"
        ".token-bloc{display:inline-flex;flex-direction:column;align-items:center}"
        ".mot{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono','Courier New', monospace;font-size:15px;padding:2px 4px;border-bottom:1px solid #bbb;border-radius:3px}"
        ".etiquette{font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono','Courier New', monospace;font-size:12px;color:#444}"
        ".stop{opacity:0.45}"
        ".pivot{background:#e63946;color:#fff}"
        ".cible{background:#1d3557;color:#fff}"
        "</style>"
    )
    corps = "\n".join(lignes_html)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(titre)}</title>{style}</head><body>"
        f"<h3>{html.escape(titre)}</h3>"
        f"{corps}</body></html>"
    )

# ================================
# INTERFACE — TITRE + EXPLICATIONS
# ================================
st.set_page_config(page_title="Cooccurrences mot pivot", layout="centered")
enforce_streamlit_access("cooccurrencesmotpivot", "Cooccurrences mot pivot")
st.markdown("<h1 style='color:#e63946'>Cooccurrences autour d’un mot pivot : fréquences et log-likelihood</h1>", unsafe_allow_html=True)
st.caption("Stéphane Meurisse — Version beta 1.1 - 27/07/2025 \\- [www.codeandcortex.fr](https://www.codeandcortex.fr)")
st.markdown("---")
st.markdown(
    "Cette application analyse les cooccurrences autour d'un mot pivot selon leurs **fréquences brutes** et le **score de log-likelihood**.\n\n"
    "Les fenêtres pour les fréquences et le log-likelihood peuvent être définies en **mots (±k)**, en **phrase** ou en **paragraphe**.\n\n"
    "Le mot pivot n’est jamais filtré. Les stopwords (spaCy), les nombres et les mots d’une lettre peuvent être exclus. "
    "Les formes avec apostrophe sont normalisées en conservant la partie à droite."
)

# ================================
# PARAMÈTRES D’ANALYSE
# ================================
# Important : pour permettre l'analyse multi-documents sans changer les textes d'interface,
# on autorise toujours le dépôt multiple ; en mode classique, les fichiers seront concaténés.
uploaded = st.file_uploader("Fichier texte (.txt)", type=["txt"], accept_multiple_files=True)
texte_libre = st.text_area("Ou collez votre texte ici", height=220)

st.markdown("<h2 style='color:#e63946'>Paramètres d’analyse</h2>", unsafe_allow_html=True)
pivot = st.text_input("Mot pivot (obligatoire)", value="soleil").strip().lower()
# Ajout du mode "Document" dans la liste, sans modifier les textes explicatifs plus haut.
fenetre = st.selectbox("Fenêtre de contexte pour Fréquences et Log-likelihood", ["Mots (±k)", "Phrase", "Paragraphe", "Document"])
k = 5
if fenetre == "Mots (±k)":
    k = st.number_input("Taille de la fenêtre k (mots de contexte)", min_value=1, max_value=100, value=5, step=1)

appliquer_stop = st.checkbox("Appliquer les stopwords (spaCy)", value=True)
exclure_nombres = st.checkbox("Exclure les nombres", value=True)
exclure_monolettre = st.checkbox("Exclure les mots d’une seule lettre", value=True)

# État
if "run_id" not in st.session_state:
    st.session_state["run_id"] = 0
if "analysis_ready" not in st.session_state:
    st.session_state["analysis_ready"] = False

# ================================
# FONCTION D'ANALYSE D'UN TEXTE UNIQUE (réutilisée pour chaque document)
# ================================
def analyser_un_texte(texte: str, fenetre_mode: str, pivot: str, stopset, exclure_nombres: bool, exclure_monolettre: bool, k: int = 5):
    """Analyse complète sur un texte unique, retourne tous les éléments nécessaires à l'affichage."""
    doc = nlp(texte)

    if fenetre_mode == "Mots (±k)":
        fenetres, seq_doc = fenetres_mots(doc, pivot, k, stopset, exclure_nombres, exclure_monolettre)
        total_mots_norm = len(seq_doc)
    elif fenetre_mode == "Phrase":
        fenetres = fenetres_phrases(doc, stopset, pivot, exclure_nombres, exclure_monolettre)
        total_mots_norm = sum(len(iter_tokens_normalises(s, stopset, pivot, exclure_nombres, exclure_monolettre)) for s in doc.sents)
    elif fenetre_mode == "Paragraphe":
        fenetres = fenetres_paragraphes(texte, stopset, pivot, exclure_nombres, exclure_monolettre)
        total_mots_norm = 0
        for pa in segmenter_paragraphes(texte):
            dpa = nlp(pa)
            total_mots_norm += len(iter_tokens_normalises(dpa, stopset, pivot, exclure_nombres, exclure_monolettre))
    else:
        # En mode Document pour un document pris isolément, on adopte des fenêtres = phrases
        fenetres = fenetres_phrases(doc, stopset, pivot, exclure_nombres, exclure_monolettre)
        total_mots_norm = sum(len(iter_tokens_normalises(s, stopset, pivot, exclure_nombres, exclure_monolettre)) for s in doc.sents)

    # Fréquences pivot-centrées (1 par fenêtre où le pivot et w co-apparaissent)
    freq_counter = Counter()
    for S in fenetres:
        if pivot in S:
            for w in S:
                if w != pivot:
                    freq_counter[w] += 1

    # Log-likelihood sur les mêmes fenêtres (scores + p-valeurs)
    scores, pvals, T, F1, F12, F2 = compter_loglike_sur_fenetres(fenetres, pivot)

    # POS pour tableaux
    pos_tags = etiqueter_pos_corpus([texte], stopset, pivot, exclure_nombres, exclure_monolettre)

    # TABLEAU — Fréquences
    df_freq = pd.DataFrame(
        [(w, pos_tags.get(w, ""), int(freq_counter[w]), int(F12.get(w, 0)))
         for w in sorted(freq_counter.keys())],
        columns=["cooccurrent", "pos", "frequence", "fenetres_ensemble"]
    ).sort_values(["frequence", "fenetres_ensemble"], ascending=[False, False]).reset_index(drop=True)

    # TABLEAU — Log-likelihood (avec p-valeur)
    df_ll = pd.DataFrame(
        [(w, pos_tags.get(w, ""), float(scores[w]), float(pvals[w]), int(F12.get(w, 0)))
         for w in sorted([x for x in scores.keys() if x != pivot])]
        , columns=["cooccurrent", "pos", "loglike", "p_value", "fenetres_ensemble"]
    ).sort_values(["loglike", "fenetres_ensemble"], ascending=[False, False]).reset_index(drop=True)

    # Concordanciers : listes de phrases
    sent_spans = list(doc.sents)

    # Statistiques
    nb_phrases = len(sent_spans)
    nb_paragraphes = len(segmenter_paragraphes(texte))
    nb_fenetres = T
    nb_fenetres_avec_pivot = F1
    nb_coocs_uniques_freq = len(df_freq)
    total_coocs_freq = int(df_freq["frequence"].sum())
    nb_coocs_uniques_ll = len(df_ll)

    return {
        "doc": doc,
        "sent_spans": sent_spans,
        "df_freq": df_freq,
        "df_ll": df_ll,
        "pos_tags": pos_tags,
        "stats": {
            "total_mots_norm": int(total_mots_norm),
            "nb_phrases": int(nb_phrases),
            "nb_paragraphes": int(nb_paragraphes),
            "nb_fenetres": int(nb_fenetres),
            "nb_fenetres_avec_pivot": int(nb_fenetres_avec_pivot),
            "nb_coocs_uniques_freq": int(nb_coocs_uniques_freq),
            "total_coocs_freq": int(total_coocs_freq),
            "nb_coocs_uniques_ll": int(nb_coocs_uniques_ll),
        },
        "fenetres": fenetres  # pour agrégation éventuelle
    }

# ================================
# ANALYSE
# ================================
if st.button("Lancer l’analyse"):
    if not pivot:
        st.error("Veuillez saisir un mot pivot."); st.stop()

    stopset = construire_stopwords(appliquer_stop)

    # Gestion des fichiers/texte
    textes_list = []
    noms_list = []

    if uploaded:
        # uploaded peut être une liste (multi-fichiers) ou un seul élément
        if isinstance(uploaded, list):
            for f in uploaded:
                try:
                    contenu = f.read().decode("utf-8", errors="ignore")
                except Exception:
                    contenu = f.read().decode("latin-1", errors="ignore")
                if contenu and contenu.strip():
                    textes_list.append(contenu)
                    noms_list.append(f.name)
        else:
            try:
                contenu = uploaded.read().decode("utf-8", errors="ignore")
            except Exception:
                contenu = uploaded.read().decode("latin-1", errors="ignore")
            if contenu and contenu.strip():
                textes_list.append(contenu)
                noms_list.append(uploaded.name)

    if not textes_list and texte_libre and texte_libre.strip():
        textes_list.append(texte_libre)
        noms_list.append("texte_libre.txt")

    if fenetre == "Document":
        if not textes_list:
            st.error("Mode Document : déposez au moins un fichier .txt ou collez un texte."); st.stop()

        resultats_docs = []
        # Analyse indépendante de chaque document (fenêtres internes choisies comme dans analyser_un_texte)
        for nom, txt in zip(noms_list, textes_list):
            res = analyser_un_texte(txt, "Document", pivot, stopset, exclure_nombres, exclure_monolettre, k)
            res["nom"] = nom
            res["texte"] = txt
            resultats_docs.append(res)

        # Agrégation simple pour les statistiques globales
        total_mots_norm = sum(r["stats"]["total_mots_norm"] for r in resultats_docs)
        nb_phrases = sum(r["stats"]["nb_phrases"] for r in resultats_docs)
        nb_paragraphes = sum(r["stats"]["nb_paragraphes"] for r in resultats_docs)

        # Agrégation des fenêtres pour un aperçu global (concaténation des fenêtres de chaque doc)
        fenetres_globales = []
        for r in resultats_docs:
            fenetres_globales.extend(r["fenetres"])

        # Comptage global pour renseigner les chiffres de synthèse
        scores_g, pvals_g, T_g, F1_g, F12_g, F2_g = compter_loglike_sur_fenetres(fenetres_globales, pivot)
        freq_counter_g = Counter()
        for S in fenetres_globales:
            if pivot in S:
                for w in S:
                    if w != pivot:
                        freq_counter_g[w] += 1

        df_freq_g = pd.DataFrame(
            [(w, int(freq_counter_g[w]), int(F12_g.get(w, 0))) for w in sorted(freq_counter_g.keys())],
            columns=["cooccurrent", "frequence", "fenetres_ensemble"]
        )
        df_ll_g = pd.DataFrame(
            [(w, float(scores_g[w]), float(pvals_g[w]), int(F12_g.get(w, 0))) for w in sorted([x for x in scores_g.keys() if x != pivot])],
            columns=["cooccurrent", "loglike", "p_value", "fenetres_ensemble"]
        )

        nb_coocs_uniques_freq = int(len(df_freq_g))
        total_coocs_freq = int(df_freq_g["frequence"].sum()) if not df_freq_g.empty else 0
        nb_coocs_uniques_ll = int(len(df_ll_g))

        # Lexique global
        pos_map_global = etiqueter_pos_corpus(textes_list, stopset, pivot, exclure_nombres, exclure_monolettre)
        df_lex_formes = pd.DataFrame(sorted([(w, pos_map_global.get(w, "")) for w in pos_map_global.keys()], key=lambda x: x[0]),
                                     columns=["forme_norm", "pos"])
        df_pos_exp = table_pos_explicative_fr_enrichie()

        st.session_state["run_id"] += 1
        st.session_state["analysis_ready"] = True
        st.session_state["mode_document"] = True
        st.session_state["fenetre_mode"] = "Document"  # <— mémorise le mode pour l’affichage des titres
        st.session_state["pivot"] = pivot
        st.session_state["docs"] = resultats_docs
        st.session_state["stopset"] = stopset
        st.session_state["excl_num"] = exclure_nombres
        st.session_state["excl_1"] = exclure_monolettre
        st.session_state["df_lex_formes"] = df_lex_formes
        st.session_state["df_pos_exp"] = df_pos_exp
        st.session_state["stats"] = {
            "nb_documents": int(len(resultats_docs)),
            "total_mots_norm": int(total_mots_norm),
            "nb_phrases": int(nb_phrases),
            "nb_paragraphes": int(nb_paragraphes),
            "nb_fenetres": int(T_g),
            "nb_fenetres_avec_pivot": int(F1_g),
            "nb_coocs_uniques_freq": int(nb_coocs_uniques_freq),
            "total_coocs_freq": int(total_coocs_freq),
            "nb_coocs_uniques_ll": int(nb_coocs_uniques_ll),
        }

    else:
        # Modes Mots/Phrase/Paragraphe : si plusieurs fichiers sont déposés, ils sont concaténés
        if not textes_list:
            st.error("Veuillez fournir un texte."); st.stop()
        texte_unique = "\n\n".join(textes_list)

        res = analyser_un_texte(texte_unique, fenetre, pivot, stopset, exclure_nombres, exclure_monolettre, k)

        st.session_state["run_id"] += 1
        st.session_state["analysis_ready"] = True
        st.session_state["mode_document"] = False
        st.session_state["fenetre_mode"] = fenetre  # <— mémorise le mode pour l’affichage des titres
        st.session_state["pivot"] = pivot
        st.session_state["df_freq"] = res["df_freq"]
        st.session_state["df_ll_full"] = res["df_ll"]
        st.session_state["sent_spans"] = res["sent_spans"]
        st.session_state["stopset"] = stopset
        st.session_state["excl_num"] = exclure_nombres
        st.session_state["excl_1"] = exclure_monolettre
        st.session_state["stats"] = res["stats"]
        pos_map = res["pos_tags"]
        st.session_state["df_lex_formes"] = pd.DataFrame(sorted([(w, pos_map.get(w, "")) for w in pos_map.keys()], key=lambda x: x[0]),
                                                         columns=["forme_norm", "pos"])
        st.session_state["df_pos_exp"] = table_pos_explicative_fr_enrichie()

# ================================
# AFFICHAGE RÉSULTATS + ONGLETS
# ================================
if st.session_state.get("analysis_ready", False):

    ong_res, ong_lex, ong_exp = st.tabs(["Résultats", "Lexique", "Explications"])

    with ong_res:
        mode_label = "Document" if st.session_state.get("mode_document", False) else st.session_state.get("fenetre_mode", "")
        st.markdown(f"<h2 style='color:#e63946'>Statistiques de l’analyse — Mode : {mode_label}</h2>", unsafe_allow_html=True)
        s = st.session_state["stats"]

        # Afficher le nombre de documents uniquement en mode Document
        if st.session_state.get("mode_document", False):
            st.write(f"Nombre de documents : {s.get('nb_documents', len(st.session_state.get('docs', [])))}\n\n")

        st.write(
            f"Nombre de mots normalisés conservés : {s['total_mots_norm']}\n\n"
            f"Nombre de phrases : {s['nb_phrases']}\n\n"
            f"Nombre de paragraphes : {s['nb_paragraphes']}\n\n"
            f"Nombre total de fenêtres (linéaires) : {s['nb_fenetres']}\n\n"
            f"Fenêtres contenant le pivot (F1) : {s['nb_fenetres_avec_pivot']}\n\n"
            f"Cooccurrents uniques (Fréquences) : {s['nb_coocs_uniques_freq']}\n\n"
            f"Total des cooccurrences (Fréquences) : {s['total_coocs_freq']}\n\n"
            f"Cooccurrents uniques (Log-likelihood) : {s['nb_coocs_uniques_ll']}"
        )

        pivot_cc = st.session_state["pivot"]
        stopset_cc = st.session_state["stopset"]
        excl_num = st.session_state["excl_num"]
        excl_1 = st.session_state["excl_1"]

        if st.session_state.get("mode_document", False):
            # Affichage répété pour chaque document, avec les mêmes textes/sections
            for i, docres in enumerate(st.session_state["docs"], start=1):
                st.markdown(f"<h3 style='color:#e63946'>Document {i} — {docres['nom']} — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                sent_spans = docres["sent_spans"]

                st.markdown(f"<h2 style='color:#e63946'>1 — Fréquences à partir du mot pivot — Mode : {mode_label}</h1>", unsafe_allow_html=True)
                st.markdown(
                    "Ici, on analyse simplement les **cooccurrences récurrentes**, c’est-à-dire les mots qui apparaissent souvent "
                    "dans le même contexte que le pivot.\n\n"
                    "Plus la fréquence est élevée, plus cela indique que ces mots sont régulièrement associés dans le texte.\n\n"
                    "Cette approche ne dit pas si l’association est due au hasard ou non : elle permet surtout d’observer "
                    "les répétitions les plus visibles dans un corpus."
                )
                st.caption("frequence = nombre de fenêtres où pivot et mot co-apparaissent ; fenetres_ensemble = nombre de fenêtres contenant simultanément pivot et mot.")

                df_freq_doc = docres["df_freq"]
                st.dataframe(df_freq_doc, use_container_width=True)
                st.download_button(
                    label=f"Télécharger le CSV (Fréquences — {docres['nom']})",
                    data=generer_csv(df_freq_doc).getvalue(),
                    file_name=f"cooccurrences_frequences_{re.sub(r'[^A-Za-z0-9_.-]+','_', docres['nom'])}.csv",
                    mime="text/csv",
                    key=f"dl_csv_freq_{st.session_state['run_id']}_{i}"
                )

                st.markdown(f"<h3 style='color:#e63946'>Nuage de cooccurrences — pondéré par la fréquence — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                st.caption("Chaque élément du nuage est une paire `pivot_voisin` ; poids = nombre de fenêtres où les deux co-apparaissent.")
                top_n_freq = st.number_input(
                    f"Top N (fréquences) — {docres['nom']}", min_value=1, max_value=500, value=10, step=1,
                    key=f"top_wc_freq_{st.session_state['run_id']}_{i}"
                )
                df_top_freq = (
                    df_freq_doc[df_freq_doc["frequence"] > 0]
                    .sort_values(["frequence", "fenetres_ensemble"], ascending=[False, False])
                    .head(int(top_n_freq))
                )
                wc_freq_data = {f"{pivot_cc}_{w}": int(freq)
                                for w, freq in zip(df_top_freq["cooccurrent"], df_top_freq["frequence"])}
                generer_wordcloud(wc_freq_data, f"{docres['nom']} — Top {int(top_n_freq)} cooccurrences (fréquence)")

                # --- téléchargement du nuage en PNG (fréquences, par document)
                wc_png = io.BytesIO()
                from wordcloud import WordCloud

                fig_wc = plt.figure(figsize=(10, 5))
                wc_obj = WordCloud(width=900, height=450, background_color="white").generate_from_frequencies(
                    {k: float(v) for k, v in wc_freq_data.items() if float(v) > 0}
                )
                plt.imshow(wc_obj, interpolation="bilinear");
                plt.axis("off")
                plt.title(f"{docres['nom']} — Top {int(top_n_freq)} cooccurrences (fréquence)")
                fig_wc.savefig(wc_png, format="png", dpi=180, bbox_inches="tight")
                plt.close(fig_wc)
                wc_png.seek(0)
                st.download_button(
                    label=f"Télécharger le nuage (PNG) — {docres['nom']}",
                    data=wc_png,
                    file_name=f"nuage_frequence_{re.sub(r'[^A-Za-z0-9_.-]+', '_', docres['nom'])}_top{int(top_n_freq)}.png",
                    mime="image/png",
                    key=f"dl_wc_freq_png_{st.session_state['run_id']}_{i}"
                )

                st.markdown(f"<h3 style='color:#e63946'>Graphe interactif — cooccurrences (fréquence) — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                n_edges_freq = st.number_input(
                    f"Nombre d’arêtes (Top-N) – fréquence — {docres['nom']}",
                    min_value=1, max_value=200, value=30, step=1, key=f"nedges_freq_{st.session_state['run_id']}_{i}"
                )
                poids_freq = dict(zip(df_freq_doc["cooccurrent"], df_freq_doc["frequence"]))
                html_freq = pyvis_reseau_html(pivot_cc, poids_freq, f"Réseau — Fréquence — {docres['nom']}", top_n=int(n_edges_freq), syntaxique=False, mode_label="freq", edge_label_size=11)
                st_html(html_freq, height=620, scrolling=True)

                st.markdown(f"<h3 style='color:#e63946'>Concordancier — à partir des fréquences — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                coocs_list_freq = list(df_freq_doc["cooccurrent"])
                if coocs_list_freq:
                    cible_freq = st.selectbox(
                        f"Cooccurrent (Fréquences) — {docres['nom']}",
                        coocs_list_freq, index=0, key=f"cc_freq_{st.session_state['run_id']}_{i}"
                    )
                    nb_max_freq = st.number_input(
                        f"Nombre maximum de phrases — {docres['nom']}",
                        min_value=1, max_value=5000, value=200, step=10, key=f"nbmax_freq_{st.session_state['run_id']}_{i}"
                    )
                    lignes_html_freq = []; n_aff = 0
                    for sent in sent_spans:
                        nlist = iter_tokens_normalises(sent, stopset_cc, pivot_cc, excl_num, excl_1)
                        sset = set(nlist)
                        if pivot_cc in sset and cible_freq in sset:
                            lignes_html_freq.append(phrase_surface_html(sent, pivot_cc, cible_freq, stopset_cc, excl_num, excl_1))
                            n_aff += 1
                            if n_aff >= int(nb_max_freq):
                                break
                    if not lignes_html_freq:
                        st.info("Aucune phrase trouvée pour ce cooccurrent.")
                    else:
                        st.markdown("\n".join(lignes_html_freq), unsafe_allow_html=True)
                        doc_html = document_html_kwic(
                            f"Concordancier — Fréquences — {docres['nom']} — pivot = {pivot_cc}, cooccurrent = {cible_freq}",
                            lignes_html_freq
                        )
                        # --- espace avant le bouton de téléchargement du concordancier
                        st.markdown("<br/>", unsafe_allow_html=True)
                        st.download_button(
                            label=f"Télécharger le concordancier (Fréquences, HTML — {docres['nom']})",
                            data=doc_html.encode("utf-8"),
                            file_name=f"concordancier_frequences_{re.sub(r'[^A-Za-z0-9_.-]+','_', docres['nom'])}_{pivot_cc}_{cible_freq}.html",
                            mime="text/html",
                            key=f"dl_kwic_freq_{st.session_state['run_id']}_{i}"
                        )

                st.markdown(f"<h2 style='color:#e63946'>2 — Scores log-likelihood — Mode : {mode_label}</h1>", unsafe_allow_html=True)
                st.caption("Score calculé sur les mêmes fenêtres que les fréquences.")
                st.markdown(
                    "Le log-likelihood sert à tester l’indépendance entre deux mots. Plus le score est élevé et la p-valeur faible, "
                    "plus l’association est statistiquement probante."
                )

                df_ll_doc_full = docres["df_ll"].copy()
                activer_filtre_p = st.checkbox(
                    f"Afficher uniquement les paires significatives (p < 0,05) — {docres['nom']}",
                    value=False, key=f"filtre_p_{st.session_state['run_id']}_{i}"
                )
                if activer_filtre_p:
                    df_ll_doc = df_ll_doc_full[df_ll_doc_full["p_value"] < 0.05].reset_index(drop=True)
                else:
                    df_ll_doc = df_ll_doc_full

                st.dataframe(df_ll_doc, use_container_width=True)
                st.download_button(
                    label=f"Télécharger le CSV (Log-likelihood — affiché — {docres['nom']})",
                    data=generer_csv(df_ll_doc).getvalue(),
                    file_name=f"cooccurrences_loglike_affiche_{re.sub(r'[^A-Za-z0-9_.-]+','_', docres['nom'])}.csv",
                    mime="text/csv",
                    key=f"dl_csv_ll_{st.session_state['run_id']}_{i}"
                )

                st.markdown(f"<h3 style='color:#e63946'>Nuage de cooccurrences — pondéré par le score de log-likelihood — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                st.caption("Chaque élément du nuage est une paire `pivot_voisin` ; poids = score de log-likelihood.")
                top_n_ll = st.number_input(
                    f"Top N (log-likelihood) — {docres['nom']}", min_value=1, max_value=500, value=10, step=1,
                    key=f"top_wc_ll_{st.session_state['run_id']}_{i}"
                )
                df_top_ll = (
                    df_ll_doc[df_ll_doc["loglike"] > 0]
                    .sort_values(["loglike", "fenetres_ensemble"], ascending=[False, False])
                    .head(int(top_n_ll))
                )
                if df_top_ll.empty:
                    st.info("Aucun élément à afficher dans le nuage (vérifiez le filtrage p ou la taille du corpus).")
                else:
                    wc_ll_data = {f"{pivot_cc}_{w}": float(s)
                                  for w, s in zip(df_top_ll["cooccurrent"], df_top_ll["loglike"])}
                    generer_wordcloud(wc_ll_data, f"{docres['nom']} — Top {int(top_n_ll)} cooccurrences (log-likelihood)")

                st.markdown(f"<h3 style='color:#e63946'>Graphe interactif — cooccurrences (log-likelihood) — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                n_edges_ll = st.number_input(
                    f"Nombre d’arêtes (Top-N) – log-likelihood — {docres['nom']}",
                    min_value=1, max_value=200, value=30, step=1,
                    key=f"nedges_ll_{st.session_state['run_id']}_{i}"
                )
                poids_ll = dict(zip(df_ll_doc["cooccurrent"], df_ll_doc["loglike"]))
                html_ll = pyvis_reseau_html(pivot_cc, poids_ll, f"Réseau — Log-likelihood (G²) — {docres['nom']}", top_n=int(n_edges_ll), syntaxique=False, mode_label="ll", edge_label_size=9)
                st_html(html_ll, height=620, scrolling=True)

                # --- export HTML du graphe log-likelihood (par document)
                st.download_button(
                    label=f"Exporter le graphe log-likelihood (HTML) — {docres['nom']}",
                    data=html_ll.encode("utf-8"),
                    file_name=f"reseau_loglike_{re.sub(r'[^A-Za-z0-9_.-]+', '_', docres['nom'])}.html",
                    mime="text/html",
                    key=f"dl_graph_ll_html_{st.session_state['run_id']}_{i}"
                )

                st.markdown(f"<h3 style='color:#e63946'>Concordancier — à partir du log-likelihood — Mode : {mode_label}</h3>", unsafe_allow_html=True)
                coocs_list_ll = list(df_ll_doc["cooccurrent"])
                if coocs_list_ll:
                    cible_ll = st.selectbox(
                        f"Cooccurrent (Log-likelihood) — {docres['nom']}",
                        coocs_list_ll, index=0, key=f"cc_ll_{st.session_state['run_id']}_{i}"
                    )
                    nb_max_ll = st.number_input(
                        f"Nombre maximum de phrases — {docres['nom']}",
                        min_value=1, max_value=5000, value=200, step=10,
                        key=f"nbmax_ll_{st.session_state['run_id']}_{i}"
                    )
                    lignes_html_ll = []; n_aff = 0
                    for sent in sent_spans:
                        nlist = iter_tokens_normalises(sent, stopset_cc, pivot_cc, excl_num, excl_1)
                        sset = set(nlist)
                        if pivot_cc in sset and cible_ll in sset:
                            lignes_html_ll.append(phrase_surface_html(sent, pivot_cc, cible_ll, stopset_cc, excl_num, excl_1))
                            n_aff += 1
                            if n_aff >= int(nb_max_ll):
                                break
                    if not lignes_html_ll:
                        st.info("Aucune phrase trouvée pour ce cooccurrent (log-likelihood).")
                    else:
                        st.markdown("\n".join(lignes_html_ll), unsafe_allow_html=True)
                        doc_html = document_html_kwic(
                            f"Concordancier — Log-likelihood — {docres['nom']} — pivot = {pivot_cc}, cooccurrent = {cible_ll}",
                            lignes_html_ll
                        )
                        # --- espace avant le bouton de téléchargement du concordancier
                        st.markdown("<br/>", unsafe_allow_html=True)
                        st.download_button(
                            label=f"Télécharger le concordancier (Log-likelihood, HTML — {docres['nom']})",
                            data=doc_html.encode("utf-8"),
                            file_name=f"concordancier_loglike_{re.sub(r'[^A-Za-z0-9_.-]+','_', docres['nom'])}_{pivot_cc}_{cible_ll}.html",
                            mime="text/html",
                            key=f"dl_kwic_ll_{st.session_state['run_id']}_{i}"
                        )

        else:
            # =====================================
            # Mode classique : on réutilise exactement l’affichage précédent
            # =====================================
            sent_spans = st.session_state["sent_spans"]
            mode_label = st.session_state.get("fenetre_mode", "")

            st.markdown(f"<h1 style='color:#e63946'>1 — Fréquences à partir du mot pivot — Mode : {mode_label}</h1>", unsafe_allow_html=True)
            st.markdown(
                "Ici, on analyse simplement les **cooccurrences récurrentes**, c’est-à-dire les mots qui apparaissent souvent "
                "dans le même contexte que le pivot.\n\n"
                "Plus la fréquence est élevée, plus cela indique que ces mots sont régulièrement associés dans le texte.\n\n"
                "Cette approche ne dit pas si l’association est due au hasard ou non : elle permet surtout d’observer "
                "les répétitions les plus visibles dans un corpus."
            )
            st.caption("frequence = nombre de fenêtres où pivot et mot co-apparaissent ; fenetres_ensemble = nombre de fenêtres contenant simultanément pivot et mot.")
            df_freq = st.session_state["df_freq"]
            st.dataframe(df_freq, use_container_width=True)
            st.download_button(
                label="Télécharger le CSV (Fréquences)",
                data=generer_csv(df_freq).getvalue(),
                file_name="cooccurrences_frequences.csv",
                mime="text/csv",
                key=f"dl_csv_freq_{st.session_state['run_id']}"
            )

            st.markdown(f"<h3 style='color:#e63946'>Nuage de cooccurrences — pondéré par la fréquence — Mode : {mode_label}</h3>", unsafe_allow_html=True)
            st.caption("Chaque élément du nuage est une paire `pivot_voisin` ; poids = nombre de fenêtres où les deux co-apparaissent.")
            top_n_freq = st.number_input(
                "Top N (fréquences)", min_value=1, max_value=500, value=10, step=1,
                key=f"top_wc_freq_{st.session_state['run_id']}"
            )
            df_top_freq = (
                st.session_state["df_freq"][st.session_state["df_freq"]["frequence"] > 0]
                .sort_values(["frequence", "fenetres_ensemble"], ascending=[False, False])
                .head(int(top_n_freq))
            )
            wc_freq_data = {f"{pivot_cc}_{w}": int(freq)
                            for w, freq in zip(df_top_freq["cooccurrent"], df_top_freq["frequence"])}
            generer_wordcloud(wc_freq_data, f"Top {int(top_n_freq)} cooccurrences (fréquence)")

            # --- téléchargement du nuage en PNG (fréquences, mode classique)
            wc_png = io.BytesIO()
            fig_wc = plt.figure(figsize=(10, 5))
            wc_obj = WordCloud(width=900, height=450, background_color="white").generate_from_frequencies(
                {k: float(v) for k, v in wc_freq_data.items() if float(v) > 0}
            )
            plt.imshow(wc_obj, interpolation="bilinear");
            plt.axis("off")
            plt.title(f"Top {int(top_n_freq)} cooccurrences (fréquence)")
            fig_wc.savefig(wc_png, format="png", dpi=180, bbox_inches="tight")
            plt.close(fig_wc)
            wc_png.seek(0)
            st.download_button(
                label="Télécharger le nuage (PNG)",
                data=wc_png,
                file_name=f"nuage_frequence_top{int(top_n_freq)}.png",
                mime="image/png",
                key=f"dl_wc_freq_png_{st.session_state['run_id']}"
            )

            st.markdown(f"<h3 style='color:#e63946'>Graphe interactif — cooccurrences (fréquence) — Mode : {mode_label}</h3>", unsafe_allow_html=True)
            n_edges_freq = st.number_input("Nombre d’arêtes (Top-N) – fréquence", min_value=1, max_value=200, value=30, step=1, key=f"nedges_freq_{st.session_state['run_id']}")
            poids_freq = dict(zip(df_freq["cooccurrent"], df_freq["frequence"]))
            html_freq = pyvis_reseau_html(pivot_cc, poids_freq, "Réseau — Fréquence", top_n=int(n_edges_freq), syntaxique=False, mode_label="freq", edge_label_size=11)
            st_html(html_freq, height=620, scrolling=True)

            st.markdown(f"<h3 style='color:#e63946'>Concordancier — à partir des fréquences — Mode : {mode_label}</h3>", unsafe_allow_html=True)
            coocs_list_freq = list(df_freq["cooccurrent"])
            if coocs_list_freq:
                cible_freq = st.selectbox("Cooccurrent (Fréquences)", coocs_list_freq, index=0, key=f"cc_freq_{st.session_state['run_id']}")
                nb_max_freq = st.number_input("Nombre maximum de phrases", min_value=1, max_value=5000, value=200, step=10, key=f"nbmax_freq_{st.session_state['run_id']}")
                lignes_html_freq = []; n_aff = 0
                for sent in sent_spans:
                    nlist = iter_tokens_normalises(sent, stopset_cc, pivot_cc, excl_num, excl_1)
                    sset = set(nlist)
                    if pivot_cc in sset and cible_freq in sset:
                        lignes_html_freq.append(phrase_surface_html(sent, pivot_cc, cible_freq, stopset_cc, excl_num, excl_1))
                        n_aff += 1
                        if n_aff >= int(nb_max_freq):
                            break
                if not lignes_html_freq:
                    st.info("Aucune phrase trouvée pour ce cooccurrent.")
                else:
                    st.markdown("\n".join(lignes_html_freq), unsafe_allow_html=True)
                    doc_html = document_html_kwic(
                        f"Concordancier — Fréquences — pivot = {pivot_cc}, cooccurrent = {cible_freq}",
                        lignes_html_freq
                    )
                    # --- espace avant le bouton de téléchargement du concordancier
                    st.markdown("<br/>", unsafe_allow_html=True)
                    st.download_button(
                        label="Télécharger le concordancier (Fréquences, HTML)",
                        data=doc_html.encode("utf-8"),
                        file_name=f"concordancier_frequences_{pivot_cc}_{cible_freq}.html",
                        mime="text/html",
                        key=f"dl_kwic_freq_{st.session_state['run_id']}"
                    )

            st.markdown(f"<h1 style='color:#e63946'>2 — Scores log-likelihood — Mode : {mode_label}</h1>", unsafe_allow_html=True)
            st.caption("Score calculé sur les mêmes fenêtres que les fréquences.")
            st.markdown(
                "Le log-likelihood sert à tester l’indépendance entre deux mots. Plus le score est élevé et la p-valeur faible, "
                "plus l’association est statistiquement probante."
            )

            activer_filtre_p = st.checkbox("Afficher uniquement les paires significatives (p < 0,05)", value=False, key=f"filtre_p_{st.session_state['run_id']}")
            df_ll_full = st.session_state["df_ll_full"].copy()
            if activer_filtre_p:
                df_ll = df_ll_full[df_ll_full["p_value"] < 0.05].reset_index(drop=True)
            else:
                df_ll = df_ll_full

            st.dataframe(df_ll, use_container_width=True)
            st.download_button(
                label="Télécharger le CSV (Log-likelihood — affiché)",
                data=generer_csv(df_ll).getvalue(),
                file_name="cooccurrences_loglike_affiche.csv",
                mime="text/csv",
                key=f"dl_csv_ll_{st.session_state['run_id']}"
            )

            st.markdown(f"<h3 style='color:#e63946'>Nuage de cooccurrences — pondéré par le score de log-likelihood — Mode : {mode_label}</h3>", unsafe_allow_html=True)
            st.caption("Chaque élément du nuage est une paire `pivot_voisin` ; poids = score de log-likelihood.")
            top_n_ll = st.number_input(
                "Top N (log-likelihood)", min_value=1, max_value=500, value=10, step=1,
                key=f"top_wc_ll_{st.session_state['run_id']}"
            )
            df_top_ll = (
                df_ll[df_ll["loglike"] > 0]
                .sort_values(["loglike", "fenetres_ensemble"], ascending=[False, False])
                .head(int(top_n_ll))
            )
            if df_top_ll.empty:
                st.info("Aucun élément à afficher dans le nuage (vérifiez le filtrage p ou la taille du corpus).")
            else:
                wc_ll_data = {f"{pivot_cc}_{w}": float(s)
                              for w, s in zip(df_top_ll["cooccurrent"], df_top_ll["loglike"])}
                generer_wordcloud(wc_ll_data, f"Top {int(top_n_ll)} cooccurrences (log-likelihood)")

            st.markdown(f"<h3 style='color:#e63946'>Graphe interactif — cooccurrences (log-likelihood) — Mode : {mode_label}</h3>", unsafe_allow_html=True)
            n_edges_ll = st.number_input("Nombre d’arêtes (Top-N) – log-likelihood", min_value=1, max_value=200, value=30, step=1, key=f"nedges_ll_{st.session_state['run_id']}")
            poids_ll = dict(zip(df_ll["cooccurrent"], df_ll["loglike"]))
            html_ll = pyvis_reseau_html(pivot_cc, poids_ll, "Réseau — Log-likelihood", top_n=int(n_edges_ll), syntaxique=False, mode_label="ll", edge_label_size=9)
            st_html(html_ll, height=620, scrolling=True)

            # --- export HTML du graphe log-likelihood (mode classique)
            st.download_button(
                label="Exporter le graphe log-likelihood (HTML)",
                data=html_ll.encode("utf-8"),
                file_name="reseau_loglike.html",
                mime="text/html",
                key=f"dl_graph_ll_html_{st.session_state['run_id']}"
            )

            st.markdown(f"<h3 style='color:#e63946'>Concordancier — à partir du log-likelihood — Mode : {mode_label}</h3>", unsafe_allow_html=True)
            coocs_list_ll = list(df_ll["cooccurrent"])
            if coocs_list_ll:
                cible_ll = st.selectbox("Cooccurrent (Log-likelihood)", coocs_list_ll, index=0, key=f"cc_ll_{st.session_state['run_id']}")
                nb_max_ll = st.number_input("Nombre maximum de phrases", min_value=1, max_value=5000, value=200, step=10, key=f"nbmax_ll_{st.session_state['run_id']}")
                lignes_html_ll = []; n_aff = 0
                for sent in sent_spans:
                    nlist = iter_tokens_normalises(sent, stopset_cc, pivot_cc, excl_num, excl_1)
                    sset = set(nlist)
                    if pivot_cc in sset and cible_ll in sset:
                        lignes_html_ll.append(phrase_surface_html(sent, pivot_cc, cible_ll, stopset_cc, excl_num, excl_1))
                        n_aff += 1
                        if n_aff >= int(nb_max_ll):
                            break
                if not lignes_html_ll:
                    st.info("Aucune phrase trouvée pour ce cooccurrent (log-likelihood).")
                else:
                    st.markdown("\n".join(lignes_html_ll), unsafe_allow_html=True)
                    doc_html = document_html_kwic(
                        f"Concordancier — Log-likelihood — pivot = {pivot_cc}, cooccurrent = {cible_ll}",
                        lignes_html_ll
                    )
                    # --- espace avant le bouton de téléchargement du concordancier
                    st.markdown("<br/>", unsafe_allow_html=True)
                    st.download_button(
                        label="Télécharger le concordancier (Log-likelihood, HTML)",
                        data=doc_html.encode("utf-8"),
                        file_name=f"concordancier_loglike_{pivot_cc}_{cible_ll}.html",
                        mime="text/html",
                        key=f"dl_kwic_ll_{st.session_state['run_id']}"
                    )

    with ong_lex:
        st.markdown("<h2 style='color:#e63946'>Lexique des formes observées</h2>", unsafe_allow_html=True)
        st.caption("Formes normalisées rencontrées et leur POS majoritaire dans votre corpus.")
        st.markdown("<h3 style='color:#e63946'>Formes (normalisées) et POS</h3>", unsafe_allow_html=True)
        st.dataframe(st.session_state["df_lex_formes"], use_container_width=True)
        st.download_button(
            label="Télécharger le CSV (Formes & POS)",
            data=generer_csv(st.session_state["df_lex_formes"]).getvalue(),
            file_name="lexique_formes_pos.csv",
            mime="text/csv",
            key=f"dl_lex_formes_{st.session_state['run_id']}"
        )

    with ong_exp:
        st.markdown("<h2 style='color:#e63946'>Explications — POS (catégories morpho-syntaxiques)</h2>", unsafe_allow_html=True)
        st.dataframe(st.session_state["df_pos_exp"], use_container_width=True)

else:
    st.info("Lancez l’analyse pour afficher les tableaux, les nuages de mots, les graphes, les concordanciers, le lexique et les explications.")
