"""### Tests de construction du sous-corpus

Les tests valident la filtration des enregistrements IRaMuTeQ et la
reconstitution des segments contenant des connecteurs afin de garantir que
seuls les prompts pertinents sont conservés."""

from __future__ import annotations

from souscorpus import build_subcorpus


def test_build_subcorpus_filters_non_prompt_records() -> None:
    records = [
        {"entete": "*doc_1", "texte": "Si ceci arrive, alors cela."},
        {"entete": "**** *model_gpt *prompt_2", "texte": "Sinon, nous attendons."},
    ]

    connectors = {"sinon": "ALTERNATIVE"}
    subcorpus_segments = build_subcorpus(records, connectors)

    assert len(subcorpus_segments) == 1
    assert subcorpus_segments[0].startswith("**** *model_gpt *prompt_2")


def test_build_subcorpus_rebuilds_prompt_with_connector_sentences() -> None:
    records = [
        {
            "entete": "**** *model_gpt *prompt_1",
            "texte": "Phrase isolée. Si le système fonctionne, alors tout se passe bien.",
        }
    ]

    connectors = {"si": "CONDITION", "alors": "ALORS"}
    subcorpus_segments = build_subcorpus(records, connectors)

    assert len(subcorpus_segments) == 1
    assert "Phrase isolée" not in subcorpus_segments[0]
    assert "Si le système fonctionne" in subcorpus_segments[0]
    assert subcorpus_segments[0].startswith("**** *model_gpt *prompt_1\n")


def test_build_subcorpus_keeps_multiple_connector_segments() -> None:
    records = [
        {
            "entete": "**** *model_gpt *prompt_3",
            "texte": "Si tu viens, alors nous partirons. Nous préparons le matériel. Donc tout ira bien.",
        }
    ]

    connectors = {"si": "CONDITION", "alors": "ALORS", "donc": "ALORS"}
    subcorpus_segments = build_subcorpus(records, connectors)

    assert len(subcorpus_segments) == 1
    assert "Si tu viens" in subcorpus_segments[0]
    assert "Donc tout ira bien" in subcorpus_segments[0]
    assert "Nous préparons ensuite" not in subcorpus_segments[0]


def test_build_subcorpus_preserves_entete_line_verbatim() -> None:
    entete = "**** *model_gpt *prompt_4   "
    records = [
        {
            "entete": entete,
            "texte": "Si tu veux venir, alors préviens-moi.",
        }
    ]

    connectors = {"si": "CONDITION"}
    subcorpus_segments = build_subcorpus(records, connectors)

    assert len(subcorpus_segments) == 1
    assert subcorpus_segments[0].split("\n", 1)[0] == entete


def test_build_subcorpus_includes_header_even_without_connectors() -> None:
    entete = "**** *model_gpt *prompt_5"
    records = [
        {
            "entete": entete,
            "texte": "Cette phrase ne contient aucun connecteur. Toujours rien.",
        }
    ]

    subcorpus_segments = build_subcorpus(records, {})


def test_build_subcorpus_respects_connector_selection() -> None:
    entete = "**** *model_gpt *prompt_6"
    records = [
        {
            "entete": entete,
            "texte": "Et ensuite nous verrons. Si besoin, alors nous agirons.",
        }
    ]

    connectors = {"si": "CONDITION", "alors": "ALORS"}
    subcorpus_segments = build_subcorpus(records, connectors)

    assert "Et ensuite" not in subcorpus_segments[0]
    assert "Si besoin" in subcorpus_segments[0]

    assert subcorpus_segments == [entete + "\nSi besoin, alors nous agirons."]
