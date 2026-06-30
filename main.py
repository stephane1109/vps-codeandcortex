from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass

import requests
import streamlit as st


DEFAULT_TITLES = "Bordeaux\nParis"
DEFAULT_LANGUAGE = "fr"
DEFAULT_KEEP_SECTIONS = [
    "geographie",
    "localisation",
    "geologie et relief",
    "paysages",
    "hydrographie",
    "climat",
]
DEFAULT_REMOVE_SECTIONS = [
    "notes et references",
    "notes",
    "cartes",
    "voir aussi",
    "bibliographie",
    "liens externes",
    "portail",
    "articles connexes",
    "devise",
]
USER_AGENT = "codeandcortex-scraper-wikipedia/1.0"


class WikipediaScraperError(RuntimeError):
    """Erreur fonctionnelle pour l'interface."""


@dataclass
class ArticleResult:
    title: str
    language: str
    output_text: str
    full_text: str
    output_filename: str


def parse_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_csv_like(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n,;]+", value) if item.strip()]


def normalize_heading(value: str) -> str:
    lowered = value.strip().lower()
    without_accents = "".join(
        character for character in unicodedata.normalize("NFD", lowered) if unicodedata.category(character) != "Mn"
    )
    without_punctuation = re.sub(r"[^\w\s-]", "", without_accents)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "article_wikipedia"


