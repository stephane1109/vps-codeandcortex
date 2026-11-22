"""Vrais processus : collision de ports, arrêt SIGTERM et perte de Streamlit."""
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

RACINE = Path(__file__).resolve().parents[1]


def port_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def verifier_ferme(port):
    with socket.socket() as s:
        assert s.connect_ex(('127.0.0.1', port)) != 0, f'Port {port} toujours ouvert'
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))


def principale():
    port, interne = port_libre(), port_libre()
    while interne == port: interne = port_libre()
    environnement = {**os.environ, 'STREAMLIT_PORT': str(interne), 'APP_TICKET_ENFORCED': '0'}
    commande = [sys.executable, str(RACINE / 'lancer_interface.py'), '--port', str(port)]
    with socket.socket() as occupe:
        occupe.bind(('127.0.0.1', interne)); occupe.listen()
        essai = subprocess.run(commande, cwd=RACINE, env=environnement, capture_output=True, timeout=15)
        assert essai.returncode != 0 and 'déjà utilisé' in essai.stderr.decode(), essai
    verifier_ferme(port)
    print('OK : aucun lancement sur un ancien Streamlit', flush=True)
    for panne in (False, True):
        with tempfile.TemporaryFile(mode='w+') as journal:
            processus = subprocess.Popen(commande, cwd=RACINE, env=environnement, stdout=journal, stderr=subprocess.STDOUT)
            enfant = None
            try:
                for _ in range(100):
                    assert processus.poll() is None, 'Le lanceur a quitté prématurément'
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=.5) as r:
                            if r.status == 200: break
                    except (OSError, urllib.error.HTTPError): pass
                    time.sleep(.1)
                else: raise AssertionError('Le service ne démarre pas')
                journal.seek(0); trace = journal.read()
                enfant = int(re.search(r'Streamlit lancé : PID (\d+)', trace).group(1))
                if not panne:
                    doublon = subprocess.run(commande, cwd=RACINE, env=environnement, capture_output=True, timeout=10)
                    assert doublon.returncode != 0
                    assert 'Streamlit lancé' not in doublon.stdout.decode()
                    processus.send_signal(signal.SIGTERM)
                else:
                    os.kill(enfant, signal.SIGTERM)
                code = processus.wait(timeout=40)
                assert code != 0 if panne else code == 0, code
                verifier_ferme(port); verifier_ferme(interne)
                print('OK : perte de Streamlit arrête le moteur' if panne else 'OK : doublon refusé et SIGTERM ferme les deux ports', flush=True)
            except Exception:
                journal.seek(0); print(journal.read()); raise
            finally:
                if processus.poll() is None:
                    processus.terminate()
                    try: processus.wait(timeout=15)
                    except subprocess.TimeoutExpired: processus.kill(); processus.wait()
                if enfant:
                    try: os.kill(enfant, signal.SIGTERM)
                    except ProcessLookupError: pass


if __name__ == '__main__': principale()
