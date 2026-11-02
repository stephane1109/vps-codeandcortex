"""Une unité textuelle par publication retenue."""
from collecte.presse import code_presse_publication


def construire_legendes(publications, variables=None):
    """Conserver les variables textuelles et la catégorie du compte connu."""
    variables = variables or {}
    documents = []
    for publication in publications:
        if not publication.get("retenue", True):
            continue
        code = code_presse_publication(publication)
        illustratives = {code: True} if code else {}
        documents.append({
            "id": publication["id"],
            "texte": publication.get("description", ""),
            "variables": {
                "type": "legende",
                "media": publication.get("media_id"),
                "categorie": publication.get("categorie_media"),
                **variables.get(publication["id"], {}),
                **illustratives,
            },
        })
    return documents
