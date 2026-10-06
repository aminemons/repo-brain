"""Small HTTP boundary for the pinned, fixed-template Najm renderer."""

from __future__ import annotations

import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = "0.0.0.0"
PORT = 8080
MAX_REQUEST_BYTES = 32 * 1024
MAX_PNG_BYTES = 8 * 1024 * 1024
RENDER_TIMEOUT_SECONDS = 30
RENDERER_DLL = "/app/dotnet/NajmRenderer.dll"
NAJM_REVISION = "6e898a51c7e7e2f0992a194891491fd1253c246e"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ID_PATTERN = re.compile(r"S[1-6]\Z")


class RequestError(ValueError):
    """The request does not match the documented graph payload."""


class RenderError(RuntimeError):
    """The renderer failed or returned an invalid image."""


class RenderTimeout(RenderError):
    """The renderer exceeded its per-request deadline."""


def validate_payload(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {"version", "title", "nodes", "edges"}:
        raise RequestError("expected version, title, nodes, and edges")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise RequestError("version must be 1")
    if not isinstance(payload["title"], str) or not 1 <= len(payload["title"]) <= 120:
        raise RequestError("title must contain 1–120 characters")

    nodes = payload["nodes"]
    edges = payload["edges"]
    if not isinstance(nodes, list) or len(nodes) > 6:
        raise RequestError("nodes must be an array containing at most 6 items")
    if not isinstance(edges, list) or len(edges) > 12:
        raise RequestError("edges must be an array containing at most 12 items")

    ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"id", "label", "source_ref"}:
            raise RequestError("each node requires id, label, and source_ref")
        node_id = node["id"]
        if not isinstance(node_id, str) or not _ID_PATTERN.fullmatch(node_id) or node_id in ids:
            raise RequestError("node IDs must be unique values from S1 through S6")
        if not isinstance(node["label"], str) or len(node["label"]) > 80:
            raise RequestError("node labels are limited to 80 characters")
        if not isinstance(node["source_ref"], str) or len(node["source_ref"]) > 160:
            raise RequestError("source_ref values are limited to 160 characters")
        ids.add(node_id)

    for edge in edges:
        if not isinstance(edge, dict) or set(edge) != {"source", "target", "label"}:
            raise RequestError("each edge requires source, target, and label")
        if (
            not isinstance(edge["source"], str)
            or not isinstance(edge["target"], str)
            or edge["source"] not in ids
            or edge["target"] not in ids
        ):
            raise RequestError("edge endpoints must reference submitted node IDs")
        if not isinstance(edge["label"], str) or len(edge["label"]) > 80:
            raise RequestError("edge labels are limited to 80 characters")


def render_png(
    payload: dict[str, Any],
    runner: Any = subprocess.run,
) -> bytes:
    validate_payload(payload)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise RequestError("request body exceeds 32 KiB")

    try:
        result = runner(
            ["dotnet", RENDERER_DLL],
            input=encoded,
            capture_output=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderTimeout("renderer exceeded 30 seconds") from exc
    except OSError as exc:
        raise RenderError("renderer process could not start") from exc

    if result.returncode != 0:
        raise RenderError("renderer could not draw this graph")
    image = result.stdout
    if not isinstance(image, bytes) or image[:8] != PNG_SIGNATURE:
        raise RenderError("renderer returned data without a PNG signature")
    if len(image) > MAX_PNG_BYTES:
        raise RenderError("renderer output exceeds 8 MiB")
    return image


class Handler(BaseHTTPRequestHandler):
    server_version = "RepoBrainNajm/1"
    render_slot = threading.BoundedSemaphore(1)

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Najm-Revision", NAJM_REVISION)
        body = json.dumps({"status": "ok", "najm_revision": NAJM_REVISION}).encode("ascii")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/render":
            self.send_error(404)
            return
        content_length = self.headers.get("Content-Length")
        if content_length is None or not content_length.isdecimal() or len(content_length) > 8:
            self.send_error(411)
            return
        size = int(content_length)
        if size > MAX_REQUEST_BYTES:
            self.send_error(413, "request body exceeds 32 KiB")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "Content-Type must be application/json")
            return
        if not self.render_slot.acquire(blocking=False):
            self.send_error(503, "renderer is busy")
            return

        try:
            body = self.rfile.read(size)
            if len(body) != size:
                self.send_error(400, "incomplete request body")
                return
            try:
                payload = json.loads(body)
                image = render_png(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, RequestError) as exc:
                self.send_error(400, str(exc))
                return
            except RenderTimeout as exc:
                self.send_error(504, str(exc))
                return
            except RenderError as exc:
                self.send_error(500, str(exc))
                return

            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(image)))
            self.send_header("X-Najm-Revision", NAJM_REVISION)
            self.end_headers()
            self.wfile.write(image)
        finally:
            self.render_slot.release()

    def log_message(self, format: str, *args: Any) -> None:
        print("renderer: " + format % args, flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
