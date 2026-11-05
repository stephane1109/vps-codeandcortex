"""Détection prudente de la langue des légendes, commune à tous les modes.

Une probabilité élevée de langdetect ne suffit pas à démontrer qu'une légende
n'est pas française. Les décisions incertaines sont conservées dans le corpus.
"""

from functools import lru_cache
import re
import unicodedata

from langdetect import DetectorFactory, LangDetectException
from langdetect.detector_factory import PROFILES_DIRECTORY


@lru_cache(maxsize=1)
def detector_factory():
    """Initialiser un détecteur déterministe et réutilisable."""
    fabrique = DetectorFactory()
    fabrique.load_profile(PROFILES_DIRECTORY)
    fabrique.seed = 0
    return fabrique


# Indices morphosyntaxiques français relativement distinctifs.
# Leur présence empêche d'écarter un texte français mal classé.
# Les mots sont normalisés sans accents avant comparaison.
INDICES_FRANCAIS = frozenset({
    "les", "des", "une", "dans", "pour", "avec", "nous", "vous",
    "sont", "cette", "leurs", "leur", "aux", "du", "etait",
    "etre", "parce", "comme", "mais", "chez", "pas", "sans",
    "sous", "avant", "apres", "depuis", "pendant", "devant",
    "contre", "lorsque", "notre", "votre", "ils", "elles",
    "ces", "cet", "ceux", "celles", "tous", "toutes",
    "aujourd", "hui", "ont", "est", "quand", "ainsi",
    "leurs", "quelques", "plusieurs",
})

# Les déterminants usuels manquaient à l'ancien contrôle : de nombreuses
# légendes françaises comportent « le », « la », « de », « et » sans deux
# termes de la liste précédente. Ces formes sont multilingues : il en faut
# plusieurs distinctes pour suspendre une exclusion, jamais pour la forcer.
INDICES_FRANCAIS_COURANTS = frozenset({
    "le", "la", "de", "en", "un", "et", "au", "ce", "se", "sa",
    "son", "ses", "par", "qui", "que", "ne", "il", "elle",
    "les", "des", "du", "aux", "une", "dans", "pour", "avec",
    "sont", "nous", "vous", "est", "ont", "pas", "sur",
    "sans", "mais", "ces", "cette", "leur", "leurs",
})


def normaliser_mot(mot):
    """Comparer les indices lexicaux sans tenir compte des accents."""
    texte = unicodedata.normalize("NFKD", mot.casefold())
    return "".join(
        caractere for caractere in texte
        if not unicodedata.combining(caractere))


def probabilites_langues(mots):
    """Estimer les langues d'un segment sans propager une erreur de détection."""
    detecteur = detector_factory().create()
    try:
        detecteur.append(" ".join(mots))
        return detecteur.get_probabilities()
    except (LangDetectException, ValueError):
        return []


def classify_description(description: str) -> str:
    """Classer la légende en fr, other ou unknown, sans modifier son contenu.

    Le filtre français est une règle d'exclusion prudente. Une légende ne
    devient « other » que si elle est assez longue, si la détection est
    très confiante, si aucun faisceau d'indices français n'est présent et
    si les deux moitiés du texte confirment la même langue étrangère.
    Les textes mixtes, courts ou ambigus restent « unknown ».
    """
    texte = unicodedata.normalize("NFC", str(description or ""))
    texte = re.sub(
        r"(?:https?://|www\.)\S+", " ", texte, flags=re.IGNORECASE)
    texte = re.sub(r"[#@][\w.]+", " ", texte)
    mots = re.findall(r"[^\W\d_]+", texte, flags=re.UNICODE)
    longueur_lettres = sum(map(len, mots))
    if len(mots) < 4 or longueur_lettres < 15:
        return "unknown"

    candidats = probabilites_langues(mots)
    if not candidats or candidats[0].prob < 0.90:
        return "unknown"
    langue = candidats[0].lang
    if langue == "fr":
        return "fr"

    # La prédiction étrangère doit être exceptionnelle et réexaminée.
    if len(mots) < 10 or longueur_lettres < 45:
        return "unknown"
    if candidats[0].prob < 0.99:
        return "unknown"

    indices = {normaliser_mot(mot) for mot in mots}
    if (len(indices.intersection(INDICES_FRANCAIS)) >= 2
            or len(indices.intersection(INDICES_FRANCAIS_COURANTS)) >= 3):
        return "unknown"

    # Une seule prédiction sur une longue légende mélangeant deux langues
    # peut masquer du français. Le résultat doit être stable dans ses
    # deux moitiés avant toute exclusion du corpus.
    milieu = len(mots) // 2
    for segment in (mots[:milieu], mots[milieu:]):
        candidats_segment = probabilites_langues(segment)
        if (not candidats_segment
                or candidats_segment[0].lang != langue
                or candidats_segment[0].prob < 0.80):
            return "unknown"
    return "other"
