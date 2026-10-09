"""Relais local HTTP/WebSocket : un seul port public et les mêmes sessions privées."""
import asyncio
import base64
import hmac
import os
from urllib.parse import urlsplit

import httpx
from fastapi import Request, WebSocket
from starlette.responses import Response
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

EXCLUS = {"host", "connection", "keep-alive", "transfer-encoding", "upgrade", "content-length", "content-encoding", "proxy-authenticate", "proxy-authorization", "te", "trailer"}


def mot_de_passe_valide(entetes):
    mot_de_passe = os.getenv("APP_ACCESS_PASSWORD", "")
    if not mot_de_passe: return True
    try:
        schema, valeur = entetes.get("authorization", "").split(" ", 1)
        utilisateur, secret = base64.b64decode(valeur, validate=True).decode().split(":", 1)
        return schema.lower() == "basic" and hmac.compare_digest(utilisateur.encode(), os.getenv("APP_ACCESS_USER", "scraptiktok").encode()) and hmac.compare_digest(secret.encode(), mot_de_passe.encode())
    except (ValueError, UnicodeError): return False


def origine_valide(entetes):
    """Le navigateur doit ouvrir le WebSocket depuis le même hôte public."""
    try:
        origine = urlsplit(entetes.get("origin", ""))
        return origine.scheme in {"http", "https"} and origine.netloc.lower() == entetes.get("host", "").lower()
    except ValueError: return False


def installer_passerelle(app):
    def adresse():
        return "127.0.0.1:" + str(int(os.getenv("STREAMLIT_PORT", "8502")))

    @app.api_route("/{chemin:path}", methods=["GET", "HEAD", "POST", "DELETE", "OPTIONS"])
    async def relayer_http(request: Request, chemin: str):
        if os.getenv("UI_STREAMLIT", "0") != "1": return Response(status_code=404)
        entetes = {k:v for k,v in request.headers.items() if k.lower() not in EXCLUS}
        entetes["accept-encoding"] = "identity"
        # La passerelle valide l'origine publique, le serveur privé voit son origine locale.
        if "origin" in entetes:
            if not origine_valide(request.headers): return Response(status_code=403)
            entetes["origin"] = "http://" + adresse()
        corps = bytearray()
        async for morceau in request.stream():
            corps.extend(morceau)
            if len(corps) > 1024**2: return Response("Requête trop volumineuse.", status_code=413)
        url = "http://" + adresse() + "/" + chemin
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                resultat = await client.request(request.method, url, params=request.query_params, headers=entetes, content=bytes(corps))
        except httpx.HTTPError:
            return Response("Interface en cours de démarrage. Actualisez la page.", status_code=503)
        reponse = Response(resultat.content, status_code=resultat.status_code)
        for cle,valeur in resultat.headers.multi_items():
            if cle.lower() not in EXCLUS: reponse.headers.append(cle,valeur)
        return reponse

    app.state.relayer_streamlit = relayer_http

    @app.websocket("/{chemin:path}")
    async def relayer_websocket(navigateur: WebSocket, chemin: str):
        session = navigateur.cookies.get("scraptiktok_session", "")
        if (os.getenv("UI_STREAMLIT", "0") != "1" or not mot_de_passe_valide(navigateur.headers)
                or not origine_valide(navigateur.headers) or len(session) != 64 or any(c not in "0123456789abcdef" for c in session)):
            await navigateur.close(code=1008); return
        entetes = {k:navigateur.headers[k] for k in ("cookie", "authorization", "user-agent") if k in navigateur.headers}
        protocoles = [p.strip() for p in navigateur.headers.get("sec-websocket-protocol", "").split(",") if p.strip()]
        url = "ws://" + adresse() + "/" + chemin
        if navigateur.url.query: url += "?" + navigateur.url.query
        try:
            async with connect(url, additional_headers=entetes, subprotocols=protocoles, origin="http://" + adresse(), max_size=16*1024**2, open_timeout=10, proxy=None) as serveur:
                await navigateur.accept(subprotocol=serveur.subprotocol)
                async def vers_serveur():
                    while True:
                        message = await navigateur.receive()
                        if message["type"] == "websocket.disconnect": return
                        await serveur.send(message.get("bytes") if message.get("bytes") is not None else message["text"])
                async def vers_navigateur():
                    async for message in serveur:
                        if isinstance(message, bytes): await navigateur.send_bytes(message)
                        else: await navigateur.send_text(message)
                taches = [asyncio.create_task(vers_serveur()), asyncio.create_task(vers_navigateur())]
                try:
                    await asyncio.wait(taches, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for tache in taches: tache.cancel()
                    await asyncio.gather(*taches, return_exceptions=True)
        except (ConnectionClosed, InvalidHandshake, WebSocketDisconnect, OSError, TimeoutError):
            pass
        finally:
            try: await navigateur.close()
            except (RuntimeError, WebSocketDisconnect): pass
