"""Recherche DINOv2 indépendante d'ORB, persistante et sans seuil d'affichage."""
import json
from importlib.util import find_spec
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from fixtures_video import image_test, ecrire_video
from video.empreintes import IndexDino
from video.embeddings import calculer_dinov2
from video.recherche_similaires import qualifier_dinov2, regrouper_dinov2
from video.parametres import charger_parametres
from video.lots import analyser_lot

@unittest.skipUnless(find_spec('faiss') and find_spec('torch'), 'Profil DINOv2 CPU requis')
class TestsDino(unittest.TestCase):
    def test_index_dix_publications_distinctes_persistant_sans_seuil(self):
        with tempfile.TemporaryDirectory() as d:
            index=IndexDino(d)
            for numero in range(14):
                v=np.zeros(384);v[numero]=1
                index.enregistrer({'id':str(numero),'sha256':str(numero),'url':'https://example.org/'+str(numero)},
                    [{'temps_s':3,'image':image_test(numero)}],[{'temps_s':3,'vecteur':v.tolist()}])
            index.preparer();index.fermer()
            index=IndexDino(d)
            try:
                r=index.rechercher('0')
                self.assertEqual(len(r),10)
                self.assertEqual(len({c['b'] for c in r}),10)
                self.assertNotIn('0',{c['b'] for c in r})
                self.assertTrue(all(c['score']==0 for c in r))
                self.assertTrue(index.miniature(r[0]['meilleure']['image_a']))
                self.assertEqual(regrouper_dinov2(r,None),[])
                self.assertEqual(regrouper_dinov2(r,.8),[])
            finally: index.fermer()

    def test_embedding_independant_par_image(self):
        import torch
        class Modele:
            def __call__(self,**pixels):
                v=torch.zeros((1,1,384));v[0,0,pixels['numero']]=1
                return type('Sortie',(),{'last_hidden_state':v})()
        with patch('video.embeddings.charger_dinov2',return_value=(Modele(),lambda **kw:{'numero':int(np.asarray(kw['images'])[0,0,0])})):
            p=charger_parametres();p['dinov2']=True
            r=calculer_dinov2([{'temps_s':i*3,'image':np.full((20,20,3),i,np.uint8)} for i in range(2)],p)
            self.assertEqual(len(r['images']),2)
            self.assertEqual(r['images'][1]['temps_s'],3)
            self.assertNotEqual(r['images'][0]['vecteur'],r['images'][1]['vecteur'])
            self.assertAlmostEqual(np.linalg.norm(r['images'][0]['vecteur']),1)

    def test_absence_modele_et_desactivation_explicitement_signalees(self):
        p=charger_parametres();p['dinov2']=False
        self.assertEqual(calculer_dinov2([],p)['statut'],'desactive')
        p['dinov2']=True
        with patch('video.embeddings.charger_dinov2',side_effect=OSError('absent')):
            self.assertEqual(calculer_dinov2([],p)['statut'],'modele_indisponible')

    def test_coherence_temporelle_distincte_de_preuve(self):
        points=[{'temps_a':i*3,'temps_b':i*3+9,'score':.9,'phash_a':f'{255<<(i*8):016x}','phash_b':f'{255<<(i*8):016x}'} for i in range(4)]
        r=qualifier_dinov2({'correspondances':points},3)
        self.assertEqual(r['nature'],'sequence_temporellement_coherente')
        self.assertFalse(r['preuve_reemploi'])
        for p in points:p['temps_b']=30-p['temps_a']
        self.assertEqual(qualifier_dinov2({'correspondances':points},3)['nature'],'ressemblance_ponctuelle')

    def test_lots_inter_sessions_sans_orb(self):
        with tempfile.TemporaryDirectory() as d:
            racine=Path(d)
            p=charger_parametres();p.update(pas_images_s=1,comparer_sequences=False,embeddings=True,conserver_images=False,nettoyer_videos=True)
            def embeddings(images,*args):
                return {'statut':'mesure','modele':'facebook/dinov2-small','images':[{'temps_s':im['temps_s'],'vecteur':([1.]+[0.]*383)} for im in images]}
            for numero in ('1','2'):
                dossier=racine/'sessions'/numero;(dossier/'videos').mkdir(parents=True)
                ecrire_video(dossier/'videos'/(numero+'.mp4'))
                (dossier/'publications.json').write_text(json.dumps([{'id':numero,'author':'test','url':'https://example.org/'+numero,'description':'','engagement':{}}]))
                with patch('video.lots.calculer_dinov2',side_effect=embeddings),patch('video.lots.calculer_embeddings',return_value={'statut':'mesure','modele':'test','poids':'test','vecteur':[1.,0.]}),patch('video.recherche_similaires.comparer_orb',side_effect=AssertionError('ORB interdit')):
                    analyser_lot(dossier,p)
            resultats=json.loads((dossier/'similarites_dino.json').read_text())
            self.assertEqual(resultats[0]['b'],'1')
            self.assertEqual(resultats[0]['score_clip'],1.)
            self.assertIn('score_clip',(dossier/'paires_dino.csv').read_text())
            self.assertEqual(resultats[0]['meilleure']['temps_a'],0)
            diagnostic=json.loads((dossier/'diagnostic_visuel.json').read_text())
            self.assertEqual(diagnostic['videos_decodees'],1)
            self.assertEqual(diagnostic['dinov2']['statuts'],{'mesure':1})
            self.assertEqual(diagnostic['videos_mp4_disponibles'],0)
            self.assertTrue(list((dossier/'miniatures_dino').glob('*.jpg')))

    def test_index_mille_publications(self):
        with tempfile.TemporaryDirectory() as d:
            index=IndexDino(d)
            try:
                hasard=np.random.default_rng(2026); image=image_test()
                for i in range(1000):
                    vecteur=hasard.normal(size=384)
                    index.enregistrer({'id':str(i),'sha256':str(i)},[{'temps_s':0,'image':image}],
                                      [{'temps_s':0,'vecteur':vecteur.tolist()}])
                index.preparer()
                self.assertEqual(index.index.ntotal,1000)
                self.assertEqual(len(index.rechercher('0')),10)
            finally:index.fermer()

    def test_modele_absent_conserve_mp4_et_signale_analyse_partielle(self):
        with tempfile.TemporaryDirectory() as d:
            dossier=Path(d)/'sessions'/'lot';(dossier/'videos').mkdir(parents=True)
            ecrire_video(dossier/'videos'/'1.mp4')
            (dossier/'publications.json').write_text(json.dumps([{'id':'1','author':'test','description':'','engagement':{}}]))
            p=charger_parametres();p.update(nettoyer_videos=True,comparer_sequences=False)
            with patch('video.lots.calculer_dinov2',return_value={'statut':'modele_indisponible','images':[]}):
                bilan=analyser_lot(dossier,p)
            self.assertEqual(bilan['statut'],'partiel')
            self.assertTrue((dossier/'videos'/'1.mp4').exists())
            diagnostic=json.loads((dossier/'diagnostic_visuel.json').read_text())
            self.assertEqual(diagnostic['dinov2']['statuts'],{'modele_indisponible':1})
            self.assertEqual(diagnostic['videos_decodees'],1)

    def test_dix_videos_toutes_les_45_paires_meme_scores_faibles(self):
        from video.recherche_similaires import synthetiser_paires
        with tempfile.TemporaryDirectory() as d:
            index=IndexDino(d)
            try:
                ids=[str(i) for i in range(10)]
                for i,identifiant in enumerate(ids):
                    v=np.zeros(384);v[i]=1
                    index.enregistrer({'id':identifiant,'sha256':identifiant},[{'temps_s':0,'image':image_test(i)}],
                                      [{'temps_s':0,'vecteur':v.tolist()}])
                resultats=[]
                for identifiant in ids:
                    voisins=index.comparer_lot(identifiant,ids)
                    self.assertEqual(len(voisins),9)
                    self.assertNotIn(identifiant,{r['b'] for r in voisins})
                    resultats.extend(voisins)
                self.assertEqual(len(resultats),90)
                self.assertEqual(len(synthetiser_paires(resultats)),45)
                with self.assertRaises(ValueError):index.comparer_lot('0',[str(i) for i in range(51)])
            finally:index.fermer()
