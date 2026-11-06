"""Collectes Research programmées : SQLite persistant, reprise et exports.

Les paramètres et données sont enregistrés sans clés API. Un volume persistant
DATA_DIR est indispensable sur le VPS. La base ne dépend pas du TTL des jobs.
"""
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid
from zipfile import ZipFile, ZIP_DEFLATED

ETATS_ACTIFS = {"programme", "en_cours"}
ETATS_FINAUX = {"termine", "arrete", "date_limite"}
from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, lignes_publications_csv, cellule_csv,
)
from collecte.selection_variables_csv import colonnes_csv_selectionnees

# Préserver les colonnes historiques et ajouter toutes les variables de l'interface.
CHAMPS_CSV = COLONNES_PUBLICATIONS_CSV


def maintenant():
    return datetime.now(timezone.utc)


def chemin_base(dossier):
    return Path(dossier) / "collectes_research.sqlite3"


def empreinte_proprietaire(proprietaire):
    return hashlib.sha256(proprietaire.encode("utf-8")).hexdigest()


def connexion(dossier):
    chemin = chemin_base(dossier)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    base = sqlite3.connect(chemin, timeout=20)
    base.row_factory = sqlite3.Row
    base.execute("PRAGMA journal_mode=WAL")
    base.execute("PRAGMA foreign_keys=ON")
    base.execute("PRAGMA busy_timeout=20000")
    base.executescript("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            proprietaire TEXT NOT NULL,
            nom_sauvegarde TEXT NOT NULL DEFAULT '',
            statut TEXT NOT NULL,
            debut_execution TEXT NOT NULL,
            fin_execution TEXT NOT NULL,
            debut_corpus TEXT NOT NULL,
            fin_corpus TEXT NOT NULL,
            parametres TEXT NOT NULL,
            source_index INTEGER NOT NULL DEFAULT 0,
            jour_index INTEGER NOT NULL DEFAULT 0,
            prochaine_tentative TEXT,
            job_id TEXT,
            message TEXT NOT NULL DEFAULT '',
            cree_le TEXT NOT NULL,
            actualise_le TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_plans_choix
            ON plans(statut, debut_execution, fin_execution, prochaine_tentative);
        CREATE INDEX IF NOT EXISTS idx_plans_proprietaire
            ON plans(proprietaire, cree_le DESC);
        CREATE TABLE IF NOT EXISTS publications (
            plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            id TEXT NOT NULL, retenue INTEGER NOT NULL,
            donnees TEXT NOT NULL,
            premiere_collecte TEXT NOT NULL, derniere_collecte TEXT NOT NULL,
            PRIMARY KEY(plan_id, id)
        );
        CREATE TABLE IF NOT EXISTS commentaires (
            plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            id TEXT NOT NULL, publication_id TEXT NOT NULL,
            donnees TEXT NOT NULL, collecte_le TEXT NOT NULL,
            PRIMARY KEY(plan_id, id)
        );
        CREATE TABLE IF NOT EXISTS journal (
            numero INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            date TEXT NOT NULL, type TEXT NOT NULL, detail TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_journal_plan ON journal(plan_id, numero);
        CREATE TABLE IF NOT EXISTS quotas (
            jour_utc TEXT PRIMARY KEY, appels INTEGER NOT NULL DEFAULT 0
        );
    """)
    # Migrer les bases créées avant l'ajout du nom, sans toucher aux corpus.
    colonnes = {ligne[1] for ligne in base.execute("PRAGMA table_info(plans)")}
    if "nom_sauvegarde" not in colonnes:
        base.execute("ALTER TABLE plans ADD COLUMN nom_sauvegarde TEXT NOT NULL DEFAULT ''")
        base.commit()
    return base


def jours_corpus(plan):
    debut = date.fromisoformat(plan["debut_corpus"])
    fin = date.fromisoformat(plan["fin_corpus"])
    return (fin - debut).days + 1


def sources(plan):
    parametres = json.loads(plan["parametres"])
    if parametres["source_collecte"] == "presse":
        return [("presse", identifiant) for identifiant in parametres["medias"]]
    if parametres["source_collecte"] == "comptes":
        return [("comptes", compte) for compte in parametres["comptes"]]
    # Les combinaisons ET/OU et variantes doivent rester globales.
    return [("hashtags", "")]


def creer_plan(dossier, proprietaire, parametres, debut_execution, fin_execution):
    """Créer un programme idempotent par identifiant, sans jeton ni secret."""
    debut = date.fromisoformat(debut_execution)
    fin = date.fromisoformat(fin_execution)
    debut_corpus = date.fromisoformat(parametres["date_debut"])
    fin_corpus = date.fromisoformat(parametres["date_fin"])
    if fin < debut or (fin - debut).days > 366:
        raise ValueError("Période d'exécution invalide (maximum 367 jours).")
    if fin_corpus < debut_corpus or (fin_corpus - debut_corpus).days > 366:
        raise ValueError("Période du corpus invalide (maximum 367 jours).")
    identifiant = uuid.uuid4().hex
    horodatage = maintenant().isoformat()
    parametres = dict(parametres)
    for secret in ("research_client_key", "research_client_secret", "cookies_tiktok",
                   "tikhub_api_key", "apify_api_token"):
        parametres.pop(secret, None)
    with connexion(dossier) as base:
        base.execute("""INSERT INTO plans (
            id, proprietaire, nom_sauvegarde, statut, debut_execution, fin_execution,
            debut_corpus, fin_corpus, parametres, cree_le, actualise_le)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (identifiant, empreinte_proprietaire(proprietaire),
             parametres.get("nom_sauvegarde", ""), "programme",
             debut.isoformat(), fin.isoformat(), debut_corpus.isoformat(),
             fin_corpus.isoformat(), json.dumps(parametres, ensure_ascii=False),
             horodatage, horodatage))
    return identifiant


def detail_plan(dossier, identifiant, proprietaire=None):
    with connexion(dossier) as base:
        if proprietaire is None:
            ligne = base.execute("SELECT * FROM plans WHERE id=?", (identifiant,)).fetchone()
        else:
            ligne = base.execute(
                "SELECT * FROM plans WHERE id=? AND proprietaire=?",
                (identifiant, empreinte_proprietaire(proprietaire))).fetchone()
        if ligne is None:
            return None
        plan = dict(ligne)
        plan["publications"] = base.execute(
            "SELECT COUNT(*) FROM publications WHERE plan_id=?", (identifiant,)).fetchone()[0]
        plan["publications_retenues"] = base.execute(
            "SELECT COUNT(*) FROM publications WHERE plan_id=? AND retenue=1",
            (identifiant,)).fetchone()[0]
        plan["commentaires"] = base.execute(
            "SELECT COUNT(*) FROM commentaires WHERE plan_id=?", (identifiant,)).fetchone()[0]
    plan.pop("proprietaire", None)
    plan.pop("parametres", None)
    plan["jour_corpus_courant"] = (
        date.fromisoformat(plan["debut_corpus"]) + timedelta(days=plan["jour_index"])
    ).isoformat() if plan["jour_index"] < jours_corpus(plan) else None
    plan["lots_totaux"] = jours_corpus(plan) * len(sources(ligne))
    plan["lots_termines"] = plan["jour_index"] * len(sources(ligne)) + plan["source_index"]
    return plan


def lister_plans(dossier, proprietaire):
    with connexion(dossier) as base:
        identifiants = [r[0] for r in base.execute(
            "SELECT id FROM plans WHERE proprietaire=? ORDER BY cree_le DESC LIMIT 30",
            (empreinte_proprietaire(proprietaire),)).fetchall()]
    return [detail_plan(dossier, identifiant, proprietaire) for identifiant in identifiants]


def changer_etat(dossier, identifiant, proprietaire, action):
    if action not in ("suspendre", "reprendre", "arreter"):
        raise ValueError("Action inconnue.")
    avec = connexion(dossier)
    try:
        avec.execute("BEGIN IMMEDIATE")
        plan = avec.execute("SELECT * FROM plans WHERE id=? AND proprietaire=?",
            (identifiant, empreinte_proprietaire(proprietaire))).fetchone()
        if plan is None:
            raise ValueError("Collecte introuvable.")
        actuel = plan["statut"]
        if action == "reprendre" and actuel == "suspendu":
            futur = "programme"
        elif action == "suspendre" and actuel in ETATS_ACTIFS:
            futur = "suspendu"
        elif action == "arreter" and actuel not in ETATS_FINAUX:
            futur = "arrete"
        else:
            futur = actuel
        avec.execute("UPDATE plans SET statut=?, actualise_le=? WHERE id=?",
                     (futur, maintenant().isoformat(), identifiant))
        avec.commit()
        return futur
    finally:
        avec.close()


def candidats(dossier):
    """Lister les plans éligibles sans exposer les identifiants privés."""
    jour = maintenant().date().isoformat()
    heure = maintenant().isoformat()
    with connexion(dossier) as base:
        lignes = base.execute(
            """SELECT * FROM plans WHERE statut='programme'
               AND debut_execution<=? AND fin_execution>=?
               AND (prochaine_tentative IS NULL OR prochaine_tentative<=?)
               ORDER BY actualise_le ASC LIMIT 20""", (jour, jour, heure)).fetchall()
        return [dict(r) for r in lignes]


def reserver_lot(dossier, identifiant):
    """Réservation atomique : un redémarrage ne perd pas la position du lot."""
    with connexion(dossier) as base:
        base.execute("BEGIN IMMEDIATE")
        plan = base.execute("SELECT * FROM plans WHERE id=?", (identifiant,)).fetchone()
        if plan is None or plan["statut"] != "programme":
            return None
        plan = dict(plan)
        if plan["jour_index"] >= jours_corpus(plan):
            base.execute("UPDATE plans SET statut='termine' WHERE id=?", (identifiant,))
            return None
        date_lot = (date.fromisoformat(plan["debut_corpus"])
                    + timedelta(days=plan["jour_index"]))
        if date_lot > maintenant().date():
            return None
        selection = sources(plan)
        if not selection:
            return None
        type_source, valeur = selection[plan["source_index"]]
        modif = base.execute(
            "UPDATE plans SET statut='en_cours', actualise_le=? "
            "WHERE id=? AND statut='programme'",
            (maintenant().isoformat(), identifiant))
        if modif.rowcount != 1:
            return None
        return {"id": identifiant, "source_collecte": type_source,
                "source": valeur, "jour": date_lot.isoformat(),
                "parametres": json.loads(plan["parametres"])}


def enregistrer_lot(dossier, identifiant, job, *, abouti):
    """Conserver les données avant toute progression dans le calendrier."""
    horodatage = maintenant().isoformat()
    with connexion(dossier) as base:
        base.execute("BEGIN IMMEDIATE")
        ligne = base.execute("SELECT * FROM plans WHERE id=?", (identifiant,)).fetchone()
        if ligne is None:
            return
        retenus = {str(p["id"]) for p in job.records}
        for publication in job.publications:
            pid = str(publication["id"])
            base.execute(
                """INSERT INTO publications
                   (plan_id,id,retenue,donnees,premiere_collecte,derniere_collecte)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(plan_id,id) DO UPDATE SET
                   retenue=MAX(publications.retenue,excluded.retenue),
                   donnees=excluded.donnees,
                   derniere_collecte=excluded.derniere_collecte""",
                (identifiant, pid, int(pid in retenus),
                 json.dumps(publication, ensure_ascii=False, allow_nan=False),
                 horodatage, horodatage))
        for commentaire in job.commentaires:
            base.execute(
                """INSERT INTO commentaires
                   (plan_id,id,publication_id,donnees,collecte_le)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(plan_id,id) DO UPDATE SET
                   donnees=excluded.donnees, collecte_le=excluded.collecte_le""",
                (identifiant, str(commentaire["id"]), str(commentaire["publication_id"]),
                 json.dumps(commentaire, ensure_ascii=False, allow_nan=False), horodatage))
        etat = ligne["statut"]
        if etat == "en_cours":
            if abouti:
                s = sources(dict(ligne))
                suivant = ligne["source_index"] + 1
                jour = ligne["jour_index"]
                if suivant >= len(s):
                    suivant = 0
                    jour += 1
                etat = "termine" if jour >= jours_corpus(dict(ligne)) else "programme"
                base.execute(
                    "UPDATE plans SET statut=?,source_index=?,jour_index=?,"
                    "prochaine_tentative=NULL,job_id=NULL,message=?,actualise_le=? WHERE id=?",
                    (etat, suivant, jour, str(job.message)[:500], horodatage, identifiant))
            else:
                lendemain = datetime.combine(
                    maintenant().date() + timedelta(days=1), datetime.min.time(),
                    tzinfo=timezone.utc).isoformat()
                base.execute(
                    "UPDATE plans SET statut='programme',prochaine_tentative=?,"
                    "job_id=NULL,message=?,actualise_le=? WHERE id=?",
                    (lendemain, str(job.message)[:500], horodatage, identifiant))
        else:
            base.execute("UPDATE plans SET job_id=NULL,message=?,actualise_le=? WHERE id=?",
                         (str(job.message)[:500], horodatage, identifiant))
        base.execute(
            "INSERT INTO journal(plan_id,date,type,detail) VALUES(?,?,?,?)",
            (identifiant, horodatage, "lot_termine" if abouti else "lot_incomplet",
             json.dumps({"job_id": job.id, "statut": job.status, "date": job.settings.date_debut,
                         "publications": len(job.publications),
                         "commentaires": len(job.commentaires)}, ensure_ascii=False)))


def journal_plan(dossier, identifiant, proprietaire):
    if detail_plan(dossier, identifiant, proprietaire) is None:
        return None
    with connexion(dossier) as base:
        lignes = base.execute(
            "SELECT date,type,detail FROM journal WHERE plan_id=? "
            "ORDER BY numero DESC LIMIT 100", (identifiant,)).fetchall()
        return [dict(l) for l in lignes]


def remettre_en_attente(dossier, identifiant):
    """Une erreur au lancement ne doit pas bloquer définitivement le plan."""
    suivant = datetime.combine(
        maintenant().date() + timedelta(days=1),
        datetime.min.time(), tzinfo=timezone.utc).isoformat()
    with connexion(dossier) as base:
        base.execute(
            "UPDATE plans SET statut='programme',prochaine_tentative=?,job_id=NULL,"
            "message='Démarrage du lot impossible ; nouvelle tentative demain' "
            "WHERE id=? AND statut='en_cours'", (suivant, identifiant))


def reprendre_apres_redemarrage(dossier):
    """Remettre en attente un lot dont le processus a disparu au redémarrage."""
    with connexion(dossier) as base:
        base.execute(
            "UPDATE plans SET statut='programme',job_id=NULL,"
            "message='Reprise après redémarrage du service', actualise_le=? "
            "WHERE statut='en_cours'", (maintenant().isoformat(),))


def enregistrer_partiel(dossier, identifiant, publication, commentaires):
    """Transférer chaque publication vers le corpus permanent avant la fin du lot."""
    horodatage = maintenant().isoformat()
    with connexion(dossier) as base:
        if publication is not None:
            pid = str(publication["id"])
            base.execute(
                """INSERT INTO publications
                   (plan_id,id,retenue,donnees,premiere_collecte,derniere_collecte)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(plan_id,id) DO UPDATE SET
                   retenue=MAX(publications.retenue,excluded.retenue),
                   donnees=excluded.donnees, derniere_collecte=excluded.derniere_collecte""",
                (identifiant, pid, int(bool(publication.get("retenue"))),
                 json.dumps(publication, ensure_ascii=False, allow_nan=False),
                 horodatage, horodatage))
        for commentaire in commentaires:
            base.execute(
                """INSERT INTO commentaires(plan_id,id,publication_id,donnees,collecte_le)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(plan_id,id) DO UPDATE SET
                   donnees=excluded.donnees,collecte_le=excluded.collecte_le""",
                (identifiant, str(commentaire["id"]),
                 str(commentaire["publication_id"]),
                 json.dumps(commentaire, ensure_ascii=False, allow_nan=False), horodatage))


def clore_dates(dossier):
    """Arrêter les plans, y compris ceux en cours, après leur échéance."""
    jour = maintenant().date().isoformat()
    with connexion(dossier) as base:
        expirations = [r[0] for r in base.execute(
            "SELECT id FROM plans WHERE statut IN "
            "('programme','suspendu','en_cours') AND fin_execution<?",
            (jour,)).fetchall()]
        base.execute(
            "UPDATE plans SET statut='date_limite',actualise_le=?,"
            "message='Date limite d’exécution atteinte : corpus potentiellement incomplet.' "
            "WHERE statut IN ('programme','suspendu','en_cours') AND fin_execution<?",
            (maintenant().isoformat(), jour))
    return expirations


def reserver_requete(dossier):
    """Budget local atomique pour tous les appels Research de cette application."""
    maximum = max(1, min(1000, int(os.getenv("RESEARCH_QUOTA_LOCAL_JOUR", "1000"))))
    jour = maintenant().date().isoformat()
    avec = connexion(dossier)
    try:
        avec.execute("BEGIN IMMEDIATE")
        actuel = avec.execute("SELECT appels FROM quotas WHERE jour_utc=?",
                             (jour,)).fetchone()
        nombre = actuel[0] if actuel else 0
        if nombre >= maximum:
            avec.rollback()
            return False
        avec.execute(
            "INSERT INTO quotas(jour_utc,appels) VALUES(?,1) "
            "ON CONFLICT(jour_utc) DO UPDATE SET appels=quotas.appels+1", (jour,))
        avec.execute("DELETE FROM quotas WHERE jour_utc<?",
                     ((maintenant().date() - timedelta(days=31)).isoformat(),))
        avec.commit()
        return True
    finally:
        avec.close()


def etat_quota(dossier):
    jour = maintenant().date().isoformat()
    maximum = max(1, min(1000, int(os.getenv("RESEARCH_QUOTA_LOCAL_JOUR", "1000"))))
    with connexion(dossier) as base:
        row = base.execute("SELECT appels FROM quotas WHERE jour_utc=?", (jour,)).fetchone()
    nombre = row[0] if row else 0
    return {"date_utc": jour, "appels_enregistres": nombre,
            "plafond_local": maximum, "reste_local": max(0, maximum - nombre)}


def donnees_plan(dossier, identifiant, proprietaire):
    if detail_plan(dossier, identifiant, proprietaire) is None:
        return None
    with connexion(dossier) as base:
        publications = [
            {**json.loads(r["donnees"]), "_retenue": bool(r["retenue"]),
             "_premiere_collecte": r["premiere_collecte"],
             "_derniere_collecte": r["derniere_collecte"]}
            for r in base.execute(
                "SELECT * FROM publications WHERE plan_id=? ORDER BY id", (identifiant,))]
        commentaires = [json.loads(r["donnees"]) for r in base.execute(
            "SELECT donnees FROM commentaires WHERE plan_id=? ORDER BY id", (identifiant,))]
    return publications, commentaires


def texte_csv(publications, commentaires, categorie, variables_csv=None):
    """Exporter le schéma historique ou les colonnes CSV sélectionnées."""
    lignes = publications if categorie == "publications" else commentaires
    if categorie == "publications":
        colonnes = colonnes_csv_selectionnees(CHAMPS_CSV, variables_csv)
        resultat = lignes_publications_csv(lignes)
    else:
        colonnes = ["id", "publication_id", "auteur", "texte",
                    "parent_id", "est_reponse"]
        if variables_csv is not None and "ville_etude" in variables_csv:
            colonnes.append("ville_etude")
        villes = {
            str(p.get("id")): p.get("ville_etude")
            for p in publications if p.get("ville_etude")
        }
        resultat = [
            {**ligne, "ville_etude": ligne.get("ville_etude")
             or villes.get(str(ligne.get("publication_id")))}
            for ligne in lignes
        ]
    flux = io.StringIO()
    ecrivain = csv.DictWriter(flux, fieldnames=colonnes)
    ecrivain.writeheader()
    for ligne in resultat:
        ecrivain.writerow({
            nom: cellule_csv(ligne.get(nom)) for nom in colonnes
        })
    return flux.getvalue()


def parametres_export_plan(dossier, identifiant, proprietaire):
    """Lire les préférences archivées sans inventer de nouveaux réglages."""
    with connexion(dossier) as base:
        ligne = base.execute(
            "SELECT parametres FROM plans WHERE id=? AND proprietaire=?",
            (identifiant, empreinte_proprietaire(proprietaire))).fetchone()
    return json.loads(ligne["parametres"]) if ligne else {}


def exporter(dossier, identifiant, proprietaire, format_):
    donnees = donnees_plan(dossier, identifiant, proprietaire)
    if donnees is None:
        return None
    publications, commentaires = donnees
    retenues = [p for p in publications if p["_retenue"]]
    options = (parametres_export_plan(dossier, identifiant, proprietaire)
               if format_ in {"csv", "commentaires.csv", "txt", "zip"} else {})
    choix_csv = options.get("variables_csv")
    # Pour les programmes créés avec une ville de corpus, la provenance
    # déclarée reste attachée aux lignes même après une reprise de collecte.
    if (options.get("source_collecte") == "comptes"
            and options.get("ville_etude")):
        retenues = [
            {**publication,
             "ville_etude": publication.get("ville_etude")
             or options["ville_etude"]}
            for publication in retenues
        ]
    if format_ == "json":
        return json.dumps({"publications": publications, "commentaires": commentaires},
                          ensure_ascii=False, indent=2).encode("utf-8")
    if format_ == "csv":
        return texte_csv(
            retenues, commentaires, "publications", choix_csv).encode("utf-8-sig")
    if format_ == "commentaires.csv":
        return texte_csv(
            retenues, commentaires, "commentaires", choix_csv).encode("utf-8-sig")
    if format_ == "txt":
        # Reprendre les options de construction du TXT existant.
        from webapp import text_export
        # Les anciennes lignes de SQLite n'ont pas forcément ces drapeaux.
        # Les préférences stockées dans le plan restent donc déterminantes.
        textes_retenus = [
            {**p,
             "inclure_categorie_compte_txt": options.get(
                 "categorie_compte_txt", True),
             "inclure_ville_etude_txt": options.get("ville_etude_txt", True),
             **({"ville_etude": options["ville_etude"]}
                if (options.get("source_collecte") == "comptes"
                    and options.get("ville_etude")) else {})}
            for p in retenues
        ]
        contenu = text_export(
            textes_retenus, options.get("include_sources", True),
            options.get("inclure_metadonnees_txt", False),
            options.get("variables_txt"),
            commentaires if options.get("collecter_commentaires", False) else None,
            supprimer_arobase_profil=options.get("supprimer_arobase_profil", False),
            inclure_texte_genere_ia=options.get("inclure_texte_genere_ia", False),
            inclure_theme_hashtag_txt=options.get("inclure_theme_hashtag_txt", True),
            follower_count_illustratif=options.get("follower_count_illustratif", False),
            abonnes_classe_illustratif=options.get("abonnes_classe_illustratif", False),
            variables_classes_txt=options.get("variables_classes_txt", []),
            taux_engagement_txt=options.get("taux_engagement_txt", "aucun"),
            themes=([options.get("hashtag_presse")]
                    if options.get("croiser_hashtag_presse") else
                    options.get("hashtags_saisis") or []))
        return contenu.encode("utf-8")
    if format_ == "zip":
        from collecte.parametres_collecte import generer_parametres_collecte
        flux = io.BytesIO()
        with ZipFile(flux, "w", ZIP_DEFLATED) as archive:
            for nom, contenu in {
                "publications.csv": texte_csv(
                    retenues, commentaires, "publications", choix_csv
                ).encode("utf-8-sig"),
                "commentaires.csv": texte_csv(
                    retenues, commentaires, "commentaires", choix_csv
                ).encode("utf-8-sig"),
                "collecte.json": json.dumps({"publications": publications, "commentaires": commentaires},
                                             ensure_ascii=False).encode("utf-8"),
                "textes.txt": exporter(dossier, identifiant, proprietaire, "txt"),
                # La base SQLite était auparavant proposée via un bouton séparé.
                "corpus.sqlite3": exporter(dossier, identifiant, proprietaire, "sqlite3"),
                "journal_research.json": json.dumps(
                    journal_plan(dossier, identifiant, proprietaire),
                    ensure_ascii=False, indent=2).encode("utf-8"),
                "parametres_collecte.txt": generer_parametres_collecte(
                    options, identifiant=identifiant,
                    statut="export d'un programme Research").encode("utf-8"),
            }.items():
                archive.writestr(nom, contenu)
        return flux.getvalue()
    if format_ == "sqlite3":
        # Copie indépendante contenant des colonnes SQL directement analysables.
        with tempfile.TemporaryDirectory() as rep:
            fichier = Path(rep) / "corpus.sqlite3"
            with sqlite3.connect(fichier) as base:
                base.execute("""CREATE TABLE publications(
                    id TEXT PRIMARY KEY, url TEXT, auteur TEXT,
                    date_publication TEXT, description TEXT,
                    region_code TEXT, is_verified TEXT,
                    vues INTEGER, likes INTEGER, commentaires INTEGER,
                    partages INTEGER, favoris INTEGER,
                    retenue INTEGER, premiere_collecte TEXT,
                    derniere_collecte TEXT, donnees_json TEXT)""")
                base.execute("""CREATE TABLE commentaires(
                    id TEXT PRIMARY KEY, publication_id TEXT, auteur TEXT,
                    texte TEXT, parent_id TEXT, est_reponse INTEGER,
                    donnees_json TEXT)""")
                def mesure(p, nom):
                    valeur = (p.get("engagement") or {}).get(nom)
                    return valeur.get("valeur") if isinstance(valeur, dict) else valeur
                base.executemany(
                    "INSERT INTO publications VALUES(" + ",".join("?" * 16) + ")",
                    [(str(p["id"]), p.get("url"), p.get("author"),
                      str(p.get("create_time") or ""),
                      p.get("description"), p.get("region_code"),
                      str(p.get("is_verified"))
                      if p.get("is_verified") is not None else None,
                      *(mesure(p, nom) for nom in
                        ("vues", "likes", "commentaires", "partages", "favoris")),
                      int(p["_retenue"]), p["_premiere_collecte"],
                      p["_derniere_collecte"], json.dumps(p, ensure_ascii=False))
                     for p in publications])
                base.executemany(
                    "INSERT INTO commentaires VALUES(?,?,?,?,?,?,?)",
                    [(str(com["id"]), str(com["publication_id"]),
                      com.get("auteur"), com.get("texte"), com.get("parent_id"),
                      int(bool(com.get("est_reponse"))),
                      json.dumps(com, ensure_ascii=False))
                     for com in commentaires])
                base.execute("CREATE INDEX idx_publications_auteur ON publications(auteur)")
                base.execute("CREATE INDEX idx_commentaires_video ON commentaires(publication_id)")
            return fichier.read_bytes()
    raise ValueError("Format d'export inconnu.")
