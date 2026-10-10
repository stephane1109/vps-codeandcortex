"""Découverte ciblée par compte, avec le moteur commun de navigation TikTok."""
from urllib.parse import quote
from .verification_comptes import normaliser_compte


def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Chercher chaque auteur avant les filtres ; ne pas tronquer un hashtag mondial."""
    from scraptiktok import collect_links, normalize_hashtag, canonical_post, manual_step, WebDriverException
    compte = normaliser_compte(compte)
    rapport = rapport if rapport is not None else {}
    hashtags = list(dict.fromkeys(normalize_hashtag(h) for h in hashtags))
    profil = "https://www.tiktok.com/@" + quote(compte)
    recherche_compte = "https://www.tiktok.com/search/video?q=" + quote("@" + compte)
    # Deux recherches en ET comme en OU : le filtre exact est appliqué aux légendes.
    # Ne pas abandonner la seconde recherche quand la première atteint sa limite.
    recherches = (["https://www.tiktok.com/search/video?q=" + quote("@" + compte + " #" + h)
                   for h in hashtags] if hashtags else [profil])
    rapport.update(compte_attendu=compte, mode_decouverte="recherche_ciblee" if hashtags else "profil",
                   recherches=[], exhaustif=False)
    liens = {}
    validation = options.pop("validation_initiale", True)
    interaction = options.pop("interact", manual_step)

    def intervenir(message):
        nonlocal validation
        interaction(message)
        validation = False

    def rechercher(url):
        recherche = {"hashtag_url": url, "compte_attendu": compte}
        rapport["recherches"].append(recherche)
        try:
            trouves = collect_links(navigateur, arguments, recherche, interact=intervenir,
                                    validation_initiale=validation, **options)
        except (RuntimeError, WebDriverException) as erreur:
            recherche["erreur"] = str(erreur)
            # Une vérification ne doit pas être masquée en changeant de page.
            if recherche.get("diagnostic", {}).get("code") == "verification_tiktok" or recherche.get("discovery_stop") == "blocked":
                rapport.update(diagnostic=recherche.get("diagnostic", {}), discovery_stop="blocked")
                raise
            return erreur
        for lien in trouves:
            identite = canonical_post(lien)
            if identite and identite[2].casefold() == compte:
                liens.setdefault(identite[0], identite[1])
        rapport.update({k: recherche[k] for k in ("hashtag_url", "discovery_stop") if k in recherche})
        return None

    erreurs = []
    for url in recherches:
        erreur = rechercher(url)
        if erreur: erreurs.append(erreur)
    # Une grille inaccessible dispose d'un second parcours public, dans la même session.
    # Une recherche ciblée sans résultat est complétée par les publications du profil.
    if not liens:
        rapport["repli"] = "profil" if hashtags else "recherche_compte"
        erreur = rechercher(profil if hashtags else recherche_compte)
        if erreur: erreurs.append(erreur)
    rapport["recherches_en_echec"] = len(erreurs)
    rapport["discovered_urls"] = list(liens.values())
    if erreurs and len(erreurs) == len(rapport["recherches"]):
        derniere = rapport["recherches"][-1]
        rapport.update({k: derniere[k] for k in ("hashtag_url", "diagnostic", "discovery_stop") if k in derniere})
        raise erreurs[-1]
    rapport["verification"] = {"compte": compte, "concordant": None,
                               "raison": "liens_avec_filtrage_auteur"}
    return list(liens.values())
