import subprocess
import sys
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import worker

FIXTURE = Path(__file__).parent / "fixtures" / "valid.png"
VALID_GRAPH = {
    "version": 1,
    "title": "Repo graph",
    "nodes": [
        {"id": "S1", "label": "Entry point", "source_ref": "src/main.py:1"},
        {"id": "S2", "label": "Service", "source_ref": "src/service.py:8"},
    ],
    "edges": [{"source": "S1", "target": "S2", "label": "calls"}],
}


def test_render_png_returns_bounded_png_from_mocked_process():
    image = FIXTURE.read_bytes()
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=image, stderr=b"")

    result = worker.render_png(VALID_GRAPH, runner)

    assert result == image
    assert result.startswith(worker.PNG_SIGNATURE)
    assert calls[0][0] == ["dotnet", worker.RENDERER_DLL]
    assert calls[0][1]["timeout"] == 30
    assert calls[0][1]["input"].startswith(b'{"version":1')


@pytest.mark.parametrize(
    "mutate",
    [
        lambda graph: graph.update(version=2),
        lambda graph: graph.update(title="x" * 121),
        lambda graph: graph.update(nodes=[{"id": "S7", "label": "x", "source_ref": "ref"}]),
        lambda graph: graph.update(edges=[{"source": "S1", "target": "S2", "label": "x" * 81}]),
    ],
)
def test_invalid_graph_is_rejected_before_process_start(mutate):
    import copy

    graph = copy.deepcopy(VALID_GRAPH)
    mutate(graph)

    with pytest.raises(worker.RequestError):
        worker.render_png(graph, runner=lambda *args, **kwargs: pytest.fail("unexpected process"))


def test_renderer_timeout_fails_closed():
    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    with pytest.raises(worker.RenderTimeout):
        worker.render_png(VALID_GRAPH, runner)


def test_renderer_must_return_png_within_limit():
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=b"not a PNG", stderr=b"")

    with pytest.raises(worker.RenderError):
        worker.render_png(VALID_GRAPH, runner)

    too_large = worker.PNG_SIGNATURE + (b"x" * worker.MAX_PNG_BYTES)

    def oversized_runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=too_large, stderr=b"")

    with pytest.raises(worker.RenderError):
        worker.render_png(VALID_GRAPH, oversized_runner)


def test_health_reports_status_and_pinned_revision_header():
    server = ThreadingHTTPServer(("127.0.0.1", 0), worker.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/health", timeout=2) as response:
            body = json.load(response)
            assert response.status == 200
            assert response.headers["X-Najm-Revision"] == "6e898a51c7e7e2f0992a194891491fd1253c246e"
            assert body == {"status": "ok", "najm_revision": worker.NAJM_REVISION}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
