"""Archivage durable et consultation des collectes ScrapTikTok dans PostgreSQL.

La connexion est exclusivement interne au VPS. Chaque lecture est isolée
par l'empreinte du cookie d'historique ; aucune requête SQL utilisateur
n'est exécutée. Les contenus JSONB conservent les valeurs d'origine.
"""
import csv
import hashlib
import io
import json
import logging
import os
import re
from datetime import datetime, timezone

JOURNAL = logging.getLogger(__name__)
IDENTIFIANT = re.compile(r"[0-9a-f]{32}\Z")
TYPES = {"collecte", "research"}
CATEGORIES = {"publications", "commentaires"}
CHAMPS_PUBLICATIONS = (
    "id", "url", "author", "created_at", "collected_at", "description",
    "retenue", "motif_non_retenue", "langue_detection", "region_code",
    "is_verified", "follower_count", "video_duration", "taux_engagement",
    "vues", "likes", "commentaires", "partages", "favoris", "hashtags",
)
CHAMPS_COMMENTAIRES = (
    "id", "publication_id", "auteur", "texte", "parent_id", "est_reponse",
    "date_brute", "likes", "source", "observe_le",
)


def empreinte(cookie):
    """Identifier le propriétaire sans enregistrer son cookie."""
    return hashlib.sha256(cookie.encode("utf-8")).hexdigest()


def adresse_configuree():
    """Indiquer si l'adresse privée PostgreSQL est renseignée."""
    return bool(os.getenv("RESEARCH_POSTGRES_DSN", "").strip())


def ouvrir_connexion():
    """Ouvrir une connexion PostgreSQL sans exposer son adresse."""
    import psycopg
    adresse = os.getenv("RESEARCH_POSTGRES_DSN", "").strip()
    if not adresse:
        raise RuntimeError(
            "PostgreSQL non configuré : renseignez RESEARCH_POSTGRES_DSN dans Coolify.")
    try:
        return psycopg.connect(adresse, connect_timeout=5)
    except Exception:
        JOURNAL.warning("Connexion PostgreSQL ScrapTikTok indisponible")
        raise RuntimeError(
            "Connexion PostgreSQL indisponible : vérifiez la base dans Coolify.") from None


def verifier_disponibilite():
    """Contrôler la connexion et les droits avant une collecte payante."""
    with ouvrir_connexion() as connexion:
        preparer_tables(connexion)
    return True


def preparer_tables(connexion):
    """Créer les tables durables sans modifier les tables Research existantes."""
    with connexion.cursor() as curseur:
        curseur.execute("""
            CREATE TABLE IF NOT EXISTS scraptiktok_collectes (
                collecte_id TEXT PRIMARY KEY,
                proprietaire_hash TEXT NOT NULL,
                nom_sauvegarde TEXT NOT NULL,
                source_collecte TEXT NOT NULL,
                moteur TEXT NOT NULL,
                statut TEXT NOT NULL,
                cree_le TIMESTAMPTZ NOT NULL,
                actualise_le TIMESTAMPTZ NOT NULL,
                traitees INTEGER NOT NULL DEFAULT 0,
                parametres JSONB NOT NULL DEFAULT '{}'::jsonb
            )""")
        curseur.execute("""
            CREATE TABLE IF NOT EXISTS scraptiktok_publications (
                collecte_id TEXT NOT NULL REFERENCES scraptiktok_collectes(collecte_id)
                    ON DELETE CASCADE,
                publication_id TEXT NOT NULL,
                retenue BOOLEAN NOT NULL,
                donnees JSONB NOT NULL,
                PRIMARY KEY(collecte_id, publication_id)
            )""")
        curseur.execute("""
            CREATE TABLE IF NOT EXISTS scraptiktok_commentaires (
                collecte_id TEXT NOT NULL REFERENCES scraptiktok_collectes(collecte_id)
                    ON DELETE CASCADE,
                commentaire_id TEXT NOT NULL,
                publication_id TEXT NOT NULL,
                donnees JSONB NOT NULL,
                PRIMARY KEY(collecte_id, commentaire_id)
            )""")
        curseur.execute(
            "CREATE INDEX IF NOT EXISTS scraptiktok_collectes_owner "
            "ON scraptiktok_collectes(proprietaire_hash, actualise_le DESC)")
        curseur.execute(
            "CREATE INDEX IF NOT EXISTS scraptiktok_commentaires_publication "
            "ON scraptiktok_commentaires(collecte_id, publication_id)")
        # Ajouter les colonnes réelles avant de maintenir les vues existantes.
        from stockage.colonnes_publications import preparer_colonnes_publications
        preparer_colonnes_publications(curseur)
        from stockage.vues_tabulaire import preparer_vues_tabulaire
        preparer_vues_tabulaire(curseur)


