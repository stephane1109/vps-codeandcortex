"""Régressions indépendantes : mouvements connus, coupures, données manquantes et exports."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from scipy.stats import spearmanr
from analyse_desordre.parametres import Parametres
from analyse_desordre.mouvement_camera import compenser_camera, mesurer_instabilite
from analyse_desordre.mouvements import mesurer_mouvements
from analyse_desordre.engagement import calculer_taux, charger_metadonnees
from analyse_desordre.statistiques import correlation_spearman
from analyse_desordre.lancement import analyser_video, analyser_lot


def creer_texture():
    hasard=np.random.default_rng(8)
    return cv2.GaussianBlur(hasard.integers(0,256,(128,192),dtype=np.uint8),(3,3),0)


def deplacer(image,x):
    return cv2.warpAffine(image,np.float32([[1,0,x],[0,1,0]]),(image.shape[1],image.shape[0]),borderMode=cv2.BORDER_REFLECT)


def ecrire_video(chemin,images):
    h,w=images[0].shape
    sortie=cv2.VideoWriter(str(chemin),cv2.VideoWriter_fourcc(*'mp4v'),10,(w,h))
    if not sortie.isOpened(): raise RuntimeError('Encodeur MP4 indisponible pour les tests.')
    try:
        for image in images: sortie.write(cv2.cvtColor(image,cv2.COLOR_GRAY2BGR))
    finally: sortie.release()


class TestsMesures(unittest.TestCase):
    def setUp(self):
        self.parametres=Parametres(permutations=99)
        self.image=creer_texture()

    def test_translation_compensee_et_scene_fixe(self):
        for x in (0,2):
            mesure=compenser_camera(self.image,deplacer(self.image,x),.1,self.parametres)
            self.assertEqual(mesure['statut'],'mesure')
            mouvements=mesurer_mouvements(mesure['residuel'],mesure['valides'],mesure['diagonale'],.1,self.parametres)
            self.assertLess(mouvements['vitesse_residuelle'],.005)
            if x: self.assertGreater(np.linalg.norm(mesure['vitesses_camera'],axis=1).mean(),.05)

    def test_secousse_et_mouvement_regulier(self):
        a=np.full((4,2),.1);b=-a
        self.assertEqual(mesurer_instabilite(a,a,.1),0)
        self.assertGreater(mesurer_instabilite(b,a,.1),2)
        self.assertIsNone(mesurer_instabilite(a,None,.1))

    def test_entropie_flux_unidirectionnel_et_multidirectionnel(self):
        flux=np.zeros((24,24,2),np.float32);flux[:,:,0]=2
        masque=np.ones((24,24),bool)
        uniforme=mesurer_mouvements(flux,masque,34,.1,self.parametres)
        self.assertAlmostEqual(uniforme['entropie_directionnelle'],0)
        angles=(np.arange(576)%12+.5)*2*np.pi/12
        flux[:,:,0]=(2*np.cos(angles)).reshape(24,24);flux[:,:,1]=(2*np.sin(angles)).reshape(24,24)
        multiple=mesurer_mouvements(flux,masque,34,.1,self.parametres)
        self.assertAlmostEqual(multiple['entropie_directionnelle'],1,places=5)

    def test_objet_mobile_sur_fond_fixe(self):
        a=self.image.copy();b=self.image.copy()
        objet=creer_texture()[:32,:32]
        a[40:72,40:72]=objet;b[40:72,44:76]=objet
        mesure=compenser_camera(a,b,.1,self.parametres)
        self.assertEqual(mesure['statut'],'mesure')
        interieur=np.linalg.norm(mesure['residuel'][45:66,47:66],axis=2).mean()
        self.assertGreater(interieur,1)
        self.assertLess(np.linalg.norm(mesure['vitesses_camera'],axis=1).mean(),.02)

    def test_coupure_et_absence_texture(self):
        noire=np.zeros_like(self.image);blanche=np.full_like(self.image,255)
        self.assertEqual(compenser_camera(noire,blanche,.1,self.parametres)['statut'],'changement_plan')
        self.assertEqual(compenser_camera(noire,noire,.1,self.parametres)['statut'],'compensation_indisponible')
        # Coupure entre deux textures distinctes, malgré des histogrammes semblables.
        hasard=np.random.default_rng(91)
        a=hasard.integers(0,256,self.image.shape,dtype=np.uint8)
        b=hasard.integers(0,256,self.image.shape,dtype=np.uint8)
        self.assertEqual(compenser_camera(a,b,.1,self.parametres)['statut'],'changement_plan')

    def test_mp4_coupure_reinitialise_les_differences(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'1.mp4';ecrire_video(p,[self.image]*5+[255-self.image]*5)
            resume,lignes=analyser_video(p,self.parametres)
            coupures=[i for i,r in enumerate(lignes) if r['statut']=='changement_plan']
            self.assertTrue(coupures)
            for i in coupures:
                self.assertNotIn('indice_desordre',lignes[i])
                if i+1<len(lignes): self.assertIsNone(lignes[i+1].get('irregularite_temporelle'))
            self.assertLess(resume['couverture_mouvement'],1)


class TestsEngagementStatistiques(unittest.TestCase):
    def test_taux_zero_absences(self):
        self.assertEqual(calculer_taux({'vues':100,'likes':10})['likes_pour_1000_vues'],100)
        self.assertIsNone(calculer_taux({'vues':0,'likes':0})['likes_pour_1000_vues'])
        self.assertIsNone(calculer_taux({'vues':100})['likes_pour_1000_vues'])
        self.assertEqual(calculer_taux({'engagement':{'vues':{'valeur':100},'likes':{'valeur':0}}})['likes_pour_1000_vues'],0)

    def test_spearman_ex_aequo_exact_et_manquants(self):
        x=[1,1,2,3,4];y=[3,2,4,1,5]
        resultat=correlation_spearman(x,y)
        self.assertAlmostEqual(resultat['rho'],spearmanr(x,y).statistic)
        self.assertEqual(resultat['methode'],'permutation_exacte')
        self.assertAlmostEqual(correlation_spearman([1,2,3],[1,2,3])['p'],1/3)
        self.assertIsNone(correlation_spearman([1,1,1],[1,2,3])['rho'])
        self.assertEqual(correlation_spearman([1,2,float('nan')],[1,2,3])['n'],2)
        self.assertEqual(correlation_spearman(range(10),range(10),99),correlation_spearman(range(10),range(10),99))

    def test_csv_identifiants_exacts_et_doublons(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'engagement.csv';p.write_text('publication_id;vues;likes\n7697829530844663072;100;10\n')
            self.assertIn('7697829530844663072',charger_metadonnees(p))
            p.write_text('id,vues\n1,3\n1,5\n')
            with self.assertRaises(ValueError): charger_metadonnees(p)


class TestsIntegration(unittest.TestCase):
    def test_lot_exports_et_sources_intactes(self):
        with tempfile.TemporaryDirectory() as d:
            dossier=Path(d);videos=dossier/'videos';videos.mkdir();image=creer_texture()
            for i in (1,2,3): ecrire_video(videos/f'id_{i}.mp4',[deplacer(image,j*(i-1)) for j in range(10)])
            (videos/'id_4.mp4').write_bytes(b'invalide')
            meta=dossier/'publications.json';meta.write_text(json.dumps([{'id':str(i),'engagement':{'vues':{'valeur':100},'likes':{'valeur':i}}} for i in range(1,6)]))
            avant=meta.read_bytes();sortie=dossier/'resultats'
            bilan=analyser_lot(videos,meta,sortie,Parametres(permutations=99))
            self.assertEqual(bilan['publications'],5);self.assertEqual(bilan['statuts']['erreur'],2)
            self.assertEqual(meta.read_bytes(),avant);self.assertEqual(len(list(videos.glob('*.mp4'))),4)
            self.assertEqual(len(list(sortie.glob('*.png'))),5)
            self.assertTrue((sortie/'mesures_temporelles.csv').is_file())
            with (sortie/'correlations_spearman.csv').open(encoding='utf-8-sig') as f:
                lignes=list(csv.DictReader(f));self.assertEqual(len(lignes),35)
            with self.assertRaises(FileExistsError): analyser_lot(videos,meta,sortie,Parametres(permutations=99))

    def test_limite_duree_et_video_uniforme(self):
        with tempfile.TemporaryDirectory() as d:
            chemin=Path(d)/'noir.mp4';ecrire_video(chemin,[np.zeros((64,64),np.uint8)]*20)
            resume,lignes=analyser_video(chemin,Parametres(duree_max=.5,permutations=99))
            self.assertTrue(resume['tronque'])
            self.assertEqual(resume['statut'],'partiel')
            self.assertIsNone(resume['indice_desordre'])
            self.assertTrue(all(r['statut']=='compensation_indisponible' for r in lignes))
