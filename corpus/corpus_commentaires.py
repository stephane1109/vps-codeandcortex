"""Commentaires et réponses dans un corpus distinct des légendes."""
def construire_commentaires(commentaires, variables=None):
    return [{"id": c["id"], "texte": c["texte"], "variables": {**(variables or {}).get(c["publication_id"],{}), "publication": c["publication_id"],
        **({"ville": c["ville_etude"]}
            if c.get("ville_etude") and c.get("inclure_ville_etude_txt", True)
            else {}),
        "type": "reponse" if c.get("est_reponse") else "commentaire"}} for c in commentaires]
