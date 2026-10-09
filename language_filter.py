"""Détection locale de la langue des descriptions, sans modifier leur export."""
from functools import lru_cache
import re
import unicodedata

from langdetect import DetectorFactory, LangDetectException
from langdetect.detector_factory import PROFILES_DIRECTORY


@lru_cache(maxsize=1)
def detector_factory():
    factory = DetectorFactory()
    factory.load_profile(PROFILES_DIRECTORY)
    factory.seed = 0
    return factory


def classify_description(description: str) -> str:
    """Retourne fr, other ou unknown ; les scores ne sont pas des garanties."""
    text = unicodedata.normalize("NFC", description)
    text = re.sub(r"(?:https?://|www\.)\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[#@][\w.]+", " ", text)
    words = re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)
    if len(words) < 4 or sum(map(len, words)) < 15:
        return "unknown"
    detector = detector_factory().create()
    detector.append(" ".join(words))
    try:
        candidates = detector.get_probabilities()
    except LangDetectException:
        return "unknown"
    if not candidates or candidates[0].prob < 0.9:
        return "unknown"
    return "fr" if candidates[0].lang == "fr" else "other"
