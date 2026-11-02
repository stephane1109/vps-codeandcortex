"""Regrouper tous les résultats récupérables d'une collecte PostgreSQL.

Les tables PostgreSQL constituent la référence durable. Les fichiers
temporaires, l'historique privé et le programme Research local peuvent fournir
des documents complémentaires, mais aucun fichier absent n'est inventé.
"""
import csv
import io
import json
import re
import sqlite3
from pathlib import Path
from shutil import copyfileobj
from tempfile import SpooledTemporaryFile, TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from .postgres_consultation import (
    description_table, donnees_sauvegarde, empreinte, exporter_sauvegarde,
    ouvrir_connexion,
)

EXTENSIONS = frozenset({
    ".txt", ".csv", ".json", ".mp4", ".jpg", ".png", ".wav", ".html",
    ".htm", ".svg", ".log", ".gexf", ".graphml", ".pdf", ".md", ".sqlite3",
})
FICHIERS_POSTGRES = (
    "publications.csv", "publications.json",
    "commentaires.csv", "commentaires.json",
)


def _enregistrements(cookie, type_sauvegarde, identifiant, categorie):
    """Lire toutes les lignes d'une collecte autorisée, sans troncature."""
    lignes = []
    decalage = 0
    while True:
        page = donnees_sauvegarde(
            cookie, type_sauvegarde, identifiant, categorie,
            limite=200, decalage=decalage,
        )
        observations = page.get("lignes") or []
        lignes.extend(observations)
        decalage += len(observations)
        if not observations or decalage >= page.get("total", 0):
            return lignes


def _normaliser_donnees(publications, commentaires):
    """Garantir les champs minimaux des exports historiques."""
    pubs = []
    for publication in publications:
        p = dict(publication)
        p["id"] = str(p.get("id") or p.get("publication_id") or "")
        p["author"] = str(p.get("author") or p.get("profil") or "")
        if not isinstance(p.get("engagement"), dict):
            p["engagement"] = {}
        p["engagement"] = {
            nom: mesure if isinstance(mesure, dict)
            else {"brut": str(mesure), "valeur": mesure}
            for nom, mesure in p["engagement"].items()
        }
        pubs.append(p)
    comms = []
    for commentaire in commentaires:
        c = dict(commentaire)
        c["id"] = str(c.get("id") or c.get("commentaire_id") or "")
        c["publication_id"] = str(c.get("publication_id") or "")
        c["texte"] = c.get("texte") or ""
        comms.append(c)
    return pubs, comms


def _ecrire_sqlite(chemin, publications, commentaires):
    """Créer un SQLite autonome avec toutes les variables des publications."""
    from corpus.publications_csv import (
        COLONNES_PUBLICATIONS_CSV, ligne_publication_csv,
    )
    from .postgres_consultation import CHAMPS_COMMENTAIRES
    with sqlite3.connect(chemin) as base:
        for table, colonnes, lignes in (
            ("publications", COLONNES_PUBLICATIONS_CSV, publications),
            ("commentaires", CHAMPS_COMMENTAIRES, commentaires),
        ):
            en_tetes = ", ".join('"' + nom + '" TEXT' for nom in colonnes)
            base.execute(f"CREATE TABLE {table} ({en_tetes})")
            marqueurs = ", ".join("?" for _ in colonnes)
            if table == "publications":
                donnees = [ligne_publication_csv(ligne) for ligne in lignes]
            else:
                donnees = lignes
            valeurs = []
            for ligne in donnees:
                valeurs.append(tuple(
                    json.dumps(ligne[nom], ensure_ascii=False)
                    if isinstance(ligne.get(nom), (dict, list))
                    else None if ligne.get(nom) is None
                    else str(ligne[nom])
                    for nom in colonnes
                ))
            if valeurs:
                base.executemany(
                    f"INSERT INTO {table} VALUES ({marqueurs})", valeurs)


