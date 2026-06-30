"""# Onglet Hash

Ce module propose l'onglet Streamlit permettant de calculer la Longueur
Moyenne des Segments (LMS) entre connecteurs et de comparer différents modes
de segmentation.

## Dépendances
- `hash.py` : calculs de longueur de segments, moyennes et modes de
  segmentation.
- `ecartype.py` : écart-type des longueurs pour enrichir les indicateurs.
- `simicosinus.py` : concaténation des textes avec entêtes pour alimenter les
  statistiques.
- `fcts_utils.py` : rappel des connecteurs sélectionnés dans l'interface.
- Bibliothèques `streamlit`, `pandas` et `altair` pour l'affichage et les
  graphiques.
"""
from __future__ import annotations

from typing import Dict, List

import altair as alt
import pandas as pd
import streamlit as st

from densite import build_text_from_dataframe
from ecartype import compute_length_standard_deviation, standard_deviation_by_modality
from friedeman import (
    calculer_indicateurs_reponses_appairees,
    calculer_statistique_friedman,
    construire_tableau_apparie,
    tests_post_hoc_wilcoxon,
)
from fcts_utils import render_connectors_reminder
from hash import (
    ECART_TYPE_EXPLANATION,
    SegmentationMode,
    TokenizationMode,
    average_segment_length,
    average_segment_length_by_modality,
    compute_segment_word_lengths,
    resumer_reponses_par_modalite,
    statistiques_par_modalite,
    segments_with_word_lengths,
)
from KolmogorovSmirnov import (
    ResultatKSTest,
    calculer_test_ks,
    comparer_modalites_par_paires,
    extraire_longueurs_par_modalite,
    p_value_par_permutation,
)
from simicosinus import concatenate_texts_with_headers


