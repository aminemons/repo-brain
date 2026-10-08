from __future__ import annotations

import struct
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, Self

import httpx
from fastapi.testclient import TestClient
from openai import APIStatusError

from backend.app.config import get_settings
from backend.app.db.store import get_store
from backend.app.main import create_app
from backend.app.services.bots.service import BotService


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


FIXTURE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    + _png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
    + _png_chunk(b"IEND", b"")
)


def test_bot_first_message_indexes_locally_and_persists_without_key(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "def answer():\n    return 'fixture answer'\n", encoding="utf-8"
    )
    (repo / "README.md").write_text("# Fixture\nThe answer function returns fixture answer.\n", encoding="utf-8")

    monkeypatch.setenv("CODEWIKI_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'bots.sqlite3'}")
    monkeypatch.setenv("CODEWIKI_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CODEWIKI_BOT_DOCUMENTATION_WATCH_ENABLED", "false")
    monkeypatch.setenv("CODEWIKI_AUTH_TOKEN", "")
    monkeypatch.setenv("CODEWIKI_VIEWER_TOKEN", "")
    monkeypatch.setenv("CODEWIKI_NAJM_ENABLED", "true")
    get_settings.cache_clear()
    get_store.cache_clear()

    calls: list[dict[str, object]] = []
    provider_failures: list[int] = []
    index_failures: list[bool] = []
    renderer_results: list[tuple[int, bytes]] = []
    test_key = "sk-proj-BotFixtureTestKey0123456789"

    class StubResponses:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            if provider_failures:
                status_code = provider_failures.pop()
                request = httpx.Request(
                    "POST", "https://api.openai.com/v1/responses", headers={"Authorization": test_key}
                )
                response = httpx.Response(status_code, request=request)
                raise APIStatusError(
                    "provider error", response=response, body={"message": test_key}
                )
            return SimpleNamespace(output_text="`answer` returns the fixture text [S1].")

    class StubOpenAI:
        def __init__(self, *, api_key: str, base_url: str, **_kwargs: object) -> None:
            assert api_key == test_key
            assert base_url == "https://api.openai.com/v1"
            self.responses = StubResponses()

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("backend.app.services.bots.service.AsyncOpenAI", StubOpenAI)
    retrieve_sources = BotService._retrieve_sources

    async def stub_retrieve_sources(self: BotService, repo_id: str, query: str):
        if index_failures:
            index_failures.pop()
            raise RuntimeError("private database detail")
        return await retrieve_sources(self, repo_id, query)

    monkeypatch.setattr(BotService, "_retrieve_sources", stub_retrieve_sources)

    class StubRendererResponse:
        headers: ClassVar[dict[str, str]] = {
            "content-type": "image/png",
            "x-najm-revision": "6e898a51c7e7e2f0992a194891491fd1253c246e",
        }

        def __init__(self, status_code: int, png: bytes) -> None:
            self.status_code = status_code
            self.png = png

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("POST", "http://najm:8080/render")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("renderer unavailable", request=request, response=response)

        async def aiter_bytes(self):
            yield self.png

    class StubRendererClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def stream(self, method: str, url: str, *, json: dict[str, object]) -> StubRendererResponse:
            assert method == "POST" and url == "http://najm:8080/render"
            assert json["version"] == 1
            assert all(set(node) == {"id", "label", "source_ref"} for node in json["nodes"])
            assert all(node["id"].startswith("S") for node in json["nodes"])
            status_code, png = renderer_results.pop(0) if renderer_results else (200, FIXTURE_PNG)
            return StubRendererResponse(status_code, png)

    monkeypatch.setattr("backend.app.services.bots.illustration.httpx.AsyncClient", StubRendererClient)

    try:
        with TestClient(create_app()) as client:
            repo_response = client.post("/api/repos", json={"path": str(repo), "name": "Fixture"})
            assert repo_response.status_code == 200, repo_response.text
            repo_id = repo_response.json()["id"]

            bot_response = client.post(
                "/api/bots",
                json={
                    "repo_id": repo_id,
                    "name": "Fixture Bot",
                    "instructions": "Be concise.",
                    "model": "gpt-5.5",
                },
            )
            assert bot_response.status_code == 201, bot_response.text
            bot = bot_response.json()
            assert bot["model"] == "gpt-5.5"

            duplicate = client.post(
                "/api/bots", json={"repo_id": repo_id, "name": "Duplicate"}
            )
            assert duplicate.status_code == 409

            conversation_response = client.post(
                f"/api/bots/{bot['id']}/conversations", json={"title": "First question"}
            )
            assert conversation_response.status_code == 201, conversation_response.text
            conversation_id = conversation_response.json()["id"]

            # No explicit refresh: the first bot question builds the missing local graph index.
            message_response = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Where is answer defined?", "mode": "explain", "api_key": test_key},
            )
            assert message_response.status_code == 200, message_response.text
            message = message_response.json()
            assert message["role"] == "assistant"
            assert "fixture text" in message["content"]
            assert calls and calls[0]["store"] is False
            assert calls[0]["max_output_tokens"] == 1600

            separate_conversation = client.post(
                f"/api/bots/{bot['id']}/conversations", json={"title": "Separate context"}
            )
            assert separate_conversation.status_code == 201
            separate_id = separate_conversation.json()["id"]
            separate_message = client.post(
                f"/api/bots/{bot['id']}/conversations/{separate_id}/messages",
                json={"message": "Fresh conversation question", "api_key": test_key},
            )
            assert separate_message.status_code == 200
            second_request_input = repr(calls[-1]["input"])
            assert "Where is answer defined?" not in second_request_input
            assert [item["role"] for item in client.get(
                f"/api/bots/{bot['id']}/conversations/{separate_id}"
            ).json()["messages"]] == ["user", "assistant"]

            detail = client.get(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}"
            )
            assert detail.status_code == 200
            assert [item["role"] for item in detail.json()["messages"]] == ["user", "assistant"]
            assert test_key not in detail.text

            index_failures.append(True)
            history_before_index_failure = detail.json()["messages"]
            index_failed_message = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Index failure test", "mode": "explain", "api_key": test_key},
            )
            assert index_failed_message.status_code == 503
            assert "private database detail" not in index_failed_message.text
            assert "Refresh the bot index" in index_failed_message.json()["detail"]
            history_after_index_failure = client.get(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}"
            ).json()["messages"]
            assert len(history_after_index_failure) == len(history_before_index_failure)

            # Provider diagnostics are actionable but never echo request headers or bodies.
            provider_failures.append(404)
            failed_message = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Another question", "mode": "explain", "api_key": test_key},
            )
            assert failed_message.status_code == 400
            assert "model was not found" in failed_message.json()["detail"]
            assert test_key not in failed_message.text
            history_after_provider_failure = client.get(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}"
            ).json()["messages"]
            assert [item["role"] for item in history_after_provider_failure] == ["user", "assistant"]

            # Renderer errors preserve the cited answer and are stored as scoped unavailable metadata.
            renderer_results.append((503, b""))
            offline = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Illustrate this answer", "mode": "illustrate", "api_key": test_key},
            )
            assert offline.status_code == 200, offline.text
            offline_message = offline.json()
            assert "fixture text" in offline_message["content"]
            assert offline_message["illustration"]["status"] == "unavailable"
            assert offline_message["illustration"]["detail"] == "The illustration service is unavailable."

            renderer_results.append((200, b"not a PNG"))
            bad_png = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Try another illustration", "mode": "illustrate", "api_key": test_key},
            )
            assert bad_png.status_code == 200
            assert bad_png.json()["illustration"]["status"] == "unavailable"

            ready = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Make one more evidence map", "mode": "illustrate", "api_key": test_key},
            )
            assert ready.status_code == 200, ready.text
            ready_message = ready.json()
            assert ready_message["illustration"]["status"] == "ready"
            image = client.get(ready_message["illustration"]["url"])
            assert image.status_code == 200
            assert image.headers["content-type"] == "image/png"
            assert image.content == FIXTURE_PNG
            restored_history = client.get(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}"
            ).json()["messages"]
            illustrations = [
                item["illustration"] for item in restored_history if item["illustration"] is not None
            ]
            assert [item["status"] for item in illustrations] == [
                "unavailable", "unavailable", "ready",
            ]

            other_repo = tmp_path / "other-repo"
            other_repo.mkdir()
            (other_repo / "main.py").write_text("def other():\n    return 1\n", encoding="utf-8")
            other_repo_response = client.post(
                "/api/repos", json={"path": str(other_repo), "name": "Other"}
            )
            other_bot = client.post(
                "/api/bots", json={"repo_id": other_repo_response.json()["id"], "name": "Other bot"}
            ).json()
            cross_bot = client.get(
                f"/api/bots/{other_bot['id']}/messages/{ready_message['id']}/illustration"
            )
            assert cross_bot.status_code == 404

            refreshed = client.post(f"/api/bots/{bot['id']}/refresh")
            assert refreshed.status_code == 200, refreshed.text
            assert refreshed.json()["chunk_count"] >= 1

        database_bytes = (tmp_path / "bots.sqlite3").read_bytes()
        assert test_key.encode() not in database_bytes
        assert test_key.encode() not in (tmp_path / "bots.sqlite3-wal").read_bytes()
    finally:
        store = get_store()
        store.close()
        get_store.cache_clear()
        get_settings.cache_clear()


