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

    def test_limite_60_secondes_telecharge_un_extrait_pas_un_filtre(self):
        """Une vidéo de 120 s doit pouvoir fournir ses 60 premières secondes."""
        from types import SimpleNamespace
        from collecte.telechargement import telecharger_video
        with tempfile.TemporaryDirectory() as d:
            appels = []

            def simuler_telechargement(commande, **kwargs):
                appels.append(commande)
                sortie = Path(commande[commande.index("-o") + 1])
                sortie.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 32)
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

            publication = {"id": "123456", "url": "https://www.tiktok.com/@lemondefr/video/123456"}
            with patch("collecte.telechargement.shutil.which", return_value="/usr/bin/ffmpeg"), \
                 patch("collecte.telechargement.subprocess.run", side_effect=simuler_telechargement):
                cible = telecharger_video(publication, Path(d),
                    {"espace_libre_min_mo": 1, "taille_max_mo": 150, "duree_max_s": 60})
            self.assertTrue(cible.is_file())
            self.assertEqual(len(appels), 1)
            self.assertIn("--download-sections", appels[0])
            self.assertIn("*0-60", appels[0])
            self.assertNotIn("--match-filter", appels[0])

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

    def test_taille_depassee_puis_videos_valides_et_resultats_sauvegardes(self):
        """L'exclusion signalée ne doit ni arrêter les téléchargements ni perdre les mesures."""
        from collecte.telechargement import ErreurTelechargement
        from analyse_desordre.tests.test_analyse import creer_texture, ecrire_video
        from analyse_desordre.service import lire_tableau
        with tempfile.TemporaryDirectory() as d:
            dossier=Path(d)
            identifiants=['7552202548308872470','7552202548308872471','7552202548308872472']
            publications=[{'id':identifiant,'url':f'https://www.tiktok.com/@test/video/{identifiant}',
                          'vues':1000,'likes':10} for identifiant in identifiants]
            (dossier/'publications.json').write_text(json.dumps(publications))
            appels=[]
            def telecharger(publication,cible,parametres):
                appels.append(publication['id'])
                if publication['id']==identifiants[0]:
                    raise ErreurTelechargement('taille_depassee','Vidéo exclue par la taille maximale configurée.')
                cible.mkdir(exist_ok=True)
                chemin=cible/(publication['id']+'.mp4')
                ecrire_video(chemin,[creer_texture()]*8)
                return chemin
            # Un échec tardif des graphiques ne doit pas effacer les mesures calculées.
            with patch('collecte.telechargement.telecharger_video',side_effect=telecharger),patch(
                    'analyse_desordre.lancement.tracer_engagements',side_effect=RuntimeError('Échec graphique simulé')):
                executer(dossier,'desordre_0123456789abcdef',10,320,600,True)
            self.assertEqual(appels,identifiants)
            etat=lire_etat(dossier)
            self.assertEqual(etat['erreurs_telechargement'][0]['cause'],'taille_depassee')
            self.assertEqual(etat['telecharges'],2)
            self.assertEqual(etat['terminees'],3)
            lignes=lire_tableau(dossier/'desordre_0123456789abcdef'/'indicateurs_engagement.csv')
            self.assertEqual(len(lignes),3)
            self.assertEqual(lignes[0]['statut'],'erreur')
            self.assertTrue(all(ligne['indice_desordre'] is not None for ligne in lignes[1:]))
            self.assertFalse(list(dossier.glob('desordre_sources_*')))
