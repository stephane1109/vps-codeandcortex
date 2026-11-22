"""Découverte des pages de hashtags TikTok, avec variantes accentuées facultatives."""
import unicodedata
from scraptiktok import normalize_hashtag

# Éviter une explosion combinatoire de pages TikTok pour une seule saisie.
ACCENTS = {
    "a": ("à", "â"), "c": ("ç",), "e": ("é", "è", "ê", "ë"),
    "i": ("î", "ï"), "o": ("ô", "ö"), "u": ("ù", "û", "ü"),
}


def sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte)
                   if not unicodedata.combining(c))


def variantes_hashtag(hashtag, *, avec_accents=False, maximum=8):
    """Produire une liste bornée de pages : original, sans accents et variantes simples.

    Les substitutions sont heuristiques : elles ne prétendent pas recenser toutes
    les graphies françaises. La vérification finale porte sur le hashtag complet.
    """
    original = normalize_hashtag(hashtag)
    if not avec_accents:
        return [original]

    base = sans_accents(original)
    variantes = list(dict.fromkeys([original, base]))
    # Privilégier le premier « é » avant les combinaisons, pour que
    # #lyceen explore rapidement #lycéen même avec un faible objectif.
    e_positions = [i for i, c in enumerate(base) if c.casefold() == "e"]
    if len(e_positions) > 1:
        premier = e_positions[0]
        simple_aigu = base[:premier] + ("É" if base[premier] == "E" else "é") + base[premier+1:]
        if simple_aigu.casefold() not in {mot.casefold() for mot in variantes}:
            variantes.append(simple_aigu)
        # Graphies avec plusieurs accents : ete -> été.
        tout_aigu = "".join("É" if c == "E" else "é" if c == "e" else c for c in base)
        if tout_aigu.casefold() not in {mot.casefold() for mot in variantes}:
            variantes.append(tout_aigu)
    # Déjà accentué : garder en priorité le terme saisi et sa forme non accentuée.
    # Sans accent : explorer les positions accentuables par ordre de lecture.
    for i, lettre in enumerate(base):
        for accent in ACCENTS.get(lettre.casefold(), ()):
            remplacement = accent.upper() if lettre.isupper() else accent
            variante = base[:i] + remplacement + base[i+1:]
            if variante.casefold() not in {mot.casefold() for mot in variantes}:
                variantes.append(variante)
            if len(variantes) >= maximum:
                return variantes
    return variantes


def collecter_hashtag(navigateur, arguments, rapport, **options):
    from scraptiktok import collect_links
    return collect_links(navigateur, arguments, rapport, **options)
