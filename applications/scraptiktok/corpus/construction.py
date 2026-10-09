"""Assemblage reproductible des exports d’une session enrichie."""
from .export_json import exporter_json
from .export_csv import exporter_csv
from .export_iramuteq import exporter_iramuteq
from .corpus_legendes import construire_legendes
from .corpus_commentaires import construire_commentaires

def construire_exports(dossier, publications, commentaires, journal, variables=None):
    exporter_json(dossier / "publications.json", publications)
    exporter_json(dossier / "commentaires.json", commentaires)
    exporter_json(dossier / "journal.json", journal)
    lignes = []
    for p in publications:
        ligne = {"publication_id": p["id"], "auteur": p["author"], "media": p.get("media_id"), "date_collecte": p.get("collected_at")}
        for nom, mesure in p.get("engagement", {}).items():
            ligne.update({nom: mesure.get("valeur"), nom + "_brut": mesure.get("brut"), nom + "_confiance": mesure.get("confiance"), nom + "_source": mesure.get("source"), nom + "_estime": mesure.get("estime")})
        lignes.append(ligne)
    exporter_csv(dossier / "engagement.csv", lignes)
    exporter_csv(dossier / "commentaires.csv", commentaires, ["id","publication_id","parent_id","est_reponse","auteur","texte","date_brute","likes","source","observe_le"])
    exporter_iramuteq(dossier / "corpus_iramuteq.txt", construire_legendes(publications, variables))
    exporter_iramuteq(dossier / "corpus_commentaires_iramuteq.txt", construire_commentaires(commentaires,variables))
