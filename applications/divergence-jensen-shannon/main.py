from __future__ import annotations

import io
import math
import re
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from nltk.corpus import stopwords


DEFAULT_TEXT_A = """
Je me réveille souvent avec une sensation d’angoisse. J’ai l’impression que quelque chose va mal se passer. Je pense immédiatement à tout ce que je dois faire. Je sens une tension dans ma poitrine dès le matin. J’ai parfois du mal à respirer calmement. Je réfléchis beaucoup avant de prendre une décision. J’ai peur de me tromper. Je vérifie souvent plusieurs fois les mêmes choses. Je me sens épuisé mentalement. Je pense constamment au travail. Je crains de ne pas être à la hauteur. Je me mets facilement la pression. Je ressasse souvent des conversations anciennes. Je me demande si les autres me jugent. J’évite parfois de répondre au téléphone. Je préfère rester seul quand l’anxiété augmente. Je dors mal depuis plusieurs mois. Je me réveille souvent pendant la nuit. Je pense immédiatement aux problèmes du lendemain. J’ai du mal à arrêter mes pensées. Je sens mon corps tendu presque toute la journée. J’ai parfois l’impression de perdre le contrôle. Je me sens fragile émotionnellement. Je me fatigue rapidement dans les situations sociales. Je redoute les imprévus. Je supporte mal l’incertitude. Je voudrais retrouver un peu de calme. Je voudrais comprendre pourquoi cette anxiété revient sans arrêt. Je fais beaucoup d’efforts pour paraître normal devant les autres. Je me sens souvent seul avec mes pensées.
""".strip()

DEFAULT_TEXT_B = """
Je me sens anxieux presque tous les jours. Je pense constamment au travail. Je dors mal la nuit. J’évite les autres quand je suis stressé. Je voudrais réussir à me calmer.
""".strip()

STOPWORDS_FR_SUPPLEMENTAIRES = {"c", "j", "l", "m", "n", "qu", "s", "t", "y"}
STOPWORDS_FR_FALLBACK = {
    "a",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "et",
    "eux",
    "il",
    "je",
    "la",
    "le",
    "les",
    "leur",
    "lui",
    "ma",
    "mais",
    "me",
    "meme",
    "mes",
    "moi",
    "mon",
    "ne",
    "nos",
    "notre",
    "nous",
    "on",
    "ou",
    "par",
    "pas",
    "pour",
    "qu",
    "que",
    "qui",
    "sa",
    "se",
    "ses",
    "son",
    "sur",
    "ta",
    "te",
    "tes",
    "toi",
    "ton",
    "tu",
    "un",
    "une",
    "vos",
    "votre",
    "vous",
}

MOTIF_MOTS = re.compile(r"[a-zàâçéèêëîïôûùüÿñæœ]+")


@st.cache_data(show_spinner=False)
def charger_stopwords_francais() -> set[str]:
    try:
        return set(stopwords.words("french")) | STOPWORDS_FR_SUPPLEMENTAIRES
    except LookupError:
        return STOPWORDS_FR_FALLBACK | STOPWORDS_FR_SUPPLEMENTAIRES


def nettoyer_texte(
    texte: str,
    stopwords_fr: set[str],
    min_length: int,
    appliquer_stopwords: bool,
    stopwords_personnalises: set[str],
) -> list[str]:
    texte = texte.lower().replace("’", "'")
    texte = re.sub(r"[']", " ", texte)
    mots = MOTIF_MOTS.findall(texte)
    stopset = (stopwords_fr | stopwords_personnalises) if appliquer_stopwords else stopwords_personnalises
    return [mot for mot in mots if mot not in stopset and len(mot) >= min_length]


def compter_mots(
    texte: str,
    stopwords_fr: set[str],
    min_length: int,
    appliquer_stopwords: bool,
    stopwords_personnalises: set[str],
) -> Counter:
    return Counter(
        nettoyer_texte(
            texte=texte,
            stopwords_fr=stopwords_fr,
            min_length=min_length,
            appliquer_stopwords=appliquer_stopwords,
            stopwords_personnalises=stopwords_personnalises,
        )
    )


def creer_vocabulaire(compteur_a: Counter, compteur_b: Counter) -> list[str]:
    return sorted(set(compteur_a.keys()) | set(compteur_b.keys()))


def creer_distribution(compteur: Counter, vocabulaire: list[str]) -> np.ndarray:
    total = sum(compteur.values())
    if total == 0:
        raise ValueError(
            "Aucun mot n'a ete conserve apres le filtrage. "
            "Assouplissez la longueur minimale ou les stopwords."
        )
    return np.array([compteur.get(mot, 0) / total for mot in vocabulaire], dtype=float)


