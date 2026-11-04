"""Régression de la reprise d'une collecte aux bilans CSV contradictoires."""
import csv
import io
import unittest

from collecte.suivi_hashtags import (
    importer_bilans_hashtags_csv, preparer_reprise_hashtags,
    positions_pagination_research,
)


IDENTIFIANT = "6626e9b78f3d489ea2754591f0adc07e"


def construire_csv(lignes):
    """Produire les cinq colonnes utilisées dans les anciens bilans."""
    tampon = io.StringIO()
    colonnes = ("collecte_id", "hashtag", "etat", "liens", "motif")
    auteur = csv.DictWriter(tampon, fieldnames=colonnes, delimiter=";")
    auteur.writeheader()
    for hashtag, etat, liens, motif in lignes:
        auteur.writerow(dict(collecte_id=IDENTIFIANT, hashtag=hashtag,
                             etat=etat, liens=liens, motif=motif))
    return tampon.getvalue().encode("utf-8")


class TestBilansHistoriques(unittest.TestCase):
    def setUp(self):
        self.bilans = [
            construire_csv([
                ("manifestation", "traitee", 1393, "Recherche terminée."),
                ("lyceen", "traitee", 0, "Recherche conjointe ET."),
            ]),
            construire_csv([
                ("manifestation", "partielle", 462, "Research HTTP 401."),
                ("lyceen", "non_commencee", 0, ""),
            ]),
            construire_csv([
                ("manifestation", "partielle", 521, "Research HTTP 401."),
                ("lyceen", "non_commencee", 0, ""),
            ]),
        ]

    def test_union_bilans_historiques(self):
        selection = importer_bilans_hashtags_csv(
            self.bilans, collecte_id=IDENTIFIANT,
            hashtags_autorises=["manifestation", "lyceen"])
        self.assertEqual(selection, ["manifestation", "lyceen"])

    def test_journal_recent_traite_peut_etre_corrige_explicitement(self):
        journal = [
            dict(source="#manifestation", statut_source="traitee", rapport={}),
            dict(source="#lyceen", statut_source="traitee", rapport={}),
        ]
        for hashtag in ["manifestation", "lyceen"]:
            journal.append({
                "source": "#" + hashtag,
                "statut_source": "partielle",
                "rapport": {"collecte_partielle": True,
                            "reprise_sans_curseur": True},
            })
        selection, variantes, _ = preparer_reprise_hashtags(
            ["manifestation", "lyceen"], False, journal,
            ["manifestation", "lyceen"])
        self.assertEqual(selection, ["manifestation", "lyceen"])
        self.assertEqual(variantes, ["manifestation", "lyceen"])

    def test_reexploration_supprime_curseur_ancien(self):
        journal = [
            {"source": "#manifestation", "statut_source": "partielle",
             "rapport": {"reprise_pagination_research": {
                 "indice_periode": 0, "debut_periode": "20261001",
                 "fin_periode": "20261030", "cursor": 100,
                 "search_id": "ancien"}}},
            {"source": "#manifestation", "statut_source": "partielle",
             "rapport": {"reprise_sans_curseur": True}},
        ]
        self.assertEqual(
            positions_pagination_research(journal, ["manifestation"]), {})


if __name__ == "__main__":
    unittest.main()
