"""Confined, bounded, line-preserving evidence reads and secret redaction."""

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from backend.app.schemas.project_brain import SourceExcerpt
from backend.app.services.project_policy import confined_repo_file, is_sensitive_path

MAX_SOURCE_BYTES = 2_000_000
MAX_DOCUMENT_BYTES = 8_000_000
MAX_EXCERPT_LINES = 200
MAX_EXCERPT_CHARS = 16_000

SECRET_ASSIGNMENT = re.compile(
    r"(?i)((?:[\"']?[\w.-]*(?:password|passwd|api[_-]?key|access[_-]?token|"
    r"auth[_-]?token|client[_-]?secret|private[_-]?key)[\w.-]*[\"']?)\s*[:=]\s*)"
    r"([^\r\n]+)"
)
TOKEN_PATTERNS = (
    re.compile(r"\b(?:sk-(?:proj-)?|gh[pousr]_)[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{16,}"),
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s/@]+(@)"),
)


@dataclass(frozen=True)
class SourceText:
    path: str
    text: str
    checksum: str
    redacted: bool
    page_ranges: tuple[tuple[int, int, int], ...] = ()


def redact_source_text(text: str) -> str:
    """Conservative redaction; retain every source newline for citation accuracy."""
    result: list[str] = []
    private_key = False
    for line in text.splitlines(keepends=True):
        if "-----BEGIN " in line and "PRIVATE KEY-----" in line:
            private_key = True
        if private_key:
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            result.append("[REDACTED PRIVATE KEY]" + newline)
            if "-----END " in line and "PRIVATE KEY-----" in line:
                private_key = False
            continue
        line = SECRET_ASSIGNMENT.sub(r'\1"[REDACTED]"', line)
        for pattern in TOKEN_PATTERNS:
            line = pattern.sub("[REDACTED]", line)
        result.append(line)
    return "".join(result)


class SourceReader:
    def __init__(self, root: Path, *, documentation: bool = False) -> None:
        self.root = root
        self.documentation = documentation
        self._cache: dict[tuple[str, int], SourceText] = {}
        self._checksums: dict[tuple[str, int], str] = {}

    def checksum(self, path: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> str:
        """Check snapshot freshness without decoding or parsing a stored document."""
        key = (path, max_bytes)
        cached = self._checksums.get(key)
        if cached is not None:
            return cached
        target = self._confined_path(path, max_bytes)
        digest = hashlib.sha256()
        size = 0
        with target.open("rb") as stream:
            while block := stream.read(65_536):
                size += len(block)
                if size > max_bytes:
                    raise ValueError("Source exceeds the configured read limit")
                digest.update(block)
        result = digest.hexdigest()
        self._checksums[key] = result
        return result

    def _confined_path(self, path: str, max_bytes: int) -> Path:
        if not self.documentation:
            return confined_repo_file(self.root, path, max_bytes=max_bytes)
        relative = Path(path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or ":" in relative.as_posix()
            or is_sensitive_path(relative)
        ):
            raise ValueError("Document path must be a safe relative documentation file")
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root) or not target.is_file():
            raise ValueError("Document does not exist within the documentation root")
        if is_sensitive_path(target.relative_to(self.root)):
            raise ValueError("Sensitive document paths are excluded")
        if target.stat().st_size > max_bytes:
            raise ValueError("Document exceeds the configured read limit")
        return target

    def read(self, path: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> SourceText:
        key = (path, max_bytes)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        target = self._confined_path(path, max_bytes)
        with target.open("rb") as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Source exceeds the configured read limit")
        page_ranges: tuple[tuple[int, int, int], ...] = ()
        if self.documentation and target.suffix.lower() == ".pdf":
            raw, page_ranges = extract_clean_pdf(data)
        else:
            if b"\x00" in data:
                raise ValueError("Binary sources are not supported")
            try:
                raw = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError("Source must be valid UTF-8 text") from exc
        redacted = redact_source_text(raw)
        source = SourceText(
            path=target.relative_to(self.root).as_posix(),
            text=redacted,
            checksum=hashlib.sha256(data).hexdigest(),
            redacted=redacted != raw,
            page_ranges=page_ranges,
        )
        self._cache[key] = source
        self._checksums[key] = source.checksum
        return source

    def excerpt(
        self,
        repo_id: str,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> SourceExcerpt:
        if start_line < 1:
            raise ValueError("start_line must be positive")
        requested_end = end_line if end_line is not None else start_line + 79
        if requested_end < start_line:
            raise ValueError("end_line must not precede start_line")
        source = self.read(
            path, max_bytes=MAX_DOCUMENT_BYTES if self.documentation else MAX_SOURCE_BYTES
        )
        lines = source.text.splitlines()
        if start_line > max(len(lines), 1):
            raise ValueError("start_line exceeds the source line count")
        actual_end = min(requested_end, start_line + MAX_EXCERPT_LINES - 1, max(len(lines), 1))
        content = "\n".join(lines[start_line - 1 : actual_end])
        clipped = len(content) > MAX_EXCERPT_CHARS
        if clipped:
            content = content[:MAX_EXCERPT_CHARS]
            actual_end = start_line + content.count("\n")
        return SourceExcerpt(
            repo_id=repo_id,
            file_path=source.path,
            start_line=start_line,
            end_line=actual_end,
            content=content,
            source_snapshot_id=source.checksum,
            redacted=source.redacted,
            truncated=clipped or requested_end > actual_end,
        )


def extract_clean_pdf(data: bytes) -> tuple[str, tuple[tuple[int, int, int], ...]]:
    """Optional clean-text PDF adapter. Page boundaries survive extraction; no OCR."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError(
            "Clean PDF ingestion requires the optional docs extra: pip install -e '.[docs]'"
        ) from exc
    try:
        pdf = PdfReader(BytesIO(data), strict=True)
        if pdf.is_encrypted:
            raise ValueError("Encrypted PDFs are unsupported")
        if len(pdf.pages) > 1_000:
            raise ValueError("PDF exceeds the 1,000-page ingestion limit")
        lines: list[str] = []
        ranges: list[tuple[int, int, int]] = []
        char_count = 0
        for number, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            char_count += len(page_text)
            if char_count > 4_000_000:
                raise ValueError("Extracted PDF text exceeds the ingestion limit")
            if page_text.strip():
                start = len(lines)
                lines.extend(page_text.splitlines())
                ranges.append((number, start, len(lines)))
        if not lines:
            raise ValueError(
                "PDF has no readable text. Scanned/layout documents need an OCR adapter"
            )
        return "\n".join(lines), tuple(ranges)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be safely parsed as a clean-text document") from exc
