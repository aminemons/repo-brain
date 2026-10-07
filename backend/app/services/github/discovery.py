"""List account repositories through the server's existing GitHub connection."""

import json
import os
import re
import subprocess
from typing import Any

from backend.app.database import get_store
from backend.app.schemas.github import GitHubRepositoriesResponse, GitHubRepository
from backend.app.services.bots import BotService
from backend.app.services.repo_scanner.scanner import normalize_git_url, public_git_url

_LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}")


class GitHubDiscoveryError(RuntimeError):
    """A sanitized error suitable for the owner interface."""


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"GH_HOST": "github.com", "GH_PROMPT_DISABLED": "1", "GH_PAGER": "cat"})
    return env


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *arguments], capture_output=True, text=True, timeout=20, check=False,
        env=_environment(), stdin=subprocess.DEVNULL,
    )


def _json(arguments: list[str]) -> Any:
    try:
        result = _run(["api", "--hostname", "github.com", *arguments])
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        raise GitHubDiscoveryError(
            "GitHub could not be reached. Check the server connection and retry."
        ) from None
    if result.returncode:
        raise GitHubDiscoveryError(
            "GitHub could not list repositories. Check GH_TOKEN and its repository access on the server."
        ) from None
    if len(result.stdout) > 2_000_000:
        raise GitHubDiscoveryError("GitHub returned too much data. Use a smaller page and retry.")
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        raise GitHubDiscoveryError("GitHub returned an invalid response. Retry later.") from None


def _configured() -> bool:
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return True
    try:
        return _run(["auth", "status", "--hostname", "github.com"]).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _repository(item: Any, account: str) -> GitHubRepository | None:
    if not isinstance(item, dict):
        return None
    slug = item.get("full_name")
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        return None
    owner, name = slug.split("/", 1)
    if owner.casefold() != account.casefold() or name in {".", ".."}:
        return None
    branch = item.get("default_branch")
    language = item.get("language")
    return GitHubRepository(
        full_name=slug, name=name, url=f"https://github.com/{slug}",
        private=item.get("private") is True, archived=item.get("archived") is True,
        default_branch=branch[:255] if isinstance(branch, str) else "",
        language=language[:80] if isinstance(language, str) else None,
    )


class GitHubDiscoveryService:
    def list_repositories(self, page: int, per_page: int) -> GitHubRepositoriesResponse:
        if not _configured():
            return GitHubRepositoriesResponse(configured=False)
        account_data = _json(["user"])
        login = account_data.get("login") if isinstance(account_data, dict) else None
        if not isinstance(login, str) or not _LOGIN.fullmatch(login):
            raise GitHubDiscoveryError("GitHub returned an invalid account. Check the server connection.")
        data = _json([
            "--method", "GET", "user/repos", "-f", "affiliation=owner", "-f", "sort=updated",
            "-f", "direction=desc", "-F", f"page={page}", "-F", f"per_page={per_page}",
        ])
        if not isinstance(data, list) or len(data) > per_page:
            raise GitHubDiscoveryError("GitHub returned an invalid repository list. Retry later.")
        repositories = [repo for item in data if (repo := _repository(item, login)) is not None]
        store = get_store()
        registered: dict[str, str] = {}
        for existing in store.list_repos():
            if not existing.git_url:
                continue
            try:
                registered[normalize_git_url(public_git_url(existing.git_url) or "")] = existing.id
            except ValueError:
                continue
        bots = {bot.repo_id: bot.id for bot in BotService().list_bots()}
        for repo in repositories:
            repo.repo_id = registered.get(normalize_git_url(repo.url))
            repo.bot_id = bots.get(repo.repo_id) if repo.repo_id else None
        return GitHubRepositoriesResponse(
            configured=True, account=login, repositories=repositories,
            next_page=page + 1 if len(data) == per_page and page < 1000 else None,
        )
