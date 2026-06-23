import re

from regexanalyse import RegexPattern, highlight_matches_html


def _pattern(regex: str, label: str = "motif") -> RegexPattern:
    return RegexPattern(
        pattern_id="id",
        label=label,
        category="test",
        regex=regex,
        compiled=re.compile(regex, re.IGNORECASE),
    )


def test_highlight_respects_punctuation_boundaries():
    pattern = _pattern(r"bonjour.+salut", label="long")
    result = highlight_matches_html("Bonjour. Salut!", [pattern])

    assert "connector-annotation" not in result
    assert "Bonjour." in result
    assert "Salut!" in result


def test_highlight_within_single_segment():
    pattern = _pattern(r"si.+alors", label="condition")
    text = "Si tu viens alors nous partirons."  # single segment

    result = highlight_matches_html(text, [pattern])

    assert "connector-condition" in result
    assert "Si tu viens alors" in result
    assert "nous partirons." in result
