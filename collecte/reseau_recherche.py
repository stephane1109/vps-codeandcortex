"""Observation passive des pages de recherche reçues par Chrome."""
import json
import re
from urllib.parse import parse_qs

from .reseau_profils import ObservationProfil


def extraire_page_recherche(donnees):
    """Lire les auteurs des objets vidéo, avant de filtrer le compte demandé."""
    from scraptiktok import canonical_post
    if not isinstance(donnees, dict):
        return None
    corps = donnees.get("data") if isinstance(donnees.get("data"), dict) else donnees
    code = donnees.get("status_code", donnees.get("statusCode",
               corps.get("status_code", corps.get("statusCode"))))
    valide = code in (None, 0, "0")
    elements = next((corps[champ] for champ in ("item_list", "itemList", "data")
                     if isinstance(corps.get(champ), list)), None)
    valide = valide and elements is not None
    liens = []
    if valide:
        trouves = {}
        pile = list(elements)
        while pile:
            element = pile.pop()
            if isinstance(element, list):
                pile.extend(element)
            elif isinstance(element, dict):
                identifiant = str(element.get("id") or "")
                auteur = element.get("author")
                auteur = auteur.get("uniqueId") if isinstance(auteur, dict) else auteur
                # Les cartes de recherche ne fournissent pas nécessairement de
                # légende : ne pas exiger le champ "desc" pour trouver une vidéo.
                if (identifiant.isdecimal() and isinstance(auteur, str)
                        and re.fullmatch(r"[\w.]+", auteur, flags=re.ASCII)
                        and (element.get("video") or element.get("imagePost"))):
                    genre = "photo" if element.get("imagePost") else "video"
                    identite = canonical_post(
                        f"https://www.tiktok.com/@{auteur}/{genre}/{identifiant}"
                    )
                    if identite:
                        trouves.setdefault(identite[0], identite[1])
                pile.extend(element.values())
        liens = list(trouves.values())
    suite = corps.get("has_more", corps.get("hasMore",
             donnees.get("has_more", donnees.get("hasMore"))))
    suite = (True if suite in (True, 1, "1", "true") else
             False if suite in (False, 0, "0", "false") else None) if valide else None
    curseur = corps.get("cursor", donnees.get("cursor"))
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
