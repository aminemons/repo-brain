from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any, ClassVar, Self

import pytest

from backend.app.config import Settings
from backend.app.schemas.bots import BotSource
from backend.app.services.bots.illustration import (
    IllustrationUnavailable,
    NajmIllustrationService,
    build_evidence_map,
)
from backend.app.services.graph.models import CodeGraphEdge, CodeGraphNode


def _chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    + _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
    + _chunk(b"IEND", b"")
)


def test_evidence_map_uses_only_verified_graph_edges_and_enforces_renderer_limits() -> None:
    sources = [
        BotSource(
            id=f"S{i}", type="code", path=f"src/{i}.py", start_line=1, end_line=4,
            snippet="pass",
        )
        for i in range(1, 9)
    ]
    nodes = [
        CodeGraphNode(id=f"node-{i}", repo_id="repo", type="function", name=f"func{i}",
                      file_path=f"src/{i}.py", start_line=1, end_line=4)
        for i in range(1, 9)
    ]
    edges = [
        CodeGraphEdge(id="verified", repo_id="repo", source_id="node-1", target_id="node-2",
                      type="calls", is_inferred=False),
        CodeGraphEdge(id="inferred", repo_id="repo", source_id="node-2", target_id="node-3",
                      type="calls", is_inferred=True),
    ]

    plan, evidence_ids = build_evidence_map("q" * 200, sources, nodes, edges)

    assert len(plan["title"]) == 120
    assert len(plan["nodes"]) == 6
    assert len(plan["edges"]) == 1
    assert plan["edges"][0] == {"source": "S1", "target": "S2", "label": "calls"}
    assert evidence_ids == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert all(len(node["label"]) <= 80 and len(node["source_ref"]) <= 160 for node in plan["nodes"])


class _Response:
    headers: ClassVar[dict[str, str]] = {
        "content-type": "image/png",
        "x-najm-revision": "6e898a51c7e7e2f0992a194891491fd1253c246e",
    }

    def __init__(self, png: bytes) -> None:
        self.png = png

    def raise_for_status(self) -> None:
        return None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def aiter_bytes(self):
        yield self.png


class _Client:
    def __init__(self, png: bytes) -> None:
        self.png = png

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def stream(self, method: str, url: str, *, json: dict[str, Any]) -> _Response:
        assert method == "POST"
        assert url == "http://najm:8080/render"
        assert json["version"] == 1
        assert all(node["id"].startswith("S") for node in json["nodes"])
        assert all(set(node) == {"id", "label", "source_ref"} for node in json["nodes"])
        assert all(set(edge) == {"source", "target", "label"} for edge in json["edges"])
        return _Response(self.png)


@pytest.mark.asyncio
async def test_renderer_persists_scoped_png_and_manifest(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(storage_dir=tmp_path, najm_enabled=True)
    monkeypatch.setattr(
        "backend.app.services.bots.illustration.httpx.AsyncClient",
        lambda **_kwargs: _Client(PNG),
    )
    service = NajmIllustrationService(settings)
    plan = {"version": 1, "title": "Question", "nodes": [], "edges": []}

    illustration = await service.render(
        repo_id="repo", bot_id="bot", message_id="msg", repo_commit="abc123",
        plan=plan, evidence_ids=["S1"],
    )

    assert illustration["status"] == "ready"
    assert service.read("repo", "bot", "msg") == PNG
    assert service.metadata("repo", "bot", "msg")["status"] == "ready"
    assert service.metadata("other-repo", "bot", "msg") is None
    manifest_path = tmp_path / "bot_illustrations" / "repo" / "bot" / "msg" / "manifest.json"
    manifest = manifest_path.read_text(encoding="utf-8")
    assert '"repo_commit": "abc123"' in manifest
    assert '"najm_revision": "6e898a51c7e7e2f0992a194891491fd1253c246e"' in manifest
    assert '"evidence_ids": ["S1"]' in manifest


@pytest.mark.asyncio
async def test_renderer_rejects_bad_png(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(storage_dir=tmp_path, najm_enabled=True)
    monkeypatch.setattr(
        "backend.app.services.bots.illustration.httpx.AsyncClient",
        lambda **_kwargs: _Client(b"\x89PNG\r\n\x1a\nnot-a-png"),
    )
    service = NajmIllustrationService(settings)

    with pytest.raises(IllustrationUnavailable, match="invalid_image"):
        await service.render(
            repo_id="repo", bot_id="bot", message_id="msg", repo_commit=None,
            plan={"version": 1, "title": "q", "nodes": [], "edges": []}, evidence_ids=[],
        )


@pytest.mark.asyncio
async def test_renderer_rejects_unreviewed_revision(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(storage_dir=tmp_path, najm_enabled=True)
    monkeypatch.setattr(
        "backend.app.services.bots.illustration.httpx.AsyncClient",
        lambda **_kwargs: _Client(PNG),
    )
    monkeypatch.setattr(
        _Response, "headers", {
            "content-type": "image/png", "x-najm-revision": "0" * 40,
        },
    )

    with pytest.raises(IllustrationUnavailable, match="renderer_unavailable"):
        await NajmIllustrationService(settings).render(
            repo_id="repo", bot_id="bot", message_id="msg", repo_commit=None,
            plan={"version": 1, "title": "q", "nodes": [], "edges": []}, evidence_ids=[],
        )

