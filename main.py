from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ticket_gate import enforce_streamlit_access, keep_ticket_alive


APP_NAME = "CHD Rainette"
APP_ID = "chdrainette"
DEFAULT_UPOS = ["NOUN", "ADJ"]
UPOS_OPTIONS = [
    "ADJ",
    "ADP",
    "ADV",
    "AUX",
    "CCONJ",
    "DET",
    "INTJ",
    "NOUN",
    "NUM",
    "PART",
    "PRON",
    "PROPN",
    "PUNCT",
    "SCONJ",
    "SYM",
    "VERB",
    "X",
]


def resolve_app_dir() -> Path:
    return Path(__file__).resolve().parent


def resolve_data_dir() -> Path:
    root = Path(os.getenv("APP_DATA_DIR", "/data/app")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_jobs_dir() -> Path:
    jobs_dir = resolve_data_dir() / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def build_run_paths() -> dict[str, Path]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = resolve_jobs_dir() / run_id
    input_dir = run_dir / "input"
    output_dir = run_dir / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": Path(run_id),
        "run_dir": run_dir,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "config_path": run_dir / "config.json",
        "input_path": input_dir / "corpus.txt",
        "zip_path": run_dir / "exports.zip",
    }


def save_uploaded_file(uploaded_file, destination: Path) -> None:
    destination.write_bytes(uploaded_file.getvalue())


