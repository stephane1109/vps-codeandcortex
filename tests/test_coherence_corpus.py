"""Vérifier les effectifs entre corpus, TXT et résultats partiels."""
import json
import tempfile
import unittest
from pathlib import Path
from webapp import Job,StartRequest
from analyse_desordre.sources import publications_sans_resultat

class TestsCoherenceCorpus(unittest.TestCase):
    def test_65_publications_et_4_textes(self):
        with tempfile.TemporaryDirectory() as dossier:
            tache=Job('prive',StartRequest(hashtag='test'),Path(dossier))
            tache.publications=[{'id':str(n),'author':'test','url':f'https://www.tiktok.com/@test/video/{n}',
                'description':'texte','retenue':n<4} for n in range(65)]
            tache.records=tache.publications[:4]
            lignes=tache.snapshot()['apercu_engagement']
            self.assertEqual(len(lignes),65)
            self.assertEqual(sum(r['retenue_txt'] for r in lignes),4)

    def test_32_resultats_sur_65_sans_fausse_mesure(self):
        with tempfile.TemporaryDirectory() as dossier:
            p=Path(dossier)
            (p/'publications.json').write_text(json.dumps([{'id':str(n)} for n in range(65)]))
            lignes=[{'publication_id':str(n),'indice_desordre':1} for n in range(32)]
            absentes=publications_sans_resultat(p,lignes,{'statut':'termine'})
            self.assertEqual(len(absentes),33)
            self.assertTrue(all(r['statut']=='sans_resultat' for r in absentes))
            self.assertTrue(all('indice_desordre' not in r for r in absentes))