def _generer_fichiers(dossier, publications, commentaires, identifiant, parametres):
    """Reconstruire tous les exports dérivables des données enregistrées."""
    from corpus.construction import construire_exports
    from webapp import text_export
    pubs, comms = _normaliser_donnees(publications, commentaires)
    retenues = [p for p in pubs if p.get("retenue", True)]
    texte = text_export(
        retenues,
        parametres.get("include_sources", True),
        parametres.get("inclure_metadonnees_txt", False),
        parametres.get("variables_txt"),
        comms if parametres.get("collecter_commentaires", False) else None,
        supprimer_arobase_profil=parametres.get("supprimer_arobase_profil", False),
        inclure_texte_genere_ia=parametres.get("inclure_texte_genere_ia", False),
        follower_count_illustratif=parametres.get("follower_count_illustratif", False),
        abonnes_classe_illustratif=parametres.get("abonnes_classe_illustratif", False),
        variables_classes_txt=parametres.get("variables_classes_txt", []),
        taux_engagement_txt=parametres.get("taux_engagement_txt", "aucun"),
    )
    source = Path(dossier) / "textes.txt"
    source.write_text(texte, encoding="utf-8")
    construire_exports(
        dossier, pubs, comms,
        {"session": identifiant, "statut": "export_postgresql",
         "parametres": parametres},
        texte_source=source,
    )
    textes_commentaires = [
        f"*id_{c['publication_id']}\n@{c.get('auteur') or 'inconnu'}\n{c['texte']}"
        for c in comms if c.get("texte")
    ]
    (Path(dossier) / "commentaires.txt").write_text(
        "\n\n".join(textes_commentaires) +
        ("\n" if textes_commentaires else ""), encoding="utf-8")
    _ecrire_sqlite(Path(dossier) / "corpus.sqlite3", pubs, comms)


def _source_historique(dossier_local, identifiant, cookie):
    """Ne lire que les anciens fichiers possédés par le même utilisateur."""
    if dossier_local is None:
        return None
    from stockage.historique_analyses import retrouver
    archive = retrouver(dossier_local, identifiant, cookie)
    return Path(archive[1]) if archive else None


def _ajouter_zip_origine(cible, chemin, noms):
    """Reprendre les résultats initiaux, dont les MP4 disponibles."""
    if chemin is None or not Path(chemin).is_file():
        return
    with ZipFile(chemin) as source:
        for entree in source.infolist():
            nom = entree.filename
            chemin_interne = Path(nom)
            if (entree.is_dir() or nom in noms or nom in FICHIERS_POSTGRES
                    or nom == "informations_export.json"
                    or chemin_interne.is_absolute() or ".." in chemin_interne.parts
                    or chemin_interne.suffix.lower() not in EXTENSIONS):
                continue
            with source.open(entree) as lecture, cible.open(nom, "w") as sortie:
                copyfileobj(lecture, sortie, length=1024 * 1024)
            noms.add(nom)


def _ajouter_dossier_origine(cible, dossier, noms):
    """Ajouter les fichiers originaux de l'historique privé sans symlinks."""
    if dossier is None:
        return
    for fichier in sorted(Path(dossier).rglob("*")):
        if not fichier.is_file() or fichier.is_symlink():
            continue
        relatif = fichier.relative_to(dossier)
        if (".." in relatif.parts or fichier.suffix.lower() not in EXTENSIONS
                or relatif.as_posix() in noms
                or relatif.as_posix() in FICHIERS_POSTGRES
                or relatif.as_posix() == "informations_export.json"):
            continue
        cible.write(fichier, relatif.as_posix())
        noms.add(relatif.as_posix())