def x_log2_x(x: float) -> float:
    return 0.0 if x <= 0 else x * math.log2(x)


def calculer_contributions_jsd(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    m = 0.5 * (p + q)
    return np.array(
        [(-x_log2_x(mi) + 0.5 * x_log2_x(pi) + 0.5 * x_log2_x(qi)) for pi, qi, mi in zip(p, q, m)],
        dtype=float,
    )


def orienter_valeurs(p: np.ndarray, q: np.ndarray, contributions: np.ndarray) -> np.ndarray:
    return np.array([-contribution if pi >= qi else contribution for pi, qi, contribution in zip(p, q, contributions)])


def determiner_dominant(p_i: float, q_i: float) -> str:
    if p_i > q_i:
        return "Texte A"
    if q_i > p_i:
        return "Texte B"
    return "Egal"


def construire_resultats_dataframe(
    vocabulaire: list[str],
    p: np.ndarray,
    q: np.ndarray,
    contributions: np.ndarray,
    top_n: int,
) -> pd.DataFrame:
    valeurs = orienter_valeurs(p, q, contributions)
    score_global = float(contributions.sum())
    indices = np.argsort(np.abs(valeurs))[::-1][:top_n]

    lignes: list[dict[str, object]] = []
    for rang, indice in enumerate(indices, start=1):
        pourcentage_jsd = (float(contributions[indice]) / score_global * 100.0) if score_global > 0 else 0.0
        lignes.append(
            {
                "Rang": rang,
                "Mot": vocabulaire[indice],
                "Score JSD": float(contributions[indice]),
                "% JSD": pourcentage_jsd,
                "pA": float(p[indice]),
                "pB": float(q[indice]),
                "Dominant": determiner_dominant(float(p[indice]), float(q[indice])),
                "Score oriente": float(valeurs[indice]),
            }
        )

    return pd.DataFrame(lignes)


def tracer_jsd_figure(resultats_df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, max(5, len(resultats_df) * 0.38)))

    donnees = resultats_df.iloc[::-1]
    couleurs = ["#8aa84f" if valeur < 0 else "#4f5f3a" for valeur in donnees["Score oriente"]]

    ax.barh(donnees["Mot"], donnees["Score oriente"], color=couleurs)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Divergence de Jensen-Shannon", fontsize=12)
    ax.set_xlabel("Gauche = Texte A | Droite = Texte B", fontsize=9)
    ax.grid(axis="x", alpha=0.25)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    return fig


def exporter_resultats_txt(
    texte_a: str,
    texte_b: str,
    taille_a: int,
    taille_b: int,
    vocabulaire_total: int,
    score_jsd: float,
    resultats_df: pd.DataFrame,
) -> str:
    buffer = io.StringIO()
    buffer.write("Analyse JSD\n\n")
    buffer.write("TEXTE A\n")
    buffer.write("=" * 100 + "\n")
    buffer.write(texte_a.strip() + "\n\n")
    buffer.write(f"Nombre de mots conserves Texte A : {taille_a}\n\n")
    buffer.write("TEXTE B\n")
    buffer.write("=" * 100 + "\n")
    buffer.write(texte_b.strip() + "\n\n")
    buffer.write(f"Nombre de mots conserves Texte B : {taille_b}\n")
    buffer.write(f"Vocabulaire total apres filtrage : {vocabulaire_total}\n")
    buffer.write(f"Score global Divergence de Jensen-Shannon : {score_jsd:.6f}\n\n")
    buffer.write("=" * 100 + "\n")
    buffer.write("Classement des mots les plus contributifs\n")
    buffer.write("=" * 100 + "\n")
    buffer.write(f"{'rang':>4s} {'mot':20s} {'score':>12s} {'%JSD':>8s} {'pA':>10s} {'pB':>10s} {'dominant':>12s}\n")

    for row in resultats_df.itertuples(index=False):
        buffer.write(
            f"{row.Rang:4d} "
            f"{str(row.Mot)[:20]:20s} "
            f"{row[2]:12.6f} "
            f"{row[3]:8.2f} "
            f"{row.pA:10.4f} "
            f"{row.pB:10.4f} "
            f"{row.Dominant:>12s}\n"
        )

    return buffer.getvalue()


def lire_stopwords_personnalises(value: str) -> set[str]:
    morceaux = re.split(r"[\s,;]+", value.lower())
    return {mot.strip() for mot in morceaux if mot.strip()}


