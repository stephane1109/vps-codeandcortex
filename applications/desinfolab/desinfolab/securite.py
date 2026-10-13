"""Accès administrateur et anti-abus sans identification des visiteurs."""

import hashlib
import hmac
import os
import secrets
import time
from datetime import timedelta, timezone
from sqlalchemy import delete, select
from .base import transaction
from .configuration import secret_application
from .modeles import Defi, Quota, maintenant


class ErreurMetier(ValueError):
    """Erreur présentable sans exposer une requête SQL ou un secret."""


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    if len(mot_de_passe) < 14:
        raise ErreurMetier("Choisir un mot de passe d'au moins 14 caractères.")
    sel = secrets.token_hex(16)
    empreinte = hashlib.scrypt(mot_de_passe.encode(), salt=bytes.fromhex(sel), n=16384, r=8, p=1).hex()
    return f"scrypt:{sel}:{empreinte}"


def verifier_mot_de_passe(mot_de_passe: str, empreinte: str) -> bool:
    try:
        algo, sel, attendu = empreinte.split(":")
        if algo != "scrypt" or len(mot_de_passe) > 1024:
            return False
        calcule = hashlib.scrypt(mot_de_passe.encode(), salt=bytes.fromhex(sel), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(calcule, attendu)
    except (ValueError, TypeError):
        return False


def signer(valeur: str) -> str:
    return hmac.new(secret_application(), valeur.encode(), hashlib.sha256).hexdigest()


def utc(date):
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date


def consommer_quota(nom: str, limite: int, secondes: int):
    # Transaction indépendante : les essais invalides consomment aussi le quota.
    depasse = False
    with transaction() as session:
        quota = session.scalar(select(Quota).where(Quota.nom == nom).with_for_update())
        if quota is None:
            raise ErreurMetier("Base non initialisée : exécuter les migrations.")
        if (maintenant() - utc(quota.debut)).total_seconds() >= secondes:
            quota.debut, quota.nombre = maintenant(), 0
        depasse = quota.nombre >= limite
        if not depasse:
            quota.nombre += 1
    if depasse:
        raise ErreurMetier("Limite temporaire atteinte. Merci de réessayer plus tard.")


def connecter_admin(mot_de_passe: str) -> str:
    empreinte = os.getenv("ADMIN_PASSWORD_HASH", "")
    if not empreinte:
        raise ErreurMetier("Configurer ADMIN_PASSWORD_HASH pour activer l'administration.")
    consommer_quota("connexion", 30, 600)
    if not verifier_mot_de_passe(mot_de_passe, empreinte):
        raise ErreurMetier("Mot de passe incorrect.")
    valeur = f"admin:{int(time.time()) + 1800}:{secrets.token_hex(16)}"
    return valeur + ":" + signer(valeur)


def exiger_admin(jeton: str | None):
    try:
        role, expiration, alea, signature = (jeton or "").split(":")
        valeur = f"{role}:{expiration}:{alea}"
        if (
            role != "admin"
            or int(expiration) <= time.time()
            or not hmac.compare_digest(signer(valeur), signature)
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise ErreurMetier("Session administrateur absente ou expirée. Reconnectez-vous.") from None


def creer_defi() -> dict:
    consommer_quota("defis", int(os.getenv("DEFIS_PAR_HEURE", "600")), 3600)
    a, b = secrets.randbelow(19) + 1, secrets.randbelow(19) + 1
    jeton = secrets.token_hex(32)
    with transaction() as session:
        session.execute(delete(Defi).where(Defi.cree_le < maintenant() - timedelta(minutes=30)))
        session.add(Defi(jeton=jeton, reponse_hachee=signer(jeton + ":" + str(a + b))))
    return {"jeton": jeton, "question": f"Combien font {a} + {b} ?"}


def verifier_defi(jeton: str, reponse: str, champ_piege: str = ""):
    consommer_quota("soumissions", int(os.getenv("SOUMISSIONS_PAR_HEURE", "120")), 3600)
    valide = False
    with transaction() as session:
        defi = session.scalar(select(Defi).where(Defi.jeton == jeton).with_for_update())
        if defi:
            age = (maintenant() - utc(defi.cree_le)).total_seconds()
            valide = (
                not champ_piege
                and 2 <= age <= 1800
                and hmac.compare_digest(defi.reponse_hachee, signer(jeton + ":" + reponse.strip()))
            )
            session.delete(defi)
    if not valide:
        raise ErreurMetier(
            "Vérification échouée ou expirée. Utilisez le nouveau calcul et attendez deux secondes."
        )
