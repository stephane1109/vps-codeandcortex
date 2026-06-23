"""Tests autour du chargement et de la gestion des connecteurs."""

from pathlib import Path

import json

from analyses import annotate_connectors_html, count_connectors, load_connectors


def test_load_connectors_preserves_newline_entries(tmp_path: Path):
    connectors_file = tmp_path / "connecteurs.json"
    raw_connectors = {
        " si": "CONDITION",
        "\n": "RETOUR À LA LIGNE",
        "\r\n": "RETOUR À LA LIGNE",
        "": "IGNORED",
    }

    connectors_file.write_text(json.dumps(raw_connectors), encoding="utf-8")

    loaded = load_connectors(connectors_file)

    assert loaded == {"si": "CONDITION", "\n": "RETOUR À LA LIGNE"}


def test_annotate_connectors_html_displays_newline_connector():
    html = annotate_connectors_html("Titre\nCorps", {"\n": "RETOUR À LA LIGNE"})

    assert "Titre" in html
    assert "connector-retour-la-ligne" in html
    assert "↵" in html
    assert "<br />Corps" in html


def test_newline_after_starred_line_is_ignored():
    text = "**** *model_gpt *prompt_1\nTexte\nFin"
    connectors = {"\n": "RETOUR À LA LIGNE"}

    html = annotate_connectors_html(text, connectors)
    stats = count_connectors(text, connectors)

    assert html.count("RETOUR À LA LIGNE") == 1
    assert stats.loc[0, "occurrences"] == 1
