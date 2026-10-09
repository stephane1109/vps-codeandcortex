"""Provenance et métadonnées non inférées."""
def extraire_metadonnees(element, date):
    video = element.get("video") if isinstance(element.get("video"),dict) else {}
    musique = element.get("music") if isinstance(element.get("music"),dict) else {}
    return {"duree_s": video.get("duration"), "largeur": video.get("width"), "hauteur": video.get("height"),
            "musique_id": musique.get("id"), "auteur_id": (element.get("author") or {}).get("id") if isinstance(element.get("author"), dict) else None,
            "source": "page_json", "observe_le": date}
