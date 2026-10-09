"""Parcours réel Chrome + HTTP + interface, avec pages synthétiques hors TikTok.

Exécution : python tests/smoke_browser.py (Chrome/Chromium doit être installé).
Les fixtures n'existent que dans ce processus de test, jamais dans l'application.
"""
import argparse
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from fastapi.responses import HTMLResponse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select

import scraptiktok as scraper
import webapp as web


TAG = """<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">
<button id="ready" style="position:absolute;left:20px;top:20px;width:220px;height:60px"
onclick="window.ready=true;update()">Autoriser la collecte de test</button>
<input type="range" id="slider" min="0" max="100" value="0" style="position:absolute;left:20px;top:120px;width:300px;height:30px;margin:0" oninput="update()">
<input id="word" style="position:absolute;left:20px;top:200px;width:300px;height:40px" oninput="update()">
<main id="posts" hidden style="position:absolute;top:280px">
<a href="https://www.tiktok.com/@fixture/video/1234567890">Publication de test</a></main>
<script>function update(){document.getElementById('posts').hidden = !(window.ready && Number(document.getElementById('slider').value)>70 && document.getElementById('word').value==='été');}</script>
</body></html>"""
CAPTION = 'Café & découvertes 🍋\nUne escapade en été #tourisme'


def main():
    artifacts = Path(os.getenv("SMOKE_ARTIFACT_DIR", "/tmp/scraptiktok-smoke"))
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        manager = web.Manager(data_dir=folder)
        app = web.create_app(manager)

        @app.get("/fixture/tag")
        def tag():
            return HTMLResponse(TAG)

        @app.get("/fixture/post")
        def post():
            item = {"id": "1234567890", "desc": CAPTION, "createTime":1700000000, "author": {"uniqueId": "fixture"}}
            return HTMLResponse('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">' + json.dumps({"itemInfo": {"itemStruct": item}}) + '</script>')

        # Notre middleware CSP protège l'app. La fixture utilise des événements
        # inline pour tester les gestes et reçoit uniquement ici une CSP adaptée.
        @app.middleware("http")
        async def fixture_policy(request, call_next):
            response = await call_next(request)
            if request.url.path.startswith("/fixture/"):
                response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"
            return response

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline:
                raise AssertionError("Le serveur de test ne démarre pas")
            time.sleep(0.05)

        args = argparse.Namespace(headless=True, profile_dir=None,
                                  driver=Path(os.environ["CHROMEDRIVER"]) if os.getenv("CHROMEDRIVER") else None,
                                  chrome_binary=Path(os.environ["CHROME_BINARY"]) if os.getenv("CHROME_BINARY") else None,
                                  timeout=15)
        firefox = os.getenv("SMOKE_FRONT_BROWSER") == "firefox"
        if firefox:
            options = webdriver.FirefoxOptions()
            options.add_argument("-headless")
            front = webdriver.Firefox(options=options)
        else:
            front = scraper.create_driver(args)
        front.set_script_timeout(15)

        def browser_request(path, body=None, binary=False):
            result = front.execute_async_script("""
                const [path, body, binary, done] = arguments;
                fetch(path, body === null ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-ScrapTikTok':'1'},body:JSON.stringify(body)})
                .then(async r=>done({status:r.status, data: binary ? Array.from(new Uint8Array(await r.arrayBuffer())) : await r.text()}))
                .catch(e=>done({error:String(e)}));
            """, path, body, binary)
            assert "error" not in result, result
            assert result["status"] < 400, result
            return bytes(result["data"]) if binary else result["data"]

        def redirected(browser, url):
            browser.get(origin + ("/fixture/tag" if "/tag/" in url else "/fixture/post"))

        try:
            with patch.object(scraper, "open_page", side_effect=redirected):
                front.set_window_size(1360, 1150)
                front.get(origin)
                WebDriverWait(front, 10).until(lambda d: d.find_element(By.ID, "start-button").is_displayed())
                front.save_screenshot(str(artifacts / "desktop.png"))
                if not firefox:
                    front.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                        "width": 390, "height": 1100, "deviceScaleFactor": 1, "mobile": True})
                    assert front.execute_script("return document.documentElement.scrollWidth <= window.innerWidth"), "Débordement mobile"
                    front.save_screenshot(str(artifacts / "mobile.png"))
                    front.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
                    front.set_window_size(1360, 1150)
                front.find_element(By.ID, "hashtag").send_keys("tourisme")
                front.find_element(By.CSS_SELECTOR,"#periode-options summary").click()
                front.execute_script("document.getElementById('date-debut').value='2023-11-15';document.getElementById('date-fin').value='2023-11-14'")
                front.find_element(By.ID,"start-button").click()
                assert "date de début" in front.find_element(By.ID,"form-error").text
                assert json.loads(browser_request("/api/session"))["job"] is None
                front.execute_script("document.getElementById('date-debut').value='2023-11-14'")
                language = front.find_element(By.ID, "french-only")
                assert language.is_selected()
                language.click()
                assert not language.is_selected()
                language.click()
                second = front.find_element(By.ID, "second-hashtag")
                second.send_keys("été")
                front.find_element(By.ID, "start-button").click()
                dialog = front.find_element(By.ID, "combination-dialog")
                assert dialog.is_displayed()
                assert "#tourisme et #été" in dialog.text
                assert front.find_element(By.CSS_SELECTOR, 'input[value="AND"]').is_selected()
                front.find_element(By.CSS_SELECTOR, 'input[value="OR"]').click()
                assert front.find_element(By.CSS_SELECTOR, 'input[value="OR"]').is_selected()
                front.save_screenshot(str(artifacts / "combination.png"))
                front.find_element(By.ID, "cancel-combination").click()
                assert not dialog.is_displayed()
                assert json.loads(browser_request("/api/session"))["job"] is None
                second.clear()
                limit = front.find_element(By.ID, "limit")
                limit.clear(); limit.send_keys("1")
                front.find_element(By.ID, "start-button").click()
                WebDriverWait(front, 30).until(lambda d: d.find_element(By.ID, "browser-screen").is_displayed())
                session = json.loads(browser_request("/api/session"))
                assert session["job"]["french_only"] is True
                assert session["job"]["filename"].endswith("_fr.txt")
                job_id = session["job"]["id"]
                frame = browser_request(f"/api/jobs/{job_id}/frame", binary=True)
                width, height = struct.unpack(">II", frame[16:24])

                def action(body):
                    browser_request(f"/api/jobs/{job_id}/action", body)
                    time.sleep(0.6)

                def point(x, y):
                    return {"x": x / width, "y": y / height}

                action({"kind": "click", "points": [point(100, 50)]})
                # Passe par les vrais événements de l'interface, pas directement par l'API.
                screen = front.find_element(By.ID, "browser-screen")
                front.execute_script("arguments[0].scrollIntoView({block:'center'})", screen)
                def mouse(x, y, phase=None):
                    rect = front.execute_script("return arguments[0].getBoundingClientRect().toJSON()", screen)
                    chain = ActionChains(front, duration=100)
                    chain.w3c_actions.pointer_action.move_to_location(
                        round(rect['x'] + x * rect['width'] / width),
                        round(rect['y'] + y * rect['height'] / height))
                    if phase == "down":
                        chain.w3c_actions.pointer_action.pointer_down()
                    if phase == "up":
                        chain.w3c_actions.pointer_action.pointer_up()
                    chain.perform()

                def displayed_pixels():
                    return front.execute_script("""
                        const img=arguments[0], c=document.createElement('canvas');
                        c.width=img.naturalWidth; c.height=img.naturalHeight;
                        c.getContext('2d').drawImage(img,0,0); return c.toDataURL();
                    """, screen)

                front.execute_script("""
                    window.gestureTrace=[];
                    for (const name of ['pointerdown','pointermove','pointerup','pointercancel','gotpointercapture','lostpointercapture','blur'])
                      window.addEventListener(name,e=>gestureTrace.push([name,e.target.id, e.clientX,e.clientY,e.buttons]),true);
                """)
                mouse(28, 135, "down")
                time.sleep(1)
                before_move = displayed_pixels()
                mouse(160, 135)
                WebDriverWait(front, 10).until(lambda d: displayed_pixels() != before_move)
                assert not front.find_element(By.ID, "continue-button").is_enabled(), front.execute_script("return {trace:gestureTrace,error:document.getElementById('browser-error').textContent}")
                middle = displayed_pixels()
                mouse(310, 135)
                WebDriverWait(front, 10).until(lambda d: displayed_pixels() != middle)
                mouse(310, 135, "up")
                WebDriverWait(front, 10).until(lambda d: d.find_element(By.ID, "continue-button").is_enabled())

                # Une perte de focus doit relâcher le bouton côté serveur.
                mouse(310, 135, "down")
                front.execute_script("window.dispatchEvent(new Event('blur'))")
                ActionChains(front).reset_actions()
                WebDriverWait(front, 10).until(lambda d: d.find_element(By.ID, "continue-button").is_enabled())
                action({"kind": "click", "points": [point(100, 220)]})
                action({"kind": "text", "text": "été"})
                front.find_element(By.ID, "continue-button").click()
                WebDriverWait(front, 35).until(lambda d: d.find_element(By.ID, "status-badge").text == "Terminé")
                download = front.find_element(By.ID, "download")
                assert download.is_displayed()
                content = browser_request(f"/api/jobs/{job_id}/download")
                assert CAPTION in content, content
                assert "@fixture" in content
                assert front.find_element(By.ID, "count-captions").text == "1"
                assert not front.find_element(By.ID, "browser-panel").is_displayed()
                front.execute_script("window.scrollTo(0,0)")
                front.save_screenshot(str(artifacts / "results.png"))
                print("PASS : filtre français activable, interface, mobile, Chrome serveur, capture, clic, glisser avec image actualisée avant relâchement, annulation, saisie, collecte et téléchargement TXT UTF-8")
                front.refresh()
                WebDriverWait(front,10).until(lambda d: d.find_element(By.ID,"date-debut").get_attribute("value")=="2023-11-14")
                assert front.find_element(By.ID,"date-fin").get_attribute("value")=="2023-11-14"
                front.find_element(By.ID,"effacer-periode").click()
                assert front.find_element(By.ID,"date-debut").get_attribute("value")==""
                assert front.find_element(By.ID,"date-fin").get_attribute("value")==""
                print("PASS : période inclusive, validation, restauration et effacement des dates")
                # Vérifie également la nouvelle collecte par compte, sans service externe.
                Select(front.find_element(By.ID,"source-collecte")).select_by_value("presse")
                WebDriverWait(front,10).until(lambda d: len(d.find_elements(By.CSS_SELECTOR,"#liste-presse input"))>=2)
                assert front.find_element(By.ID,"presse-section").is_displayed()
                Select(front.find_element(By.ID,"source-collecte")).select_by_value("comptes")
                front.find_element(By.ID,"comptes").send_keys("@fixture")
                front.find_element(By.ID,"hashtag").clear()
                assert not front.find_element(By.ID,"hashtag").get_attribute("required")
                record={"id":"1234567890","url":"https://www.tiktok.com/@fixture/video/1234567890","author":"fixture","description":CAPTION,"engagement":{}}
                with patch("collecte.comptes.collecter_compte",return_value=[record["url"]]), patch.object(scraper,"read_post",return_value=record):
                    front.find_element(By.ID,"start-button").click()
                    WebDriverWait(front,25).until(lambda d: d.find_element(By.ID,"download-archive").is_displayed())
                    actuel=json.loads(browser_request("/api/session"))["job"]
                    assert actuel["source_collecte"]=="comptes"
                    archive=browser_request(f"/api/jobs/{actuel['id']}/archive",binary=True)
                    import io,zipfile
                    with zipfile.ZipFile(io.BytesIO(archive)) as contenu:
                        assert "publications.json" in contenu.namelist()
                        assert "corpus_iramuteq.txt" in contenu.namelist()
                    front.save_screenshot(str(artifacts / "presse.png"))
                print("PASS : sélection presse/comptes, hashtag facultatif, archive ZIP privée et corpus IRaMuTeQ")
                print(f"Captures : {artifacts}")
        finally:
            front.quit()
            server.should_exit = True
            thread.join(timeout=30)


if __name__ == "__main__":
    main()