def rendu_hash(
    tab,
    filtered_df: pd.DataFrame,
    filtered_connectors: Dict[str, str],
    combined_text: str,
) -> None:
    st.subheader("Hash (LMS entre connecteurs)")
    render_connectors_reminder(filtered_connectors)
    st.write(
        """
La "LMS" correspond à la Longueur Moyenne des Segments d'un texte. Vous pouvez choisir
un découpage basé uniquement sur les connecteurs sélectionnés, ou bien considérer qu'une
ponctuation forte (. / ? / ! / ; /:) ferme aussi le segment.
- Des segments courts signalent un texte plutôt "haché", saccadé, algorithmique.
- Des segments longs évoquent une prose plus fluide.
        """
    )
    segmentation_labels: Dict[str, SegmentationMode] = {
        "Entre connecteurs uniquement (ignore la ponctuation)": "connecteurs",
        "Connecteurs + ponctuation qui ferme le segment": "connecteurs_et_ponctuation",
    }
    segmentation_choice = st.radio(
        "Mode de calcul de la LMS",
        list(segmentation_labels.keys()),
        help=(
            "Le découpage peut se faire uniquement entre connecteurs, ou bien s'arrêter"
            " dès qu'un signe de ponctuation forte (., ?, !, ;, :) est rencontré."
        ),
    )
    segmentation_mode = segmentation_labels[segmentation_choice]

    tokenization_labels: Dict[str, TokenizationMode] = {
        "Regex (Tokenisation avec une 'regex \b\w+\b')": "regex",
        "spaCy (fr_core_news_md - Tokenisation plus précise)": "spacy",
    }
    tokenization_choice = st.radio(
        "Mode de tokenisation", list(tokenization_labels.keys()), help=(
            "Choisissez le mode de découpage des mots pour compter la longueur des segments :\n"
            "- Regex : tokens basés sur une expression régulière (regex \b\w+\b).\n"
            "- spaCy : tokens linguistiques du modèle français fr_core_news_md (plus précis)."
        ),
    )
    tokenization_mode = tokenization_labels[tokenization_choice]

    try:
        segment_lengths = compute_segment_word_lengths(
            combined_text, filtered_connectors, segmentation_mode, tokenization_mode
        )
    except RuntimeError as error:
        st.error(str(error))
        return

    if not segment_lengths:
        st.info(
            "Impossible de calculer la LMS : aucun segment n'a été détecté entre connecteurs."
        )
        return

    st.subheader("Sélection des variables/modalités")
    hash_variables = [
        column for column in filtered_df.columns if column not in ("texte", "entete")
    ]

    if not hash_variables:
        st.info("Aucune variable n'a été trouvée dans le fichier importé.")
        return

    selected_hash_variables = st.multiselect(
        "Variables à filtrer pour la LMS",
        hash_variables,
        default=hash_variables,
        help=(
            "Sélectionnez les variables et modalités à inclure avant de calculer la "
            "LMS."
        ),
    )

    if not selected_hash_variables:
        st.info(
            "Sélectionnez au moins une variable pour calculer la LMS."
        )
        return

    hash_modality_filters: Dict[str, List[str]] = {}
    hash_filtered_df = filtered_df.copy()

    for variable in selected_hash_variables:
        modality_options = sorted(
            hash_filtered_df[variable].dropna().unique().tolist()
        )
        selected_modalities = st.multiselect(
            f"Modalités à inclure pour {variable}",
            modality_options,
            default=modality_options,
            help=(
                "Sélectionnez les modalités dont les textes seront pris en compte pour"
                " cette variable."
            ),
            key=f"modalites_{variable}",
        )
        hash_modality_filters[variable] = selected_modalities

        if selected_modalities:
            hash_filtered_df = hash_filtered_df[
                hash_filtered_df[variable].isin(selected_modalities)
            ]
        else:
            hash_filtered_df = hash_filtered_df.iloc[0:0]

    if hash_filtered_df.empty:
        st.info(
            "Aucun texte ne correspond aux filtres appliqués. Ajustez vos sélections pour"
            " continuer."
        )
        return

    hash_text = build_text_from_dataframe(hash_filtered_df)
    export_text = concatenate_texts_with_headers(
        hash_filtered_df, selected_hash_variables
    )

    if export_text:
        st.download_button(
            label="Télécharger les textes concaténés",
            data=export_text,
            file_name="textes_concatenation_hash.txt",
            mime="text/plain",
            help=(
                "Export des textes regroupés selon les variables et modalités choisies "
                "pour vérifier la composition de la LMS."
            ),
        )
    try:
        segment_lengths = compute_segment_word_lengths(
            hash_text, filtered_connectors, segmentation_mode, tokenization_mode
        )
    except RuntimeError as error:
        st.error(str(error))
        return

    if not hash_text or not segment_lengths:
        st.info(
            "Impossible de calculer la LMS : aucun segment n'a été détecté dans les données"
            " filtrées."
        )
        return

    average_length = average_segment_length(
        hash_text, filtered_connectors, segmentation_mode, tokenization_mode
    )
    _, std_dev = compute_length_standard_deviation(
        hash_text, filtered_connectors, segmentation_mode, tokenization_mode
    )

    col1, col2 = st.columns(2)
    col1.metric(
        "Longueur moyenne des segments (LMS)", f"{average_length:.4f}"
    )
    col2.metric(
        "Écart-type des segments", f"{std_dev:.4f}"
    )

    st.caption(
        "Ces indicateurs permettent de quantifier la fluidité ou la segmentation du texte."
    )

    segment_entries = segments_with_word_lengths(
        hash_text, filtered_connectors, segmentation_mode, tokenization_mode
    )

    st.markdown("### Segments et longueurs")
    st.dataframe(pd.DataFrame(segment_entries), use_container_width=True)

    st.download_button(
        label="Exporter les segments (CSV)",
        data=pd.DataFrame(segment_entries).to_csv(index=False),
        file_name="segments_longueurs.csv",
        mime="text/csv",
    )

    for variable in selected_hash_variables:
        st.markdown(f"### Analyse par variable : {variable}")

        selected_modalities = hash_modality_filters.get(variable, [])
        per_modality_hash_df = average_segment_length_by_modality(
            hash_filtered_df,
            variable,
            filtered_connectors,
            selected_modalities or None,
            segmentation_mode,
            tokenization_mode,
        )

        if per_modality_hash_df.empty and not selected_modalities:
            st.info(
                "Aucune modalité n'a été trouvée pour cette variable dans les données sélectionnées."
            )
            continue

        if selected_modalities and per_modality_hash_df.empty:
            st.info(
                "Aucun texte ne correspond aux modalités choisies : impossible de calculer la LMS."
            )
            continue

        if not per_modality_hash_df.empty:
            st.subheader(f"Modalité(s) sélectionnée(s) de la variable : {variable}")
            st.dataframe(
                per_modality_hash_df.rename(
                    columns={
                        "modalite": "Modalité",
                        "segments": "Segments comptés",
                        "lms": "LMS",
                    }
                ),
                use_container_width=True,
            )

            lms_chart = (
                alt.Chart(per_modality_hash_df)
                .mark_bar()
                .encode(
                    x=alt.X("modalite:N", title="Modalité"),
                    y=alt.Y("lms:Q", title="LMS (mots)"),
                    color=alt.Color("modalite:N", title="Modalité"),
                    tooltip=[
                        alt.Tooltip("modalite:N", title="Modalité"),
                        alt.Tooltip("lms:Q", title="LMS", format=".4f"),
                        alt.Tooltip("segments:Q", title="Segments"),
                    ],
                )
            )

            st.altair_chart(lms_chart, use_container_width=True)

        std_by_modality_df = standard_deviation_by_modality(
            hash_filtered_df,
            variable,
            filtered_connectors,
            selected_modalities or None,
            segmentation_mode,
            tokenization_mode,
        )

        if not std_by_modality_df.empty:
            st.subheader(f"Ecart-type de la variable : {variable}")
            st.markdown(ECART_TYPE_EXPLANATION)
            st.dataframe(
                std_by_modality_df.rename(
                    columns={
                        "modalite": "Modalité",
                        "segments": "Segments comptés",
                        "lms": "LMS",
                        "ecart_type": "Écart-type",
                    }
                ),
                use_container_width=True,
            )

            std_chart = (
                alt.Chart(std_by_modality_df)
                .mark_bar()
                .encode(
                    x=alt.X("modalite:N", title="Modalité"),
                    y=alt.Y("ecart_type:Q", title="Écart-type (mots)"),
                    color=alt.Color("modalite:N", title="Modalité"),
                    tooltip=[
                        alt.Tooltip("modalite:N", title="Modalité"),
                        alt.Tooltip("ecart_type:Q", title="Écart-type", format=".4f"),
                        alt.Tooltip("segments:Q", title="Segments"),
                        alt.Tooltip("lms:Q", title="LMS", format=".4f"),
                    ],
                )
            )

            st.altair_chart(std_chart, use_container_width=True)

            st.markdown(
                "#### Dispersion des longueurs (moyenne ± écart-type)"
            )

            dispersion_chart = (
                alt.Chart(
                    std_by_modality_df.assign(
                        borne_inferieure=lambda df: (
                            df["lms"] - df["ecart_type"]
                        ).clip(lower=0),
                        borne_superieure=lambda df: df["lms"] + df["ecart_type"],
                    )
                )
                .mark_errorbar(orient="horizontal")
                .encode(
                    y=alt.Y("modalite:N", title="Modalité"),
                    x=alt.X("borne_inferieure:Q", title="Longueur (mots)"),
                    x2="borne_superieure:Q",
                    color=alt.Color("modalite:N", title="Modalité"),
                    tooltip=[
                        alt.Tooltip("modalite:N", title="Modalité"),
                        alt.Tooltip("lms:Q", title="LMS (moyenne)", format=".2f"),
                        alt.Tooltip("ecart_type:Q", title="Écart-type", format=".2f"),
                        alt.Tooltip("segments:Q", title="Segments comptés"),
                    ],
                )
            )

            lms_points = (
                alt.Chart(std_by_modality_df)
                .mark_point(size=70, filled=True)
                .encode(
                    y=alt.Y("modalite:N", title="Modalité"),
                    x=alt.X("lms:Q", title="Longueur (mots)"),
                    color=alt.Color("modalite:N", title="Modalité"),
                )
            )

            st.altair_chart(
                dispersion_chart + lms_points, use_container_width=True
            )

    st.markdown("### Inférence au niveau réponse")
    st.caption(
        "Les tests sont réalisés au niveau des réponses (une valeur par réponse), afin de respecter l'indépendance statistique ; les segments d'une même réponse ne sont pas considérés comme des observations indépendantes."
    )

    if not hash_variables:
        st.info(
            "Aucune variable disponible pour l'inférence. Importez un corpus contenant des variables (ex. modèle, prompt)."
        )
        st.markdown("---")
    else:
        variable_inference = st.selectbox(
            "Variable pour l'inférence par réponse",
            hash_variables,
            help=(
                "Sélectionnez la variable dont vous souhaitez comparer les modalités en considérant chaque réponse comme une observation indépendante."
            ),
        )

        modalites_possibles = sorted(
            hash_filtered_df[variable_inference].dropna().unique().tolist()
        )

        modalites_selectionnees = st.multiselect(
            "Modalités à comparer",
            modalites_possibles,
            default=modalites_possibles,
            help="Choisissez les modalités à inclure dans les tests statistiques.",
        )

        seuil_court = int(
            st.number_input(
                "Seuil (mots) pour qualifier un segment de court",
                min_value=1,
                max_value=200,
                value=10,
                step=1,
                help="Utilisé pour calculer la proportion de segments courts par réponse.",
            )
        )

        indicateur_labels = {
            "LMS (moyenne des segments)": "lms",
            "Écart-type des segments": "ecart_type",
            "Coefficient de variation": "coefficient_variation",
            "Médiane des segments": "mediane",
            "Proportion de segments courts": "proportion_courts",
        }

        choix_indicateur = st.selectbox(
            "Indicateur pour le test statistique",
            list(indicateur_labels.keys()),
            index=0,
        )
        indicateur_colonne = indicateur_labels[choix_indicateur]

        resumes_reponses, reponses_ignorees = resumer_reponses_par_modalite(
            hash_filtered_df,
            variable_inference,
            filtered_connectors,
            modalites_selectionnees or None,
            segmentation_mode,
            tokenization_mode,
            seuil_segment_court=seuil_court,
        )

        if resumes_reponses.empty:
            st.info(
                "Impossible de calculer les indicateurs par réponse : aucune réponse exploitable après filtrage ou segmentation."
            )
            if reponses_ignorees:
                st.caption(f"Réponses ignorées (sans segments détectés) : {reponses_ignorees}")
        else:
            if reponses_ignorees:
                st.caption(f"Réponses ignorées (sans segments détectés) : {reponses_ignorees}")

            stats_modalites = statistiques_par_modalite(resumes_reponses)

            if not stats_modalites.empty:
                st.markdown("#### Tableau récapitulatif par modalité")
                st.caption(
                    """
Modalité : valeur de la variable catégorielle sélectionnée (par ex. un modèle ou un prompt) à laquelle les indicateurs sont rattachés.

LMS moyenne : moyenne pondérée par segment des longueurs de segments (en mots) pour la modalité ; elle est calculée en divisant la somme des longueurs de segments par le nombre total de segments de toutes les réponses de cette modalité.

Médiane (réponses) : médiane des médianes de longueur calculées pour chaque réponse de la modalité (robuste aux valeurs extrêmes).

Écart-type : dispersion absolue des longueurs de segments, calculée pour chaque réponse puis agrégée sur la modalité.

Coefficient de variation : dispersion relative (« écart-type / moyenne ») des longueurs de segments, calculée pour chaque réponse ; si une réponse a une moyenne nulle, son coefficient est fixé à 0 avant l’agrégation.

Proportion segments courts : moyenne, sur les réponses de la modalité, de la proportion de segments dont la longueur est inférieure ou égale au seuil de segment court (par défaut 10 mots).

Réponses utilisées : nombre de réponses exploitables (après segmentation) rattachées à la modalité et incluses dans les agrégations.
"""
                )
                st.dataframe(
                    stats_modalites.rename(
                        columns={
                            "modalite": "Modalité",
                            "lms_moyenne": "LMS moyenne",
                            "mediane_reponses": "Médiane (réponses)",
                            "ecart_type_moyen": "Écart-type",
                            "cv_moyen": "Coefficient de variation",
                            "proportion_courts_moyenne": "Proportion segments courts",
                            "n_reponses": "Réponses utilisées",
                        }
                    ),
                    use_container_width=True,
                )

            donnees_par_modalite = {
                modalite: groupe[indicateur_colonne]
                .dropna()
                .astype(float)
                .tolist()
                for modalite, groupe in resumes_reponses.groupby("modalite")
                if modalite in (modalites_selectionnees or modalites_possibles)
            }

            st.markdown("#### Distribution de l'indicateur par modalité")
            st.caption(
                "Le graphique ci-dessous affiche l'indicateur choisi dans la liste"
                " déroulante (LMS, écart-type, coefficient de variation, médiane ou"
                " proportion de segments courts) pour chaque réponse, regroupée par"
                " modalité. Les valeurs sont calculées avec les réglages de"
                " segmentation et de tokenisation sélectionnés en haut de l'onglet"
                " ainsi que le seuil de segment court saisi ci-dessus."
            )
            box_chart = (
                alt.Chart(resumes_reponses)
                .mark_boxplot()
                .encode(
                    x=alt.X("modalite:N", title="Modalité"),
                    y=alt.Y(f"{indicateur_colonne}:Q", title=choix_indicateur),
                    color=alt.Color("modalite:N", title="Modalité"),
                    tooltip=[
                        alt.Tooltip("modalite:N", title="Modalité"),
                        alt.Tooltip(f"{indicateur_colonne}:Q", title="Valeur", format=".3f"),
                    ],
                )
            )

            st.altair_chart(box_chart, use_container_width=True)

    st.markdown("---")
    st.subheader("Test de Friedman (modèles appariés par prompt)")
    st.caption(
        "Le test de Friedman est un test non paramétrique pour comparer plusieurs conditions lorsque les mesures sont répétées sur les mêmes cas (données appariées). Il évalue si les distributions des rangs diffèrent entre conditions, en tenant compte de l’appariement. Il teste l’effet d’un seul facteur à la fois (par exemple le modèle), avec un identifiant de cas servant d’appariement (par exemple la question)."
    )
    st.caption(
        "Le test de Friedman compare plusieurs conditions appariées : ici, chaque prompt est un bloc et chaque modèle est une condition. Il teste si au moins un modèle diffère des autres."
    )

    if len(hash_variables) < 2:
        st.info(
            "Sélectionnez au moins deux variables dans vos données (par exemple *modele et *prompt) pour lancer le test de Friedman."
        )
    else:
        variable_modele = st.selectbox(
            "Variable correspondant aux modèles",
            hash_variables,
            help="Choisissez la variable indiquant les modèles (ex. *modele).",
        )

        variables_bloc = [var for var in hash_variables if var != variable_modele]
        variable_bloc = st.selectbox(
            "Variable correspondant aux blocs d'appariement (prompts)",
            variables_bloc if variables_bloc else hash_variables,
            help="Choisissez la variable qui identifie les blocs appariés (ex. *prompt ou *question).",
        )

        indicateur_labels_friedman = {
            "LMS (moyenne des segments)": "lms",
            "Écart-type des segments": "ecart_type",
            "Coefficient de variation": "coefficient_variation",
            "Médiane des segments": "mediane",
            "Proportion de segments courts": "proportion_courts",
        }

        choix_indicateur_friedman = st.selectbox(
            "Indicateur à comparer entre modèles",
            list(indicateur_labels_friedman.keys()),
            index=0,
        )
        indicateur_cible = indicateur_labels_friedman[choix_indicateur_friedman]

        seuil_court_friedman = int(
            st.number_input(
                "Seuil (mots) pour définir un segment court (Friedman)",
                min_value=1,
                max_value=200,
                value=10,
                step=1,
                help="Utilisé pour la proportion de segments courts dans le test de Friedman.",
            )
        )

        methode_agregation = st.radio(
            "Agrégation si plusieurs réponses par couple (bloc, modèle)",
            ["moyenne", "mediane"],
            format_func=lambda val: "Moyenne" if val == "moyenne" else "Médiane",
            help="Si plusieurs réponses existent pour un même prompt et modèle, choisit comment les résumer.",
        )

        indicateurs_reponses, reponses_ignorees_friedman = calculer_indicateurs_reponses_appairees(
            hash_filtered_df,
            variable_modele,
            variable_bloc,
            filtered_connectors,
            segmentation_mode,
            tokenization_mode,
            seuil_segment_court=seuil_court_friedman,
        )

        if indicateurs_reponses.empty:
            st.info(
                "Impossible de construire le tableau apparié : aucune réponse exploitable avec les variables choisies."
            )
            if reponses_ignorees_friedman:
                st.caption(
                    f"Réponses ignorées (vides ou sans segments détectés) : {reponses_ignorees_friedman}"
                )
        else:
            tableau_apparie, prompts_initiaux, prompts_exclus = construire_tableau_apparie(
                indicateurs_reponses,
                variable_modele,
                variable_bloc,
                indicateur_cible,
                methode_agregation=methode_agregation,
            )

            if reponses_ignorees_friedman:
                st.caption(
                    f"Réponses ignorées (vides ou sans segments détectés) : {reponses_ignorees_friedman}"
                )

            if tableau_apparie.empty:
                st.info(
                    "Tableau apparié vide ou incomplet : aucun prompt ne contient toutes les modalités sélectionnées."
                )
            else:
                nb_modeles = tableau_apparie.shape[1]
                modeles_list = list(tableau_apparie.columns)
                prompts_complets = tableau_apparie.index.tolist()
                st.markdown(
                    f"**Modèles inclus (k = {nb_modeles})** : {', '.join(str(m) for m in modeles_list)}"
                )
                st.markdown(
                    f"Prompts initiaux : {len(prompts_initiaux)} | Prompts complets utilisés : {len(prompts_complets)} | Prompts exclus : {len(prompts_exclus)}"
                )

                if prompts_exclus:
                    st.caption("Prompts exclus (données manquantes) : " + ", ".join(map(str, prompts_exclus)))

                resultat_friedman = calculer_statistique_friedman(tableau_apparie)

                if resultat_friedman is None:
                    st.info("Test de Friedman impossible : au moins deux modèles et deux prompts complets sont requis.")
                else:
                    st.markdown(
                        f"Chi² de Friedman = {resultat_friedman['statistique']:.4f}, p-value = {resultat_friedman['p_value']:.4g}"
                    )
                    st.markdown(
                        f"Kendall W = {resultat_friedman['kendall_w']:.4f} (n = {resultat_friedman['n_prompts']}, k = {resultat_friedman['k_modeles']})"
                    )

                st.dataframe(
                    tableau_apparie.reset_index().rename(columns={variable_bloc: "Bloc / prompt"}),
                    use_container_width=True,
                )

                st.markdown("#### Comparaisons post-hoc (Wilcoxon signé-rang)")
                st.caption(
                    "Après le test global de Friedman, ces comparaisons par paires"
                    " identifient quelles modalités diffèrent réellement. Les p-values"
                    " sont ajustées pour contrôler les erreurs liées aux tests multiples."
                )

                corrections = {
                    "Aucun": None,
                    "Holm": "holm",
                    "Bonferroni": "bonferroni",
                    "Benjamini–Hochberg": "fdr_bh",
                }
                methode_corr = st.selectbox(
                    "Méthode d'ajustement des p-values (post-hoc)",
                    list(corrections.keys()),
                )

                if tableau_apparie.shape[0] < 3:
                    st.warning(
                        "Attention : moins de 3 prompts appariés, les tests de Wilcoxon peuvent manquer de puissance."
                    )

                resultats_post_hoc = tests_post_hoc_wilcoxon(
                    tableau_apparie, methode_correction=corrections[methode_corr]
                )

                if resultats_post_hoc.empty:
                    st.info("Aucune comparaison post-hoc exploitable (prompts complets insuffisants ou paires invalides).")
                else:
                    st.dataframe(
                        resultats_post_hoc.rename(
                            columns={
                                "modele_a": "Modèle A",
                                "modele_b": "Modèle B",
                                "statistique": "Statistique (Wilcoxon)",
                                "p_brute": "p-value brute",
                                "p_ajustee": "p-value ajustée",
                                "n": "Prompts",
                            }
                        ),
                        use_container_width=True,
                    )

                long_format = tableau_apparie.reset_index().melt(
                    id_vars=variable_bloc, var_name="modele", value_name="valeur"
                )

                st.markdown("#### Visualisation des valeurs appariées")
                box_chart_appaire = (
                    alt.Chart(long_format)
                    .mark_boxplot()
                    .encode(
                        x=alt.X("modele:N", title="Modèle"),
                        y=alt.Y("valeur:Q", title=choix_indicateur_friedman),
                        color=alt.Color("modele:N", title="Modèle"),
                        tooltip=[
                            alt.Tooltip("modele:N", title="Modèle"),
                            alt.Tooltip("valeur:Q", title="Valeur", format=".3f"),
                            alt.Tooltip(variable_bloc + ":N", title="Bloc/prompt"),
                        ],
                    )
                )

                st.altair_chart(box_chart_appaire, use_container_width=True)

                st.markdown("#### Comparaison post-hoc par prompt")
                st.caption(
                    "Ce graphique relie les valeurs de chaque modèle pour un même prompt. "
                    "Après le test de Friedman, il met en évidence où se situent les "
                    "écarts entre modalités et comment chaque prompt contribue aux "
                    "différences globales."
                )

                spaghetti_chart = (
                    alt.Chart(long_format)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("modele:N", title="Modèle"),
                        y=alt.Y("valeur:Q", title=choix_indicateur_friedman),
                        color=alt.Color(variable_bloc + ":N", title="Bloc/prompt", legend=None),
                        tooltip=[
                            alt.Tooltip(variable_bloc + ":N", title="Bloc/prompt"),
                            alt.Tooltip("modele:N", title="Modèle"),
                            alt.Tooltip("valeur:Q", title="Valeur", format=".3f"),
                        ],
                    )
                )

                st.altair_chart(spaghetti_chart, use_container_width=True)

    st.markdown("---")
    st.subheader("Comparaison de distributions (KS)")
    st.write(
        "Comparez les distributions de longueurs de segments entre modalités avec le test"
        " de Kolmogorov–Smirnov à deux échantillons. Les longueurs sont calculées avec"
        " les mêmes réglages de segmentation/tokenisation que ci-dessus."
    )

    variable_ks = st.selectbox(
        "Variable pour la comparaison des distributions",
        hash_variables,
        help=(
            "Choisissez la variable (modèle, prompt…) dont vous voulez comparer les distributions"
            " de longueurs de segments."
        ),
    )

    longueurs_par_modalite = extraire_longueurs_par_modalite(
        hash_filtered_df,
        variable_ks,
        filtered_connectors,
        segmentation_mode=segmentation_mode,
        tokenization_mode=tokenization_mode,
    )

    if not longueurs_par_modalite:
        st.info(
            "Impossible de calculer les distributions : aucune longueur de segment n'a été"
            " trouvée pour les modalités disponibles."
        )
        return

    modalites_disponibles = sorted(longueurs_par_modalite)

    comparer_toutes = st.checkbox(
        "Comparer toutes les modalités par paires",
        help=(
            "Calcule le test KS pour toutes les paires de modalités de la variable choisie"
            " et applique éventuellement une correction pour comparaisons multiples."
        ),
    )

    if comparer_toutes:
        methodes_correction = {
            "Aucune": None,
            "Bonferroni": "bonferroni",
            "Holm": "holm",
            "Benjamini–Hochberg (FDR)": "fdr_bh",
        }
        methode_label = st.selectbox(
            "Méthode de correction",
            list(methodes_correction.keys()),
            help=(
                "Choisissez la méthode d'ajustement des p-values : Bonferroni et Holm sont"
                " plus conservateurs, Benjamini–Hochberg contrôle le taux de fausses"
                " découvertes."
            ),
        )

        resultats_paires = comparer_modalites_par_paires(
            longueurs_par_modalite, methode_correction=methodes_correction[methode_label]
        )

        if resultats_paires.empty:
            st.info("Aucune paire exploitable (tailles d'échantillon insuffisantes ou données vides).")
            return

        st.write(
            "Tableau trié par p-value" + (" ajustée" if methodes_correction[methode_label] else "")
        )
        st.dataframe(
            resultats_paires.rename(
                columns={
                    "modalite_a": "Modalité A",
                    "modalite_b": "Modalité B",
                    "D": "D (écart max)",
                    "p_brute": "p-value brute",
                    "p_ajustee": "p-value ajustée",
                    "n_a": "nA",
                    "n_b": "nB",
                    "rejette": "Rejet H0",
                }
            ),
            use_container_width=True,
        )
        st.caption(
            "D mesure l'écart maximal entre les proportions cumulées (0 = distributions identiques,"
            " 1 = distributions disjointes). p-value brute et ajustée sont affichées sans ambiguïté."
        )
        return

    if len(modalites_disponibles) < 2:
        st.info("Au moins deux modalités sont nécessaires pour une comparaison KS.")
        return

    modalite_a = st.selectbox("Modalité A", modalites_disponibles, index=0)
    modalite_b = st.selectbox(
        "Modalité B",
        modalites_disponibles,
        index=1 if len(modalites_disponibles) > 1 else 0,
        help="Choisissez une modalité différente pour comparer deux distributions.",
    )

    if modalite_a == modalite_b:
        st.warning("Sélectionnez deux modalités distinctes pour lancer la comparaison KS.")
        return

    longueurs_a = longueurs_par_modalite.get(modalite_a, [])
    longueurs_b = longueurs_par_modalite.get(modalite_b, [])

    resultat_ks: ResultatKSTest | None = calculer_test_ks(longueurs_a, longueurs_b)

    if resultat_ks is None:
        st.info("Impossible de calculer le test KS : échantillons vides ou trop petits.")
        return

    st.markdown(
        f"**D = {resultat_ks.D:.4f}**, **p-value brute = {resultat_ks.p_value:.4g}**, "
        f"**nA = {resultat_ks.n_a}**, **nB = {resultat_ks.n_b}**"
    )
    st.caption(
        "D représente l'écart maximal entre les proportions cumulées des deux distributions (entre 0 et 1)."
    )

    if resultat_ks.ecart_max:
        st.write(
            "Écart maximal atteint à L = {longueur:.0f} mots : {prop_a:.2f} vs {prop_b:.2f}"
            " (écart = {ecart:.2f}).".format(
                longueur=resultat_ks.ecart_max["longueur"],
                prop_a=resultat_ks.ecart_max["proportion_a"],
                prop_b=resultat_ks.ecart_max["proportion_b"],
                ecart=resultat_ks.ecart_max["ecart"],
            )
        )

    utiliser_permutation = st.checkbox(
        "Calculer aussi une p-value par permutation (option empirique)",
        help=(
            "Approche plus coûteuse mais robuste : mélange les longueurs, recombine deux groupes"
            " de même taille et estime la proportion de D_perm >= D_observé."
        ),
    )

    if utiliser_permutation:
        n_permutations = int(
            st.number_input(
                "Nombre de permutations", min_value=100, max_value=20000, value=2000, step=100
            )
        )
        total_obs = resultat_ks.n_a + resultat_ks.n_b
        if total_obs > 5000:
            st.warning(
                "Attention : le calcul par permutation peut être long pour des échantillons volumineux."
            )

        progression = st.progress(0.0)
        with st.spinner("Calcul des permutations en cours..."):
            p_perm = p_value_par_permutation(
                longueurs_a,
                longueurs_b,
                n_permutations=n_permutations,
                progress_callback=lambda avance: progression.progress(min(avance, 1.0)),
            )

        if p_perm is not None:
            resultat_ks.p_value_permutation = p_perm
            st.markdown(f"p-value par permutation ≈ {p_perm:.4g}")
        else:
            st.info("P-value par permutation non calculée (échantillons vides ou paramètres invalides).")

    if not resultat_ks.ecdf_a.empty and not resultat_ks.ecdf_b.empty:
        ecdf_plot_df = pd.concat(
            [
                resultat_ks.ecdf_a.assign(modalite=modalite_a),
                resultat_ks.ecdf_b.assign(modalite=modalite_b),
            ]
        )

        ecdf_chart = (
            alt.Chart(ecdf_plot_df)
            .mark_line(interpolate="step-after")
            .encode(
                x=alt.X("longueur:Q", title="Longueur de segment (mots)"),
                y=alt.Y("proportion_cumulee:Q", title="Proportion cumulée"),
                color=alt.Color("modalite:N", title="Modalité"),
                tooltip=[
                    alt.Tooltip("modalite:N", title="Modalité"),
                    alt.Tooltip("longueur:Q", title="Longueur"),
                    alt.Tooltip("proportion_cumulee:Q", title="Proportion cumulée", format=".2f"),
                ],
            )
        )

        st.markdown("#### Fonctions de répartition cumulée (ECDF)")
        st.altair_chart(ecdf_chart, use_container_width=True)