def main() -> None:
    st.set_page_config(page_title="Divergence Jensen-Shannon", page_icon="📊", layout="wide")
    st.title("Divergence de Jensen-Shannon")
    st.markdown("[www.codeandcortex.fr](https://www.codeandcortex.fr)")
    st.markdown(
        """
        Cette application compare deux textes, calcule la divergence de Jensen-Shannon sur les distributions lexicales,
        identifie les mots qui contribuent le plus a l'ecart, et genere un graphique oriente :

        - gauche : mots davantage portes par le texte A
        - droite : mots davantage portes par le texte B
        """
    )

    stopwords_fr = charger_stopwords_francais()

    with st.sidebar:
        st.header("Parametres")
        top_n = st.slider("Nombre de mots affiches", min_value=5, max_value=100, value=25, step=5)
        min_length = st.slider("Longueur minimale des mots", min_value=2, max_value=8, value=3)
        appliquer_stopwords = st.checkbox("Retirer les stopwords francais", value=True)
        stopwords_personnalises = st.text_area(
            "Stopwords additionnels",
            value="",
            help="Separez les termes par des espaces, virgules ou points-virgules.",
        )
        st.caption("Les stopwords NLTK sont utilises si disponibles, sinon une liste de secours est appliquee.")

    col_a, col_b = st.columns(2)
    with col_a:
        texte_a = st.text_area("Texte A", value=DEFAULT_TEXT_A, height=320)
    with col_b:
        texte_b = st.text_area("Texte B", value=DEFAULT_TEXT_B, height=320)

    if st.button("Lancer l'analyse", type="primary"):
        try:
            stopwords_custom = lire_stopwords_personnalises(stopwords_personnalises)
            compteur_a = compter_mots(texte_a, stopwords_fr, min_length, appliquer_stopwords, stopwords_custom)
            compteur_b = compter_mots(texte_b, stopwords_fr, min_length, appliquer_stopwords, stopwords_custom)

            vocabulaire = creer_vocabulaire(compteur_a, compteur_b)
            p = creer_distribution(compteur_a, vocabulaire)
            q = creer_distribution(compteur_b, vocabulaire)
            contributions = calculer_contributions_jsd(p, q)
            score_jsd = float(contributions.sum())

            taille_a = int(sum(compteur_a.values()))
            taille_b = int(sum(compteur_b.values()))
            resultats_df = construire_resultats_dataframe(vocabulaire, p, q, contributions, top_n)
            rapport_txt = exporter_resultats_txt(
                texte_a=texte_a,
                texte_b=texte_b,
                taille_a=taille_a,
                taille_b=taille_b,
                vocabulaire_total=len(vocabulaire),
                score_jsd=score_jsd,
                resultats_df=resultats_df,
            )

            st.subheader("Informations generales")
            info1, info2, info3, info4 = st.columns(4)
            info1.metric("Mots conserves A", taille_a)
            info2.metric("Mots conserves B", taille_b)
            info3.metric("Vocabulaire total", len(vocabulaire))
            info4.metric("Score JSD", f"{score_jsd:.6f}")

            fig = tracer_jsd_figure(resultats_df)
            png_buffer = io.BytesIO()
            fig.savefig(png_buffer, format="png", dpi=300, bbox_inches="tight")
            png_buffer.seek(0)

            tab_resultats, tab_graphique, tab_exports = st.tabs(["Resultats", "Graphique", "Exports"])

            with tab_resultats:
                st.dataframe(
                    resultats_df.drop(columns=["Score oriente"]),
                    use_container_width=True,
                    hide_index=True,
                )

            with tab_graphique:
                st.pyplot(fig, use_container_width=True)

            with tab_exports:
                st.download_button(
                    "Telecharger les resultats TXT",
                    data=rapport_txt,
                    file_name="resultats_jsd.txt",
                    mime="text/plain",
                )
                st.download_button(
                    "Telecharger les resultats CSV",
                    data=resultats_df.drop(columns=["Score oriente"]).to_csv(index=False).encode("utf-8"),
                    file_name="resultats_jsd.csv",
                    mime="text/csv",
                )
                st.download_button(
                    "Telecharger le graphique PNG",
                    data=png_buffer.getvalue(),
                    file_name="jsd_texte_a_vs_b.png",
                    mime="image/png",
                )

        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover - garde-fou Streamlit
            st.error(f"Erreur inattendue : {exc}")


if __name__ == "__main__":
    main()
