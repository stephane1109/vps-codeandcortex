"""Parcours Streamlit + FastAPI réel, avec pages TikTok synthétiques locales."""
import argparse
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import urllib.request
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as conditions
import scraptiktok as moteur
import webapp as web
from collecte.presse import charger_inventaire
from smoke_browser import TAG, CAPTION


def principale():
    with tempfile.TemporaryDirectory() as temporaire:
        ecoute=socket.socket(); ecoute.bind(('127.0.0.1',0)); ecoute.listen(128)
        port=ecoute.getsockname()[1]
        libre=socket.socket(); libre.bind(('127.0.0.1',0)); port_streamlit=libre.getsockname()[1]; libre.close()
        origine=f'http://127.0.0.1:{port}'
        environnement={'UI_STREAMLIT':'1','STREAMLIT_PORT':str(port_streamlit),'SCRAPTIKTOK_API_URL':origine,'INSTALL_VIDEO':'1'}
        with patch.dict(os.environ,environnement),patch.object(web,'video_disponible',return_value=True):
            gestionnaire=web.Manager(data_dir=temporaire)
            app=web.create_app(gestionnaire)
            visites_sources=[]
            @app.get('/fixture/tag')
            def page_source(request: Request):
                valide=request.cookies.get('fixture_validee')=='1'
                visites_sources.append(valide)
                if valide:
                    return HTMLResponse('<a href="https://www.tiktok.com/@fixture/video/1234567890">Publication accessible</a>')
                return HTMLResponse(TAG.replace("function update(){", "function update(){if(window.ready && Number(document.getElementById('slider').value)>70 && document.getElementById('word').value==='été')document.cookie='fixture_validee=1; path=/';fetch('/fixture/state?ready='+!!window.ready+'&slider='+document.getElementById('slider').value+'&word='+encodeURIComponent(document.getElementById('word').value));"))
            comptes_presse = {m['compte']:str(2000000000+i) for i,m in enumerate(charger_inventaire())}
            profils_visites = []
            @app.get('/fixture/profil/{compte}')
            def page_profil(compte:str):
                profils_visites.append(compte)
                identifiant = comptes_presse[compte]
                return HTMLResponse(f'<main><a href="https://www.tiktok.com/@{compte}/video/{identifiant}">Publication</a></main>')
            observations={}
            @app.get('/fixture/state')
            def observer(ready:str,slider:str,word:str):
                observations.update(ready=ready,slider=slider,word=word)
                return {"ok":True}
            @app.get('/fixture/post')
            def page_publication(compte:str='fixture', identifiant:str='1234567890'):
                publication={'id':identifiant,'desc':CAPTION+' #été','createTime':1700000000,'author':{'uniqueId':compte}}
                return HTMLResponse('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'+json.dumps({'itemInfo':{'itemStruct':publication}})+'</script>')
            @app.middleware('http')
            async def politique_fixture(requete,suivant):
                reponse=await suivant(requete)
                if requete.url.path.startswith('/fixture/'):
                    reponse.headers['Content-Security-Policy']="default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"
                return reponse
            # Les pages synthétiques précèdent le relais général de Streamlit.
            relais=[route for route in app.router.routes if getattr(route, 'path', None)=='/{chemin:path}']
            app.router.routes[:]=[route for route in app.router.routes if route not in relais]+relais
            serveur=uvicorn.Server(uvicorn.Config(app,log_level='warning'))
            fil=threading.Thread(target=lambda:serveur.run(sockets=[ecoute]),daemon=True); fil.start()
            journal=open(Path(temporaire)/'streamlit.log','w+')
            processus=subprocess.Popen([sys.executable,'-m','streamlit','run','streamlit_app.py','--server.address=127.0.0.1',f'--server.port={port_streamlit}',
                '--server.headless=true','--server.fileWatcherType=none','--browser.gatherUsageStats=false','--client.toolbarMode=minimal'],stdout=journal,stderr=subprocess.STDOUT)
            navigateur=None
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(origine+'/healthz',timeout=1): break
                    except OSError: time.sleep(.2)
                else: raise AssertionError('Interface indisponible')
                arguments=argparse.Namespace(headless=True,profile_dir=None,driver=Path(os.environ['CHROMEDRIVER']) if os.getenv('CHROMEDRIVER') else None,
                    chrome_binary=Path(os.environ['CHROME_BINARY']) if os.getenv('CHROME_BINARY') else None,timeout=20)
                navigateur=moteur.create_driver(arguments); navigateur.set_window_size(1200,1100)
                attente=WebDriverWait(navigateur,30)
                def bouton(texte): return navigateur.find_element(By.XPATH,"//button[normalize-space(.)="+json.dumps(texte,ensure_ascii=False)+"]")
                def onglet(numero): navigateur.find_elements(By.CSS_SELECTOR,'[role="tab"]')[numero].click()
                def requete(chemin,donnees=None,binaire=False):
                    resultat=navigateur.execute_async_script('''const [chemin,donnees,binaire,fin]=arguments; fetch(chemin,donnees===null?{}:{method:'POST',headers:{'Content-Type':'application/json','X-ScrapTikTok':'1'},body:JSON.stringify(donnees)}).then(async r=>fin({code:r.status,contenu:binaire?Array.from(new Uint8Array(await r.arrayBuffer())):await r.text()}));''',chemin,donnees,binaire)
                    assert resultat['code']<400,resultat
                    return bytes(resultat['contenu']) if binaire else resultat['contenu']
                def rediriger(pilote,url):
                    if '/tag/' in url: chemin='/fixture/tag'
                    elif '/video/' in url:
                        identifiant, _, compte = moteur.canonical_post(url)
                        chemin=f'/fixture/post?compte={compte}&identifiant={identifiant}'
                    else: chemin='/fixture/profil/'+url.rsplit('@',1)[1]
                    pilote.get(origine+chemin)
                with patch.object(moteur,'open_page',side_effect=rediriger),patch.object(web,'wait_for_user',wraps=web.wait_for_user) as interventions:
                    navigateur.get(origine+'/interface/')
                    attente.until(lambda d:'Lancer la collecte' in d.find_element(By.TAG_NAME,'body').text)
                    assert navigateur.current_url==origine+'/'
                    onglet(1)
                    attente.until(lambda d:'Comment utiliser l’application' in d.find_element(By.TAG_NAME,'body').text)
                    assert 'SHA-256' not in navigateur.find_element(By.TAG_NAME,'body').text
                    navigateur.save_screenshot('/tmp/scraptiktok-aide.png')
                    onglet(0)
                    assert 'Options vidéo' not in navigateur.find_element(By.TAG_NAME,'body').text
                    navigateur.find_element(By.XPATH,"//label[.//*[normalize-space(.)='Presse et médias']]").click()
                    attente.until(lambda d:'Le Parisien (@leparisien)' in d.find_element(By.TAG_NAME,'body').text)
                    attente.until(lambda d:'20 Minutes (@20minutesfrance)' in d.find_element(By.TAG_NAME,'body').text)
                    navigateur.save_screenshot('/tmp/scraptiktok-presse.png')
                    navigateur.find_element(By.XPATH,"//label[.//*[normalize-space(.)='Hashtags']]").click()
                    attente.until(lambda d:'Hashtag facultatif' not in d.find_element(By.TAG_NAME,'body').text)
                    champ=navigateur.find_element(By.CSS_SELECTOR,'[data-testid="stTextInput"] input'); champ.send_keys('tourisme')
                    navigateur.find_elements(By.CSS_SELECTOR,'[data-testid="stTextInput"] input')[1].send_keys('été')
                    limite=navigateur.find_element(By.CSS_SELECTOR,'[data-testid="stNumberInput"] input')
                    limite.click()
                    modificateur=Keys.COMMAND if sys.platform=='darwin' else Keys.CONTROL
                    ActionChains(navigateur).key_down(modificateur).send_keys('a').key_up(modificateur).send_keys('1',Keys.TAB).perform()
                    attente.until(lambda d:d.find_element(By.CSS_SELECTOR,'[data-testid="stNumberInput"] input').get_attribute('value')=='1')
                    bouton('Lancer la collecte').click()
                    attente.until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'iframe'))>0)
                    etat=json.loads(requete('/api/session'))['job']; identifiant=etat['id']
                    assert etat['limit']==1,etat
                    navigateur.switch_to.frame(navigateur.find_element(By.CSS_SELECTOR,'iframe'))
                    attente.until(lambda d:d.find_element(By.ID,'browser-screen').is_displayed())
                    assert not navigateur.find_element(By.ID,'search-form').is_displayed()
                    # Les clics et le glisser traversent l’iframe de contrôle et le moteur Chrome réel.
                    def action(donnees):
                        requete(f'/api/jobs/{identifiant}/action',donnees); time.sleep(.3)
                    # Les dimensions de la fenêtre source proviennent de l’image réelle.
                    ecran=navigateur.find_element(By.ID,'browser-screen')
                    dimensions=navigateur.execute_script('return [arguments[0].naturalWidth,arguments[0].naturalHeight]',ecran)
                    largeur,hauteur=dimensions
                    action({'kind':'click','points':[{'x':100/largeur,'y':50/hauteur}]})
                    navigateur.execute_script("arguments[0].scrollIntoView({block:'center'})",ecran)
                    def souris(x,y,phase=None):
                        rectangle=navigateur.execute_script('const r=arguments[0].getBoundingClientRect(),f=window.frameElement.getBoundingClientRect(); return {x:r.x+f.x,y:r.y+f.y,width:r.width,height:r.height}',ecran)
                        chaine=ActionChains(navigateur,duration=100)
                        chaine.w3c_actions.pointer_action.move_to_location(round(rectangle['x']+x*rectangle['width']/largeur),round(rectangle['y']+y*rectangle['height']/hauteur))
                        if phase=='down': chaine.w3c_actions.pointer_action.pointer_down()
                        if phase=='up': chaine.w3c_actions.pointer_action.pointer_up()
                        chaine.perform()
                    # Les coordonnées des actions WebDriver sont celles de la fenêtre principale.
                    # Utiliser les événements de pointeur dans l’iframe avec l’offset du cadre.
                    navigateur.execute_script("window.traces=[];for(const nom of ['pointerdown','pointermove','pointerup'])window.addEventListener(nom,e=>traces.push([nom,e.target.id,e.clientX,e.clientY]),true)")
                    souris(28,135,'down'); time.sleep(.8); souris(160,135); time.sleep(.8); souris(310,135); time.sleep(.8); souris(310,135,'up')
                    assert any(e[0]=='pointerdown' and e[1]=='browser-screen' for e in navigateur.execute_script('return traces')), 'Le geste doit atteindre le navigateur intégré'
                    action({'kind':'click','points':[{'x':100/largeur,'y':220/hauteur}]})
                    action({'kind':'text','text':'été'})
                    attente.until(lambda d:d.find_element(By.ID,'continue-button').is_enabled())
                    assert observations.get('ready')=='true' and float(observations.get('slider',0))>70 and observations.get('word')=='été',observations
                    navigateur.find_element(By.ID,'continue-button').click()
                    navigateur.switch_to.default_content()
                    attente.until(lambda d:len(d.find_elements(By.LINK_TEXT,'Télécharger le TXT'))>0)
                    assert visites_sources==[False,True],visites_sources
                    assert interventions.call_count==1,interventions.call_count
                    assert CAPTION in requete(f'/api/jobs/{identifiant}/download')
                    archive=requete(f'/api/jobs/{identifiant}/archive',binaire=True)
                    with zipfile.ZipFile(io.BytesIO(archive)) as z: assert 'publications.json' in z.namelist()
                    # Une seconde collecte parcourt les 29 profils cochés, dans un seul navigateur.
                    navigateur.find_element(By.XPATH,"//label[.//*[normalize-space(.)='Presse et médias']]").click()
                    attente.until(lambda d:'Tout cocher' in d.find_element(By.TAG_NAME,'body').text)
                    bouton('Tout cocher').click()
                    attente.until(lambda d:'29 média(s) sélectionné(s) sur 29' in d.find_element(By.TAG_NAME,'body').text)
                    champs=navigateur.find_elements(By.CSS_SELECTOR,'[data-testid="stTextInput"] input')
                    assert all(champ.get_attribute('value')=='' for champ in champs), 'Les anciens hashtags ne doivent pas filtrer les médias'
                    # Les 29 profils accessibles ne doivent pas demander une validation manuelle.
                    # Seule l’attente entre lectures est accélérée pour ce test local.
                    with patch.object(web,'wait_for_user',side_effect=AssertionError('Arrêt manuel inattendu')) as attente_presse, patch.object(web.Job,'pause',lambda t,secondes:t.check()):
                        bouton('Lancer la collecte').click()
                        attente.until(lambda d:json.loads(requete('/api/session'))['job']['id']!=identifiant)
                        etat=json.loads(requete('/api/session'))['job']; identifiant_presse=etat['id']
                        assert etat['medias']==[m['id'] for m in charger_inventaire()],etat
                        WebDriverWait(navigateur,90).until(lambda d:not json.loads(requete('/api/session'))['job']['busy'])
                        attente_presse.assert_not_called()
                    etat=json.loads(requete('/api/session'))['job']
                    assert etat['captions']==29,etat
                    assert len(etat['bilan_sources'])==29,etat
                    assert profils_visites==list(comptes_presse),profils_visites
                    texte=requete(f'/api/jobs/{identifiant_presse}/download')
                    assert all('@'+compte in texte for compte in comptes_presse),texte
                    attente.until(lambda d:'Médias pris en compte par la collecte : 29' in d.find_element(By.TAG_NAME,'body').text)
                    assert 'Options vidéo' not in navigateur.find_element(By.TAG_NAME,'body').text
                    navigateur.save_screenshot('/tmp/scraptiktok-presse-resultats.png')
                    navigateur.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':390,'height':1000,'deviceScaleFactor':1,'mobile':True})
                    assert navigateur.execute_script('return document.documentElement.scrollWidth<=innerWidth'),'Débordement mobile'
                    print('PASS : Streamlit, liste presse, deux hashtags et une seule validation, session privée, 29 médias sélectionnables, collecte et export des 29 profils sans arrêt manuel, gestes, TXT/ZIP et mobile')
            except Exception:
                if navigateur:
                    navigateur.save_screenshot('/tmp/scraptiktok-streamlit-erreur.png')
                    print(navigateur.find_element(By.TAG_NAME,'body').text[-5000:])
                    print('TACHES', [t.snapshot() for t in gestionnaire.jobs.values()])
                journal.flush(); journal.seek(0); print(journal.read()[-5000:]); raise
            finally:
                if navigateur: navigateur.quit()
                serveur.should_exit=True; fil.join(30)
                processus.terminate()
                try:processus.wait(timeout=10)
                except subprocess.TimeoutExpired:processus.kill();processus.wait()
                journal.close()

if __name__=='__main__': principale()
