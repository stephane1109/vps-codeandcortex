"""Provenance et métadonnées non inférées."""
def extraire_metadonnees(element, date):
    video = element.get("video") if isinstance(element.get("video"),dict) else {}
    musique = element.get("music") if isinstance(element.get("music"),dict) else {}
    return {"duree_s": video.get("duration"), "largeur": video.get("width"), "hauteur": video.get("height"),
            "musique_id": musique.get("id"), "auteur_id": (element.get("author") or {}).get("id") if isinstance(element.get("author"), dict) else None,
            "source": "page_json", "observe_le": date}


def indicateur_ia(element):
    """Lire une étiquette IA déclarée par TikTok, sans inférer son absence."""
    if not isinstance(element, dict):
        return None
    etiquettes = element.get("video_tag") or element.get("videoTag") or []
    if isinstance(etiquettes, dict):
        etiquettes = [etiquettes]
    if isinstance(etiquettes, list):
        for etiquette in etiquettes:
            if not isinstance(etiquette, dict):
                continue
            if str(etiquette.get("type", "")).upper() in ("AIGC", "AIGC TYPE", "AIGC_TYPE"):
                numero = str(etiquette.get("number", ""))
                if numero == "1":
                    return "declare_par_createur"
                if numero == "2":
                    return "etiquete_automatique"
    valeur = element.get("aigcLabelType", element.get("aigc_label_type"))
    if str(valeur) == "1":
        return "declare_par_createur"
    if str(valeur) == "2":
        return "etiquete_automatique"
    return None
