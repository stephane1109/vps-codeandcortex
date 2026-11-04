"""Restaurer un historique de hashtags sans fabriquer de nouveau corpus.

Les fichiers CSV de bilan ne contiennent pas le curseur Research. Seuls un
journal local complet ou une sauvegarde ZIP de la collecte peuvent restaurer
les positions de pagination. La propriété PostgreSQL est vérifiée avant tout.
"""
from __future__ import annotations

import base64
import binascii
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from zipfile import BadZipFile, ZipFile

FICHIERS_PERMIS = {
    "publications.json", "journal.json", "commentaires.json",
    "republications.json", "profils_medias.json", "textes.txt",
    "corpus_iramuteq.txt", "commentaires.txt", "bilan_hashtags.csv",
    "publications.csv", "commentaires.csv", "engagement.csv",
    "ratios_engagement.csv", "profils_medias.csv", "videos.csv",
    "videos.json", "diagnostic_collecte.json",
}
TAILLE_ZIP_MAX = 25_000_000
TAILLE_DECOMPRESSEE_MAX = 150_000_000


def verifier_propriete_postgres(cookie, identifiant):
    """Confirmer la propriété et la taille du corpus enregistré."""
    from stockage.postgres_consultation import (
        compter_publications_collecte, obtenir_nom_collecte)
    try:
        nom = obtenir_nom_collecte(cookie, "collecte", identifiant)
        nombre = compter_publications_collecte(cookie, identifiant)
    except ValueError as erreur:
        raise ValueError(
            "La collecte n'est pas accessible dans PostgreSQL avec "
            "votre cookie d'historique actuel. Les CSV ne constituent "
            "pas une autorisation d'accès : ouvrez la session privée "
            "d'origine ou restaurez son accès.") from erreur
    return nom, nombre


def controler_journal_et_corpus(donnees, identifiant, nom_pg, nombre_pg):
    """Valider la sauvegarde complète avant d'écrire quoi que ce soit."""
    try:
        publications = json.loads(donnees["publications.json"].decode("utf-8"))
        journal = json.loads(donnees["journal.json"].decode("utf-8"))
    except (KeyError, UnicodeError, ValueError) as erreur:
        raise ValueError(
            "Sauvegarde incomplète : publications.json et journal.json "
            "sont obligatoires pour poursuivre la pagination Research.") from erreur
    if not isinstance(publications, list) or not isinstance(journal, dict):
        raise ValueError("Les fichiers JSON du corpus sont invalides.")
    if not isinstance(journal.get("evenements"), list):
        raise ValueError("Le journal de pagination est absent de la sauvegarde.")
    if journal.get("session") != identifiant:
        raise ValueError("Le ZIP ou le journal ne correspond pas à la collecte sélectionnée.")
    parametres = journal.get("parametres")
    if not isinstance(parametres, dict):
        raise ValueError("Les paramètres de la collecte manquent dans le journal.")
    if (parametres.get("source_collecte") != "hashtags"
            or parametres.get("hashtag_moteur") != "research"):
        raise ValueError("La sauvegarde ne correspond pas à une collecte Research hashtags.")
    if parametres.get("nom_sauvegarde") != nom_pg:
        raise ValueError("Le nom du corpus sauvegardé diffère de PostgreSQL.")
    if len(publications) < nombre_pg:
        raise ValueError(
            f"Le ZIP contient {len(publications)} publications, "
            f"mais PostgreSQL en contient {nombre_pg} : restauration refusée "
            "pour ne pas perdre les observations.")
    ids = [str(p.get("id") or "") for p in publications if isinstance(p, dict)]
    if len(ids) != len(publications) or not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("La sauvegarde comporte des publications invalides ou dupliquées.")
    return parametres, publications, journal


