from pathlib import Path

import pytest

from backend.app.database import SQLiteStore
from backend.app.schemas.ask import AskRequest
from backend.app.services.graphrag import GraphRAGRetriever
from backend.app.services.llm.gateway import LLMResult
from backend.app.services.question_answerer import QuestionAnswerer
from backend.app.services.repo_scanner import RepoScanner


@pytest.mark.asyncio
async def test_question_answerer_returns_answer_sources_and_related_graph(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "service.py").write_text("def answer():\n    return 42\n")
    (repo_dir / "api.py").write_text(
        "from service import answer\n\ndef handler():\n    return answer()\n"
    )
    store = SQLiteStore(tmp_path / "codewiki.sqlite3")
    repo = store.upsert_repo(RepoScanner().describe(str(repo_dir)))
    assert store.get_graph(repo.id) == ([], [])

    response = await QuestionAnswerer(GraphRAGRetriever(store=store), _FakeQALLM(), store=store).answer(
        repo.id,
        AskRequest(question="What does handler call?"),
    )

    assert "answer" in response.answer
    assert response.sources
    assert any(source.file_path == "api.py" for source in response.sources)
    assert response.related_nodes
    assert any(node["name"] == "handler" for node in response.related_nodes)
    assert response.related_edges
    assert response.related_communities
    assert store.list_llm_runs(repo.id, task_type="qa")

    # The same Ask flow refreshes changed source instead of retaining stale chunks.
    (repo_dir / "service.py").write_text("def answer():\n    return 84\n")
    recorder = _CapturingQALLM()
    await QuestionAnswerer(GraphRAGRetriever(store=store), recorder, store=store).answer(
        repo.id, AskRequest(question="What does handler call?")
    )
    assert "return 84" in recorder.payload
    assert "return 42" not in recorder.payload
    store.close()


class _CapturingQALLM:
    payload = ""

    async def complete(self, task_type: str, messages: list[dict[str, str]], *, response_format: str | None = None) -> LLMResult:
        self.payload = messages[-1]["content"]
        return await _FakeQALLM().complete(task_type, messages, response_format=response_format)


class _FakeQALLM:
    async def complete(
        self,
        task_type: str,
        messages: list[dict[str, str]],
        *,
        response_format: str | None = None,
    ) -> LLMResult:
        assert task_type == "qa"
        assert response_format is None
        assert "Stable QA contract" in messages[-2]["content"]
        assert messages[-1]["content"].startswith("GraphRAG QA payload:")
        assert "community_summaries" in messages[-1]["content"]
        assert "handler" in messages[-1]["content"]
        assert "api.py" in messages[-1]["content"]
        return LLMResult(
            content="`handler` calls `answer`, which returns 42. See api.py and service.py.",
            model="fake/qa",
            usage={"prompt_tokens": 10, "completion_tokens": 12},
        )
