"""Enrichissement de la publication exacte, jamais d’une recommandation."""
import json
from .engagement import extraire_engagement
from .metadonnees import extraire_metadonnees

def enrichir_publication(publication, instantane):
    from scraptiktok import find_item
    element = None
    for contenu in instantane.get("payloads", []):
        try:
            element = find_item(json.loads(contenu), publication["id"])
        except (ValueError, TypeError):
            continue
        if element is not None:
            break
    date = publication["collected_at"]
    publication["engagement"] = extraire_engagement(element, instantane.get("engagement"), date)
    publication["metadonnees"] = extraire_metadonnees(element, date) if element else {"source": None}
    return publication
