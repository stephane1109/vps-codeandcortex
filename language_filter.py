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


# Indices grammaticaux : ils ne prouvent pas le français, mais empêchent
# d'exclure une légende potentiellement française sur une seule prédiction.
INDICES_FRANCAIS = frozenset({
    "les", "des", "une", "dans", "pour", "avec", "nous", "vous",
    "sont", "cette", "leurs", "leur", "aux", "du", "était",
    "était", "être", "parce", "comme", "mais", "chez",
})


def classify_description(description: str) -> str:
    """Détecter une langue avec priorité à la conservation en cas de doute.

    Les légendes TikTok très courtes produisent de faux positifs « autre
    langue » avec langdetect. La modalité unknown conserve le texte original
    dans les corpus Hashtags comme dans les corpus Presse et médias.
    """
    texte = unicodedata.normalize("NFC", description or "")
    texte = re.sub(r"(?:https?://|www\.)\S+", " ", texte, flags=re.IGNORECASE)
    texte = re.sub(r"[#@][\w.]+", " ", texte)
    mots = re.findall(r"[^\W\d_]+", texte, flags=re.UNICODE)
    if len(mots) < 4 or sum(map(len, mots)) < 15:
        return "unknown"

    detecteur = detector_factory().create()
    detecteur.append(" ".join(mots))
    try:
        candidats = detecteur.get_probabilities()
    except LangDetectException:
        return "unknown"
    if not candidats or candidats[0].prob < 0.9:
        return "unknown"
    if candidats[0].lang == "fr":
        return "fr"

    # Un score élevé sur quelques mots ne suffit pas à prouver qu'une
    # légende française est étrangère. Ne l'exclure que si le corpus lexical
    # est assez long et la prédiction particulièrement nette.
    if len(mots) < 10 or sum(map(len, mots)) < 45:
        return "unknown"
    if candidats[0].prob < 0.99:
        return "unknown"

    indices = {unicodedata.normalize("NFC", mot).casefold() for mot in mots}
    if len(indices.intersection(INDICES_FRANCAIS)) >= 2:
        return "unknown"
    return "other"
