"""Régressions du moteur persistant, sans réseau ni modèle neuronal."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures_video import VIDEO, image_test, ecrire_video
from video.empreintes import IndexVisuel, calculer_phash, calculer_regions, distance_phash
from video.parametres import charger_parametres, charger_seuils
from video.recherche_similaires import comparer_videos
from video.groupes_visuels import TYPES_REEMPLOI
from video.lots import analyser_lot


@unittest.skipUnless(VIDEO, 'OpenCV requis')
class TestsIndexVisuel(unittest.TestCase):
    def setUp(self):
        self.temporaire=tempfile.TemporaryDirectory()
        self.chemin=Path(self.temporaire.name)/'index.sqlite'
        self.index=IndexVisuel(self.chemin)
        self.seuils=charger_seuils()

    def tearDown(self):
        self.index.fermer()
        self.temporaire.cleanup()

    def enregistrer(self, identifiant, images, sha=None):
        video={'id':identifiant,'sha256':sha or identifiant,'pas_s':1,'duree_s':len(images),
               'media_id':'media'+identifiant,'images':[]}
        self.index.enregistrer_video(video,[{'temps_s':i,'image':image} for i,image in enumerate(images)])
        self.index.preparer_candidats(identifiant,self.seuils)

    def comparer(self,a='1',b='2'):
        ligne=self.index.base.execute('SELECT candidats FROM paires WHERE a=? AND b=?',(a,b)).fetchone()
        self.assertIsNotNone(ligne,'La recherche indexée doit retrouver cette paire')
        return comparer_videos(self.index.lire_video(a),self.index.lire_video(b),self.seuils,
                               candidats_indexes=json.loads(ligne[0]),index=self.index)

    def test_identite_reencodage_et_orb_paresseux(self):
        import cv2
        images=[image_test(i) for i in range(5)]
        self.enregistrer('1',images)
        self.assertEqual(self.index.base.execute('SELECT count(*) FROM images WHERE orb IS NOT NULL').fetchone()[0],0)
        compressees=[]
        for image in images:
            _,octets=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,45])
            compressees.append(cv2.imdecode(octets,1))
        self.enregistrer('2',compressees)
        self.assertIn(self.comparer()['type'],TYPES_REEMPLOI)
        with patch('video.comparaison_orb.extraire_orb',side_effect=AssertionError('Cache ORB perdu')):
            self.assertIn(self.comparer()['type'],TYPES_REEMPLOI)
        self.enregistrer('3',images,sha='1')
        self.assertEqual(self.comparer('1','3')['type'],'fichier_identique')

    def test_recadrage_fort_et_extrait_decale(self):
        import cv2
        images=[image_test(i) for i in range(8)]
        self.enregistrer('1',images)
        # Il ne reste que 36 % de la surface originale.
        recadrees=[cv2.resize(image[48:192,64:256],(320,240)) for image in images[2:7]]
        self.assertTrue(any(distance_phash(calculer_phash(a),calculer_phash(b))>16 for a,b in zip(images[2:7],recadrees)))
        self.enregistrer('2',recadrees)
        resultat=self.comparer()
        self.assertIn(resultat['type'],TYPES_REEMPLOI)
        self.assertEqual(resultat['segments'][0]['debut_a_s'],2)
        self.assertEqual(resultat['segments'][0]['debut_b_s'],0)

    def test_proches_differentes_et_image_fixe(self):
        import cv2
        images=[image_test(i) for i in range(5)]
        autres=[image_test(50+i) for i in range(5)]
        for image in images+autres:
            cv2.rectangle(image,(0,0),(319,30),(240,240,240),-1)
            cv2.putText(image,'JOURNAL',(10,25),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,0),2)
        self.enregistrer('1',images); self.enregistrer('2',autres)
        ligne=self.index.base.execute('SELECT 1 FROM paires WHERE a="1" AND b="2"').fetchone()
        if ligne: self.assertNotIn(self.comparer()['type'],TYPES_REEMPLOI)
        self.enregistrer('3',[image_test(1)]*5)
        self.enregistrer('4',[image_test(1)]*5)
        self.assertNotIn(self.comparer('3','4')['type'],TYPES_REEMPLOI)

    def test_mille_publications_indexees_sans_parcours_exhaustif(self):
        import random
        # Mille publications synthétiques avec leurs empreintes ; aucune vidéo chargée.
        hasard=random.Random(42)
        with self.index.base:
            for i in range(1000):
                h=f'{hasard.getrandbits(63):016x}'
                self.index.base.execute('INSERT INTO videos VALUES(?,?,?)',(str(i),str(i),json.dumps({'id':str(i),'sha256':str(i)})))
                numero=self.index.base.execute('INSERT INTO images(video,temps,phash,regions) VALUES(?,?,?,?)',(str(i),0,h,json.dumps([h]))).lastrowid
                self.index.base.executemany('INSERT INTO bandes VALUES(?,?,?)',[(b,(int(h,16)>>(16*b))&65535,numero) for b in range(4)])
        with patch('video.comparaison_orb.extraire_orb',side_effect=AssertionError('ORB prématuré')):
            for i in range(1000): self.index.preparer_candidats(str(i),self.seuils)
        nombre=self.index.base.execute('SELECT count(*) FROM paires').fetchone()[0]
        self.assertLess(nombre,5000)  # Au lieu de 499 500 paires exhaustives.
        self.index.fermer(); self.index=IndexVisuel(self.chemin)
        self.assertEqual(self.index.base.execute('SELECT count(*) FROM videos').fetchone()[0],1000)

    def test_lots_sessions_et_nettoyage_mp4(self):
        racine=Path(self.temporaire.name)/'donnees'
        param=charger_parametres(); param.update(videos_max=1,conserver_images=False,nettoyer_videos=True)
        for numero in ('1','2'):
            dossier=racine/'sessions'/numero
            (dossier/'videos').mkdir(parents=True)
            ecrire_video(dossier/'videos'/f'{numero}.mp4')
            (dossier/'publications.json').write_text(json.dumps([{'id':numero,'author':'compte'+numero,'description':'Texte','engagement':{}}]))
            self.assertEqual(analyser_lot(dossier,param)['statut'],'termine')
            self.assertFalse((dossier/'videos'/f'{numero}.mp4').exists())
        liens=json.loads((dossier/'comparaisons.json').read_text())
        self.assertEqual((liens[0]['a'],liens[0]['b']),('1','2'))
        self.assertIn('groupe_visuel',(dossier/'engagement.csv').read_text())
        self.assertIn('*reemploi_visuel_detecte',(dossier/'corpus_iramuteq.txt').read_text())
        # La reprise doit fonctionner même quand les MP4 ont été nettoyés.
        self.assertEqual(analyser_lot(dossier,param)['statut'],'termine')

    def test_erreur_ne_bloque_pas_les_lots_suivants(self):
        import subprocess
        import sys
        dossier=Path(self.temporaire.name)/'donnees'/'sessions'/'lot'
        (dossier/'videos').mkdir(parents=True)
        publications=[{'id':str(i),'author':'m'+str(i),'description':'Texte','engagement':{}} for i in range(1,4)]
        (dossier/'publications.json').write_text(json.dumps(publications))
        for i in (2,3): ecrire_video(dossier/'videos'/f'{i}.mp4')
        options=charger_parametres(); options.update(videos_max=1,conserver_images=False)
        configuration=Path(self.temporaire.name)/'parametres.json'
        configuration.write_text(json.dumps(options))
        processus=subprocess.run([sys.executable,'-m','video.lots','--session',str(dossier),
                                  '--parametres',str(configuration)],capture_output=True,text=True,timeout=30)
        self.assertEqual(processus.returncode,2,processus.stderr)
        bilan=json.loads(processus.stdout)
        self.assertEqual(bilan['videos_analysees'],2)
        self.assertEqual(bilan['videos_restantes'],1)
        self.assertEqual(bilan['erreurs'][0]['id'],'1')

    def test_proprietaires_separes(self):
        from stockage.base_donnees import BaseDonnees
        racine=Path(self.temporaire.name)/'prive'
        base=BaseDonnees(racine/'scraptiktok.sqlite')
        for identifiant in ('1','2'):
            dossier=racine/'sessions'/identifiant
            (dossier/'videos').mkdir(parents=True)
            base.creer_session(identifiant,'proprietaire'+identifiant,'2026-10-20',{})
            ecrire_video(dossier/'videos'/f'{identifiant}.mp4')
            (dossier/'publications.json').write_text(json.dumps([{'id':identifiant,'author':'m','description':'Texte','engagement':{}}]))
            analyser_lot(dossier,charger_parametres())
        self.assertEqual(json.loads((dossier/'comparaisons.json').read_text()),[])

    def test_fichier_remplace_invalide_les_preuves(self):
        images=[image_test(i) for i in range(5)]
        self.enregistrer('1',images); self.enregistrer('2',images)
        resultat=self.comparer()
        with self.index.base:
            self.index.base.execute('UPDATE paires SET resultat=?',(json.dumps(resultat),))
        self.assertEqual(len(list(self.index.liens())),1)
        self.enregistrer('2',[image_test(i+50) for i in range(5)],sha='remplace')
        self.assertEqual(list(self.index.liens()),[])

    def test_texte_incruste_sur_une_sequence_reutilisee(self):
        import cv2
        images=[image_test(i) for i in range(5)]
        surimpressions=[]
        for i,image in enumerate(images):
            copie=image.copy()
            cv2.rectangle(copie,(0,0),(319,36),(255,255,255),-1)
            cv2.putText(copie,'ACTUALITE '+str(i),(4,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,0),2)
            surimpressions.append(copie)
        self.enregistrer('1',images); self.enregistrer('2',surimpressions)
        self.assertIn(self.comparer()['type'],TYPES_REEMPLOI)

    def test_reencodage_mp4_reel(self):
        import cv2
        from video.extraction_images import extraire_images
        from video.empreintes import calculer_sha256
        source=Path(self.temporaire.name)/'source.mp4'
        sortie=Path(self.temporaire.name)/'reencode.mp4'
        ecrire_video(source)
        capture=cv2.VideoCapture(str(source))
        encodeur=cv2.VideoWriter(str(sortie),cv2.VideoWriter_fourcc(*'mp4v'),5,(320,240))
        try:
            while True:
                succes,image=capture.read()
                if not succes: break
                encodeur.write(image)
        finally:
            capture.release(); encodeur.release()
        self.assertNotEqual(calculer_sha256(source),calculer_sha256(sortie))
        for identifiant,chemin in [('1',source),('2',sortie)]:
            images=extraire_images(chemin,charger_parametres())['images']
            self.enregistrer(identifiant,[i['image'] for i in images],sha=calculer_sha256(chemin))
        self.assertIn(self.comparer()['type'],{'reemploi_sequence','videos_visuellement_quasi_identiques'})
