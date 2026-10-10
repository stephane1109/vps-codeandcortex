"""Vérifier dans Chrome le contrôleur intégré, sa reprise et ses erreurs visibles.

Exécution : .venv/bin/python tests/smoke_controle.py (sans accès à TikTok).
"""
import argparse
import base64
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from fastapi.responses import HTMLResponse, JSONResponse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import scraptiktok
import webapp


def principale():
    with tempfile.TemporaryDirectory() as dossier:
        gestionnaire = webapp.Manager(data_dir=dossier)
        application = webapp.create_app(gestionnaire)
        panne = {"session": False}
        cible = {"id": None}
        appels = []

        @application.get('/cadre-test')
        def cadre():
            url = '/controle?collecte='+cible['id'] if cible['id'] else '/controle'
            return HTMLResponse(f'<iframe src="{url}" width="900" height="850"></iframe>')

        @application.middleware('http')
        async def simuler_panne(requete, suivant):
            appels.append((requete.method, requete.url.path))
            if panne['session'] and requete.url.path == '/api/session':
                return JSONResponse({'detail': 'Session momentanément indisponible.'}, status_code=503)
            return await suivant(requete)

        # Les fixtures de test précèdent la passerelle générale de Streamlit.
        relais = [r for r in application.router.routes if getattr(r, 'path', None) == '/{chemin:path}']
        application.router.routes[:] = [r for r in application.router.routes if r not in relais] + relais
        ecoute = socket.socket()
        ecoute.bind(('127.0.0.1', 0))
        ecoute.listen(128)
        origine = f'http://127.0.0.1:{ecoute.getsockname()[1]}'
        serveur = uvicorn.Server(uvicorn.Config(application, log_level='warning'))
        fil = threading.Thread(target=lambda: serveur.run(sockets=[ecoute]), daemon=True)
        fil.start()
        navigateur = None
        try:
            limite = time.monotonic() + 10
            while not serveur.started:
                assert time.monotonic() < limite, 'Démarrage du serveur impossible'
                time.sleep(.05)
            navigateur = scraptiktok.create_driver(argparse.Namespace(
                headless=True, profile_dir=None, driver=None, chrome_binary=None, timeout=15))
            attente = WebDriverWait(navigateur, 8)
            navigateur.get(origine + '/controle')
            proprietaire = navigateur.get_cookie(webapp.COOKIE)['value']
            collecte = webapp.Job(proprietaire, webapp.StartRequest(
                source_collecte='comptes', comptes=['lemondefr'], variables_txt=['date', 'url']), Path(dossier))
            collecte.update(status='attention', message='Profil en attente de validation',
                frame=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII='))
            gestionnaire.jobs[collecte.id] = collecte
            cible['id'] = collecte.id
            autre = webapp.Job(proprietaire, webapp.StartRequest(hashtag='autre'), Path(dossier))
            autre.update(busy=False,status='completed')
            gestionnaire.jobs[autre.id] = autre
            appels.clear()
            navigateur.get(origine + '/cadre-test')
            navigateur.switch_to.frame(navigateur.find_element(By.TAG_NAME, 'iframe'))
            try:
                attente.until(lambda d: d.find_element(By.ID, 'browser-screen').is_displayed())
            except Exception:
                print('ERREUR_CONTROLE:', navigateur.find_element(By.ID, 'controle-etat').get_attribute('textContent'))
                raise
            assert navigateur.find_element(By.ID, 'continue-button').is_enabled()
            assert not navigateur.find_elements(By.ID, 'search-form')
            assert not navigateur.find_elements(By.ID, 'video-options')
            assert ('GET', '/api/session') not in appels
            assert ('GET', '/api/presse') not in appels
            assert ('POST', '/api/jobs') not in appels
            navigateur.find_element(By.ID, 'continue-button').click()
            attente.until(lambda d: not collecte.commands.empty())
            assert collecte.commands.get_nowait() == 'continue'
            assert autre.commands.empty()
            print('OK : cadre sans formulaire ni lancement ; Continuer vise la collecte indiquée malgré une collecte plus récente')

            gestionnaire.jobs.clear()
            cible['id'] = None
            navigateur.refresh()
            navigateur.switch_to.frame(navigateur.find_element(By.TAG_NAME, 'iframe'))
            attente.until(lambda d: 'Aucune collecte' in d.find_element(By.ID, 'controle-etat').text)
            panne['session'] = True
            navigateur.refresh()
            navigateur.switch_to.frame(navigateur.find_element(By.TAG_NAME, 'iframe'))
            attente.until(lambda d: 'Session momentanément indisponible' in d.find_element(By.ID, 'controle-etat').text)
            print('OK : absence de collecte et erreur de session visibles dans le cadre')
        finally:
            if navigateur is not None:
                navigateur.quit()
            serveur.should_exit = True
            fil.join(timeout=10)


if __name__ == '__main__':
    principale()
