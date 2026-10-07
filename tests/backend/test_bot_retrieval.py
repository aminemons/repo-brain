from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.database import SQLiteStore
from backend.app.schemas.project_brain import IngestDocumentRequest
from backend.app.services.analyzer import AnalysisService
from backend.app.services.bots.retrieval import BotEvidenceRetriever
from backend.app.services.project_brain.service import ProjectBrainService
from backend.app.services.repo_scanner import RepoScanner


@pytest.mark.asyncio
@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
@pytest.mark.parametrize("filename,lines", [
    ("service.py", [b"def handler():", b"    return True", b""]),
    ("vite.config.ts", [b"export function handler() {", b"    return true;", b"}", b""]),
])
async def test_bot_retrieval_accepts_unchanged_source_with_any_line_ending(tmp_path: Path, newline: bytes, filename: str, lines: list[bytes]) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / filename).write_bytes(newline.join(lines))
    store = SQLiteStore(tmp_path / "codewiki.sqlite3")
    repo = store.upsert_repo(RepoScanner().describe(str(repo_dir)))
    retriever = BotEvidenceRetriever(store, Settings(storage_dir=tmp_path / "storage", project_root=repo_dir))
    try:
        sources = await retriever.retrieve(repo.id, "handler")
        assert any("handler" in item.source.snippet for item in sources)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_bot_retrieval_reindexes_edited_code_and_uses_current_line_numbers(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    source = repo_dir / "service.py"
    source.write_text("def old_handler():\n    return 'old'\n", encoding="utf-8")
    store = SQLiteStore(tmp_path / "codewiki.sqlite3")
    repo = store.upsert_repo(RepoScanner().describe(str(repo_dir)))
    settings = Settings(storage_dir=tmp_path / "storage", project_root=repo_dir)
    retriever = BotEvidenceRetriever(store, settings)

    initial = await retriever.retrieve(repo.id, "old_handler")
    assert any("old_handler" in item.source.snippet for item in initial)

    source.write_text(
        "# shifted source\n# another line\ndef current_handler():\n    return 'current'\n",
        encoding="utf-8",
    )
    refreshed = await retriever.retrieve(repo.id, "current_handler")

    current = [item.source for item in refreshed if item.source.type == "code"]
    assert current
    assert any("current_handler" in item.snippet for item in current)
    assert all("old_handler" not in item.snippet for item in current)
    assert any(item.start_line >= 3 for item in current)
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["edit", "delete"])
async def test_bot_retrieval_drops_edited_or_deleted_document_evidence(
    tmp_path: Path,
    change: str,
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("def run():\n    return True\n", encoding="utf-8")
    readme = repo_dir / "README.md"
    readme.write_text(
        "# Operations\n\nThe deployment uses the original release process.\n",
        encoding="utf-8",
    )
    store = SQLiteStore(tmp_path / "codewiki.sqlite3")
    repo = store.upsert_repo(RepoScanner().describe(str(repo_dir)))
    AnalysisService(store=store).analyze(repo.id)
    ProjectBrainService(store=store, settings=Settings(project_root=repo_dir)).ingest(
        repo.id,
        IngestDocumentRequest(path="README.md", authoritative=True),
    )
    retriever = BotEvidenceRetriever(
        store,
        Settings(storage_dir=tmp_path / "storage", project_root=repo_dir),
    )

    initial = await retriever.retrieve(repo.id, "original release process")
    assert any(item.source.type == "documentation" for item in initial)

    if change == "edit":
        readme.write_text("# Operations\n\nThe deployment now uses a new release process.\n", encoding="utf-8")
    else:
        readme.unlink()

    refreshed = await retriever.retrieve(repo.id, "original release process")

    assert all(item.source.type != "documentation" for item in refreshed)
    store.close()
