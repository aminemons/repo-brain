"""Check repository evidence against pinned owner projects without executing their code.

Only Git metadata, parsing, indexing, and local retrieval run. No model requests,
package installs, repository edits, or provider credentials are needed.
"""

import argparse
import asyncio
import gc
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import get_settings
from backend.app.database import SQLiteStore
from backend.app.schemas.project_brain import IngestDocumentRequest
from backend.app.services.bots.retrieval import BotEvidenceRetriever
from backend.app.services.project_brain.service import ProjectBrainService
from backend.app.services.repo_scanner import RepoScanner


async def check(checkouts: Path, report_path: Path | None) -> None:
    fixture_path = Path(__file__).resolve().parent.parent / "tests/acceptance/owner-repositories.json"
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    keys = ("CODEWIKI_STORAGE_DIR", "CODEWIKI_PROJECT_ROOT", "CODEWIKI_DOCUMENTATION_ROOT")
    original = {key: os.environ.get(key) for key in keys}
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="repo-brain-acceptance-") as temporary:
        store = SQLiteStore(Path(temporary) / "acceptance.sqlite3")
        try:
            os.environ["CODEWIKI_STORAGE_DIR"] = temporary
            os.environ["CODEWIKI_DOCUMENTATION_ROOT"] = ""
            get_settings.cache_clear()
            settings = get_settings()
            for fixture in fixtures:
                root = (checkouts / fixture["name"]).resolve()
                if not root.is_relative_to(checkouts) or not root.is_dir():
                    raise ValueError(f"Missing checkout: {fixture['name']}")
                os.environ["CODEWIKI_PROJECT_ROOT"] = str(root)
                get_settings.cache_clear()
                settings = get_settings()
                revision = await asyncio.to_thread(subprocess.run,
                    ["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                    capture_output=True, text=True, timeout=10,
                )
                commit = revision.stdout.strip()
                if commit != fixture["commit"]:
                    raise ValueError(f"Checkout revision differs from the acceptance pin: {fixture['name']}")
                repo = store.upsert_repo(RepoScanner().describe(str(root)))
                brain = ProjectBrainService(store=store, settings=settings)
                if (root / "README.md").is_file():
                    brain.ingest(repo.id, IngestDocumentRequest(path="README.md", authoritative=False))
                retriever = BotEvidenceRetriever(store, settings)
                matched = 0
                for question in fixture["questions"]:
                    evidence = await retriever.retrieve(repo.id, question["query"])
                    sources = [item.source for item in evidence]
                    if not any(source.path == question["path"] and question["symbol"] in source.snippet for source in sources):
                        raise ValueError(f"Expected evidence missing: {fixture['name']} / {question['symbol']}")
                    for source in sources:
                        path = (root / source.path).resolve()
                        if not path.is_relative_to(root) or source.start_line < 1 or source.end_line < source.start_line:
                            raise ValueError("Evidence escaped its repository or has invalid line ranges")
                    matched += 1
                nodes, edges = store.get_graph(repo.id)
                results.append({
                    "repository": fixture["name"], "commit": commit,
                    "questions_passed": matched, "questions_total": len(fixture["questions"]),
                    "graph_nodes": len(nodes), "graph_edges": len(edges),
                })
        finally:
            store.close()
            gc.collect()
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            get_settings.cache_clear()
    report = json.dumps({"scope": "evidence retrieval; no model inference or target execution", "results": results}, indent=2)
    print(report)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkouts", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    asyncio.run(check(arguments.checkouts.expanduser().resolve(), arguments.report))
