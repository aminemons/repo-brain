"""Bounded, evidence-linked Najm rendering for bot answers."""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from pathlib import Path
from typing import Any

import httpx

from backend.app.config import Settings
from backend.app.schemas.bots import BotSource
from backend.app.services.graph.models import CodeGraphEdge, CodeGraphNode

MAX_NODES = 6
MAX_EDGES = 12
MAX_PNG_BYTES = 8 * 1024 * 1024
TEMPLATE_VERSION = "evidence-map-v1"
PINNED_NAJM_REVISION = "6e898a51c7e7e2f0992a194891491fd1253c246e"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IllustrationUnavailable(RuntimeError):
    """Renderer is unavailable or returned an invalid image."""


def _label(value: str, limit: int) -> str:
    clean = " ".join(value.replace("\x00", "").split())
    return clean[:limit] or "Repository evidence"


def build_evidence_map(
    title: str,
    sources: list[BotSource],
    nodes: list[CodeGraphNode],
    edges: list[CodeGraphEdge],
) -> tuple[dict[str, Any], list[str]]:
    """Create a small evidence map; relationships must exist in the verified code graph."""
    payload_nodes: list[dict[str, str]] = []
    evidence_ids: list[str] = []
    evidence_node_ids: dict[str, set[str]] = {}
    for source in sources:
        source_id = source.id
        if len(payload_nodes) >= MAX_NODES:
            break
        label = source.path
        matched: list[CodeGraphNode] = []
        if source.type == "code":
            matched = [
                node for node in nodes
                if node.file_path == source.path
                and (node.start_line or 1) <= source.end_line
                and (node.end_line or node.start_line or 1) >= source.start_line
                and node.type not in {"repository", "directory", "file", "module"}
            ]
            matched.sort(key=lambda node: (node.start_line or 1, node.name, node.id))
            if matched:
                label = f"{matched[0].name} · {source.path}"
        item_id = source_id
        source_ref = f"[{source_id}] {source.path}:{source.start_line}-{source.end_line}"
        payload_nodes.append({
            "id": item_id,
            "label": _label(label, 80),
            "source_ref": _label(source_ref, 160),
        })
        evidence_ids.append(source_id)
        evidence_node_ids[item_id] = {node.id for node in matched}

    payload_edges: list[dict[str, str]] = []
    # Keep only direct, non-inferred static relationships whose endpoints both map to
    # retrieved code evidence. No source order or runtime sequence is inferred here.
    eligible = {"calls", "references", "routes_to"}
    for source_id, source_nodes in evidence_node_ids.items():
        for target_id, target_nodes in evidence_node_ids.items():
            if source_id == target_id:
                continue
            matching_edges = [
                edge for edge in edges
                if edge.source_id in source_nodes and edge.target_id in target_nodes
                and edge.type in eligible and not edge.is_inferred
            ]
            if not matching_edges:
                continue
            edge = min(matching_edges, key=lambda item: (item.type, item.id))
            payload_edges.append({
                "source": source_id,
                "target": target_id,
                "label": _label(edge.type.replace("_", " "), 80),
            })
            if len(payload_edges) >= MAX_EDGES:
                break
        if len(payload_edges) >= MAX_EDGES:
            break

    return (
        {"version": 1, "title": _label(title, 120), "nodes": payload_nodes, "edges": payload_edges},
        evidence_ids,
    )


class NajmIllustrationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def render(
        self,
        *,
        repo_id: str,
        bot_id: str,
        message_id: str,
        repo_commit: str | None,
        plan: dict[str, Any],
        evidence_ids: list[str],
    ) -> dict[str, str | None]:
        if not self.settings.najm_enabled:
            raise IllustrationUnavailable("disabled")
        endpoint = self.settings.najm_endpoint.rstrip("/") + "/render"
        try:
            async with (
                httpx.AsyncClient(timeout=self.settings.najm_timeout_seconds) as client,
                client.stream("POST", endpoint, json=plan) as response,
            ):
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if content_type != "image/png":
                        raise IllustrationUnavailable("invalid_image")
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > MAX_PNG_BYTES:
                        raise IllustrationUnavailable("oversized_image")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_PNG_BYTES:
                            raise IllustrationUnavailable("oversized_image")
                        chunks.append(chunk)
                    png = b"".join(chunks)
                    _validate_png(png)
                    revision = response.headers.get("x-najm-revision", "")
                    if revision != PINNED_NAJM_REVISION:
                        raise IllustrationUnavailable("renderer_unavailable")
        except IllustrationUnavailable:
            raise
        except (httpx.HTTPError, ValueError, OSError):
            raise IllustrationUnavailable("renderer_unavailable") from None

        directory = self._directory(repo_id, bot_id, message_id)
        directory.mkdir(parents=True, exist_ok=True)
        image_path = directory / "image.png"
        manifest_path = directory / "manifest.json"
        digest = hashlib.sha256(png).hexdigest()
        manifest = {
            "version": 1,
            "status": "ready",
            "repo_id": repo_id,
            "bot_id": bot_id,
            "message_id": message_id,
            "repo_commit": repo_commit,
            "najm_revision": revision,
            "template_version": TEMPLATE_VERSION,
            "digest_sha256": digest,
            "evidence_ids": evidence_ids,
            "caption": "Evidence map from retrieved repository sources.",
            "alt_text": _alt_text(plan),
        }
        _atomic_write(image_path, png)
        _atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
        return {
            "status": "ready",
            "url": f"/api/bots/{bot_id}/messages/{message_id}/illustration",
            "caption": manifest["caption"],
            "alt_text": manifest["alt_text"],
            "detail": None,
        }

    def read(self, repo_id: str, bot_id: str, message_id: str) -> bytes:
        directory = self._directory(repo_id, bot_id, message_id)
        manifest_path = directory / "manifest.json"
        image_path = directory / "image.png"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if any(manifest.get(key) != value for key, value in {
                "repo_id": repo_id, "bot_id": bot_id, "message_id": message_id,
            }.items()):
                raise ValueError("manifest scope mismatch")
            png = image_path.read_bytes()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raise ValueError("Illustration not found") from None
        try:
            _validate_png(png)
        except IllustrationUnavailable:
            raise ValueError("Illustration not found") from None
        if manifest.get("digest_sha256") != hashlib.sha256(png).hexdigest():
            raise ValueError("Illustration not found")
        return png

    def metadata(self, repo_id: str, bot_id: str, message_id: str) -> dict[str, str | None] | None:
        directory = self._directory(repo_id, bot_id, message_id)
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            if any(manifest.get(key) != value for key, value in {
                "repo_id": repo_id, "bot_id": bot_id, "message_id": message_id,
            }.items()):
                return None
            status = manifest.get("status", "ready")
            if status == "ready":
                self.read(repo_id, bot_id, message_id)
            elif status != "unavailable":
                return None
            return {
                "status": status,
                "url": f"/api/bots/{bot_id}/messages/{message_id}/illustration" if status == "ready" else None,
                "caption": str(manifest.get("caption") or "Evidence map from retrieved repository sources."),
                "alt_text": str(manifest.get("alt_text") or "Repository evidence map."),
                "detail": (
                    manifest.get("detail") if isinstance(manifest.get("detail"), str) else None
                ),
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError, IllustrationUnavailable):
            return None

    def record_unavailable(
        self, repo_id: str, bot_id: str, message_id: str, reason: str,
    ) -> dict[str, str | None]:
        directory = self._directory(repo_id, bot_id, message_id)
        directory.mkdir(parents=True, exist_ok=True)
        details = {
            "disabled": "Illustrations are disabled on this server.",
            "invalid_image": "The illustration service returned an invalid image.",
            "oversized_image": "The illustration service returned an image that was too large.",
            "renderer_unavailable": "The illustration service is unavailable.",
            "insufficient_evidence": "There is not enough repository evidence to illustrate this answer.",
        }
        detail = details.get(reason, "The illustration could not be created.")
        manifest = {
            "version": 1, "status": "unavailable", "repo_id": repo_id,
            "bot_id": bot_id, "message_id": message_id,
            "caption": "Illustration unavailable.", "alt_text": "No illustration is available.",
            "detail": detail,
        }
        _atomic_write(directory / "manifest.json", json.dumps(manifest).encode("utf-8"))
        return {
            "status": "unavailable", "url": None,
            "caption": "Illustration unavailable.",
            "alt_text": "No illustration is available.", "detail": detail,
        }

    def _directory(self, repo_id: str, bot_id: str, message_id: str) -> Path:
        # IDs are validated as opaque path components and resolved under managed storage.
        for value in (repo_id, bot_id, message_id):
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
                raise ValueError("Illustration not found")
        root = (self.settings.storage_dir / "bot_illustrations").expanduser().resolve()
        directory = (root / repo_id / bot_id / message_id).resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Illustration not found")
        return directory


def _validate_png(png: bytes) -> None:
    if len(png) < 45 or len(png) > MAX_PNG_BYTES or not png.startswith(PNG_SIGNATURE):
        raise IllustrationUnavailable("invalid_image")
    offset = len(PNG_SIGNATURE)
    seen_header = seen_data = seen_end = False
    width = height = 0
    while offset + 12 <= len(png):
        length = int.from_bytes(png[offset:offset + 4], "big")
        kind = png[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if length > MAX_PNG_BYTES or chunk_end > len(png):
            raise IllustrationUnavailable("invalid_image")
        data = png[offset + 8:offset + 8 + length]
        crc = int.from_bytes(png[offset + 8 + length:chunk_end], "big")
        if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise IllustrationUnavailable("invalid_image")
        if not seen_header:
            if kind != b"IHDR" or length != 13:
                raise IllustrationUnavailable("invalid_image")
            width = int.from_bytes(data[:4], "big")
            height = int.from_bytes(data[4:8], "big")
            seen_header = True
        elif kind == b"IDAT":
            seen_data = True
        elif kind == b"IEND":
            if length != 0 or chunk_end != len(png):
                raise IllustrationUnavailable("invalid_image")
            seen_end = True
            break
        offset = chunk_end
    if (
        not seen_header or not seen_data or not seen_end or not width or not height
        or width > 12000 or height > 12000 or width * height > 40_000_000
    ):
        raise IllustrationUnavailable("invalid_image")


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _alt_text(plan: dict[str, Any]) -> str:
    labels = [node["label"] for node in plan.get("nodes", [])]
    if not labels:
        return "Evidence map with no repository nodes."
    return "Evidence map showing: " + "; ".join(labels)[:500]
