"""Conservation des liens parent-enfant uniquement quand ils sont observés."""
def rattacher_reponses(commentaires):
    identifiants = {c["id"] for c in commentaires}
    for commentaire in commentaires:
        parent = commentaire.get("parent_id")
        commentaire["parent_collecte"] = parent in identifiants if parent else None
    return commentaires
