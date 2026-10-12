"""Découverte ciblée par compte, avec le moteur commun de navigation TikTok."""
from urllib.parse import quote
from .verification_comptes import normaliser_compte


def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Lire les pages publiques de hashtags ou de profil en contrôlant l'auteur."""
    from scraptiktok import collect_links, normalize_hashtag, canonical_post, manual_step, WebDriverException
    compte = normaliser_compte(compte)
    rapport = rapport if rapport is not None else {}
    hashtags = list(dict.fromkeys(normalize_hashtag(h) for h in hashtags))
    profil = "https://www.tiktok.com/@" + quote(compte)
    # Même entrée /tag/ que le mode hashtag, sans passer par la recherche globale.
    # Sans hashtag, lire directement les publications du profil public demandé.
    recherches = (["https://www.tiktok.com/tag/" + quote(h) for h in hashtags]
                  if hashtags else [profil])
    rapport.update(compte_attendu=compte, mode_decouverte="hashtags_publics" if hashtags else "profil_public",
                   recherches=[], exhaustif=False)
    liens = {}
    # Compatibilité avec les anciens appelants : ne jamais imposer de validation
    # préalable en mode compte. Le profil montre aussi automatiquement une page
    # sans liens ou une pagination bloquée, même sans CAPTCHA reconnu.
    options.pop("validation_initiale", None)
    options["intervention_si_vide"] = False
    options["sans_connexion"] = True
    interaction = options.pop("interact", manual_step)

    def rechercher(url, plafond=None):
        recherche = {"hashtag_url": url, "compte_attendu": compte}
        rapport["recherches"].append(recherche)
        try:
            if url == profil:
                from .profil_selenium import collecter_grille_profil
                trouves = collecter_grille_profil(navigateur, arguments, recherche,
                    interact=interaction, check=options.get("check"), progress=options.get("progress"))
            else:
                trouves = collect_links(navigateur, arguments, recherche, interact=interaction,
                                       validation_initiale=False, **options)
        except (RuntimeError, WebDriverException) as erreur:
            recherche["erreur"] = str(erreur)
            # Une vérification ne doit pas être masquée en changeant de page.
            if recherche.get("diagnostic", {}).get("code") == "verification_tiktok" or recherche.get("discovery_stop") == "blocked":
                rapport.update(diagnostic=recherche.get("diagnostic", {}), discovery_stop="blocked")
                raise
            return erreur
        for lien in trouves:
            identite = canonical_post(lien)
            if (identite and identite[2].casefold() == compte
                    and (plafond is None or len(liens) < plafond)):
                liens.setdefault(identite[0], identite[1])
        rapport.update({k: recherche[k] for k in ("hashtag_url", "discovery_stop", "diagnostic") if k in recherche})
        return None

    erreurs = []
    for url in recherches:
        erreur = rechercher(url)
        if erreur: erreurs.append(erreur)
    # Quelques résultats de recherche ne représentent pas l'historique du compte.
    # Compléter aussi les résultats partiels, sans dépasser l'objectif avec ce repli.
    if hashtags and len(liens) < arguments.limit:
        rapport["repli"] = "profil"
        rapport["liens_avant_profil"] = len(liens)
        erreur = rechercher(profil, plafond=arguments.limit)
        if erreur: erreurs.append(erreur)
    rapport["recherches_en_echec"] = len(erreurs)
    rapport["discovered_urls"] = list(liens.values())
    rapport["objectif_liens"] = arguments.limit
    rapport["objectif_atteint"] = len(liens) >= arguments.limit
    rapport["limite_acces_public"] = any(
        r.get("diagnostic", {}).get("code") == "connexion_sans_publications_publiques"
        or r.get("discovery_stop") == "connexion_apres_resultats"
        for r in rapport["recherches"])
    if erreurs and len(erreurs) == len(rapport["recherches"]):
        derniere = rapport["recherches"][-1]
        rapport.update({k: derniere[k] for k in ("hashtag_url", "diagnostic", "discovery_stop") if k in derniere})
        raise erreurs[-1]
    rapport["verification"] = {"compte": compte, "concordant": None,
                               "raison": "liens_avec_filtrage_auteur"}
    return list(liens.values())
