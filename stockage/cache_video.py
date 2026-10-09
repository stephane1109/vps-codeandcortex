"""Cache invalidé par SHA-256, paramètres et version de l’algorithme."""
import hashlib
import json
from datetime import datetime, timezone, timedelta

def cle_cache(sha256, parametres):
    return hashlib.sha256((sha256 + json.dumps(parametres,sort_keys=True) + "v1").encode()).hexdigest()

def lire_cache(base, cle):
    with base.connexion() as connexion:
        ligne = connexion.execute("SELECT donnees FROM cache_video WHERE cle=?",(cle,)).fetchone()
    return json.loads(ligne[0]) if ligne else None

def ecrire_cache(base, cle, donnees):
    with base.connexion() as connexion:
        connexion.execute("INSERT OR REPLACE INTO cache_video VALUES(?,?,?)",(cle,json.dumps(donnees,ensure_ascii=False,allow_nan=False),datetime.now(timezone.utc).isoformat()))

        connexion.execute("DELETE FROM cache_video WHERE cle NOT IN (SELECT cle FROM cache_video ORDER BY cree_le DESC LIMIT 100)")


def purger_cache(base, retention_s):
    """Appliquer au cache la même durée de conservation que les sessions."""
    limite=(datetime.now(timezone.utc)-timedelta(seconds=retention_s)).isoformat()
    with base.connexion() as connexion:
        connexion.execute("DELETE FROM cache_video WHERE cree_le < ?",(limite,))
