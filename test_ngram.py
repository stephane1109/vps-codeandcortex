"""### Tests des utilitaires n-grammes

Ces scénarios vérifient la génération de motifs, le calcul de statistiques
et l'extraction de contexte autour des séquences fréquentes afin de sécuriser
les analyses quantitatives et qualitatives sur le corpus."""

import pandas as pd

from ngram import build_ngram_pattern, compute_ngram_statistics, extract_ngram_context


def test_compute_specific_trigrams_topk_and_modalities():
    df = pd.DataFrame(
        {
            "texte": [
                "alpha beta gamma alpha beta gamma",
                "alpha beta delta",
            ],
            "groupe": ["A", "B"],
        }
    )

    result = compute_ngram_statistics(
        df,
        min_n=2,
        max_n=4,
        top_k=2,
        specific_n=3,
        top_modalities=2,
    )

    assert not result.empty
    assert set(result["Taille"]) == {3}
    # the trigram "alpha beta gamma" should appear twice across group A
    first_row = result.iloc[0]
    assert first_row["N-gram"] == "alpha beta gamma"
    assert first_row["Fréquence"] == 2
    assert "groupe=A" in first_row["Modalités associées"]


def test_extract_ngram_context_handles_apostrophes():
    text = "Tu n’es pas obligé de répondre. Une autre phrase suit."
    tokens = ("tu", "n", "es", "pas")

    context = extract_ngram_context(text, tokens)

    assert "Tu n’es pas" in context


def test_build_ngram_pattern_matches_with_punctuation():
    pattern = build_ngram_pattern(["tu", "n", "es", "pas"])

    assert pattern.search("Tu n’es pas obligé de répondre")
    assert pattern.search("tu n'es pas obligé de répondre")