def test_bot_owner_access_and_conversation_isolation(tmp_path: Path, monkeypatch) -> None:
    first_repo = tmp_path / "first-repo"
    second_repo = tmp_path / "second-repo"
    first_repo.mkdir()
    second_repo.mkdir()
    (first_repo / "main.py").write_text("def first():\n    return 1\n", encoding="utf-8")
    (second_repo / "main.py").write_text("def second():\n    return 2\n", encoding="utf-8")
    monkeypatch.setenv("CODEWIKI_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'auth.sqlite3'}")
    monkeypatch.setenv("CODEWIKI_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CODEWIKI_AUTH_TOKEN", "owner-test-token")
    monkeypatch.setenv("CODEWIKI_VIEWER_TOKEN", "viewer-test-token")
    monkeypatch.setenv("CODEWIKI_BOT_DOCUMENTATION_WATCH_ENABLED", "false")
    get_settings.cache_clear()
    get_store.cache_clear()
    owner = {"Authorization": "Bearer owner-test-token"}
    viewer = {"Authorization": "Bearer viewer-test-token"}

    try:
        with TestClient(create_app()) as client:
            denied = client.get("/api/bots")
            assert denied.status_code == 401
            assert denied.json()["detail"] == "API access token required. Enter it in Settings."
            invalid = client.get("/api/bots", headers={"Authorization": "Bearer wrong-token"})
            assert invalid.status_code == 401

            first = client.post("/api/repos", json={"path": str(first_repo)}, headers=owner)
            second = client.post("/api/repos", json={"path": str(second_repo)}, headers=owner)
            assert first.status_code == second.status_code == 200
            first_bot = client.post(
                "/api/bots", json={"repo_id": first.json()["id"], "name": "First"}, headers=owner
            ).json()
            second_bot = client.post(
                "/api/bots", json={"repo_id": second.json()["id"], "name": "Second"}, headers=owner
            ).json()
            conversation = client.post(
                f"/api/bots/{first_bot['id']}/conversations", json={"title": "Private"}, headers=owner
            )
            assert conversation.status_code == 201
            conversation_id = conversation.json()["id"]

            assert client.get(f"/api/bots/{first_bot['id']}", headers=viewer).status_code == 200
            assert client.post(
                f"/api/bots/{first_bot['id']}/conversations",
                json={"title": "Viewer cannot write"}, headers=viewer,
            ).status_code == 403
            cross_bot_history = client.get(
                f"/api/bots/{second_bot['id']}/conversations/{conversation_id}", headers=owner
            )
            assert cross_bot_history.status_code == 404
            cross_bot_message = client.post(
                f"/api/bots/{second_bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "must not send", "api_key": "sk-test-private"}, headers=owner,
            )
            assert cross_bot_message.status_code == 404
            assert "sk-test-private" not in cross_bot_message.text
    finally:
        store = get_store()
        store.close()
        get_store.cache_clear()
        get_settings.cache_clear()
