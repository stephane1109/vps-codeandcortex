"""Commentaires et réponses dans un corpus distinct des légendes."""
def construire_commentaires(commentaires, variables=None):
    return [{"id": c["id"], "texte": c["texte"], "variables": {**(variables or {}).get(c["publication_id"],{}), "publication": c["publication_id"],
        "type": "reponse" if c.get("est_reponse") else "commentaire"}} for c in commentaires]
