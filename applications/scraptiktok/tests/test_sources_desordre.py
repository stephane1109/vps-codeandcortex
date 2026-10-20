"""Les publications collectées doivent pouvoir préparer leurs MP4 avant l'analyse."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from analyse_desordre.sources import inventaire_sources,retrouver_sources
from analyse_desordre.service import executer,lire_etat


class TestsSourcesDesordre(unittest.TestCase):
    def test_collecte_sans_mp4_dix_urls_disponibles(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'publications.json').write_text(json.dumps([{'id':str(n),'url':f'https://www.tiktok.com/@test/video/{n}'} for n in range(10)]))
            self.assertEqual(inventaire_sources(p),{'publications_collectees':10,'mp4_locaux':0,'mp4_manquants':10,'mp4_telechargeables':10})

    def test_chemin_reference_sous_dossier_et_exclusion_externe(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);session=p/'session';session.mkdir()
            (session/'videos'/'import').mkdir(parents=True)
            (session/'videos'/'import'/'id_1.MP4').write_bytes(b'mp4')
            (session/'fichier_importe.mp4').write_bytes(b'mp4')
            (p/'externe.mp4').write_bytes(b'prive')
            (session/'lien.mp4').symlink_to(p/'externe.mp4')
            (session/'publications.json').write_text(json.dumps([{'id':'1'},{'id':'2','video_fichier':'fichier_importe.mp4'},
                {'id':'3','video_fichier':'../externe.mp4'},{'id':'4','video_fichier':'lien.mp4'}]))
            _,fichiers=retrouver_sources(session)
            self.assertEqual(set(fichiers),{'1','2'})

    def test_preparation_telecharge_et_reutilise_sans_moteur_similarite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'videos').mkdir();(p/'videos'/'id_1.mp4').write_bytes(b'existant')
            publications=[{'id':str(n),'url':f'https://www.tiktok.com/@test/video/{n}'} for n in (1,2,3)]
            (p/'publications.json').write_text(json.dumps(publications))
            def telecharger(publication,dossier,parametres):
                if publication['id']=='3': raise RuntimeError('Refus de téléchargement')
                chemin=dossier/'2.mp4';chemin.write_bytes(b'nouveau');return chemin
            def analyser(videos,metadonnees,sortie,parametres,progression):
                self.assertEqual({f.name for f in Path(videos).glob('*.mp4')},{'1.mp4','2.mp4'})
                self.assertEqual((Path(videos)/'1.mp4').read_bytes(),b'existant')
                return {'statuts':{'mesure':2,'erreur':1}}
            with patch('collecte.telechargement.telecharger_video',side_effect=telecharger) as recuperer,patch('analyse_desordre.lancement.analyser_lot',side_effect=analyser):
                executer(p,'desordre_0123456789abcdef',10,320,600,True)
            self.assertEqual(recuperer.call_count,2)
            etat=lire_etat(p)
            self.assertEqual(etat['statut'],'partiel');self.assertEqual(etat['telecharges'],1)
            self.assertEqual(etat['erreurs_telechargement'][0]['publication_id'],'3')
            self.assertFalse(list(p.glob('desordre_sources_*')))
            self.assertTrue((p/'videos'/'2.mp4').exists())
