"""Run the real HTTP handler against an in-memory connection."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

from sfxforge.server import SFXRequestHandler


class MemoryConnection:
    def __init__(self, request_bytes: bytes) -> None:
        self.request = io.BytesIO(request_bytes)
        self.response = io.BytesIO()

    def makefile(self, mode: str, buffering: int | None = None) -> io.BytesIO:
        if "r" in mode:
            return self.request
        return self.response

    def sendall(self, data: bytes) -> None:
        self.response.write(data)

    def close(self) -> None:
        return


class MemoryServer:
    server_name = "localhost"
    server_port = 80


@dataclass
class HTTPResult:
    status: int
    headers: dict[str, str]
    body: bytes


def request(path: str, payload: dict[str, object] | None = None) -> HTTPResult:
    if payload is None:
        raw = f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode(
            "ascii"
        )
    else:
        body = json.dumps(payload).encode("utf-8")
        head = (
            f"POST {path} HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        raw = head + body

    connection = MemoryConnection(raw)
    SFXRequestHandler(connection, ("127.0.0.1", 32000), MemoryServer())
    response_bytes = connection.response.getvalue()
    head_bytes, body = response_bytes.split(b"\r\n\r\n", 1)
    lines = head_bytes.decode("iso-8859-1").split("\r\n")
    status = int(lines[0].split(" ", 2)[1])
    headers = {}
    for line in lines[1:]:
        name, value = line.split(":", 1)
        headers[name.lower()] = value.strip()
    return HTTPResult(status, headers, body)
