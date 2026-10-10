"""Démarrer Streamlit et FastAPI sur un unique port public, en local ou sur le VPS."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request


def principale():
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--port", type=int, default=int(os.getenv("PORT", "8501")))
    parseur.add_argument("--host", default="127.0.0.1")
    arguments = parseur.parse_args()
    port_interne = int(os.getenv("STREAMLIT_PORT", str(arguments.port + 1)))
    if not 1 <= arguments.port <= 65535 or not 1 <= port_interne <= 65535 or port_interne == arguments.port:
        parseur.error("Les ports public et interne doivent être valides et distincts.")
    os.environ.update(STREAMLIT_PORT=str(port_interne), SCRAPTIKTOK_API_URL=f"http://127.0.0.1:{arguments.port}")
    racine = Path(__file__).resolve().parent
    commande = [sys.executable, "-m", "streamlit", "run", str(racine / "streamlit_app.py"),
        "--server.address=127.0.0.1", f"--server.port={port_interne}",
        "--server.headless=true", "--browser.gatherUsageStats=false", "--server.fileWatcherType=none",
        "--client.toolbarMode=minimal", "--server.enableCORS=true", "--server.enableXsrfProtection=true"]
    processus = subprocess.Popen(commande, cwd=racine, start_new_session=True)
    try:
        for _ in range(100):
            if processus.poll() is not None: raise RuntimeError("Le serveur Streamlit n’a pas démarré.")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port_interne}/_stcore/health", timeout=1): break
            except OSError: time.sleep(.2)
        else: raise RuntimeError("Le serveur Streamlit ne répond pas.")
        import uvicorn
        uvicorn.run("webapp:app", host=arguments.host, port=arguments.port, workers=1, timeout_graceful_shutdown=30)
    finally:
        if processus.poll() is None:
            os.killpg(processus.pid, signal.SIGTERM)
            try: processus.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(processus.pid, signal.SIGKILL); processus.wait()

if __name__ == "__main__": principale()
