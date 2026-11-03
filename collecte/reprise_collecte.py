"""Validation d'une reprise dans le même corpus scientifique et sans nouvelle collecte."""
from __future__ import annotations

import json

from collecte.suivi_sources import etablir_bilan_medias, medias_a_reprendre


def lire_archive_json(dossier, nom, *, obligatoire=False):
    """Lire une sauvegarde existante en refusant les données incomplètes."""
    chemin = dossier / nom
    if not chemin.is_file() or chemin.is_symlink():
        if obligatoire:
            raise ValueError("Archive de collecte incomplète : " + nom)
        return []
    try:
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as erreur:
        raise ValueError("Fichier d'archive illisible : " + nom) from erreur
    return contenu


def preparer_reprise_medias(sources, journal, selection=None, *, source_en_cours=None):
    """Ne proposer que les médias inachevés, avec conservation de l'ordre demandé."""
    bilan = etablir_bilan_medias(
        sources, journal, source_en_cours=source_en_cours, termine=True)
    disponibles = medias_a_reprendre(bilan)
    if not disponibles:
        raise ValueError("Toutes les sources sont déjà parcourues : aucune reprise nécessaire.")
    if not selection:
        return disponibles, bilan
    if len(selection) != len(set(selection)):
        raise ValueError("Un média a été sélectionné plusieurs fois.")
    ids_disponibles = set(disponibles)
    if any(media_id not in ids_disponibles for media_id in selection):
        raise ValueError("La reprise accepte uniquement les médias inachevés de cette collecte.")
    return list(selection), bilan


def initialiser_donnees_reprise(job, dossier, manifeste, medias_selectionnes):
    """Restaurer les publications, commentaires et sources sans perdre le corpus."""
    publications = lire_archive_json(dossier, "publications.json", obligatoire=True)
    historique = lire_archive_json(dossier, "journal.json", obligatoire=True)
    if not isinstance(publications, list) or not isinstance(historique, dict):
        raise ValueError("Les fichiers de la collecte ne sont pas au format attendu.")
    evenements = historique.get("evenements")
    if not isinstance(evenements, list):
        raise ValueError("Le journal des sources est absent : reprise automatique impossible.")
    job.publications = publications
    job.publications_avant_reprise = len(publications)
    job.records = [p for p in publications if isinstance(p, dict) and p.get("retenue")]
    for nom, attribut in (
        ("commentaires.json", "commentaires"),
        ("republications.json", "republications"),
        ("profils_medias.json", "profils_medias"),
    ):
        donnees = lire_archive_json(dossier, nom)
        if not isinstance(donnees, list):
            raise ValueError("Archive invalide : " + nom)
        setattr(job, attribut, donnees)
    job.journal = list(evenements)
    job.medias_reprise = list(medias_selectionnes)
    job.source_en_cours_id = manifeste.get("source_en_cours_id")
    # Le moteur utilise l'indice des vidéos déjà connues comme curseur de lecture.
    # Les anciennes tentatives sans publication ne doivent pas être relancées.
    from scraptiktok import canonical_post
    ids_anciens = set()
    for publication in publications:
        if not isinstance(publication, dict):
            raise ValueError("Une publication archivée est invalide.")
        url = publication.get("url")
        identite = canonical_post(url) if url else None
        if identite:
            ids_anciens.add(str(identite[0]))
    job.processed = len(ids_anciens)
    ancien_compteur = int(manifeste.get("traites") or 0)
    job.reprise_decalage = max(0, ancien_compteur - len(ids_anciens))
    job.discovered = len(ids_anciens)
    job.decouvertes_ids = set(ids_anciens)
    job.archive_prete = False
    job.message = "Reprise de la collecte existante : mêmes paramètres et même identifiant."
    job._pg_publications = len(publications)
    job._pg_commentaires = len(job.commentaires)
    job._pg_traitees = job.processed
    job._pg_initialise = True
    job.sauvegarde_postgres = "synchronise"
    return len(ids_anciens)