def nettoyer_parametres(parametres):
    """Écarter tous les secrets avant leur archivage."""
    donnees = dict(parametres)
    for cle in (
        "research_client_key", "research_client_secret", "cookies_tiktok",
        "tikhub_api_key", "apify_api_token",
    ):
        donnees.pop(cle, None)
    return donnees


def archiver_collecte(job, *, a_partir_publications=0, a_partir_commentaires=0):
    """Sauvegarder une collecte ponctuelle, même sans légende TXT retenue.

    L'archivage est idempotent : une relance actualise les lignes existantes.
    Les indices facultatifs permettent une sauvegarde incrémentale pendant
    la collecte, sans réécrire toutes les observations à chaque point.
    Une synchronisation finale sans indices reste exhaustive.
    """
    if not job.owner_historique or not IDENTIFIANT.fullmatch(str(job.id)):
        raise RuntimeError("Cookie de sauvegarde ou identifiant de collecte absent.")
    from psycopg.types.json import Jsonb

    with job.lock:
        publications = list(job.publications or job.records)
        commentaires = list(job.commentaires)
        publications = publications[max(0, a_partir_publications):]
        commentaires = commentaires[max(0, a_partir_commentaires):]
        parametres = nettoyer_parametres(job.settings.model_dump())
        statut = job.status
        traitees = job.processed
        identifiant = job.id
        nom = job.settings.nom_sauvegarde or job.settings.libelle
        source = job.settings.source_collecte
        moteur = job.settings.moteur_actif
    maintenant = datetime.now(timezone.utc)
    with ouvrir_connexion() as connexion:
        preparer_tables(connexion)
        with connexion.cursor() as curseur:
            curseur.execute("""
                INSERT INTO scraptiktok_collectes (
                    collecte_id, proprietaire_hash, nom_sauvegarde,
                    source_collecte, moteur, statut, cree_le, actualise_le,
                    traitees, parametres)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (collecte_id) DO UPDATE SET
                    nom_sauvegarde=EXCLUDED.nom_sauvegarde,
                    statut=EXCLUDED.statut,
                    actualise_le=EXCLUDED.actualise_le,
                    traitees=EXCLUDED.traitees,
                    parametres=EXCLUDED.parametres
            """, (
                identifiant, empreinte(job.owner_historique), nom, source,
                moteur, statut, maintenant, maintenant, traitees, Jsonb(parametres)))
            for publication in publications:
                code = str(publication.get("id") or "")
                if not code:
                    continue
                curseur.execute("""
                    INSERT INTO scraptiktok_publications (
                        collecte_id, publication_id, retenue, donnees)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT(collecte_id,publication_id) DO UPDATE SET
                        retenue=EXCLUDED.retenue, donnees=EXCLUDED.donnees
                """, (identifiant, code, bool(publication.get("retenue")),
                      Jsonb(publication)))
            for commentaire in commentaires:
                code = str(commentaire.get("id") or "")
                if not code:
                    continue
                curseur.execute("""
                    INSERT INTO scraptiktok_commentaires (
                        collecte_id, commentaire_id, publication_id, donnees)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT(collecte_id,commentaire_id) DO UPDATE SET
                        publication_id=EXCLUDED.publication_id,
                        donnees=EXCLUDED.donnees
                """, (identifiant, code,
                      str(commentaire.get("publication_id") or ""),
                      Jsonb(commentaire)))
    return {"statut": "synchronise", "publications": len(publications),
            "commentaires": len(commentaires)}


