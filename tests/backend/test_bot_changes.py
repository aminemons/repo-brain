"""Isolated Git integration tests for bot proposals and documentation tracking."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.config import Settings
from backend.app.database import create_store
from backend.app.models.base import Base
from backend.app.services.bot_changes.models import BotChangeRecord, BotDocumentationJobRecord
from backend.app.services.bot_changes.service import BotChangeService
from backend.app.services.bots.models import BotRecord
from backend.app.services.repo_scanner import RepoDescriptor


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, shell=False,
    )
    return result.stdout.strip()


class _Response:
    def __init__(self, text: str) -> None:
        self._text = text

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"output": [{"content": [{"type": "output_text", "text": self._text}]}]}


@pytest.fixture
def bot_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.name", "Fixture User")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "README.md").write_text("# Fixture\n\nOriginal docs.\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("def answer():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "README.md", "src/app.py")
    _git(repo, "commit", "-m", "initial")
    base = _git(repo, "rev-parse", "HEAD")

    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'db.sqlite3').as_posix()}",
        storage_dir=tmp_path / "storage",
        project_root=None,
    )
    store = create_store(settings.database_url)
    Base.metadata.create_all(store.engine)
    repo_descriptor = RepoDescriptor(
        id="fixture-repo", name="Fixture", path=str(repo), source_type="local", commit_hash=base,
    )
    store.upsert_repo(repo_descriptor)
    from backend.app.services import project_policy
    from backend.app.services.bot_changes import service as service_module

    monkeypatch.setattr(service_module, "get_store", lambda: store)
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    monkeypatch.setattr(project_policy, "get_settings", lambda: settings)
    with store.orm_session() as session:
        session.add(BotRecord(
            id="fixture-bot", repo_id=repo_descriptor.id, name="Fixture bot", instructions="",
            model="gpt-5.5", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        ))
    yield SimpleNamespace(repo=repo, base=base, store=store, settings=settings)
    store.close()


def _mock_proposal(
    monkeypatch: pytest.MonkeyPatch, *, source: str, docs: str, calls: list[dict[str, Any]],
    documentation_only: bool = False,
) -> None:
    from backend.app.services.bot_changes import service as service_module

    answer = {
        "summary": "Update answer behavior and docs",
        "files": ([{"path": "README.md", "action": "update", "content": docs}]
                  if documentation_only else [
                      {"path": "src/app.py", "action": "update", "content": source},
                      {"path": "README.md", "action": "update", "content": docs},
                  ]),
    }

    def post(url: str, **kwargs: Any) -> _Response:
        calls.append({"url": url, **kwargs})
        return _Response(json.dumps(answer))

    monkeypatch.setattr(service_module.httpx, "post", post)


def test_propose_apply_uses_isolated_worktree_and_preserves_base_checkout(
    bot_fixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo: Path = bot_fixture.repo
    from backend.app.services.bot_changes.service import _run_git
    assert _run_git(repo, "status", "--porcelain", "--untracked-files=all") == ""
    original_head = _git(repo, "rev-parse", "HEAD")
    original_readme = (repo / "README.md").read_text(encoding="utf-8")
    calls: list[dict[str, Any]] = []
    _mock_proposal(
        monkeypatch, calls=calls,
        source="def answer():\n    return 42\n",
        docs="# Fixture\n\nThe answer function returns 42.\n",
    )

    service = BotChangeService(bot_fixture.settings)
    proposal = service.propose("fixture-bot", "Return the new answer", "sk-test-one-time-key")

    assert proposal["status"] == "proposed"
    assert proposal["base_commit"] == original_head
    assert proposal["files"][0]["diff"].startswith("--- a/src/app.py")
    assert calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert calls[0]["json"]["store"] is False
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-test-one-time-key"
    assert "sk-test-one-time-key" not in proposal["request"]

    applied = service.apply("fixture-bot", proposal["id"])

    assert applied["status"] == "applied"
    assert _git(repo, "rev-parse", "HEAD") == original_head
    assert (repo / "README.md").read_text(encoding="utf-8") == original_readme
    with bot_fixture.store.orm_session() as session:
        stored = session.get(BotChangeRecord, proposal["id"])
        assert stored is not None
        worktree = Path(stored.worktree_path or "")
        assert _git(worktree, "rev-parse", "HEAD") == applied["commit_hash"]
        assert (worktree / "src" / "app.py").read_text(encoding="utf-8").endswith("return 42\n")
        assert "sk-test-one-time-key" not in stored.request
        assert "sk-test-one-time-key" not in json.dumps(stored.files)


def test_local_model_proposes_changes_without_an_api_key(bot_fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.services.bots import provider

    with bot_fixture.store.orm_session() as session:
        bot = session.get(BotRecord, "fixture-bot")
        assert bot is not None
        bot.model = "ollama/qwen2.5-coder:7b"
    calls: list[dict[str, Any]] = []

    async def generate_text(
        model: str, instructions: str, input_messages: list[dict[str, Any]], api_key=None, output_schema=None,
    ) -> str:
        calls.append({
            "model": model, "instructions": instructions, "messages": input_messages,
            "api_key": api_key, "output_schema": output_schema,
        })
        return json.dumps({
            "summary": "Update answer behavior and docs",
            "files": [
                {"path": "src/app.py", "action": "update", "content": "def answer():\n    return 42\n"},
                {"path": "README.md", "action": "update", "content": "# Fixture\n\nThe answer is 42.\n"},
            ],
        })

    monkeypatch.setattr(provider, "generate_text", generate_text)
    proposal = BotChangeService(bot_fixture.settings).propose("fixture-bot", "Return 42", None)

    assert proposal["status"] == "proposed"
    assert calls[0]["model"] == "ollama/qwen2.5-coder:7b"
    assert calls[0]["api_key"] is None
    assert calls[0]["messages"][0]["role"] == "user"
    assert calls[0]["output_schema"]["type"] == "object"
    prompt = json.loads(calls[0]["messages"][0]["content"])
    assert prompt["request"] == "Return 42"
    assert len(calls[0]["messages"][0]["content"]) <= 12_000 - len(calls[0]["instructions"])


def test_local_model_drafts_documentation_without_an_api_key(
    bot_fixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services.bots import provider

    with bot_fixture.store.orm_session() as session:
        bot = session.get(BotRecord, "fixture-bot")
        assert bot is not None
        bot.model = "ollama/qwen2.5-coder:7b"
    source_path = bot_fixture.repo / "src" / "app.py"
    source_path.write_text("def answer():\n    return 2\n", encoding="utf-8")
    _git(bot_fixture.repo, "add", "src/app.py")
    _git(bot_fixture.repo, "commit", "-m", "change source")
    calls: list[dict[str, Any]] = []

    async def generate_text(
        model: str, instructions: str, input_messages: list[dict[str, Any]], api_key=None, output_schema=None,
    ) -> str:
        calls.append({"model": model, "api_key": api_key, "messages": input_messages})
        return json.dumps({
            "summary": "Document the changed answer",
            "files": [{
                "path": "README.md", "action": "update",
                "content": "# Fixture\n\nThe answer function now returns 2.\n",
            }],
        })

    monkeypatch.setattr(provider, "generate_text", generate_text)
    service = BotChangeService(bot_fixture.settings)
    status = service.check_documentation("fixture-bot", bot_fixture.base)
    assert status["queued_count"] == 1

    draft = service.propose_documentation("fixture-bot", None, ["src/app.py"])

    assert draft["status"] == "proposed"
    assert draft["documentation_sources"] == ["src/app.py"]
    assert calls[0]["model"] == "ollama/qwen2.5-coder:7b"
    assert calls[0]["api_key"] is None


def test_local_model_rejects_request_that_would_truncate_json(
    bot_fixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services.bots import provider

    with bot_fixture.store.orm_session() as session:
        bot = session.get(BotRecord, "fixture-bot")
        assert bot is not None
        bot.model = "ollama/qwen2.5-coder:7b"
        bot.instructions = "instruction " * 700

    async def unexpected_generate(*_args, **_kwargs) -> str:
        raise AssertionError("The provider must not receive truncated JSON.")

    monkeypatch.setattr(provider, "generate_text", unexpected_generate)
    with pytest.raises(ValueError, match="exceed the local model input limit"):
        BotChangeService(bot_fixture.settings).propose("fixture-bot", "request " * 1_000, None)


@pytest.mark.parametrize("server_token", [False, True])
def test_publish_uses_noninteractive_stubbed_git_and_gh(bot_fixture, monkeypatch: pytest.MonkeyPatch, server_token: bool) -> None:
    import shutil

    from backend.app.services.bot_changes import service as service_module

    _git(bot_fixture.repo, "remote", "add", "origin", "https://github.com/example/fixture.git")
    _mock_proposal(
        monkeypatch, calls=[], source="def answer():\n    return 42\n",
        docs="# Fixture\n\nUpdated behavior.\n",
    )
    service = BotChangeService(bot_fixture.settings)
    proposal = service.propose("fixture-bot", "Change the answer", "sk-test")
    service.apply("fixture-bot", proposal["id"])
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    if server_token:
        monkeypatch.setenv("GH_TOKEN", "fixture-github-token")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "fixture.untrusted")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "fixture")
    original_run = subprocess.run
    calls: list[list[str]] = []

    def run(args, **kwargs):
        if args[0] == "gh":
            assert args[args.index("--repo") + 1] == "example/fixture"
            calls.append(list(args))
            if args[1:3] == ["pr", "view"]:
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            return SimpleNamespace(
                returncode=0, stdout="https://github.com/example/fixture/pull/123\n", stderr="",
            )
        if args[0] == "git" and "push" in args:
            assert "GIT_CONFIG_COUNT" not in kwargs["env"]
            assert "fixture-github-token" not in " ".join(args)
            helper = "credential.https://github.com.helper=!gh auth git-credential"
            assert (helper in args) == server_token
            calls.append(list(args))
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return original_run(args, **kwargs)

    monkeypatch.setattr(service_module.subprocess, "run", run)
    monkeypatch.setattr(service_module.shutil, "which", lambda name: "gh.exe" if name == "gh" else shutil.which(name))

    published = service.publish("fixture-bot", proposal["id"])

    assert published["status"] == "published"
    assert published["pull_request_url"] == "https://github.com/example/fixture/pull/123"
    assert any(command[0] == "gh" and command[1:3] == ["pr", "create"] for command in calls)
    assert any(command[0] == "git" and "push" in command for command in calls)


def test_apply_rejects_content_changed_after_review(bot_fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_proposal(
        monkeypatch, calls=[], source="def answer():\n    return 42\n",
        docs="# Fixture\n\nUpdated behavior.\n",
    )
    service = BotChangeService(bot_fixture.settings)
    proposal = service.propose("fixture-bot", "Change the answer", "sk-test")
    (bot_fixture.repo / "src" / "app.py").write_text("def answer():\n    return 99\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after review"):
        service.apply("fixture-bot", proposal["id"])
    assert (bot_fixture.repo / "src" / "app.py").read_text(encoding="utf-8").endswith("return 99\n")
    assert _git(bot_fixture.repo, "branch", "--show-current") == "main"


def test_documentation_check_queues_head_changes_and_proposal_is_idempotent(
    bot_fixture, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo: Path = bot_fixture.repo
    (repo / "src" / "app.py").write_text("def answer():\n    return 2\n", encoding="utf-8")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-m", "change source")
    changed_head = _git(repo, "rev-parse", "HEAD")
    service = BotChangeService(bot_fixture.settings)

    checked = service.check_documentation("fixture-bot", bot_fixture.base)
    assert checked["queued_count"] == 1
    assert checked["current_commit"] == changed_head
    assert checked["changed_files"] == ["src/app.py"]

    calls: list[dict[str, Any]] = []
    _mock_proposal(
        monkeypatch, calls=calls, source="def answer():\n    return 3\n",
        docs="# Fixture\n\nThe answer function returns 3.\n", documentation_only=True,
    )
    first = service.propose_documentation("fixture-bot", "sk-doc-key", ["src/app.py"])
    second = service.propose_documentation("fixture-bot", "sk-doc-key", ["src/app.py"])

    assert first["id"] == second["id"]
    assert first["documentation_sources"] == ["src/app.py"]
    assert all(file["path"].endswith((".md", ".mdx")) or file["path"].startswith("docs/")
               for file in first["files"])
    assert len(calls) == 1
    with bot_fixture.store.orm_session() as session:
        jobs = session.query(BotDocumentationJobRecord).all()
        assert len(jobs) == 1 and jobs[0].status == "proposed"
        change = session.get(BotChangeRecord, first["id"])
        assert change is not None and change.documentation_commit == changed_head

    service.apply("fixture-bot", first["id"])
    with bot_fixture.store.orm_session() as session:
        applied_worktree = Path(session.get(BotChangeRecord, first["id"]).worktree_path)
    assert "src/app.py" in _git(applied_worktree, "ls-files").splitlines()
    with bot_fixture.store.orm_session() as session:
        change = session.get(BotChangeRecord, first["id"])
        assert change is not None and change.branch
        branch = change.branch
    _git(repo, "merge", "--ff-only", branch)
    from backend.app.services.bot_changes.service import _run_git
    assert _run_git(repo, "diff", "--name-only", changed_head, _git(repo, "rev-parse", "HEAD"), "--", "src/app.py") == ""
    completed = service.check_documentation("fixture-bot")
    assert completed["pending_jobs"] == []


def test_documentation_batches_leave_unselected_jobs_pending(bot_fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    repo: Path = bot_fixture.repo
    files = []
    for index in range(21):
        relative = f"src/module_{index:02}.py"
        (repo / relative).write_text(f"VALUE = {index}\n", encoding="utf-8")
        files.append(relative)
    _git(repo, "add", "src")
    _git(repo, "commit", "-m", "many source changes")
    service = BotChangeService(bot_fixture.settings)
    assert service.check_documentation("fixture-bot", bot_fixture.base)["queued_count"] == 21
    calls: list[dict[str, Any]] = []
    _mock_proposal(
        monkeypatch, calls=calls, source="def answer():\n    return 4\n",
        docs="# Fixture\n\nUpdated documentation.\n", documentation_only=True,
    )

    first_batch = service.propose_documentation("fixture-bot", "sk-doc-key", files[:20])
    status = service.documentation_status("fixture-bot")
    assert first_batch["documentation_sources"] == sorted(files[:20])
    assert sum(job["status"] == "pending" for job in status["pending_jobs"]) == 1
    repeated = service.propose_documentation("fixture-bot", "sk-doc-key", files[:20])
    assert repeated["id"] == first_batch["id"]
    final_batch = service.propose_documentation("fixture-bot", "sk-doc-key", files[20:])
    assert final_batch["id"] != first_batch["id"]
    assert final_batch["documentation_sources"] == files[20:]
    assert len(calls) == 2


def test_watcher_queues_local_head_changes_before_refresh(bot_fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.services import repo_metadata
    from backend.app.services.bot_changes import watcher
    from backend.app.services.bots import service as bots_service

    repo = bot_fixture.repo
    descriptor = RepoDescriptor(
        id="fixture-repo", name="Fixture", path=str(repo), source_type="local", commit_hash=bot_fixture.base,
    )
    repo_metadata.write_repo_metadata(descriptor, settings=bot_fixture.settings)
    (repo / "src" / "app.py").write_text("def answer():\n    return 8\n", encoding="utf-8")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-m", "watcher source change")
    new_head = _git(repo, "rev-parse", "HEAD")
    refreshed: list[str] = []

    async def refresh(self, bot_id: str):
        refreshed.append(bot_id)
        repo_metadata.write_repo_metadata(
            RepoDescriptor(
                id="fixture-repo", name="Fixture", path=str(repo), source_type="local", commit_hash=new_head,
            ),
            settings=bot_fixture.settings,
        )

    monkeypatch.setattr(watcher, "get_store", lambda: bot_fixture.store)
    monkeypatch.setattr(bots_service.BotService, "refresh", refresh)

    asyncio.run(watcher._watch_once(bot_fixture.settings))

    assert refreshed == ["fixture-bot"]
    status = BotChangeService(bot_fixture.settings).documentation_status("fixture-bot")
    assert status["current_commit"] == new_head
    assert status["changed_files"] == ["src/app.py"]

