######################
# www.codeandcortex.fr
######################

from __future__ import annotations

from pathlib import Path

import streamlit as st

from analysedebit import analyser_debit, format_timestamp, resolve_storage_directory
from analysepauses import analyser_pauses, generer_export_pauses, graph_pauses
from ticket_gate import enforce_streamlit_access, keep_ticket_alive


APP_NAME = "Analyse du débit de parole"


def render_download_button(path_str: str, label: str, mime: str) -> None:
    path = Path(path_str)
    if not path.exists():
        return
    st.download_button(
        label=label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime,
        use_container_width=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="centered")

    # #### VARIABLES D'ENVIRONNEMENT VPS A AJUSTER DANS COOLIFY SI BESOIN
    # - REDIS_URL
    # - APP_TICKET_ID
    # - APP_TICKET_MAX_ACTIVE
    # - APP_TICKET_COST
    # - CAPACITE_SERVEUR
    # - APP_TICKET_TTL_SECONDS
    # - APP_DATA_DIR
    # - WHISPER_MODEL_NAME
    enforce_streamlit_access("analyse_debit_parole", APP_NAME)

    st.title("Analyse du débit de parole d'une vidéo YouTube")
    st.markdown("[www.codeandcortex.fr](https://www.codeandcortex.fr)")
    st.markdown(
        """
        Cette application télécharge une vidéo YouTube, découpe un sous-clip et le transcrit avec Whisper.

        Choisissez la méthode de segmentation :

        - **whisper** : segmentation automatique effectuée par Whisper
        - **ponctuation** : découpage de la transcription par ponctuation sur la base des timestamps

        Tous les exports sont conservés côté serveur dans le dossier applicatif, et peuvent aussi être téléchargés depuis l'interface.
        """
    )

    with st.form(key="form_analyse"):
        video_url = st.text_input("URL de la vidéo YouTube", "")
        start_time = st.text_input("Temps de début (en secondes)", "0")
        end_time = st.text_input("Temps de fin (en secondes)", "60")
        repertoire = st.text_input(
            "Répertoire de stockage",
            "analyse-debit-parole",
            help="Nom du dossier de stockage sur le serveur VPS. Le dossier réel sera créé sous APP_DATA_DIR.",
        )
        segmentation_mode = st.selectbox(
            "Mode de segmentation",
            options=["whisper", "ponctuation"],
            help="Choisissez la méthode de segmentation.",
        )
        submit_button = st.form_submit_button(label="Analyser la vidéo")

    if submit_button:
        try:
            keep_ticket_alive("analyse_debit_parole", APP_NAME)
            output_dir = resolve_storage_directory(repertoire)
            st.info(f"Analyse en cours... Les fichiers seront stockés dans : {output_dir}")

            with st.spinner("Traitement de la vidéo et transcription Whisper..."):
                results = analyser_debit(
                    video_url,
                    float(start_time),
                    float(end_time),
                    repertoire,
                    segmentation_mode=segmentation_mode,
                )

            keep_ticket_alive("analyse_debit_parole", APP_NAME)

            (
                df_debit,
                chart_barres,
                chart_combine,
                export_text,
                export_fichier,
                df_csv,
                graph_barres_html,
                graph_barres_png,
                graph_combine_html,
                graph_combine_png,
                dialogue_file,
                transcript_segments,
                output_dir_str,
            ) = results

            st.video(video_url)
            st.success(f"Analyse terminée. Répertoire serveur : {output_dir_str}")

            st.subheader("Débit de parole par segment")
            st.dataframe(df_debit, use_container_width=True)
            st.altair_chart(chart_barres, use_container_width=True)
            st.altair_chart(chart_combine, use_container_width=True)

            st.subheader("Rapport détaillé des segments")
            st.text_area("Export texte", export_text, height=300)

            st.subheader("Exports")
            col1, col2 = st.columns(2)
            with col1:
                render_download_button(export_fichier, "Télécharger le rapport TXT", "text/plain")
                render_download_button(df_csv, "Télécharger le CSV", "text/csv")
                render_download_button(graph_barres_png, "Télécharger le graphique barres PNG", "image/png")
                render_download_button(graph_combine_png, "Télécharger le graphique combiné PNG", "image/png")
            with col2:
                render_download_button(graph_barres_html, "Télécharger le graphique barres HTML", "text/html")
                render_download_button(graph_combine_html, "Télécharger le graphique combiné HTML", "text/html")
                if dialogue_file:
                    render_download_button(dialogue_file, "Télécharger le fichier dialogues TXT", "text/plain")

            st.markdown(f"**Rapport TXT exporté :** `{export_fichier}`")
            st.markdown(f"**DataFrame CSV exportée :** `{df_csv}`")
            st.markdown(f"**Graphique en barres HTML :** `{graph_barres_html}`")
            st.markdown(f"**Graphique en barres PNG :** `{graph_barres_png}`")
            st.markdown(f"**Graphique combiné HTML :** `{graph_combine_html}`")
            st.markdown(f"**Graphique combiné PNG :** `{graph_combine_png}`")
            if dialogue_file:
                st.markdown(f"**Fichier de dialogue exporté :** `{dialogue_file}`")

            pauses = analyser_pauses(transcript_segments, seuil=1.0)
            if pauses:
                pause_text = generer_export_pauses(pauses, format_timestamp)
                st.subheader("Analyse des pauses")
                st.text_area("Analyse des pauses", pause_text, height=180)
                chart_pauses = graph_pauses(pauses)
                st.altair_chart(chart_pauses, use_container_width=True)
            else:
                st.subheader("Analyse des pauses")
                st.info("Aucune pause supérieure à 1 seconde n'a été détectée.")

            st.markdown(
                """
                **Remarque sur le découpage :**

                - En mode **whisper**, seule la segmentation interne détectée par Whisper est utilisée.
                - En mode **ponctuation**, la transcription globale est découpée par ponctuation.
                """
            )
        except Exception as exc:
            st.error(f"Une erreur est survenue : {exc}")


if __name__ == "__main__":
    main()
