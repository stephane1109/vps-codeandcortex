"""Filtre français strict combiné aux dates et au hashtag, cas réel de légende seule."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import webapp as web
from language_filter import classify_description

# Légende observée dans le lecteur public TikTok de cette publication.
URL_SIGNALEE = 'https://www.tiktok.com/@lorvynaa/video/7700212272081161505'
LEGENDE_SIGNALEE = '#manifesting #manifestation #fyp #foryourepage #xyzabc'


class TestsFrancaisDatesHashtag(unittest.TestCase):
    def test_legende_signalee_sans_mots_a_classifier(self):
        self.assertEqual(classify_description(LEGENDE_SIGNALEE), 'unknown')

    def test_periode_hashtag_langue_et_exports_coherents(self):
        for francais_seulement in (True, False):
            with self.subTest(filtre=francais_seulement), tempfile.TemporaryDirectory() as dossier:
                parametres = web.StartRequest(hashtag='manifestation', french_only=francais_seulement,
                    date_debut='2026-10-01', date_fin='2026-10-31', enrichir=True, limit=10)
                tache = web.Job('test', parametres, Path(dossier))
                textes = [LEGENDE_SIGNALEE,
                          'Les manifestants demandent une augmentation des salaires et de meilleures conditions de travail. #manifestation',
                          'Today we are visiting the city and sharing our favorite places with friends. #manifestation',
                          'Les manifestants demandent une augmentation des salaires et de meilleures conditions de travail. #manifestation',
                          'Les manifestants demandent une augmentation des salaires et de meilleures conditions de travail. #autre']
                publications = []
                for numero, texte in enumerate(textes):
                    adresse = URL_SIGNALEE if numero == 0 else f'https://www.tiktok.com/@test/video/{1111111111 + numero}'
                    # Dates contrôlées pour ce test, pas une mesure de la date du post réel.
                    publications.append({'id': adresse.rsplit('/', 1)[1], 'url': adresse,
                        'author': 'lorvynaa' if numero == 0 else 'test', 'description': texte,
                        'created_at': '2026-09-25T12:00:00Z' if numero == 3 else '2026-10-25T12:00:00Z'})
                par_url = {p['url']: p for p in publications}
                with patch.object(web.scraper, 'collect_links', return_value=list(par_url)), \
                     patch.object(web.scraper, 'read_post', side_effect=lambda _n, url, *_a, **_k: dict(par_url[url])), \
                     patch.object(tache, 'pause'):
                    web.execute_job(tache, driver_factory=lambda _args: Mock())
                self.assertEqual(tache.status, 'completed', tache.message)
                self.assertEqual(tache.hors_periode, 1)
                self.assertEqual(tache.filtered, 1)
                attendus = [publications[1]['id']] if francais_seulement else [p['id'] for p in publications[:3]]
                self.assertEqual([p['id'] for p in tache.records], attendus)
                self.assertEqual(LEGENDE_SIGNALEE in tache.path.read_text(), not francais_seulement)
                self.assertEqual(tache.non_french, 1 if francais_seulement else 0)
                self.assertEqual(tache.language_unknown, 1 if francais_seulement else 0)
                ligne = next(p for p in tache.snapshot()['apercu_engagement'] if p['url'] == URL_SIGNALEE)
                self.assertEqual(ligne['retenue_txt'], not francais_seulement)
                self.assertEqual(ligne['langue_detection'], 'unknown' if francais_seulement else None)
                self.assertEqual((tache.directory / 'corpus_iramuteq.txt').read_bytes(), tache.path.read_bytes())


if __name__ == '__main__':
    unittest.main()