def write_config(destination: Path, payload: dict) -> None:
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_rainette_batch(config_path: Path, input_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    app_dir = resolve_app_dir()
    script_path = app_dir / "backend" / "run_chdrainette.R"
    env = os.environ.copy()
    env.setdefault("CHDRAINETTE_CACHE_DIR", str(resolve_data_dir() / "cache"))
    Path(env["CHDRAINETTE_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["Rscript", str(script_path), str(config_path), str(input_path), str(output_dir)],
        cwd=str(app_dir),
        capture_output=True,
        text=True,
        env=env,
    )


def read_json_if_exists(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_csv_if_exists(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def build_zip_archive(source_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(source_dir))
    return zip_path


def render_download_button(path: Path, label: str, mime: str | None = None) -> None:
    if not path.exists():
        return
    guessed = mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    st.download_button(
        label=label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=guessed,
        use_container_width=True,
    )


def display_image_if_exists(path: Path, caption: str) -> None:
    if path.exists():
        st.image(str(path), caption=caption, use_container_width=True)


def render_outputs(run_state: dict) -> None:
    output_dir = Path(run_state["output_dir"])
    metadata = read_json_if_exists(output_dir / "metadata.json") or {}
    summary_df = load_csv_if_exists(output_dir / "resume_classes.csv")
    details_df = load_csv_if_exists(output_dir / "mots_chi2_frequence_segments.csv")
    concordance_csv = output_dir / "mots_chi2_segments.csv"
    concordance_html = output_dir / "segments_par_classe.html"
    zip_path = build_zip_archive(output_dir, Path(run_state["zip_path"]))

    tabs = st.tabs(["Synthèse", "Graphiques", "Concordancier", "Exports", "Logs"])

    with tabs[0]:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Documents importés", metadata.get("n_documents_imported", "—"))
        col2.metric("Segments créés", metadata.get("n_segments_created", "—"))
        col3.metric("Segments analysés", metadata.get("n_segments_analyzed", "—"))
        col4.metric("Classes", metadata.get("n_classes", "—"))

        st.markdown(
            "L'exploration interactive `rainette_explor(...)` n'est pas utilisée sur le VPS : "
            "elle est remplacée ici par des exports statiques intégrés à l'interface."
        )

        if metadata.get("settings"):
            with st.expander("Paramètres utilisés"):
                st.json(metadata["settings"])

        if summary_df is not None and not summary_df.empty:
            st.subheader("Résumé des classes")
            st.dataframe(summary_df, use_container_width=True)

        if details_df is not None and not details_df.empty:
            st.subheader("Aperçu des mots discriminants")
            st.dataframe(details_df.head(100), use_container_width=True)

    with tabs[1]:
        display_image_if_exists(output_dir / "rainette_plot.png", "Visualisation statique Rainette")
        display_image_if_exists(output_dir / "class_distribution.png", "Répartition des classes")

        wordcloud_dir = output_dir / "wordclouds"
        if wordcloud_dir.exists():
            pngs = sorted(wordcloud_dir.glob("*.png"))
            if pngs:
                st.subheader("Nuages de mots")
                cols = st.columns(2)
                for idx, image_path in enumerate(pngs):
                    cols[idx % 2].image(str(image_path), caption=image_path.name, use_container_width=True)

    with tabs[2]:
        if concordance_html.exists():
            html_content = concordance_html.read_text(encoding="utf-8", errors="ignore")
            components.html(html_content, height=700, scrolling=True)
        else:
            st.info("Le concordancier HTML n'a pas été généré.")

        if concordance_csv.exists():
            render_download_button(concordance_csv, "Télécharger le concordancier CSV", "text/csv")

    with tabs[3]:
        render_download_button(zip_path, "Télécharger tous les exports (ZIP)", "application/zip")

        exports = [path for path in sorted(output_dir.rglob("*")) if path.is_file()]
        if exports:
            for file_path in exports:
                render_download_button(file_path, f"Télécharger {file_path.relative_to(output_dir)}")
        else:
            st.info("Aucun export disponible.")

    with tabs[4]:
        if run_state.get("returncode", 1) == 0:
            st.success("Analyse terminée avec succès.")
        else:
            st.error("Analyse terminée avec erreur.")

        st.code(run_state.get("stdout", "") or "(stdout vide)")
        if run_state.get("stderr"):
            st.code(run_state["stderr"])


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")

    # #### VARIABLES D'ENVIRONNEMENT VPS A AJUSTER DANS COOLIFY SI BESOIN
    # - REDIS_URL=redis://:motdepasse@nom-du-service-redis:6379/0
    # - APP_TICKET_ID=chdrainette
    # - APP_TICKET_MAX_ACTIVE=1
    # - APP_TICKET_COST=4
    # - CAPACITE_SERVEUR=6
    # - APP_TICKET_TTL_SECONDS=3600
    # - APP_TICKET_MAX_WAITING=20
    # - APP_TICKET_WAIT_REFRESH_MS=10000
    # - APP_TICKET_HEARTBEAT_MS=300000
    # - APP_TICKET_RELEASE_URL=https://vps.codeandcortex.fr/api/tickets/release
    # - APP_TICKET_HIDDEN_RELEASE_SECONDS=300
    # - APP_DATA_DIR=/data/app
    # - CHDRAINETTE_R_LIBS_USER=/data/app/r-library
    # - PORT=8501
    enforce_streamlit_access(APP_ID, APP_NAME)

    st.title(APP_NAME)
    st.markdown("[www.codeandcortex.fr](https://www.codeandcortex.fr)")
    st.markdown(
        """
Cette adaptation VPS exécute la CHD Rainette en **mode batch R** puis affiche les sorties
dans la même interface. La visualisation `rainette_explor(...)` qui ouvre un navigateur Shiny séparé
est remplacée ici par des **exports statiques** : image Rainette, répartition des classes, nuages de mots,
concordancier HTML et exports CSV/TXT.
"""
    )

    st.session_state.setdefault("chdrainette_last_run", None)

    with st.sidebar:
        st.header("Paramètres CHD")
        mode_decoupage = st.selectbox(
            "Mode de découpage",
            options=["segment_size", "ponctuation"],
            index=0,
            help="segment_size = segments de taille fixe ; ponctuation = phrases.",
        )
        segment_size = st.number_input(
            "Taille des segments (mots)",
            min_value=10,
            max_value=500,
            value=40,
            step=5,
            disabled=mode_decoupage != "segment_size",
        )
        k = st.number_input("Nombre de classes (k)", min_value=2, max_value=20, value=6, step=1)
        min_split_segments = st.number_input(
            "Segments minimum avant division",
            min_value=3,
            max_value=100,
            value=12,
            step=1,
        )
        min_docfreq = st.number_input(
            "Fréquence documentaire minimale",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
        )
        top_n = st.number_input(
            "Nombre maximal de mots par classe",
            min_value=5,
            max_value=100,
            value=20,
            step=1,
        )
        lemmatisation = st.checkbox("Activer la lemmatisation UDPipe", value=True)
        upos = st.multiselect(
            "UPOS à conserver",
            options=UPOS_OPTIONS,
            default=DEFAULT_UPOS,
            disabled=not lemmatisation,
        )

    uploaded_file = st.file_uploader(
        "Importer un corpus texte compatible IRaMuTeQ (.txt)",
        type=["txt"],
        help="Le corpus peut contenir des lignes commençant par `****` comme dans IRaMuTeQ.",
    )

    if uploaded_file is not None:
        preview = uploaded_file.getvalue().decode("utf-8", errors="ignore").splitlines()
        with st.expander("Aperçu du corpus importé"):
            st.code("\n".join(preview[:40]) or "(fichier vide)")

    if st.button("Lancer l'analyse CHD Rainette", use_container_width=True):
        if uploaded_file is None:
            st.warning("Importe d'abord un corpus texte.")
        else:
            keep_ticket_alive(APP_ID, APP_NAME)
            paths = build_run_paths()
            save_uploaded_file(uploaded_file, paths["input_path"])
            config_payload = {
                "mode_decoupage": mode_decoupage,
                "segment_size": int(segment_size),
                "k": int(k),
                "min_split_segments": int(min_split_segments),
                "min_docfreq": int(min_docfreq),
                "top_n": int(top_n),
                "lemmatisation": bool(lemmatisation),
                "upos_a_conserver": upos or DEFAULT_UPOS,
            }
            write_config(paths["config_path"], config_payload)

            with st.spinner("Analyse Rainette en cours... cela peut prendre plusieurs minutes."):
                result = run_rainette_batch(paths["config_path"], paths["input_path"], paths["output_dir"])

            keep_ticket_alive(APP_ID, APP_NAME)
            st.session_state["chdrainette_last_run"] = {
                "run_dir": str(paths["run_dir"]),
                "output_dir": str(paths["output_dir"]),
                "zip_path": str(paths["zip_path"]),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

            if result.returncode == 0:
                st.success("Analyse Rainette terminée.")
            else:
                st.error("L'analyse Rainette a échoué. Regarde l'onglet Logs pour le détail.")

    if st.session_state.get("chdrainette_last_run"):
        render_outputs(st.session_state["chdrainette_last_run"])


if __name__ == "__main__":
    main()
