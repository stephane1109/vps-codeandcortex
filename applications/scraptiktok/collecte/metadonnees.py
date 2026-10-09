"""Provenance et métadonnées non inférées."""
def extraire_metadonnees(element, date):
    video = element.get("video") or {}
    musique = element.get("music") or {}
    return {"duree_s": video.get("duration"), "largeur": video.get("width"), "hauteur": video.get("height"),
            "musique_id": musique.get("id"), "auteur_id": (element.get("author") or {}).get("id") if isinstance(element.get("author"), dict) else None,
            "source": "page_json", "observe_le": date}
