"""Suivi exhaustif des médias sélectionnés et reprise manuelle sans dépasser les quotas."""
from __future__ import annotations

import csv
import io

STATUTS_REPRISE = frozenset({"non_commencee", "interrompue", "partielle", "echec"})
STATUTS_VALIDES = STATUTS_REPRISE | {"traitee", "en_attente", "en_cours"}


def etablir_bilan_medias(sources, journal, *, source_en_cours=None, termine=False):
    """Comparer l'inventaire sélectionné au journal réel, sans supposer une collecte exhaustive."""
    operations = {}
    for entree in journal:
        if not isinstance(entree, dict) or not entree.get("source"):
            continue
        rapport = entree.get("rapport") or {}
        identifiant = rapport.get("media_id")
        compte = rapport.get("compte_selectionne")
        if compte is None and entree["source"].startswith("@"):
            compte = entree["source"][1:]
        if identifiant:
            operations[("id", str(identifiant))] = entree
        if compte:
            operations[("compte", str(compte).casefold())] = entree

    bilan = []
    for source in sources:
        media_id = str(source.get("id") or "")
        compte = str(source.get("compte") or "")
        entree = (operations.get(("id", media_id))
                  or operations.get(("compte", compte.casefold())))
        if entree is None:
            if media_id and media_id == source_en_cours:
                etat = "interrompue" if termine else "en_cours"
            else:
                etat = "non_commencee" if termine else "en_attente"
            raison = ("Aucune recherche enregistrée pour cette source."
                      if termine else "Source non encore parcourue.")
            liens = 0
        else:
            rapport = entree.get("rapport") or {}
            etat = entree.get("statut_source")
            if etat not in STATUTS_VALIDES:
                if entree.get("statut") == "inaccessible":
                    etat = "echec"
                elif (rapport.get("collecte_partielle")
                      or rapport.get("recherches_en_echec")
                      or any((r.get("collecte_partielle") or r.get("recherches_en_echec"))
                             for r in rapport.get("recherches_compte", []))):
                    etat = "partielle"
                else:
                    etat = "traitee"
            if etat == "en_cours" and termine:
                etat = "interrompue"
            raison = str(entree.get("message") or "").strip()
            liens = len(rapport.get("discovered_urls") or [])
        bilan.append({
            "media_id": media_id,
            "nom": str(source.get("nom") or compte),
            "compte": compte,
            "etat": etat,
            "liens": liens,
            "motif": raison,
        })
    return bilan


def medias_a_reprendre(bilan):
    """Conserver l'ordre des médias et ne pas reprendre ceux déjà traités."""
    return [ligne["media_id"] for ligne in bilan
            if ligne["etat"] in STATUTS_REPRISE and ligne.get("media_id")]


def exporter_bilan_medias_csv(bilan):
    """Produire un fichier compatible Excel et réimportable le lendemain."""
    tampon = io.StringIO()
    colonnes = ("media_id", "nom", "compte", "etat", "liens", "motif")
    writer = csv.DictWriter(tampon, fieldnames=colonnes, delimiter=";",
                            extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for ligne in bilan:
        writer.writerow(ligne)
    return ("\ufeff" + tampon.getvalue()).encode("utf-8")


def importer_bilan_medias_csv(contenu, inventaire):
    """Extraire uniquement les identifiants à reprendre, validés par l'inventaire."""
    if len(contenu) > 2_000_000:
        raise ValueError("Le bilan CSV dépasse la limite de 2 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        raise ValueError("Le bilan CSV doit être encodé en UTF-8.") from erreur
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
    if not lecteur.fieldnames or not {"media_id", "etat"}.issubset(lecteur.fieldnames):
        raise ValueError("Le fichier n'est pas un bilan de médias ScrapTikTok.")
    reprise, absents, vus = [], [], set()
    lignes = 0
    for ligne in lecteur:
        lignes += 1
        identifiant = str(ligne.get("media_id") or "").strip()
        etat = str(ligne.get("etat") or "").strip()
        if not identifiant or etat not in STATUTS_VALIDES:
            raise ValueError("Le bilan contient un identifiant ou un état invalide.")
        if identifiant in vus:
            raise ValueError("Le bilan contient un média en double.")
        vus.add(identifiant)
        if etat in STATUTS_REPRISE:
            if identifiant in inventaire:
                reprise.append(identifiant)
            else:
                absents.append(identifiant)
    if not lignes:
        raise ValueError("Le bilan ne contient aucun média.")
    return reprise, absents