def construire_archive_postgres(
        cookie, type_sauvegarde, identifiant, dossier_local=None,
        archive_active=None):
    """Assembler un ZIP unique des résultats retrouvables depuis PostgreSQL.

    L'archive inclut les exports standards, les données reconstituables,
    et les fichiers originaux encore présents pour cette collecte.
    """
    from .postgres_consultation import IDENTIFIANT
    if not cookie or not IDENTIFIANT.fullmatch(str(identifiant)):
        raise ValueError("Identifiant ou session de sauvegarde invalide.")
    parent, _, cle, _ = description_table(type_sauvegarde, "publications")
    with ouvrir_connexion() as connexion:
        with connexion.cursor() as curseur:
            colonnes = ("nom_sauvegarde, parametres" if type_sauvegarde == "collecte"
                        else "nom_sauvegarde")
            curseur.execute(
                f"SELECT {colonnes} FROM {parent} "
                f"WHERE {cle}=%s AND proprietaire_hash=%s",
                (identifiant, empreinte(cookie)))
            ligne = curseur.fetchone()
    if not ligne:
        raise ValueError("Collecte PostgreSQL introuvable.")
    nom = str(ligne[0] or "collecte")
    parametres = ligne[1] if type_sauvegarde == "collecte" else {}
    if isinstance(parametres, str):
        parametres = json.loads(parametres)
    parametres = parametres if isinstance(parametres, dict) else {}
    nom_fichier = re.sub(r"[^\w-]+", "_", nom).strip("_")[:80] or "collecte"

    archive = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    try:
        publications = _enregistrements(
            cookie, type_sauvegarde, identifiant, "publications")
        commentaires = _enregistrements(
            cookie, type_sauvegarde, identifiant, "commentaires")
        with TemporaryDirectory(prefix="scraptiktok_export_pg_") as dossier:
            _generer_fichiers(
                dossier, publications, commentaires, identifiant, parametres)
            with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=5) as cible:
                noms = set()
                # La version originale, lorsqu'elle existe, prime sur les
                # fichiers reconstruits (TXT exacts, annotations et MP4).
                _ajouter_zip_origine(cible, archive_active, noms)
                if type_sauvegarde == "collecte":
                    _ajouter_dossier_origine(
                        cible,
                        _source_historique(dossier_local, identifiant, cookie),
                        noms)
                elif (dossier_local is not None
                      and (Path(dossier_local) / "collectes_research.sqlite3").is_file()):
                    # Ne pas créer une nouvelle base SQLite vide si l'ancienne
                    # n'existe plus : PostgreSQL demeure exportable seul.
                    import sqlite3
                    from stockage.collectes_research import exporter
                    try:
                        source_sqlite = exporter(
                            dossier_local, identifiant, cookie, "zip")
                    except (sqlite3.Error, ValueError, KeyError):
                        source_sqlite = None
                    if source_sqlite is not None:
                        from tempfile import NamedTemporaryFile
                        with NamedTemporaryFile(suffix=".zip") as temporaire:
                            temporaire.write(source_sqlite)
                            temporaire.flush()
                            _ajouter_zip_origine(cible, temporaire.name, noms)
                for fichier in sorted(Path(dossier).rglob("*")):
                    if (not fichier.is_file()
                            or fichier.is_symlink()
                            or fichier.suffix.lower() not in EXTENSIONS
                            or fichier.relative_to(dossier).as_posix() in noms
                            or fichier.name in FICHIERS_POSTGRES):
                        continue
                    nom_interne = fichier.relative_to(dossier).as_posix()
                    cible.write(fichier, nom_interne)
                    noms.add(nom_interne)
                # Les quatre exports PostgreSQL sont la référence : ils
                # contiennent toutes les données conservées, même lorsque
                # l'archive locale est plus ancienne.
                for categorie in ("publications", "commentaires"):
                    for format_ in ("csv", "json"):
                        nom_interne = f"{categorie}.{format_}"
                        with cible.open(nom_interne, "w") as sortie:
                            for morceau in exporter_sauvegarde(
                                    cookie, type_sauvegarde, identifiant,
                                    categorie, format_):
                                sortie.write(morceau.encode("utf-8"))
                        noms.add(nom_interne)
                manifeste = {
                    "format": "scraptiktok-resultats-v2",
                    "source": "PostgreSQL et fichiers originaux disponibles",
                    "type_collecte": type_sauvegarde,
                    "identifiant": identifiant,
                    "nom_collecte": nom,
                    "publications": len(publications),
                    "commentaires": len(commentaires),
                    "fichiers": sorted(noms),
                    "mp4_presents": any(n.lower().endswith(".mp4") for n in noms),
                    "avertissement": (
                        "Les MP4 et les analyses ne peuvent être inclus que "
                        "s'ils existent encore dans les archives de la collecte. "
                        "Le corpus.sqlite3 de secours est reconstruit depuis "
                        "les données PostgreSQL, sauf copie SQLite locale disponible. "
                        "Ce ZIP n'est pas un dump physique PostgreSQL."
                    ),
                }
                cible.writestr("informations_export.json", json.dumps(
                    manifeste, ensure_ascii=False, indent=2))
        archive.seek(0)
        return archive, nom_fichier + ".zip"
    except Exception:
        archive.close()
        raise
