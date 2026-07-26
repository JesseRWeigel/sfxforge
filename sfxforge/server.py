"""Local HTTP server for the SFX Forge browser editor."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .engine import build_bank_archive, render_wav_bytes
from .presets import PRESETS, SURFACES

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
MAX_REQUEST_BYTES = 64 * 1024


def _request_values(payload: dict[str, Any]) -> tuple[str, int, int, dict[str, float | str]]:
    kind = str(payload.get("kind", "impact"))
    seed = int(payload.get("seed", 0))
    sample_rate = int(payload.get("sample_rate", 44_100))
    parameters: dict[str, float | str] = {}
    for key in ("duration", "brightness", "resonance", "variation"):
        if key in payload:
            parameters[key] = float(payload[key])
    if "surface" in payload:
        parameters["surface"] = str(payload["surface"])
    return kind, seed, sample_rate, parameters


class SFXRequestHandler(BaseHTTPRequestHandler):
    server_version = "SFXForge/1.0"

    def log_message(self, format_string: str, *args: object) -> None:
        return

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        filename: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("request body size is invalid")
        data = self.rfile.read(content_length)
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/presets":
            self._send_json({"presets": PRESETS, "surfaces": SURFACES})
            return

        relative_path = "index.html" if path == "/" else path.lstrip("/")
        if relative_path not in {"index.html", "app.js", "style.css"}:
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        file_path = WEB_ROOT / relative_path
        try:
            data = file_path.read_bytes()
        except OSError:
            self._send_json({"error": "editor asset is unavailable"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self._send_bytes(data, content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/render", "/api/bank"}:
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            kind, seed, sample_rate, parameters = _request_values(payload)
            if path == "/api/render":
                wav_bytes = render_wav_bytes(kind, seed, sample_rate, parameters)
                self._send_bytes(
                    wav_bytes,
                    "audio/wav",
                    filename=f"{kind}_{seed}.wav",
                )
                return
            count = int(payload.get("count", 16))
            archive = build_bank_archive(
                kind,
                count,
                seed=seed,
                sample_rate=sample_rate,
                parameters=parameters,
            )
            self._send_bytes(
                archive,
                "application/zip",
                filename=f"{kind}_bank.zip",
            )
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create a reusable HTTP server without starting its event loop."""
    return ThreadingHTTPServer((host, port), SFXRequestHandler)
