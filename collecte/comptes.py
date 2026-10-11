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
    # Commencer par les vidéos du compte, même sans hashtag : la grille du profil
    # n'est plus le point d'entrée obligatoire. Les hashtags restent facultatifs.
    recherches = [recherche_compte]
    # Compléter les candidats pour chacun des hashtags ; le filtre ET/OU exact
    # reste appliqué aux légendes, sans confondre la requête TikTok avec ce filtre.
    recherches.extend("https://www.tiktok.com/search/video?q=" + quote("@" + compte + " #" + h)
                      for h in hashtags)
    rapport.update(compte_attendu=compte, mode_decouverte="recherche_compte",
                   recherches=[], exhaustif=False)
    liens = {}
    validation = options.pop("validation_initiale", True)
    # Une grille vide doit permettre le repli automatique, pas demander une
    # confirmation « vidéos visibles ». Une vraie vérification reste interactive.
    options.setdefault("intervention_si_vide", False)
    options["sans_connexion"] = True
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
    # Une recherche sans résultat est complétée par le profil, dans la même session.
    if not liens:
        rapport["repli"] = "profil"
        erreur = rechercher(profil)
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
