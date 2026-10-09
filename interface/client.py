"""Client de l’API privée ; aucune donnée utilisateur dans un cache partagé."""
import os
import httpx


def appeler_api(chemin, session, autorisation="", donnees=None):
    entetes = {"Cookie":"scraptiktok_session=" + session, "X-ScrapTikTok":"1"}
    if autorisation: entetes["Authorization"] = autorisation
    adresse = os.getenv("SCRAPTIKTOK_API_URL", "http://127.0.0.1:8501")
    try:
        with httpx.Client(timeout=15, trust_env=False) as client:
            resultat = client.request("GET" if donnees is None else "POST", adresse + chemin, headers=entetes, json=donnees)
    except httpx.HTTPError as erreur:
        raise RuntimeError("Le moteur de collecte ne répond pas. Réessayez dans un instant.") from erreur
    if resultat.is_error:
        try: detail = resultat.json().get("detail")
        except ValueError: detail = None
        if isinstance(detail,list): detail = " / ".join(d.get("msg", "Valeur incorrecte").removeprefix("Value error, ") for d in detail)
        raise RuntimeError(detail or "La requête n’a pas pu aboutir.")
    return resultat.json()
