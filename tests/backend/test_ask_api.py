from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import ask
from backend.app.config import Settings


def test_unconfigured_ask_directs_owner_to_bot_without_provider_request(monkeypatch) -> None:
    monkeypatch.setattr(ask, "get_settings", Settings)
    monkeypatch.setattr(ask, "get_store", lambda: SimpleNamespace(
        get_repo=lambda repo_id: object() if repo_id == "registered" else None,
    ))

    def forbidden_gateway(*args):
        raise AssertionError("Unconfigured Ask must not call a model")

    monkeypatch.setattr(ask, "LLMGateway", forbidden_gateway)
    app = FastAPI()
    app.include_router(ask.router, prefix="/repos")
    with TestClient(app) as client:
        response = client.post("/repos/registered/ask", json={"question": "Explain the code"})
        assert response.status_code == 400
        assert "repository's bot" in response.json()["detail"]
        assert "OpenAI key" in response.json()["detail"]
        missing = client.post("/repos/missing/ask", json={"question": "Explain the code"})
        assert missing.status_code == 404
