"""Période inclusive sur la date de publication UTC, sans inférer les dates absentes."""
from datetime import date, datetime, timezone


def normaliser_date(valeur):
    if valeur is None or not valeur.strip(): return None
    valeur = valeur.strip()
    try:
        if date.fromisoformat(valeur).isoformat() != valeur: raise ValueError()
    except ValueError as erreur:
        raise ValueError("Date invalide : utilisez le format AAAA-MM-JJ.") from erreur
    return valeur


def evaluer_periode(date_publication, debut=None, fin=None):
    if not debut and not fin: return "sans_filtre"
    try:
        instant = datetime.fromisoformat(date_publication.replace("Z", "+00:00"))
        if instant.tzinfo is None: instant = instant.replace(tzinfo=timezone.utc)
        jour = instant.astimezone(timezone.utc).date().isoformat()
    except (ValueError, TypeError, AttributeError, OverflowError): return "date_indeterminee"
    if (debut and jour < debut) or (fin and jour > fin): return "hors_periode"
    return "dans_periode"
