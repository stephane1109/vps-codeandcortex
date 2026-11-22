"""Démarrer une seule instance cohérente de Streamlit et du moteur FastAPI."""
import argparse
import asyncio
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import urllib.request


def verifier_port_interne(port):
    """Refuser un ancien Streamlit au lieu d'accepter son état de santé."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sonde:
        # Un port fermé peut rester en TIME_WAIT après un redémarrage normal.
        sonde.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sonde.bind(('127.0.0.1', port))
        except OSError as erreur:
            raise RuntimeError(f"Le port interne {port} est déjà utilisé. Arrêtez l’ancienne instance de ScrapTikTok avant de relancer.") from erreur


def attendre_streamlit(processus, port, arret):
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        if arret.is_set(): return False
        if processus.poll() is not None:
            raise RuntimeError("Streamlit s’est arrêté pendant le démarrage.")
        try:
            with client.open(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as reponse:
                pret = reponse.status == 200 and reponse.read().strip() == b'ok'
            if pret:
                # Laisser aussi remonter un échec de liaison au port du processus enfant.
                if arret.wait(.2): return False
                if processus.poll() is not None:
                    raise RuntimeError("Le processus Streamlit lancé ne répond pas ; démarrage annulé.")
                return True
        except OSError:
            pass
        arret.wait(.2)
    raise RuntimeError("Le serveur Streamlit ne répond pas.")


async def superviser(serveur, processus, ecoute):
    """Arrêter le moteur si son interface disparaît, sans servir une version orpheline."""
    tache = asyncio.create_task(serveur.serve(sockets=[ecoute]))
    panne = False
    try:
        while not tache.done():
            await asyncio.sleep(.2)
            if processus.poll() is not None:
                panne = True
                serveur.should_exit = True
                break
        await tache
    finally:
        if not tache.done():
            serveur.should_exit = True
            await tache
    if panne:
        raise RuntimeError("Streamlit s’est arrêté. Le moteur a été arrêté pour permettre un redémarrage complet.")


def terminer_streamlit(processus):
    if processus is None or processus.poll() is not None: return
    try:
        os.killpg(processus.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        processus.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try: os.killpg(processus.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        processus.wait()


def principale():
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument('--port', type=int, default=int(os.getenv('PORT', '8501')))
    parseur.add_argument('--host', default='127.0.0.1')
    arguments = parseur.parse_args()
    port_interne = int(os.getenv('STREAMLIT_PORT', str(arguments.port + 1)))
    if not 1 <= arguments.port <= 65535 or not 1 <= port_interne <= 65535 or port_interne == arguments.port:
        parseur.error('Les ports public et interne doivent être valides et distincts.')
    import uvicorn
    configuration = uvicorn.Config('webapp:app', host=arguments.host, port=arguments.port,
                                   workers=1, timeout_graceful_shutdown=30)
    arret = threading.Event()
    # Uvicorn retransmet les signaux reçus en quittant sa boucle. Les intercepter
    # jusqu'à la fermeture de l'enfant évite de laisser un Streamlit orphelin.
    anciens_signaux = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    for s in anciens_signaux: signal.signal(s, lambda *_: arret.set())
    processus = None
    ecoute = None
    try:
        # Réserver le port public avant de lancer un autre processus.
        ecoute = configuration.bind_socket()
        verifier_port_interne(port_interne)
        os.environ.update(STREAMLIT_PORT=str(port_interne), SCRAPTIKTOK_API_URL=f'http://127.0.0.1:{arguments.port}')
        racine = Path(__file__).resolve().parent
        commande = [sys.executable, '-m', 'streamlit', 'run', str(racine / 'streamlit_app.py'),
            '--server.address=127.0.0.1', f'--server.port={port_interne}',
            '--server.headless=true', '--browser.gatherUsageStats=false', '--server.fileWatcherType=none',
            '--client.toolbarMode=minimal', '--server.enableCORS=true', '--server.enableXsrfProtection=true']
        processus = subprocess.Popen(commande, cwd=racine, start_new_session=True)
        print(f"Streamlit lancé : PID {processus.pid}, port interne {port_interne}.", flush=True)
        if attendre_streamlit(processus, port_interne, arret) and not arret.is_set():
            asyncio.run(superviser(uvicorn.Server(configuration), processus, ecoute))
    finally:
        terminer_streamlit(processus)
        if ecoute is not None: ecoute.close()
        for s, gestionnaire in anciens_signaux.items(): signal.signal(s, gestionnaire)


if __name__ == '__main__':
    try: principale()
    except (RuntimeError, OSError) as erreur:
        print(f'Démarrage interrompu : {erreur}', file=sys.stderr)
        sys.exit(1)
