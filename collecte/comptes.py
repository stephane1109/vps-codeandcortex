"""Collecte bornée d’un profil ; exclut les recommandations d’autres auteurs."""
from .verification_comptes import normaliser_compte

def collecter_compte(navigateur, arguments, compte, rapport=None, **options):
    from scraptiktok import collect_links
    compte = normaliser_compte(compte)
    rapport = rapport if rapport is not None else {}
    rapport.update(hashtag_url="https://www.tiktok.com/@" + compte, compte_attendu=compte)
    liens = collect_links(navigateur, arguments, rapport, **options)
    from .verification_comptes import observer_profil
    try: rapport["verification"] = observer_profil(navigateur,compte)
    except Exception: rapport["verification"] = {"concordant":None,"raison":"profil_indisponible"}
    return liens
