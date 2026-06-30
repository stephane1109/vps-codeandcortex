from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from gestion_tickets import (
    connecter_redis,
    construire_tableau_de_bord,
    construire_tableau_de_bord_indisponible,
    liberer_ticket,
)


ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
STYLE_FILE = ROOT / "style.css"
AIDE_FILE = ROOT / "aide.md"
STATIC_FILES = {
    "/": (INDEX_FILE, "text/html; charset=utf-8"),
    "/index.html": (INDEX_FILE, "text/html; charset=utf-8"),
    "/style.css": (STYLE_FILE, "text/css; charset=utf-8"),
    "/aide.md": (AIDE_FILE, "text/markdown; charset=utf-8"),
}


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _merge_request_params(handler: BaseHTTPRequestHandler) -> tuple[str, dict[str, str]]:
    parsed = urlparse(handler.path)
    merged = {
        key: values[-1]
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
        if values
    }

    if handler.command != "POST":
        return parsed.path, merged

    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length <= 0:
        return parsed.path, merged

    body = handler.rfile.read(content_length)
    content_type = (handler.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()

    try:
        if content_type == "application/json":
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, dict):
                for key, value in payload.items():
                    if value is not None:
                        merged[str(key)] = str(value)
        elif content_type == "application/x-www-form-urlencoded":
            for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items():
                if values:
                    merged[key] = values[-1]
    except Exception:
        return parsed.path, merged

    return parsed.path, merged


class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self) -> None:  # pragma: no cover - couche HTTP
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # pragma: no cover - couche HTTP
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:  # pragma: no cover - couche HTTP
        self._handle_request(send_body=False)

    def do_GET(self) -> None:  # pragma: no cover - couche HTTP
        self._handle_request(send_body=True)

    def do_POST(self) -> None:  # pragma: no cover - couche HTTP
        self._handle_request(send_body=True)

    def log_message(self, format: str, *args) -> None:  # pragma: no cover - bruit serveur
        return

    def _handle_request(self, send_body: bool) -> None:
        path, params = _merge_request_params(self)

        if path in STATIC_FILES:
            self._serve_static(path, send_body)
            return
        if path == "/api/health":
            self._serve_health(send_body)
            return
        if path == "/api/tickets/dashboard":
            self._serve_dashboard(params, send_body)
            return
        if path == "/api/tickets/release":
            self._serve_release(params, send_body)
            return

        self._send_text(HTTPStatus.NOT_FOUND, "Not Found", send_body)

    def _serve_static(self, path: str, send_body: bool) -> None:
        file_path, media_type = STATIC_FILES[path]
        if not file_path.exists():
            self._send_text(HTTPStatus.NOT_FOUND, "Not Found", send_body)
            return

        payload = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def _serve_health(self, send_body: bool) -> None:
        try:
            connecter_redis()
        except Exception:
            payload = {"status": "degraded"}
        else:
            payload = {"status": "ok"}
        self._send_json(HTTPStatus.OK, payload, send_body)

    def _serve_dashboard(self, params: dict[str, str], send_body: bool) -> None:
        applications = [item.strip() for item in (params.get("applications") or "").split(",") if item.strip()] or None
        try:
            client_redis = connecter_redis()
            payload = construire_tableau_de_bord(client_redis, applications)
        except Exception as exc:
            payload = construire_tableau_de_bord_indisponible(applications, str(exc))
        self._send_json(HTTPStatus.OK, payload, send_body)

    def _serve_release(self, params: dict[str, str], send_body: bool) -> None:
        application_id = (params.get("application_id") or "").strip()
        session_id = (params.get("session_id") or "").strip()
        if not application_id or not session_id:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "message": "application_id et session_id sont requis."},
                send_body,
            )
            return

        try:
            client_redis = connecter_redis()
            liberer_ticket(client_redis, session_id, application_id)
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"status": "error", "message": str(exc)},
                send_body,
            )
            return

        self._send_json(
            HTTPStatus.OK,
            {"status": "released", "application_id": application_id, "session_id": session_id},
            send_body,
        )

    def _send_json(self, status: HTTPStatus, payload: dict, send_body: bool) -> None:
        raw = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if send_body:
            self.wfile.write(raw)

    def _send_text(self, status: HTTPStatus, payload: str, send_body: bool) -> None:
        raw = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if send_body:
            self.wfile.write(raw)


def main() -> None:  # pragma: no cover - point d'entree runtime
    port = int(os.getenv("PORT", "8000") or "8000")
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Dashboard home listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover - point d'entree runtime
    main()
