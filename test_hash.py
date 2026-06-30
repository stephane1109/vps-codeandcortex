"""### Tests du calcul de hachage textuel

Les tests couvrent les règles de découpe des segments en fonction des
connecteurs et de la ponctuation, afin d'assurer la cohérence des métriques
de "hachage" utilisées pour qualifier la fluidité des textes."""

from __future__ import annotations

import hash as hash_module


def test_punctuation_ignored_without_connectors():
    connectors = {"mais": "adversatif"}
    text = (
        "Le fait que tu en parles, que tu mettes des mots dessus, c’est déjà un pas important."
        " Il n'y a pas de connecteur logique explicite dans cet exemple."
    )

    segments = hash_module.split_segments_by_connectors(
        text, connectors, segmentation_mode="connecteurs_et_ponctuation"
    )

    assert [segment.strip() for segment in segments] == [text.strip()]


def test_punctuation_applied_when_connectors_present():
    connectors = {"mais": "adversatif", "pourtant": "adversatif"}
    text = "Il avance mais il hésite. Pourtant il continue"

    segments = hash_module.split_segments_by_connectors(
        text, connectors, segmentation_mode="connecteurs_et_ponctuation"
    )

    assert [segment.strip() for segment in segments] == [
        "Il avance",
        "il hésite",
        "il continue",
    ]


def test_punctuation_segments_must_touch_connectors():
    connectors = {"si": "condition"}
    text = "Bonjour. Ensuite si tu veux. Merci."

    segments = hash_module.split_segments_by_connectors(
        text, connectors, segmentation_mode="connecteurs_et_ponctuation"
    )

    assert [segment.strip() for segment in segments] == [
        "Ensuite",
        "tu veux",
    ]


def test_metadata_line_removed_for_claude_model():
    connectors = {"mais": "adversatif"}
    text = "\n".join(
        [
            "**** *model_claude *prompt_1 []",
            "Ceci est un texte mais pas un autre",
        ]
    )

    segments = hash_module.split_segments_by_connectors(text, connectors)

    assert [segment.strip() for segment in segments] == [
        "Ceci est un texte",
        "pas un autre",
    ]


def test_all_metadata_lines_are_removed():
    connectors = {"mais": "adversatif", "pourtant": "adversatif"}
    text = "\n".join(
        [
            "**** *model_claude *prompt_1 []",
            "Introduction sans connecteur explicite",
            "   **** ligne metadonnees indentee",
            "Il avance mais il hésite",
            "**** autre metadonnees",
            "Pourtant il continue",
        ]
    )

    segments = hash_module.split_segments_by_connectors(text, connectors)

    assert [segment.strip() for segment in segments] == [
        "Introduction sans connecteur explicite\nIl avance",
        "il hésite",
        "il continue",
    ]


def test_newline_connectors_are_recognized():
    connectors = {"\n": "RETOUR À LA LIGNE", "\r\n": "RETOUR À LA LIGNE"}
    text = "Première ligne\nDeuxième ligne\nTroisième ligne"

    segments = hash_module.split_segments_by_connectors(text, connectors)

    assert [segment.strip() for segment in segments] == [
        "Première ligne",
        "Deuxième ligne",
        "Troisième ligne",
    ]


def test_spacy_tokenization_counts_words_without_punctuation():
    connectors = {"mais": "adversatif"}
    text = "Il avance, mais il hésite encore !"

    lengths = hash_module.compute_segment_word_lengths(
        text,
        connectors,
        segmentation_mode="connecteurs_et_ponctuation",
        tokenization_mode="spacy",
    )

    assert lengths == [2, 3]
