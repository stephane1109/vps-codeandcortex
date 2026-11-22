"""Dédoublonnage stable des publications par identifiant TikTok."""
def dedoublonner(publications):
    return list({p["id"]: p for p in reversed(publications)}.values())[::-1]

def deja_collectee(base, session, identifiant):
    return base.contient_publication(session, str(identifiant))
