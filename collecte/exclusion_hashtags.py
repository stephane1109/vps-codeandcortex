"""Filtre exact des hashtags exclus du corpus TikTok."""
import re


def hashtags_publication(publication):
    """Conserver les hashtags structurés et explicitement écrits dans la légende."""
    hashtags = set()
    valeurs = publication.get("hashtags")
    if not isinstance(valeurs, (list, tuple, set)):
        valeurs = publication.get("hashtag_names")
    if isinstance(valeurs, (list, tuple, set)):
        for valeur in valeurs:
            if isinstance(valeur, str) and valeur.strip().lstrip("#"):
                hashtags.add(valeur.strip().lstrip("#").casefold())
    texte = publication.get("description") or publication.get("video_description") or ""
    if isinstance(texte, str):
        hashtags.update(
            nom.casefold() for nom in re.findall(r"(?<!\w)#(\w+)", texte)
        )
    return hashtags


def hashtags_a_exclure(publication, exclusions):
    """Renvoyer les exclusions constatées ; un mot sans # ne suffit jamais."""
    presents = hashtags_publication(publication)
    return [nom for nom in exclusions if nom.lstrip("#").casefold() in presents]
