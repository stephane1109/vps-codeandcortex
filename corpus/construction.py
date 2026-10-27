"""Assemblage reproductible des exports d’une session enrichie."""
from pathlib import Path
from telechargement_videos import CHAMPS_VIDEO, correspondance_video
from .export_json import exporter_json
from .export_csv import exporter_csv
from .export_iramuteq import exporter_iramuteq
from .corpus_legendes import construire_legendes
from .corpus_commentaires import construire_commentaires
from analyse.engagement import calculer_ratios
from analyse.comparaison_medias import comparer_medias

CHAMPS_VISUELS = ["groupe_visuel", "reemploi_visuel"]

COLONNES_ENGAGEMENT = CHAMPS_VISUELS + ["publication_id", "url", "auteur", "media", "date_collecte", "legende", "retenue", "langue_detection"] + list(CHAMPS_VIDEO) + [nom+suffixe for nom in ("likes", "vues", "partages", "commentaires", "favoris") for suffixe in ("", "_brut")]

def lignes_engagement(publications):
    """Conserve les compteurs bruts, les inconnues et le statut de sélection."""
    lignes = []
    for p in publications:
        ligne = {"publication_id": p["id"], "auteur": p["author"], "media": p.get("media_id"), "date_collecte": p.get("collected_at"),
                 "url": p.get("url"), "legende": p.get("description"), "retenue": p.get("retenue"), "langue_detection": p.get("langue_detection")}
        ligne.update({k:p.get(k) for k in CHAMPS_VISUELS})
        ligne.update(correspondance_video(p))
        for nom, mesure in p.get("engagement", {}).items():
            ligne.update({nom: mesure.get("valeur"), nom + "_brut": mesure.get("brut")})
        lignes.append(ligne)
    return lignes

def construire_exports(dossier, publications, commentaires, journal, variables=None, *, texte_source=None):
    """Reprendre le TXT téléchargeable comme corpus principal dès qu’il existe."""
    dossier = Path(dossier)
    source = Path(texte_source) if texte_source is not None else dossier / "textes.txt"
    # Une source explicitement attendue doit être lisible : pas de corpus de remplacement.
    # Lire les octets conserve aussi les accents, retours à la ligne et un TXT vide.
    contenu_txt = source.read_bytes() if texte_source is not None or source.is_file() else None
    publications = [{**p, **correspondance_video(p)} for p in publications]
    correspondances = {str(p["id"]): correspondance_video(p) for p in publications}
    commentaires = [{**c, **correspondances.get(str(c.get("publication_id")), {})} for c in commentaires]
    exporter_json(dossier / "publications.json", publications)
    if (journal.get("parametres") or {}).get("telecharger_mp4") or any("video_statut" in p for p in publications):
        videos = [{**correspondance_video(p), "video_statut": p.get("video_statut", "non_retenue"),
                   "video_message": p.get("video_message"), "video_diagnostic": p.get("video_diagnostic")} for p in publications]
        exporter_json(dossier / "videos.json", videos)
        exporter_csv(dossier / "videos.csv", videos, [*CHAMPS_VIDEO, "video_statut", "video_message", "video_diagnostic"])
    exporter_json(dossier / "commentaires.json", commentaires)
    exporter_json(dossier / "journal.json", journal)
    exporter_csv(dossier / "engagement.csv", lignes_engagement(publications), COLONNES_ENGAGEMENT)
    exporter_csv(dossier / "ratios_engagement.csv",[{"publication_id":p["id"],"id_":str(p["id"]),"url":p.get("url"),**correspondance_video(p),**calculer_ratios(p.get("engagement",{}))} for p in publications])
    exporter_csv(dossier / "comparaison_medias.csv",comparer_medias(publications))
    urls = {str(p["id"]): p.get("url") for p in publications}
    # id reste celui du commentaire ; id_ désigne toujours la publication TikTok.
    commentaires_csv = [{**c, "id_": str(c.get("publication_id") or ""),
                         "url": urls.get(str(c.get("publication_id")))} for c in commentaires]
    exporter_csv(dossier / "commentaires.csv", commentaires_csv, ["id","publication_id","id_","url","parent_id","est_reponse","auteur","texte","date_brute","likes","source","observe_le",*CHAMPS_VIDEO])
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
    exporter_iramuteq(dossier / "corpus_commentaires_iramuteq.txt", construire_commentaires(commentaires,variables))