def importer_historique(dossier, cookie):
    """Importer dans PostgreSQL les archives locales encore conservées.

    Ne récupère que l'historique du cookie courant. Ne requiert aucune
    clé TikTok et conserve les archives originales sans les supprimer.
    """
    from pathlib import Path
    from threading import RLock
    from types import SimpleNamespace
    from stockage.historique_analyses import lister, retrouver

    comptes = {"imports": 0, "publications": 0, "commentaires": 0,
               "erreurs": 0}
    for entree in lister(dossier, cookie):
        archive = retrouver(dossier, entree["id"], cookie)
        if archive is None:
            comptes["erreurs"] += 1
            continue
        _, repertoire, manifeste = archive
        try:
            chemin_publications = Path(repertoire) / "publications.json"
            chemin_commentaires = Path(repertoire) / "commentaires.json"
            publications = (
                json.loads(chemin_publications.read_text(encoding="utf-8"))
                if chemin_publications.is_file() else [])
            commentaires = (
                json.loads(chemin_commentaires.read_text(encoding="utf-8"))
                if chemin_commentaires.is_file() else [])
            if not isinstance(publications, list) or not isinstance(commentaires, list):
                raise ValueError("Format d'archive incorrect.")
            parametres = nettoyer_parametres(manifeste.get("parametres") or {})
            nom = parametres.get("nom_sauvegarde") or entree.get("titre") or entree["id"]
            source = parametres.get("source_collecte") or "presse"
            moteur = parametres.get({
                "presse": "presse_moteur", "hashtags": "hashtag_moteur",
                "comptes": "profil_moteur"}.get(source, "presse_moteur")) or "inconnu"

            class ParametresImportes:
                """Enveloppe des paramètres historiques sans clé confidentielle."""
                nom_sauvegarde = nom
                libelle = nom
                source_collecte = source
                moteur_actif = moteur

                def model_dump(self):
                    """Renvoyer les paramètres historiques épurés."""
                    return parametres

            travail = SimpleNamespace(
                lock=RLock(), owner_historique=cookie, id=entree["id"],
                settings=ParametresImportes(),
                publications=publications, records=publications,
                commentaires=commentaires, processed=manifeste.get("traites", 0),
                status=entree.get("statut") or "termine")
            resultat = archiver_collecte(travail)
            comptes["imports"] += 1
            comptes["publications"] += resultat["publications"]
            comptes["commentaires"] += resultat["commentaires"]
        except Exception:
            JOURNAL.warning("Archive ancienne non importée : %s", entree["id"])
            comptes["erreurs"] += 1
    return comptes


def tables_disponibles(curseur):
    """Identifier les programmes Research sans créer de faux programmes."""
    curseur.execute("SELECT to_regclass('research_plans') IS NOT NULL")
    return bool(curseur.fetchone()[0])


def lister_sauvegardes(cookie, filtre=""):
    """Lister toutes les sauvegardes privées, ponctuelles et programmées."""
    if not cookie:
        raise RuntimeError("Historique privé absent : rechargez l'application.")
    recherche = "%" + str(filtre or "")[:100].strip() + "%"
    proprietaire = empreinte(cookie)
    with ouvrir_connexion() as connexion:
        preparer_tables(connexion)
        with connexion.cursor() as curseur:
            curseur.execute("""
                SELECT c.collecte_id, c.nom_sauvegarde, c.statut,
                    c.source_collecte, c.moteur, c.actualise_le,
                    (SELECT count(*) FROM scraptiktok_publications p
                     WHERE p.collecte_id=c.collecte_id),
                    (SELECT count(*) FROM scraptiktok_commentaires m
                     WHERE m.collecte_id=c.collecte_id)
                FROM scraptiktok_collectes c
                WHERE c.proprietaire_hash=%s
                  AND c.nom_sauvegarde ILIKE %s
                ORDER BY c.actualise_le DESC LIMIT 500
            """, (proprietaire, recherche))
            resultats = [{
                "id": r[0], "type": "collecte", "nom": r[1], "statut": r[2],
                "source": r[3], "moteur": r[4], "date": r[5].isoformat(),
                "publications": r[6], "commentaires": r[7]
            } for r in curseur.fetchall()]
            if tables_disponibles(curseur):
                curseur.execute("""
                    SELECT c.plan_id, c.nom_sauvegarde, c.statut,
                           c.synchronise_le,
                           (SELECT count(*) FROM research_publications p
                            WHERE p.plan_id=c.plan_id),
                           (SELECT count(*) FROM research_commentaires m
                            WHERE m.plan_id=c.plan_id)
                    FROM research_plans c
                    WHERE c.proprietaire_hash=%s
                      AND c.nom_sauvegarde ILIKE %s
                    ORDER BY c.synchronise_le DESC LIMIT 500
                """, (proprietaire, recherche))
                resultats.extend({
                    "id": r[0], "type": "research", "nom": r[1],
                    "statut": r[2], "source": "research_programme",
                    "moteur": "research", "date": r[3].isoformat(),
                    "publications": r[4], "commentaires": r[5]
                } for r in curseur.fetchall())
    return sorted(resultats, key=lambda r: r["date"], reverse=True)


def description_table(type_sauvegarde, categorie):
    """Choisir exclusivement des noms de tables définis par l'application."""
    if type_sauvegarde not in TYPES or categorie not in CATEGORIES:
        raise ValueError("Type de sauvegarde ou catégorie inconnus.")
    if type_sauvegarde == "collecte":
        parent = "scraptiktok_collectes"
        table = "scraptiktok_" + categorie
        cle = "collecte_id"
        identifiant = "publication_id" if categorie == "publications" else "commentaire_id"
    else:
        parent = "research_plans"
        table = "research_" + categorie
        cle = "plan_id"
        identifiant = "publication_id" if categorie == "publications" else "commentaire_id"
    return parent, table, cle, identifiant


