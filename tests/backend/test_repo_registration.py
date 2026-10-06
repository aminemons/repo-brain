"""Regression checks for recoverable repository registration."""
import subprocess
from pathlib import Path

import pytest

from backend.app.services.repo_scanner.git_ops import GitOperations
from backend.app.services.repo_scanner.scanner import (
    RepoScanner,
    clone_path_for_git_url,
    public_git_url,
)


def test_github_url_aliases_share_one_checkout(tmp_path: Path) -> None:
    urls = ["https://github.com/Owner/Repo", "https://github.com/owner/repo.git/", "git@github.com:OWNER/REPO.git"]
    assert len({clone_path_for_git_url(url, tmp_path) for url in urls}) == 1


@pytest.mark.parametrize("url", ["https://user:fixture-secret@github.com/owner/repo", "https://github.com/owner/repo/tree/main", " "])
def test_bad_repository_inputs_fail_before_git(url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("Git must not run for this input")
    monkeypatch.setattr(GitOperations, "clone", fail)
    with pytest.raises(ValueError) as result:
        RepoScanner(storage_dir=tmp_path).describe(url)
    assert "fixture-secret" not in str(result.value)


def test_failed_clone_is_atomic_and_can_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.services.repo_scanner import git_ops
    destination = tmp_path / "checkout"
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["timeout"] == 180
        checkout = Path(command[-1])
        checkout.mkdir()
        (checkout / ".git").mkdir()
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, command, stderr="fixture-secret")
        (checkout / "README.md").write_text("fixture")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(git_ops.subprocess, "run", run)
    with pytest.raises(ValueError) as result:
        GitOperations().clone("https://github.com/owner/repo", destination)
    assert "fixture-secret" not in str(result.value)
    assert not destination.exists()
    assert not list(tmp_path.glob(".clone-*"))
    GitOperations().clone("https://github.com/owner/repo", destination)
    assert (destination / "README.md").read_text() == "fixture"


def test_timed_out_clone_is_cleaned_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.services.repo_scanner import git_ops
    def run(command, **kwargs):
        Path(command[-1]).mkdir()
        raise subprocess.TimeoutExpired(command, 180)
    monkeypatch.setattr(git_ops.subprocess, "run", run)
    with pytest.raises(ValueError, match="timed out"):
        GitOperations().clone("https://github.com/owner/repo", tmp_path / "checkout")
    assert list(tmp_path.iterdir()) == []


def test_existing_local_origin_is_redacted_in_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GitOperations, "metadata", lambda *_: ("https://user:fixture-secret@github.com/owner/repo.git", None))
    repo = RepoScanner().describe(str(tmp_path))
    assert repo.git_url == "https://github.com/owner/repo.git"
    assert public_git_url(repo.git_url) == repo.git_url


def test_registration_reuses_existing_clone_for_url_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from backend.app.api import repos
    from backend.app.services.repo_scanner import RepoDescriptor
    existing = RepoDescriptor(id="older", name="Saved name", path=str(tmp_path), source_type="git", git_url="https://github.com/owner/repo")
    monkeypatch.setattr(repos, "get_store", lambda: SimpleNamespace(list_repos=lambda: [existing]))
    monkeypatch.setattr(GitOperations, "metadata", lambda *_: (existing.git_url, None))
    def fail(*args, **kwargs):
        raise AssertionError("Existing clone must be reused")
    monkeypatch.setattr(GitOperations, "clone", fail)
    registered = repos._describe_registration(repos.CreateRepoRequest(path="https://github.com/OWNER/REPO.git"))
    assert registered.path == existing.path
    assert registered.name == "Saved name"
