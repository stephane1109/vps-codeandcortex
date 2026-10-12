"""Observation passive des pages de recherche reçues par Chrome."""
import json
import re
from urllib.parse import parse_qs

from .reseau_profils import ObservationProfil


def extraire_page_recherche(donnees):
    """Lire les auteurs des objets vidéo, avant de filtrer le compte demandé."""
    from scraptiktok import liens_donnees_publications
    if not isinstance(donnees, dict):
        return None
    code = donnees.get("status_code", donnees.get("statusCode"))
    valide = code in (None, 0, "0")
    elements = next((donnees[c] for c in ("item_list", "itemList", "data")
                     if isinstance(donnees.get(c), list)), None)
    valide = valide and elements is not None
    liens = liens_donnees_publications([json.dumps(elements)]) if valide else []
    suite = donnees.get("has_more", donnees.get("hasMore"))
    suite = (True if suite in (True, 1, "1", "true") else
             False if suite in (False, 0, "0", "false") else None) if valide else None
    curseur = donnees.get("cursor")
    curseur = str(curseur) if valide and re.fullmatch(r"\d{1,32}", str(curseur)) else None
    code = code if re.fullmatch(r"\d{1,10}", str(code)) else None
    return {"liens": liens, "liste_valide": bool(valide), "suite": suite,
            "curseur": curseur, "code_tiktok": code}


class ObservationRecherche(ObservationProfil):
    """Réutiliser le canal borné sans requête directe ni repli vers un profil."""
    def accepter_reponse(self, url):
        requete = parse_qs(url.query)
        mots = requete.get("keyword", requete.get("q", []))
        return (url.scheme == "https" and url.hostname in {"www.tiktok.com", "tiktok.com"}
                and url.path.rstrip("/") in {"/api/search/item/full", "/api/search/general/full"}
                and len(mots) == 1 and mots[0].casefold() == "@" + self.compte.casefold())

    def analyser_page(self, donnees):
        return extraire_page_recherche(donnees)