def donnees_sauvegarde(cookie, type_sauvegarde, identifiant, categorie,
                       filtre="", limite=100, decalage=0):
    """Lire une page de données sans consulter celles d'un autre utilisateur."""
    if not cookie or not IDENTIFIANT.fullmatch(str(identifiant)):
        raise ValueError("Accès à la sauvegarde impossible.")
    parent, table, cle, code = description_table(type_sauvegarde, categorie)
    limite = min(200, max(1, int(limite)))
    decalage = max(0, int(decalage))
    terme = str(filtre or "")[:150].strip()
    with ouvrir_connexion() as connexion:
        preparer_tables(connexion)
        with connexion.cursor() as curseur:
            if type_sauvegarde == "research" and not tables_disponibles(curseur):
                raise ValueError("Aucune sauvegarde Research synchronisée.")
            condition = (
                f"FROM {table} d JOIN {parent} c ON c.{cle}=d.{cle} "
                f"WHERE c.proprietaire_hash=%s AND c.{cle}=%s"
            )
            parametres = [empreinte(cookie), identifiant]
            if terme:
                condition += (
                    " AND (coalesce(d.donnees->>'description','') ILIKE %s "
                    "OR coalesce(d.donnees->>'texte','') ILIKE %s "
                    "OR coalesce(d.donnees->>'author','') ILIKE %s "
                    "OR coalesce(d.donnees->>'auteur','') ILIKE %s "
                    f"OR d.{code} ILIKE %s)")
                parametres.extend(["%" + terme + "%"] * 5)
            curseur.execute("SELECT count(*) " + condition, parametres)
            nombre = curseur.fetchone()[0]
            curseur.execute(
                f"SELECT d.donnees, d.{code}, d.retenue " + condition +
                f" ORDER BY d.{code} LIMIT %s OFFSET %s"
                if categorie == "publications" else
                f"SELECT d.donnees, d.{code}, NULL " + condition +
                f" ORDER BY d.{code} LIMIT %s OFFSET %s",
                [*parametres, limite, decalage])
            lignes = []
            for donnees, id_, retenue in curseur.fetchall():
                donnees = donnees if isinstance(donnees, dict) else json.loads(donnees)
                lignes.append({**donnees, "id": str(id_),
                               **({"retenue": retenue}
                                  if categorie == "publications" else {})})
    return {"total": nombre, "decalage": decalage, "limite": limite,
            "lignes": lignes}


def valeur_colonne(donnees, nom):
    """Construire une cellule CSV sans perdre les nombres ni les valeurs nulles."""
    if nom in ("vues", "likes", "commentaires", "partages", "favoris"):
        mesure = (donnees.get("engagement") or {}).get(nom)
        valeur = mesure.get("valeur") if isinstance(mesure, dict) else None
    else:
        valeur = donnees.get(nom)
    if valeur is None:
        return ""
    if isinstance(valeur, (list, dict)):
        return json.dumps(valeur, ensure_ascii=False)
    return str(valeur)


def exporter_sauvegarde(cookie, type_sauvegarde, identifiant, categorie, format_):
    """Exporter tout le corpus depuis PostgreSQL en CSV ou JSON, par pages."""
    if format_ not in ("csv", "json"):
        raise ValueError("Format inconnu.")
    # Valider la propriété avant d'émettre le moindre octet d'un export.
    donnees_sauvegarde(cookie, type_sauvegarde, identifiant, categorie, limite=1)
    entetes = (CHAMPS_PUBLICATIONS if categorie == "publications"
               else CHAMPS_COMMENTAIRES)

    def morceaux():
        """Émettre un export complet sans limiter le nombre de publications."""
        if format_ == "csv":
            flux = io.StringIO()
            ecrivain = csv.writer(flux)
            ecrivain.writerow(entetes)
            yield "\ufeff" + flux.getvalue()
        else:
            yield "["
        decalage = 0
        premier = True
        while True:
            page = donnees_sauvegarde(
                cookie, type_sauvegarde, identifiant, categorie,
                limite=200, decalage=decalage)
            for ligne in page["lignes"]:
                if format_ == "csv":
                    flux = io.StringIO()
                    csv.writer(flux).writerow([
                        valeur_colonne(ligne, champ) for champ in entetes])
                    yield flux.getvalue()
                else:
                    yield ("" if premier else ",") + json.dumps(
                        ligne, ensure_ascii=False, default=str)
                    premier = False
            decalage += len(page["lignes"])
            if decalage >= page["total"] or not page["lignes"]:
                break
        if format_ == "json":
            yield "]"

    return morceaux()
