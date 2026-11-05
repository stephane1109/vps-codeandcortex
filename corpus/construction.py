"""Assemblage reproductible des exports d’une session enrichie."""
from pathlib import Path
from telechargement_videos import CHAMPS_VIDEO, correspondance_video
from .export_json import exporter_json
from .export_csv import exporter_csv
from .publications_csv import (COLONNES_PUBLICATIONS_CSV, lignes_publications_csv,
                               hashtags_pour_csv, hashtags_collecte_pour_csv,
                               compte_reposteur_pour_csv)
from .export_iramuteq import exporter_iramuteq
from .corpus_legendes import construire_legendes
from .corpus_commentaires import construire_commentaires
from analyse.engagement import calculer_ratios
from analyse.comparaison_medias import comparer_medias
from collecte.variables_numeriques import indicateurs_numeriques
from collecte.presse import colonnes_categories_presse

CHAMPS_VISUELS = ["groupe_visuel", "reemploi_visuel"]

COLONNES_ENGAGEMENT = CHAMPS_VISUELS + ["publication_id", "url", "auteur", "ville_etude", "media", "presse_nationale", "presse_regio_dpt", "presse_indep", "presse_autre", "hashtags", "htag_collecte", "hashtags_correspondants", "operateur_hashtags", "type_publication", "compte_reposteur", "auteur_original", "id_video_originale", "republication_confirmee", "date_republication", "date_collecte", "statut_resume_ia", "resume_ia_tiktok", "legende", "retenue", "langue_detection", "follower_count", "follower_count_statut", "classe_abonnes", "region_code", "is_verified", "is_verified_statut", "video_duration", "taux_engagement", "classe_taux_engagement", "vues_classe", "likes_classe", "commentaires_classe", "partages_classe", "favoris_classe", "duree_classe"] + list(CHAMPS_VIDEO) + [nom+suffixe for nom in ("likes", "vues", "partages", "commentaires", "favoris") for suffixe in ("", "_brut")]

def lignes_engagement(publications):
    """Conserve les compteurs bruts, les inconnues et le statut de sélection."""
    lignes = []
    for p in publications:
        ligne = {"publication_id": p["id"], "auteur": p["author"], "ville_etude": p.get("ville_etude"), "media": p.get("media_id"), "date_collecte": p.get("collected_at"),
                 "url": p.get("url"), "statut_resume_ia": p.get("statut_resume_ia"), "resume_ia_tiktok": p.get("resume_ia_tiktok"), "legende": p.get("description"), "retenue": p.get("retenue"), "langue_detection": p.get("langue_detection"),
                 "follower_count": p.get("follower_count"),
                 "follower_count_statut": p.get("follower_count_statut"),
                 "classe_abonnes": p.get("classe_abonnes"),
                 "region_code": p.get("region_code"),
                 "is_verified": p.get("is_verified"),
                 "is_verified_statut": p.get("is_verified_statut"),
                 "video_duration": p.get("video_duration"),
                 "hashtags": hashtags_pour_csv(p),
                 "htag_collecte": hashtags_collecte_pour_csv(p),
                 "hashtags_correspondants": p.get("hashtags_correspondants"),
                 "operateur_hashtags": p.get("operateur_hashtags"),
                 "type_publication": p.get("type_publication"),
                 "compte_reposteur": compte_reposteur_pour_csv(p),
                 "auteur_original": p.get("auteur_original"),
                 "id_video_originale": p.get("id_video_originale"),
                 "republication_confirmee": p.get("republication_confirmee"),
                 "date_republication": p.get("date_republication")}
        ligne.update(indicateurs_numeriques(p))
        ligne.update(colonnes_categories_presse(p))
        ligne.update({k:p.get(k) for k in CHAMPS_VISUELS})
        ligne.update(correspondance_video(p))
        for nom, mesure in p.get("engagement", {}).items():
            ligne.update({nom: mesure.get("valeur"), nom + "_brut": mesure.get("brut")})
        lignes.append(ligne)
    return lignes

