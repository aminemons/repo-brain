"""Periodic local HEAD checks and safe fast-forward for app-managed GitHub clones."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import Settings, get_settings
from backend.app.database import get_store
from backend.app.services.async_tasks import repo_write_lock, run_blocking
from backend.app.services.bot_changes.service import (
    BotChangeService,
    _bot_repo,
    _git_prefix,
    _run_git,
    _valid_github_remote,
)
from backend.app.services.bots.models import BotRecord
from backend.app.services.bots.service import BotService
from backend.app.services.repo_metadata import read_repo_metadata
from backend.app.services.repo_scanner import clone_path_for_git_url

logger = logging.getLogger("project_brain.bot_changes.watcher")


def _sync_managed_clone(bot_id: str, settings: Settings) -> bool:
    """Fast-forward only clean app-owned checkouts. Return whether HEAD changed."""
    _, repo, root = _bot_repo(bot_id)
    if repo.source_type != "git" or not repo.git_url or not settings.bot_github_sync_enabled:
        return False
    expected = clone_path_for_git_url(repo.git_url, settings.storage_dir).resolve()
    if root != expected or not _valid_github_remote(repo.git_url):
        return False
    origin = _run_git(root, "remote", "get-url", "origin")
    if not _valid_github_remote(origin) or _github_slug(origin) != _github_slug(repo.git_url):
        return False
    current = _run_git(root, "rev-parse", "HEAD")
    branch = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if (not re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", branch) or branch.startswith("-")
            or ".." in branch or "//" in branch):
        return False
    upstream = _run_git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream != f"origin/{branch}":
        return False
    if _run_git(root, "status", "--porcelain", "--untracked-files=all"):
        return False
    refspec = f"+refs/heads/{branch}:refs/remotes/origin/{branch}"
    env = os.environ.copy()
    for name in tuple(env):
        if name.startswith("GIT_"):
            env.pop(name, None)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
    hooks = (settings.storage_dir / "bot_changes" / "disabled-hooks").resolve()
    hooks.mkdir(parents=True, exist_ok=True)
    git_prefix = _git_prefix(root, hooks, env)
    result = subprocess.run(
        [*git_prefix, "fetch", "--no-tags", "origin", refspec],
        capture_output=True, text=True, timeout=120, check=False, env=env, shell=False,
    )
    if result.returncode:
        logger.info("managed clone sync failed bot_id=%s", bot_id)
        return False
    merge = subprocess.run(
        [*git_prefix, "merge", "--ff-only", f"refs/remotes/origin/{branch}"],
        capture_output=True, text=True, timeout=60, check=False, env=env, shell=False,
    )
    if merge.returncode:
        logger.info("managed clone fast-forward skipped bot_id=%s", bot_id)
        return False
    return _run_git(root, "rev-parse", "HEAD") != current


def _github_slug(remote: str) -> str | None:
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?",
        remote,
    )
    return f"{match.group(1)}/{match.group(2)}".casefold() if match else None


async def _watch_once(settings: Settings) -> None:
    try:
        store = get_store()
        with store.orm_session() as session:
            bot_ids = list(session.scalars(select(BotRecord.id)).all())
    except (SQLAlchemyError, OSError):
        logger.info("bot documentation scan could not read its database")
        return

    for bot_id in bot_ids:
        try:
            _, repo, root = await run_blocking(_bot_repo, bot_id)
            indexed = read_repo_metadata(repo.id, settings=settings)
            initial_baseline = indexed.commit_hash if indexed else repo.commit_hash
            async with repo_write_lock(repo.id):
                try:
                    await run_blocking(_sync_managed_clone, bot_id, settings)
                except (ValueError, OSError, subprocess.SubprocessError):
                    logger.info("managed clone sync skipped bot_id=%s", bot_id)
            current = await run_blocking(_run_git, root, "rev-parse", "HEAD")
            async with repo_write_lock(repo.id):
                await run_blocking(
                    BotChangeService(settings).check_documentation, bot_id, initial_baseline
                )
            latest = read_repo_metadata(repo.id, settings=settings)
            if latest is None or latest.commit_hash != current:
                # BotService.refresh owns the same repository lock itself.
                await BotService(store=get_store(), settings=settings).refresh(bot_id)
        except asyncio.CancelledError:
            raise
        except (ValueError, OSError, RuntimeError, SQLAlchemyError, subprocess.SubprocessError):
            # A bad path or remote for one bot must not stop checks for the rest.
            logger.info("bot documentation check skipped bot_id=%s", bot_id)


async def _watch_loop(settings: Settings) -> None:
    interval = max(15, settings.bot_documentation_watch_seconds)
    while True:
        await asyncio.sleep(interval)
        await _watch_once(settings)


def start_documentation_watcher(settings: Settings | None = None) -> asyncio.Task[None]:
    """Start the app-lifespan watcher. Cancel the returned task during shutdown."""
    return asyncio.create_task(_watch_loop(settings or get_settings()), name="bot-documentation-watcher")
