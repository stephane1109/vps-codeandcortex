"""Numérotation, effectifs et unités lisibles sans changer les coordonnées."""
import unittest
import pandas as pd
from analyse_desordre.presentation import formater_nombre,preparer_graphique,superposer_droite_regression,AIDE_INDICE


class TestsPresentationDesordre(unittest.TestCase):
    def test_notation_francaise(self):
        self.assertEqual(formater_nombre(1600000,0),'1 600 000')
        self.assertEqual(formater_nombre(1234.56),'1 234,56')
        self.assertEqual(formater_nombre(0),'0')
        self.assertEqual(formater_nombre(None),'Non disponible')
        self.assertIn('ni un pourcentage',AIDE_INDICE)

    def test_points_numeros_manquants_et_superpositions(self):
        tableau=pd.DataFrame({'numero_video':[1,2,3,4,5],'publication_id':['7697829530844663072','2','3','4','5'],
            'indice_desordre':[10,10,20,None,float('inf')],'vues':[1600000,1600000,300,20,50]})
        points,specification,bilan=preparer_graphique(tableau,'indice_desordre','vues','Indice','Nombre de vues')
        self.assertEqual(bilan,{'videos':3,'exclues':2,'positions':2,'superposees':2})
        self.assertEqual(list(points['numero_video']),[1,2,3])
        self.assertEqual(points.iloc[0]['videos_superposees'],'1, 2')
        self.assertEqual(points.iloc[0]['valeur_y'],'1 600 000')
        self.assertEqual(points.iloc[0]['y'],1600000)
        self.assertEqual(points.iloc[0]['publication_id'],'7697829530844663072')
        self.assertEqual(specification['encoding']['y']['axis']['tickMinStep'],1)
        self.assertTrue(any(t['field']=='numero_video' for t in specification['encoding']['tooltip']))
        self.assertIn('replace',specification['encoding']['y']['axis']['labelExpr'])

    def test_favoris_en_axe_vertical_et_en_entiers(self):
        tableau=pd.DataFrame({
            'numero_video':[1,2,3,4],
            'publication_id':['10','11','12','13'],
            'indice_desordre':[5,15,25,35],
            'favoris':[1000,1500,None,0],
        })
        points,specification,effectifs=preparer_graphique(
            tableau,'indice_desordre','favoris','Indice','Nombre de favoris')
        self.assertEqual(effectifs['videos'],3)
        self.assertEqual(effectifs['exclues'],1)
        self.assertEqual(points['y'].tolist(),[1000.,1500.,0.])
        self.assertEqual(points.iloc[0]['valeur_y'],'1 000')
        self.assertEqual(specification['encoding']['y']['axis']['tickMinStep'],1)
        self.assertTrue(any(t['field']=='valeur_y' for t in specification['encoding']['tooltip']))
        graphique,raison=superposer_droite_regression(points,specification)
        self.assertIsNone(raison)
        self.assertEqual(graphique['layer'][0]['transform'][0]['regression'],'y')

    def test_droite_disponible_et_superposee_sans_modifier_les_points(self):
        tableau=pd.DataFrame({
            'numero_video':[1,2,3,4],
            'publication_id':['10','11','12','13'],
            'indice_desordre':[10,20,30,40],
            'likes':[4,9,7,15],
        })
        points,specification,_=preparer_graphique(tableau,'indice_desordre','likes','Indice','Likes')
        original=specification.copy()
        graphique,raison=superposer_droite_regression(points,specification)
        self.assertIsNone(raison)
        self.assertEqual(len(graphique['layer']),2)
        self.assertEqual(graphique['layer'][0]['transform'],[
            {'regression':'y','on':'x','method':'linear'}
        ])
        self.assertEqual(graphique['layer'][0]['mark']['type'],'line')
        self.assertEqual(graphique['layer'][1]['mark'],original['mark'])
        self.assertEqual(graphique['layer'][1]['encoding'],original['encoding'])
        self.assertEqual(graphique['height'],380)
        self.assertEqual(specification,original)
        self.assertEqual(points['x'].tolist(),[10.,20.,30.,40.])

    def test_droite_impossible_avec_peu_de_points_ou_variable_constante(self):
        cas=[
            ([10.,20.],[10.,30.],"trois vidéos"),
            ([10.,10.,10.],[1.,3.,5.],"constante"),
            ([10.,20.,30.],[7.,7.,7.],"constante"),
        ]
        for x,y,motif in cas:
            points=pd.DataFrame({'x':x,'y':y})
            spec={'mark':{'type':'circle'},'encoding':{'x':{'field':'x'},'y':{'field':'y'}},'height':380}
            graphique,raison=superposer_droite_regression(points,spec)
            self.assertIs(graphique,spec)
            self.assertIn(motif,raison)
            self.assertNotIn('layer',graphique)
