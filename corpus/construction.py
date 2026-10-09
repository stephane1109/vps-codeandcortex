"""Assemblage reproductible des exports d’une session enrichie."""
from .export_json import exporter_json
from .export_csv import exporter_csv
from .export_iramuteq import exporter_iramuteq
from .corpus_legendes import construire_legendes
from .corpus_commentaires import construire_commentaires
from analyse.engagement import calculer_ratios
from analyse.comparaison_medias import comparer_medias

COLONNES_ENGAGEMENT = ["publication_id", "auteur", "media", "date_collecte", "url", "legende", "retenue", "langue_detection"] + [nom+suffixe for nom in ("likes", "vues", "partages", "commentaires", "favoris") for suffixe in ("", "_brut", "_confiance", "_source", "_estime")]

def lignes_engagement(publications):
    """Conserve les compteurs bruts, les inconnues et le statut de sélection."""
    lignes = []
    for p in publications:
        ligne = {"publication_id": p["id"], "auteur": p["author"], "media": p.get("media_id"), "date_collecte": p.get("collected_at"),
                 "url": p.get("url"), "legende": p.get("description"), "retenue": p.get("retenue"), "langue_detection": p.get("langue_detection")}
        for nom, mesure in p.get("engagement", {}).items():
            ligne.update({nom: mesure.get("valeur"), nom + "_brut": mesure.get("brut"), nom + "_confiance": mesure.get("confiance"), nom + "_source": mesure.get("source"), nom + "_estime": mesure.get("estime")})
        lignes.append(ligne)
    return lignes

def construire_exports(dossier, publications, commentaires, journal, variables=None):
    exporter_json(dossier / "publications.json", publications)
    exporter_json(dossier / "commentaires.json", commentaires)
    exporter_json(dossier / "journal.json", journal)
    exporter_csv(dossier / "engagement.csv", lignes_engagement(publications), COLONNES_ENGAGEMENT)
    exporter_csv(dossier / "ratios_engagement.csv",[{"publication_id":p["id"],**calculer_ratios(p.get("engagement",{}))} for p in publications])
    exporter_csv(dossier / "comparaison_medias.csv",comparer_medias(publications))
    exporter_csv(dossier / "commentaires.csv", commentaires, ["id","publication_id","parent_id","est_reponse","auteur","texte","date_brute","likes","source","observe_le"])
    exporter_iramuteq(dossier / "corpus_iramuteq.txt", construire_legendes(publications, variables))
    exporter_iramuteq(dossier / "corpus_commentaires_iramuteq.txt", construire_commentaires(commentaires,variables))
