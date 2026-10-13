"""Afficher une configuration à conserver dans .env ou dans les secrets Coolify."""

import getpass
import secrets
from desinfolab.securite import hacher_mot_de_passe

mot_de_passe = getpass.getpass("Mot de passe administrateur (14 caractères minimum) : ")
confirmation = getpass.getpass("Confirmer : ")
if mot_de_passe != confirmation:
    raise SystemExit("Les mots de passe ne correspondent pas.")
print("POSTGRES_PASSWORD=" + secrets.token_urlsafe(36))
print("APP_SECRET=" + secrets.token_urlsafe(48))
print("ADMIN_PASSWORD_HASH=" + hacher_mot_de_passe(mot_de_passe))
