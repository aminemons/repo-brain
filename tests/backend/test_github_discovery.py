"""GitHub account metadata stays private and does not create bots implicitly."""

import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import create_app
from backend.app.schemas.github import GitHubRepositoriesResponse
from backend.app.services.github import discovery


def test_listing_selects_safe_fields_and_matches_existing_bot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "fixture-github-secret")
    calls: list[list[str]] = []
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert "fixture-github-secret" not in " ".join(command)
        assert kwargs["timeout"] == 20
        if command[-1] == "user":
            body: object = {"login": "owner", "email": "private-fixture-email"}
        else:
            body = [
                {"full_name": "owner/repo", "html_url": "https://fixture-secret@github.com/owner/repo",
                 "description": "private-fixture-description", "private": True, "archived": False,
                 "default_branch": "main", "language": "Python"},
                {"full_name": "other/unselected", "private": True},
                {"full_name": "owner/../../escape"},
            ]
        return subprocess.CompletedProcess(command, 0, json.dumps(body))
    monkeypatch.setattr(discovery.subprocess, "run", run)
    monkeypatch.setattr(discovery, "get_store", lambda: SimpleNamespace(list_repos=lambda: [
        SimpleNamespace(id="registered-repo", git_url="git@github.com:OWNER/REPO.git"),
    ]))
    monkeypatch.setattr(discovery, "BotService", lambda: SimpleNamespace(list_bots=lambda: [
        SimpleNamespace(id="existing-bot", repo_id="registered-repo"),
    ]))
    result = discovery.GitHubDiscoveryService().list_repositories(2, 3)
    assert result.account == "owner" and result.configured
    assert result.next_page == 3
    assert len(result.repositories) == 1
    repo = result.repositories[0]
    assert repo.bot_id == "existing-bot" and repo.repo_id == "registered-repo"
    assert repo.url == "https://github.com/owner/repo" and repo.private
    assert all(secret not in result.model_dump_json() for secret in (
        "fixture-secret", "private-fixture-description", "private-fixture-email",
    ))
    assert "page=2" in calls[1] and "affiliation=owner" in calls[1]


def test_unconfigured_listing_needs_no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    def no_gh(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("gh")
    monkeypatch.setattr(discovery.subprocess, "run", no_gh)
    result = discovery.GitHubDiscoveryService().list_repositories(1, 30)
    assert not result.configured and not result.repositories


@pytest.mark.parametrize("failure", ["exit", "timeout", "json", "shape"])
def test_github_failures_are_sanitized(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "fixture-github-secret")
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 20, stderr="fixture-github-secret")
        return subprocess.CompletedProcess(
            command, 1 if failure == "exit" else 0,
            "fixture-github-secret" if failure == "json" else "[]", "fixture-github-secret",
        )
    monkeypatch.setattr(discovery.subprocess, "run", run)
    with pytest.raises(discovery.GitHubDiscoveryError) as exc:
        discovery.GitHubDiscoveryService().list_repositories(1, 30)
    assert "fixture-github-secret" not in str(exc.value)


def test_github_api_is_owner_only_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEWIKI_AUTH_TOKEN", "owner-fixture-token")
    monkeypatch.setenv("CODEWIKI_VIEWER_TOKEN", "viewer-fixture-token")
    monkeypatch.setenv("CODEWIKI_BOT_DOCUMENTATION_WATCH_ENABLED", "false")
    get_settings.cache_clear()
    calls: list[tuple[int, int]] = []
    def listing(self: discovery.GitHubDiscoveryService, page: int, per_page: int) -> GitHubRepositoriesResponse:
        calls.append((page, per_page))
        return GitHubRepositoriesResponse(configured=True, account="owner")
    monkeypatch.setattr(discovery.GitHubDiscoveryService, "list_repositories", listing)
    try:
        with TestClient(create_app()) as client:
            assert client.get("/api/github/repositories").status_code == 401
            assert client.get("/api/github/repositories", headers={"Authorization": "Bearer viewer-fixture-token"}).status_code == 403
            assert not calls
            headers = {"Authorization": "Bearer owner-fixture-token"}
            assert client.get("/api/github/repositories?per_page=101", headers=headers).status_code == 422
            response = client.get("/api/github/repositories?page=2&per_page=10", headers=headers)
            assert response.status_code == 200 and calls == [(2, 10)]
            assert response.headers["Cache-Control"] == "no-store"
    finally:
        get_settings.cache_clear()