def reconstruire_historique(dossier_source, dossier_donnees, identifiant, cookie):
    """Réinscrire une archive complète vérifiée dans l'historique privé."""
    from stockage.historique_analyses import base, empreinte, enregistrer
    from stockage.postgres_consultation import nettoyer_parametres

    nom_pg, nombre_pg = verifier_propriete_postgres(cookie, identifiant)
    dossier_source = Path(dossier_source)
    donnees = {}
    for nom in ("publications.json", "journal.json"):
        fichier = dossier_source / nom
        if not fichier.is_file() or fichier.is_symlink():
            raise ValueError(
                "Aucun journal local complet n'est disponible pour ce corpus. "
                "Importez son ZIP de résultats d'origine (pas seulement les CSV).")
        donnees[nom] = fichier.read_bytes()
    parametres, publications, journal = controler_journal_et_corpus(
        donnees, identifiant, nom_pg, nombre_pg)
    with base(dossier_donnees) as connexion:
        ligne = connexion.execute(
            "SELECT proprietaire FROM analyses WHERE id=?", (identifiant,)
        ).fetchone()
        if ligne and ligne["proprietaire"] != empreinte(cookie):
            raise ValueError("Un historique appartenant à une autre session existe.")

    evenements = journal["evenements"]
    incompletes = {"non_commencee", "interrompue", "partielle", "echec", "en_cours"}
    source_en_cours = next(
        (ev.get("source") for ev in reversed(evenements)
         if isinstance(ev, dict) and ev.get("statut_source") in incompletes
         and str(ev.get("source") or "").startswith("#")), None)
    nombre_traite = journal.get("compteurs_collecte", {}).get("traitees")
    try:
        nombre_traite = max(len(publications), int(nombre_traite or 0))
    except (TypeError, ValueError):
        nombre_traite = len(publications)
    parametres = nettoyer_parametres(parametres)
    parametres.update(
        research_client_key=None, research_client_secret=None)

    class Parametres:
        """Vue minimale des paramètres validés par le journal et PostgreSQL."""
        nom_sauvegarde = nom_pg
        libelle = nom_pg

        def model_dump(self):
            return dict(parametres)

    fichiers_extra = [p for p in dossier_source.iterdir()
                     if p.is_file() and not p.is_symlink()
                     and p.name in FICHIERS_PERMIS]
    travail = SimpleNamespace(
        id=identifiant, directory=dossier_source,
        racine=Path(dossier_donnees), owner_historique=cookie,
        historique=False, reprise=False,
        settings=Parametres(), status=str(journal.get("statut") or "partial"),
        processed=nombre_traite, reprise_decalage=0,
        records=[p for p in publications if p.get("retenue")],
        publications=publications, source_en_cours_id=source_en_cours,
    )
    # Tous les fichiers copiés par enregistrer doivent être explicitement
    # autorisés ; un ZIP ne peut pas faire écrire un chemin extérieur.
    if any(p.name not in FICHIERS_PERMIS for p in fichiers_extra):
        raise ValueError("La sauvegarde contient un fichier non reconnu.")
    enregistrer(travail, cookie)
    return identifiant


def restaurer_depuis_zip(dossier_donnees, identifiant, cookie, archive_base64):
    """Restaurer depuis le ZIP original si l'historique local est perdu."""
    try:
        archive = base64.b64decode(archive_base64, validate=True)
    except (ValueError, binascii.Error) as erreur:
        raise ValueError("Le ZIP importé n'est pas valide.") from erreur
    if not archive or len(archive) > TAILLE_ZIP_MAX:
        raise ValueError("Le ZIP doit peser au maximum 25 Mo.")
    # Vérifier le propriétaire avant d'écrire ou de lire les données du ZIP.
    nom_pg, nombre_pg = verifier_propriete_postgres(cookie, identifiant)
    try:
        with ZipFile(BytesIO(archive)) as zipf:
            fichiers = [
                item for item in zipf.infolist()
                if not item.is_dir() and item.filename in FICHIERS_PERMIS
            ]
            if sum(item.file_size for item in fichiers) > TAILLE_DECOMPRESSEE_MAX:
                raise ValueError("Le ZIP dépasse 150 Mo de fichiers décompressés.")
            donnees = {}
            for item in fichiers:
                if item.filename in donnees:
                    raise ValueError("Le ZIP contient plusieurs fichiers de même nom.")
                donnees[item.filename] = zipf.read(item)
    except (BadZipFile, OSError, RuntimeError) as erreur:
        raise ValueError("Le ZIP de collecte est endommagé ou illisible.") from erreur
    controler_journal_et_corpus(donnees, identifiant, nom_pg, nombre_pg)
    with tempfile.TemporaryDirectory(prefix="reprise_hashtags_",
                                      dir=str(dossier_donnees)) as temporaire:
        source = Path(temporaire)
        for nom, contenu in donnees.items():
            (source / nom).write_bytes(contenu)
        return reconstruire_historique(
            source, dossier_donnees, identifiant, cookie)


def retrouver_ou_reconstruire(dossier_donnees, identifiant, cookie):
    """Chercher l'historique, puis les sauvegardes locales d'origine."""
    from stockage.historique_analyses import retrouver
    archive = retrouver(dossier_donnees, identifiant, cookie)
    if archive is not None:
        return archive
    # Ces emplacements sont des archives du serveur, non un nouveau corpus.
    for dossier in (
        Path(dossier_donnees) / "sessions" / identifiant,
        Path(dossier_donnees) / identifiant,
    ):
        if not (dossier / "journal.json").is_file():
            continue
        reconstruire_historique(
            dossier, dossier_donnees, identifiant, cookie)
        archive = retrouver(dossier_donnees, identifiant, cookie)
        if archive is not None:
            return archive
    return None