def extract_article_text(title: str, language: str = DEFAULT_LANGUAGE) -> str:
    url_api = f"https://{language}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "titles": title,
        "format": "json",
    }

    try:
        response = requests.get(
            url_api,
            params=params,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise WikipediaScraperError(f"Requete Wikipedia impossible pour '{title}' : {exc}") from exc
    except ValueError as exc:
        raise WikipediaScraperError(f"Reponse JSON invalide pour '{title}'.") from exc

    pages = (data.get("query") or {}).get("pages") or {}
    if not pages:
        raise WikipediaScraperError(f"Aucune page retournee pour '{title}'.")

    page = next(iter(pages.values()))
    if "missing" in page:
        raise WikipediaScraperError(f"L'article '{title}' est introuvable sur Wikipedia ({language}).")

    extract = str(page.get("extract") or "").strip()
    if not extract:
        raise WikipediaScraperError(f"Aucun texte exploitable n'a ete trouve pour '{title}'.")

    return extract


def split_sections(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [block.strip() for block in re.split(r"\n(?=[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸ][^\n]{0,80}\n)", normalized) if block.strip()]


def filter_useful_sections(text: str, keep_sections: list[str], remove_sections: list[str]) -> str:
    blocks = split_sections(text)
    if not blocks:
        return text.strip()

    keep_set = {normalize_heading(item) for item in keep_sections if item.strip()}
    remove_set = {normalize_heading(item) for item in remove_sections if item.strip()}

    filtered_blocks = [blocks[0].strip()]
    for block in blocks[1:]:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        heading = normalize_heading(lines[0])
        if heading in remove_set or any(heading.startswith(prefix) for prefix in remove_set):
            continue
        if keep_set and not any(heading.startswith(prefix) for prefix in keep_set):
            continue

        filtered_blocks.append(block.strip())

    return "\n\n".join(filtered_blocks).strip()


def build_zip_payload(results: list[ArticleResult]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result in results:
            archive.writestr(result.output_filename, result.output_text)
    return buffer.getvalue()


def process_titles(
    titles: list[str],
    language: str,
    apply_filter: bool,
    keep_sections: list[str],
    remove_sections: list[str],
) -> tuple[list[ArticleResult], list[str]]:
    results: list[ArticleResult] = []
    errors: list[str] = []

    for title in titles:
        try:
            full_text = extract_article_text(title, language=language)
            output_text = (
                filter_useful_sections(full_text, keep_sections=keep_sections, remove_sections=remove_sections)
                if apply_filter
                else full_text.strip()
            )
            if not output_text.strip():
                raise WikipediaScraperError(f"Aucun contenu n'a ete conserve pour '{title}' apres filtrage.")

            results.append(
                ArticleResult(
                    title=title,
                    language=language,
                    full_text=full_text,
                    output_text=output_text,
                    output_filename=f"{sanitize_filename(title)}_{language}.txt",
                )
            )
        except WikipediaScraperError as exc:
            errors.append(str(exc))

    return results, errors


def init_state() -> None:
    st.session_state.setdefault("wikipedia_results", [])
    st.session_state.setdefault("wikipedia_errors", [])


def main() -> None:
    st.set_page_config(page_title="Scraper Wikipedia", layout="wide")
    init_state()

    st.title("Scraper Wikipedia")
    st.markdown("[www.codeandcortex.fr](https://www.codeandcortex.fr)")
    st.markdown(
        """
        Cette application recupere le texte brut d'articles Wikipedia via l'API,
        applique au besoin un filtrage sur les sections utiles, puis permet de telecharger
        les articles nettoyes en `.txt` ou dans une archive `.zip`.
        """
    )

    with st.sidebar:
        st.header("Parametres")
        language = st.text_input("Code langue Wikipedia", value=DEFAULT_LANGUAGE)
        apply_filter = st.checkbox("Filtrer les sections utiles", value=True)
        keep_sections_value = st.text_area(
            "Sections a conserver",
            value="\n".join(DEFAULT_KEEP_SECTIONS),
            help="Une section par ligne, ou separees par virgules/points-virgules.",
        )
        remove_sections_value = st.text_area(
            "Sections a exclure",
            value="\n".join(DEFAULT_REMOVE_SECTIONS),
            help="Une section par ligne, ou separees par virgules/points-virgules.",
        )
        show_full_text = st.checkbox("Afficher aussi le texte integral", value=False)

    titles_value = st.text_area(
        "Titres d'articles Wikipedia",
        value=DEFAULT_TITLES,
        height=160,
        help="Un titre par ligne. Exemple : Bordeaux, Paris, Lyon.",
    )

    col_action, col_info = st.columns([1, 2])
    with col_action:
        launch = st.button("Lancer le scraping", type="primary")
    with col_info:
        st.caption("Le telechargement multiple genere une archive ZIP contenant un fichier texte par article.")

    if launch:
        titles = parse_lines(titles_value)
        if not titles:
            st.error("Veuillez renseigner au moins un titre d'article Wikipedia.")
        else:
            keep_sections = parse_csv_like(keep_sections_value)
            remove_sections = parse_csv_like(remove_sections_value)

            with st.spinner("Recuperation des articles Wikipedia..."):
                results, errors = process_titles(
                    titles=titles,
                    language=language.strip() or DEFAULT_LANGUAGE,
                    apply_filter=apply_filter,
                    keep_sections=keep_sections,
                    remove_sections=remove_sections,
                )

            st.session_state["wikipedia_results"] = results
            st.session_state["wikipedia_errors"] = errors

    results: list[ArticleResult] = st.session_state["wikipedia_results"]
    errors: list[str] = st.session_state["wikipedia_errors"]

    if results or errors:
        summary1, summary2, summary3 = st.columns(3)
        summary1.metric("Articles demandes", len(parse_lines(titles_value)))
        summary2.metric("Articles recuperes", len(results))
        summary3.metric("Erreurs", len(errors))

    if errors:
        st.subheader("Erreurs")
        for error in errors:
            st.error(error)

    if results:
        st.subheader("Exports")
        zip_payload = build_zip_payload(results)
        st.download_button(
            "Telecharger tous les articles (.zip)",
            data=zip_payload,
            file_name="articles_wikipedia.zip",
            mime="application/zip",
        )

        st.subheader("Apercu des articles")
        for result in results:
            with st.expander(f"{result.title} ({result.language})", expanded=len(results) == 1):
                preview_col, meta_col = st.columns([3, 1])
                with preview_col:
                    st.text_area(
                        f"Texte nettoye - {result.title}",
                        value=result.output_text,
                        height=280,
                        key=f"clean_{result.title}_{result.language}",
                    )
                with meta_col:
                    st.metric("Caracteres nettoyes", len(result.output_text))
                    st.metric("Caracteres bruts", len(result.full_text))
                    st.download_button(
                        f"Telecharger {result.title}",
                        data=result.output_text,
                        file_name=result.output_filename,
                        mime="text/plain",
                        key=f"download_{result.title}_{result.language}",
                    )

                if show_full_text:
                    st.text_area(
                        f"Texte integral - {result.title}",
                        value=result.full_text,
                        height=240,
                        key=f"full_{result.title}_{result.language}",
                    )


if __name__ == "__main__":
    main()