def construire_exports(dossier, publications, commentaires, journal, variables=None, *,
                      texte_source=None, republications=None,
                      inclure_commentaires_txt=True, profils_medias=None,
                      profils_medias_variables=None, profils_medias_classes=None):
    """Reprendre le TXT téléchargeable comme corpus principal dès qu’il existe."""
    dossier = Path(dossier)
    source = Path(texte_source) if texte_source is not None else dossier / "textes.txt"
    # Une source explicitement attendue doit être lisible : pas de corpus de remplacement.
    # Lire les octets conserve aussi les accents, retours à la ligne et un TXT vide.
    contenu_txt = source.read_bytes() if texte_source is not None or source.is_file() else None
    publications = [{**p, **correspondance_video(p)} for p in publications]
    correspondances = {str(p["id"]): correspondance_video(p) for p in publications}
    villes_par_video = {
        str(p["id"]): p["ville_etude"] for p in publications
        if p.get("ville_etude")
    }
    commentaires = [
        {**c, **correspondances.get(str(c.get("publication_id")), {}),
         **({"ville_etude": villes_par_video[str(c.get("publication_id"))]}
            if str(c.get("publication_id")) in villes_par_video else {})}
        for c in commentaires
    ]
    exporter_json(dossier / "publications.json", publications)
    # La table complète est disponible aussi pour les collectes ponctuelles.
    exporter_csv(dossier / "publications.csv",
                 lignes_publications_csv(publications), COLONNES_PUBLICATIONS_CSV)
    if (journal.get("parametres") or {}).get("telecharger_mp4") or any("video_statut" in p for p in publications):
        videos = [{**correspondance_video(p), "video_statut": p.get("video_statut", "non_retenue"),
                   "video_message": p.get("video_message"), "video_diagnostic": p.get("video_diagnostic")} for p in publications]
        exporter_json(dossier / "videos.json", videos)
        exporter_csv(dossier / "videos.csv", videos, [*CHAMPS_VIDEO, "video_statut", "video_message", "video_diagnostic"])
    if republications is not None:
        # Une ligne par relation compte reposteur–vidéo originale. La table
        # reste séparée : l'auteur de la vidéo peut être hors des médias choisis.
        exporter_json(dossier / "republications.json", republications)
        exporter_csv(dossier / "republications.csv",
                     lignes_publications_csv(republications), COLONNES_PUBLICATIONS_CSV)
    if profils_medias is not None:
        from collecte.profils_medias import colonnes_profils_medias
        exporter_json(dossier / "profils_medias.json", profils_medias)
        exporter_csv(
            dossier / "profils_medias.csv", profils_medias,
            colonnes_profils_medias(
                profils_medias_variables or [], profils_medias_classes or []))
    exporter_json(dossier / "commentaires.json", commentaires)
    exporter_json(dossier / "journal.json", journal)
    exporter_csv(dossier / "engagement.csv", lignes_engagement(publications), COLONNES_ENGAGEMENT)
    exporter_csv(dossier / "ratios_engagement.csv",[{"publication_id":p["id"],"id_":str(p["id"]),"url":p.get("url"),**correspondance_video(p),**calculer_ratios(p.get("engagement",{}))} for p in publications])
    exporter_csv(dossier / "comparaison_medias.csv",comparer_medias(publications))
    urls = {str(p["id"]): p.get("url") for p in publications}
    # id reste celui du commentaire ; id_ désigne toujours la publication TikTok.
    commentaires_csv = [{**c, "id_": str(c.get("publication_id") or ""),
                         "url": urls.get(str(c.get("publication_id")))} for c in commentaires]
    exporter_csv(dossier / "commentaires.csv", commentaires_csv, ["id","publication_id","id_","url","parent_id","est_reponse","auteur","nom_affiche","ville_etude","texte","date_brute","likes","source","observe_le",*CHAMPS_VIDEO])
    if contenu_txt is not None:
        if variables:
            # Enrichir uniquement les en-têtes avec un ID, sans réécrire les textes collectés.
            import re
            from .export_iramuteq import normaliser_modalite
            def enrichir_entete(correspondance):
                entete=correspondance.group(0)
                identifiant=re.search(r"\*id_(\d+)(?:\s|$)",entete)
                if not identifiant: return entete
                champs=variables.get(identifiant.group(1),{})
                cles_a_ajouter=set(CHAMPS_VISUELS)|{cle for cle,valeur in champs.items() if valeur=='no'}
                for cle in sorted(cles_a_ajouter):
                    entete=re.sub(r" \*"+cle+r"_\S+", "", entete)
                    entete+=" *"+cle+"_"+normaliser_modalite(champs.get(cle))
                return entete
            contenu_txt=re.sub(r"^\*[^\r\n]*",enrichir_entete,contenu_txt.decode('utf-8'),flags=re.M).encode('utf-8')
            # Corpus garanti avec identifiants même si l'utilisateur a désactivé les en-têtes TXT.
            exporter_iramuteq(dossier / "corpus_visuel_iramuteq.txt",construire_legendes(publications,variables))
        (dossier / "corpus_iramuteq.txt").write_bytes(contenu_txt)
    else:
        # Compatibilité des lots autonomes créés sans collecte textuelle préalable.
        exporter_iramuteq(dossier / "corpus_iramuteq.txt", construire_legendes(publications, variables))
    # Le corpus des commentaires est facultatif : une collecte CSV seule ne
    # génère aucun fichier TXT contenant ces textes.
    if inclure_commentaires_txt:
        exporter_iramuteq(dossier / "corpus_commentaires_iramuteq.txt",
                         construire_commentaires(commentaires, variables))
