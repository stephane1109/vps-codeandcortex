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
from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, ligne_publication_csv, cellule_csv,
)

JOURNAL = logging.getLogger(__name__)
IDENTIFIANT = re.compile(r"[0-9a-f]{32}\Z")
TYPES = {"collecte", "research"}
CATEGORIES = {"publications", "commentaires"}
# Une même liste complète pour les archives, Research et la consultation SQL.
CHAMPS_PUBLICATIONS = COLONNES_PUBLICATIONS_CSV
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
                parametres JSONB NOT NULL DEFAULT '{}'::jsonb,
                journal_research JSONB NOT NULL DEFAULT '[]'::jsonb,
                source_en_cours_id TEXT
            )""")
        # Les anciennes sauvegardes n'ont pas encore ces colonnes.
        curseur.execute(
            "ALTER TABLE scraptiktok_collectes "
            "ADD COLUMN IF NOT EXISTS journal_research JSONB "
            "NOT NULL DEFAULT '[]'::jsonb")
        curseur.execute(
            "ALTER TABLE scraptiktok_collectes "
            "ADD COLUMN IF NOT EXISTS source_en_cours_id TEXT")
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
        curseur.execute("""
            CREATE TABLE IF NOT EXISTS scraptiktok_republications (
                collecte_id TEXT NOT NULL REFERENCES scraptiktok_collectes(collecte_id)
                    ON DELETE CASCADE,
                compte_reposteur TEXT NOT NULL,
                publication_id TEXT NOT NULL,
                donnees JSONB NOT NULL,
                PRIMARY KEY(collecte_id, compte_reposteur, publication_id)
            )""")
        curseur.execute(
            "CREATE INDEX IF NOT EXISTS scraptiktok_republications_video "
            "ON scraptiktok_republications(collecte_id, publication_id)")
        # Lecture tabulaire directe dans pgAdmin, sans décodage manuel du JSONB.
        curseur.execute("""
            CREATE OR REPLACE VIEW v_scraptiktok_republications AS
            SELECT r.collecte_id, r.compte_reposteur,
                   r.publication_id AS id_video_originale,
                   r.donnees->>'auteur_original' AS auteur_original,
                   r.donnees->>'url' AS url,
                   r.donnees->>'description' AS description,
                   r.donnees->>'created_at' AS date_creation_video,
                   r.donnees->>'date_republication' AS date_republication,
                   r.donnees->>'region_code' AS region_code,
                   r.donnees->>'video_duration' AS video_duration,
                   r.donnees->>'republication_confirmee' AS republication_confirmee,
                   r.donnees->'engagement'->'vues'->>'valeur' AS vues,
                   r.donnees->'engagement'->'likes'->>'valeur' AS likes,
                   r.donnees->'engagement'->'commentaires'->>'valeur' AS commentaires,
                   r.donnees->'engagement'->'partages'->>'valeur' AS partages,
                   r.donnees->'engagement'->'favoris'->>'valeur' AS favoris
            FROM scraptiktok_republications r""")
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
        republications = list(getattr(job, "republications", []))
        publications = publications[max(0, a_partir_publications):]
        commentaires = commentaires[max(0, a_partir_commentaires):]
        parametres = nettoyer_parametres(job.settings.model_dump())
        journal_research = list(getattr(job, "journal", []) or [])
        source_en_cours_id = getattr(job, "source_en_cours_id", None)
        statut = job.status
        traitees = job.processed + getattr(job, "reprise_decalage", 0)
        identifiant = job.id
        nom = job.settings.nom_sauvegarde or job.settings.libelle
        source = job.settings.source_collecte
        moteur = job.settings.moteur_actif
    maintenant = datetime.now(timezone.utc)
    with ouvrir_connexion() as connexion:
        preparer_tables(connexion)
        with connexion.cursor() as curseur:
            if getattr(job, "reprise", False):
                # Verrouiller la collecte d'origine et interdire la création
                # accidentelle d'un second corpus sous un identifiant repris.
                curseur.execute(
                    "SELECT 1 FROM scraptiktok_collectes "
                    "WHERE collecte_id=%s AND proprietaire_hash=%s FOR UPDATE",
                    (identifiant, empreinte(job.owner_historique)))
                if curseur.fetchone() is None:
                    raise RuntimeError(
                        "Collecte d'origine absente de PostgreSQL : reprise arrêtée.")
            curseur.execute("""
                INSERT INTO scraptiktok_collectes (
                    collecte_id, proprietaire_hash, nom_sauvegarde,
                    source_collecte, moteur, statut, cree_le, actualise_le,
                    traitees, parametres, journal_research, source_en_cours_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (collecte_id) DO UPDATE SET
                    nom_sauvegarde=EXCLUDED.nom_sauvegarde,
                    statut=EXCLUDED.statut,
                    actualise_le=EXCLUDED.actualise_le,
                    traitees=EXCLUDED.traitees,
                    parametres=EXCLUDED.parametres,
                    journal_research=EXCLUDED.journal_research,
                    source_en_cours_id=EXCLUDED.source_en_cours_id
            """, (
                identifiant, empreinte(job.owner_historique), nom, source,
                moteur, statut, maintenant, maintenant, traitees,
                Jsonb(parametres), Jsonb(journal_research),
                source_en_cours_id))
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
            for relation in republications:
                video_id = str(relation.get("id_video_originale")
                               or relation.get("id") or "")
                reposteur = str(relation.get("compte_reposteur") or "")
                if not video_id or not reposteur:
                    continue
                curseur.execute("""
                    INSERT INTO scraptiktok_republications (
                        collecte_id, compte_reposteur, publication_id, donnees)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT(collecte_id,compte_reposteur,publication_id)
                    DO UPDATE SET donnees=EXCLUDED.donnees
                """, (identifiant, reposteur, video_id, Jsonb(relation)))
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
            "commentaires": len(commentaires),
            "republications": len(republications)}


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
            chemin_republications = Path(repertoire) / "republications.json"
            republications = (
                json.loads(chemin_republications.read_text(encoding="utf-8"))
                if chemin_republications.is_file() else [])
            publications = (
                json.loads(chemin_publications.read_text(encoding="utf-8"))
                if chemin_publications.is_file() else [])
            commentaires = (
                json.loads(chemin_commentaires.read_text(encoding="utf-8"))
                if chemin_commentaires.is_file() else [])
            if not all(isinstance(lignes, list) for lignes in
                       (publications, commentaires, republications)):
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
                commentaires=commentaires, republications=republications,
                processed=manifeste.get("traites", 0),
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



def supprimer_collecte_postgres(cookie, type_sauvegarde, identifiant, nom_confirmation):
    """Supprimer une collecte précise et ses lignes liées, jamais les tables.

    L'identité privée, l'identifiant et le nom exact sont vérifiés dans
    la transaction. Les clés étrangères ON DELETE CASCADE suppriment les
    publications et commentaires de cette seule collecte.
    """
    if (not cookie or not IDENTIFIANT.fullmatch(str(identifiant))
            or type_sauvegarde not in TYPES):
        raise ValueError("Collecte introuvable ou non autorisée.")
    parent, _, cle, _ = description_table(type_sauvegarde, "publications")
    with ouvrir_connexion() as connexion:
        with connexion.cursor() as curseur:
            if type_sauvegarde == "research" and not tables_disponibles(curseur):
                raise ValueError("Collecte Research introuvable.")
            curseur.execute(
                f"SELECT nom_sauvegarde FROM {parent} "
                f"WHERE {cle}=%s AND proprietaire_hash=%s FOR UPDATE",
                (identifiant, empreinte(cookie)),
            )
            ligne = curseur.fetchone()
            if ligne is None:
                raise ValueError("Collecte introuvable ou non autorisée.")
            nom = str(ligne[0])
            if nom_confirmation != nom:
                raise ValueError("Le nom de confirmation ne correspond pas.")
            curseur.execute(
                f"DELETE FROM {parent} WHERE {cle}=%s "
                "AND proprietaire_hash=%s RETURNING nom_sauvegarde",
                (identifiant, empreinte(cookie)),
            )
            resultat = curseur.fetchone()
            if resultat is None:
                raise ValueError("Collecte introuvable ou non autorisée.")
    return {"statut": "supprime", "nom": nom, "type": type_sauvegarde}



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
        valeur = mesure.get("valeur") if isinstance(mesure, dict) else donnees.get(nom)
    else:
        valeur = donnees.get(nom)
    return cellule_csv(valeur)




def compter_publications_collecte(cookie, identifiant):
    """Contrôler le corpus PostgreSQL avant reprise, sans modifier les données."""
    if not cookie or not IDENTIFIANT.fullmatch(str(identifiant)):
        raise ValueError("Collecte inconnue ou non autorisée.")
    with ouvrir_connexion() as connexion:
        with connexion.cursor() as curseur:
            curseur.execute(
                "SELECT COUNT(p.publication_id) "
                "FROM scraptiktok_collectes AS c "
                "LEFT JOIN scraptiktok_publications AS p "
                "ON p.collecte_id=c.collecte_id "
                "WHERE c.collecte_id=%s AND c.proprietaire_hash=%s "
                "GROUP BY c.collecte_id",
                (identifiant, empreinte(cookie)),
            )
            resultat = curseur.fetchone()
    if resultat is None:
        raise ValueError("Collecte PostgreSQL introuvable ou non autorisée.")
    return int(resultat[0])



def obtenir_nom_collecte(cookie, type_sauvegarde, identifiant):
    """Lire le nom d'une collecte PostgreSQL appartenant à la session privée."""
    if not cookie or not IDENTIFIANT.fullmatch(str(identifiant)):
        raise ValueError("Collecte inconnue ou non autorisée.")
    parent, _, cle, _ = description_table(type_sauvegarde, "publications")
    with ouvrir_connexion() as connexion:
        preparer_tables(connexion)
        with connexion.cursor() as curseur:
            if type_sauvegarde == "research" and not tables_disponibles(curseur):
                raise ValueError("Collecte Research inconnue.")
            curseur.execute(
                f"SELECT nom_sauvegarde FROM {parent} "
                f"WHERE {cle}=%s AND proprietaire_hash=%s",
                (identifiant, empreinte(cookie)),
            )
            ligne = curseur.fetchone()
    if ligne is None:
        raise ValueError("Collecte inconnue ou non autorisée.")
    return str(ligne[0])



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
                    cellules = (
                        ligne_publication_csv(ligne)
                        if categorie == "publications" else ligne)
                    csv.writer(flux).writerow([
                        valeur_colonne(cellules, champ) for champ in entetes])
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
