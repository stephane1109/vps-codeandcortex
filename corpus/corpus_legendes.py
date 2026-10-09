"""Une unité textuelle par publication retenue."""
def construire_legendes(publications, variables=None):
    variables = variables or {}
    return [{"id": p["id"], "texte": p.get("description", ""), "variables": {
        "type": "legende", "media": p.get("media_id"), "categorie": p.get("categorie_media"),
        **variables.get(p["id"], {})}} for p in publications if p.get("retenue", True)]
