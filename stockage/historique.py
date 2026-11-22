"""Journal append-only d’une session ; contenu structuré, sans secrets navigateur."""
import json
from datetime import datetime, timezone

def ajouter_evenement(base, session, donnees):
    with base.connexion() as connexion:
        connexion.execute("INSERT INTO evenements(session_id,date,donnees) VALUES(?,?,?)", (session,datetime.now(timezone.utc).isoformat(),json.dumps(donnees,ensure_ascii=False)))

def lister_sessions(base, proprietaire):
    with base.connexion() as connexion:
        return [dict(zip(("id","cree_le","statut"),ligne)) for ligne in connexion.execute("SELECT id,cree_le,statut FROM sessions WHERE proprietaire=? ORDER BY cree_le DESC", (proprietaire,))]
