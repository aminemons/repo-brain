"""Test-only Repo Brain entrypoint with deterministic model providers.

This process still uses the production API, auth middleware, repository scanner,
index, SQLite store, and Najm renderer. Only paid OpenAI HTTP calls are replaced.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Self


def _prepare_fixture_repositories() -> None:
    from backend.app.config import get_settings

    run_id = os.environ.get("E2E_RUN_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise RuntimeError("E2E_RUN_ID must be set to a safe per-run identifier")
    storage = get_settings().storage_dir.expanduser().resolve()
    fixtures_root = (storage / "e2e-fixtures").resolve()
    if not fixtures_root.is_relative_to(storage):
        raise RuntimeError("E2E fixture directory escaped application storage")
    run_root = (fixtures_root / run_id).resolve()
    if not run_root.is_relative_to(fixtures_root) or run_root.exists():
        raise RuntimeError("E2E fixture directory is unsafe or already exists")

    for name in ("repo-one", "repo-two"):
        root = run_root / name
        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "README.md").write_text(
            f"# {name} fixture\n\n"
            "This repository documents the zeta initializer and its startup sequence.\n",
            encoding="utf-8",
        )
        (root / "src" / "app.py").write_text(
            "\"\"\"Small source fixture used by the Repo Brain browser tests.\"\"\"\n\n"
            "def zeta_initializer(config: dict[str, str]) -> str:\n"
            "    \"\"\"Return the startup state used to verify evidence retrieval.\"\"\"\n"
            "    service_name = config.get('service_name', 'fixture-service')\n"
            "    return f'{service_name}: initialized'\n\n"
            "def start_application(config: dict[str, str]) -> str:\n"
            "    \"\"\"Start the fixture through the zeta initializer.\"\"\"\n"
            "    return zeta_initializer(config)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "--quiet", str(root)], check=True, timeout=10)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "Repo Brain E2E"],
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(root), "config", "user.email", "repo-brain-e2e@example.invalid"],
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(root), "add", "README.md", "src/app.py"], check=True, timeout=10
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "--quiet", "-m", "Create browser test fixture"],
            check=True,
            timeout=10,
        )
        subprocess.run(["git", "-C", str(root), "branch", "-M", "main"], check=True, timeout=10)


class _FakeOpenAIResponses:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        inputs = kwargs.get("input", [])
        user_text = " ".join(
            str(item.get("content", "")) for item in inputs if item.get("role") == "user"
        )
        if "E2E_FAIL_MODEL" in user_text:
            raise RuntimeError("deterministic e2e model failure")
        if "SECOND_BOT_MARKER" in user_text:
            return SimpleNamespace(output_text="Deterministic answer for SECOND_BOT_MARKER.")
        return SimpleNamespace(
            output_text="Deterministic answer: the zeta initializer prepares the startup state."
        )


class _FakeAsyncOpenAI:
    def __init__(self, *, api_key: str, base_url: str, timeout: float, max_retries: int) -> None:
        if (
            not api_key
            or base_url != "https://api.openai.com/v1"
            or timeout > 60
            or max_retries != 0
        ):
            raise RuntimeError("unexpected model client configuration in e2e test")
        self.responses = _FakeOpenAIResponses()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeProposalResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        proposal = {
            "summary": "Clarify the fixture README",
            "files": [
                {
                    "path": "README.md",
                    "action": "update",
                    "content": (
                        "# repo-one fixture\n\n"
                        "Updated by the deterministic Repo Brain browser test.\n"
                    ),
                }
            ],
        }
        return {"output": [{"content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}


def _install_test_providers() -> None:
    from backend.app.config import get_settings
    from backend.app.services.bot_changes import service as changes_service
    from backend.app.services.bots import service as bots_service

    settings = get_settings()
    if not settings.auth_token:
        raise RuntimeError("The E2E server requires the configured owner token")
    if not settings.najm_enabled:
        raise RuntimeError("The E2E server requires the genuine Najm renderer to be enabled")

    bots_service.AsyncOpenAI = _FakeAsyncOpenAI  # type: ignore[assignment,misc]
    changes_service.httpx.post = (  # type: ignore[assignment]
        lambda *args, **kwargs: _FakeProposalResponse()
    )


def main() -> None:
    if os.environ.get("CODEWIKI_E2E_TEST_MODE") != "1":
        raise RuntimeError("This entrypoint is restricted to the isolated E2E test deployment")
    sys.path.insert(0, "/app")
    _prepare_fixture_repositories()
    _install_test_providers()

    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, access_log=False)


if __name__ == "__main__":
    main()
