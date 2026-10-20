"""Numérotation, effectifs et unités lisibles sans changer les coordonnées."""
import unittest
import pandas as pd
from analyse_desordre.presentation import formater_nombre,preparer_graphique,AIDE_INDICE


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
