"""Faux négatifs de présélection, diagnostic et modalités des options désactivées."""
import json
from pathlib import Path
import tempfile
import unittest
from fixtures_video import VIDEO,ecrire_video,image_test
from analyse.codage_automatique import coder_variables
from corpus.construction import construire_exports
from video.empreintes import IndexVisuel,repartir_candidats
from video.parametres import charger_parametres,charger_seuils
from video.recherche_similaires import comparer_videos
from video.lots import analyser_lot


class TestsOptions(unittest.TestCase):
    def test_option_desactivee_distincte_d_une_erreur(self):
        publication={'id':'1','author':'a','description':'Texte','engagement':{}}
        parametres=charger_parametres()
        variables=coder_variables(publication,{},None,parametres)['variables']
        for cle in ('audio','texte','parole','ocr','transcription','embeddings'):
            self.assertEqual(variables[cle],'no')
        parametres.update(audio=True,ocr=True,transcription=True)
        variables=coder_variables(publication,{},None,parametres)['variables']
        for cle in ('audio','texte','parole'): self.assertEqual(variables[cle],'indetermine')
        self.assertEqual(variables['ocr'],'yes')
        parametres.update(comparer_sha256=False,comparer_sequences=False)
        self.assertEqual(coder_variables(publication,{},None,parametres)['variables']['reemploi'],'no')

    def test_budget_conserve_les_images_en_fin_de_video(self):
        candidats=[[i,j,0] for i in range(180) for j in range(10)]
        retenus=repartir_candidats(candidats,400)
        self.assertEqual(len(retenus),400)
        self.assertEqual({c[0] for c in retenus},set(range(180)))

    def test_export_no_dans_les_entetes_et_texte_inchange(self):
        publication={'id':'123','author':'a','description':'Texte conservé','engagement':{}}
        variables={'123':coder_variables(publication,{},None,charger_parametres())['variables']}
        with tempfile.TemporaryDirectory() as temporaire:
            dossier=Path(temporaire)
            # Les deux formes d'en-tête existent dans les exports historiques.
            for prefixe in ('**** ', ''):
                source=prefixe+'*profil_a *id_123\nTexte conservé\n'
                (dossier/'textes.txt').write_text(source)
                construire_exports(dossier,[publication],[],{},variables)
                corpus=(dossier/'corpus_iramuteq.txt').read_text()
                for cle in ('audio','ocr','transcription','embeddings'):
                    self.assertIn('*'+cle+'_no',corpus)
                self.assertIn('Texte conservé',corpus)
                self.assertEqual((dossier/'textes.txt').read_text(),source)


@unittest.skipUnless(VIDEO,'OpenCV requis')
class TestsReemploi(unittest.TestCase):
    def test_presel_phash_stable_ne_bloque_pas_orb(self):
        with tempfile.TemporaryDirectory() as temporaire:
            index=IndexVisuel(Path(temporaire)/'index.sqlite')
            try:
                for identifiant in ('1','2'):
                    meta={'id':identifiant,'sha256':identifiant,'duree_s':5,'pas_s':1,'images':[]}
                    index.enregistrer_video(meta,[{'temps_s':i,'image':image_test(i)} for i in range(5)])
                    index.preparer_candidats(identifiant,charger_seuils())
                # Les empreintes globales sont identiques, mais les régions appariées changent.
                with index.base: index.base.execute("UPDATE images SET phash='0000000000000000'")
                candidats=json.loads(index.base.execute('SELECT candidats FROM paires WHERE a="1" AND b="2"').fetchone()[0])
                resultat=comparer_videos(index.lire_video('1'),index.lire_video('2'),charger_seuils(),candidats_indexes=candidats,index=index)
                self.assertEqual(resultat['type'],'videos_visuellement_quasi_identiques')
                self.assertGreater(resultat['paires_orb_testees'],0)
            finally: index.fermer()

    def test_migration_conserve_vignettes_et_rejoue_recherches(self):
        with tempfile.TemporaryDirectory() as temporaire:
            chemin=Path(temporaire)/'index.sqlite'
            index=IndexVisuel(chemin)
            index.enregistrer_video({'id':'1','sha256':'1'},[{'temps_s':0,'image':image_test()}])
            with index.base:
                index.base.execute('DELETE FROM version_recherche')
                index.base.execute('DELETE FROM recherches')
            index.fermer()
            index=IndexVisuel(chemin)
            try:
                self.assertEqual(index.base.execute('SELECT video FROM recherches').fetchall(),[('1',)])
                self.assertIsNotNone(index.lire_image(1)['orb'])
            finally: index.fermer()

    def test_dix_videos_et_passage_commun(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier=Path(temporaire)/'sessions'/'lot'
            (dossier/'videos').mkdir(parents=True)
            publications=[]
            for i in range(1,11):
                graines=(1,2,3,4,5) if i in (1,10) else tuple(range(10*i,10*i+5))
                ecrire_video(dossier/'videos'/f'{i}.mp4',graines=graines,recadrer=i==10)
                publications.append({'id':str(i),'author':'compte'+str(i),'description':'Texte','engagement':{}})
            (dossier/'publications.json').write_text(json.dumps(publications))
            parametres=charger_parametres(); parametres.update(pas_images_s=1,dinov2=False); parametres['conserver_images']=False
            analyser_lot(dossier,parametres)
            liens=json.loads((dossier/'comparaisons.json').read_text())
            self.assertTrue(any({c['a'],c['b']}=={'1','10'} for c in liens))
            diagnostic=json.loads((dossier/'diagnostic_visuel.json').read_text())
            self.assertEqual(diagnostic['videos_analysees'],10)
            self.assertGreater(diagnostic['images_confirmees'],0)
            self.assertEqual(diagnostic['videos_en_erreur'],0)
            self.assertIn('*audio_no',(dossier/'corpus_iramuteq.txt').read_text())
