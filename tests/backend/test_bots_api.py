from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Self

import httpx
from fastapi.testclient import TestClient
from openai import APIStatusError

from backend.app.config import get_settings
from backend.app.db.store import get_store
from backend.app.main import create_app


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
    get_settings.cache_clear()
    get_store.cache_clear()

    calls: list[dict[str, object]] = []
    provider_failures: list[int] = []
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

    try:
        with TestClient(create_app()) as client:
            repo_response = client.post("/api/repos", json={"path": str(repo), "name": "Fixture"})
            assert repo_response.status_code == 200, repo_response.text
            repo_id = repo_response.json()["id"]

            bot_response = client.post(
                "/api/bots",
                json={"repo_id": repo_id, "name": "Fixture Bot", "instructions": "Be concise."},
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

            detail = client.get(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}"
            )
            assert detail.status_code == 200
            assert [item["role"] for item in detail.json()["messages"]] == ["user", "assistant"]
            assert test_key not in detail.text

            # Provider diagnostics are actionable but never echo request headers or bodies.
            provider_failures.append(404)
            failed_message = client.post(
                f"/api/bots/{bot['id']}/conversations/{conversation_id}/messages",
                json={"message": "Another question", "mode": "explain", "api_key": test_key},
            )
            assert failed_message.status_code == 400
            assert "model was not found" in failed_message.json()["detail"]
            assert test_key not in failed_message.text

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
