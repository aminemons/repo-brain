from pathlib import Path
from threading import Lock

from backend.app.services.project_policy import confined_repo_file, validate_project_root


class SourceFileContentProvider:
    """Thread-safe per-repository text cache for repeated source reads."""

    def __init__(self, repo_root: Path | str) -> None:
        self.repo_root = validate_project_root(repo_root)
        self._texts: dict[str, str] = {}
        self._lock = Lock()

    def read_text(self, path: Path | str) -> str:
        resolved = Path(path).resolve()
        key = self._cache_key(resolved)
        resolved = confined_repo_file(self.repo_root, key)
        with self._lock:
            cached = self._texts.get(key)
        if cached is not None:
            return cached

        content = resolved.read_text(encoding="utf-8", errors="replace")
        with self._lock:
            return self._texts.setdefault(key, content)

    def read_lines(self, path: Path | str) -> list[str]:
        return self.read_text(path).splitlines()

    def _cache_key(self, path: Path) -> str:
        try:
            return path.relative_to(self.repo_root).as_posix()
        except ValueError:
            raise ValueError("Source file escapes the repository root.") from None
