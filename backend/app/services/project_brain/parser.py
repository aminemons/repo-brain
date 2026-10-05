"""Native document parser preserving heading hierarchy, blocks and source lines."""

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from backend.app.schemas.project_brain import DocumentSection, SourceCard
from backend.app.services.project_brain.sources import SourceText

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}
MAX_SECTION_CHARS = 6_000
MAX_BLOCK_CHARS = 64_000
MAX_SECTIONS = 5_000
ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class ParsedDocument:
    sections: list[DocumentSection]
    parser: Literal["native_markdown", "native_text", "native_pdf"]


def _identifier(*values: str) -> str:
    return hashlib.sha256("\x00".join(values).encode()).hexdigest()[:32]


def parse_document(
    source: SourceText,
    *,
    document_id: str,
    title: str,
    version: int,
    authoritative: bool,
    markdown: bool,
) -> ParsedDocument:
    lines = source.text.splitlines()
    if not source.text.strip():
        raise ValueError("Document is empty")
    # Segment on headings only outside fenced code examples.
    starts: list[tuple[int, int, str]] = [(0, 0, title)]
    if source.page_ranges:
        starts += [(start, 1, f"Page {page}") for page, start, _end in source.page_ranges]
    fence_char = ""
    fence_width = 0
    skip_heading_at = -1
    for index, line in enumerate(lines):
        marker = FENCE.match(line) if markdown else None
        if marker:
            run = marker.group(1)
            if not fence_char:
                fence_char, fence_width = run[0], len(run)
            elif run[0] == fence_char and len(run) >= fence_width:
                fence_char = ""
            continue
        if fence_char or not markdown or index == skip_heading_at:
            continue
        heading_match = ATX_HEADING.match(line)
        if heading_match:
            starts.append((index, len(heading_match.group(1)), heading_match.group(2)))
        elif index + 1 < len(lines) and line.strip():
            underline = lines[index + 1].strip()
            if re.fullmatch(r"={3,}|-{3,}", underline):
                starts.append((index, 1 if underline[0] == "=" else 2, line.strip()))
                skip_heading_at = index + 1

    sections: list[DocumentSection] = []
    stack: list[tuple[int, str, str]] = []
    for segment_index, (start, level, heading) in enumerate(starts):
        end = starts[segment_index + 1][0] if segment_index + 1 < len(starts) else len(lines)
        if start == end or not "\n".join(lines[start:end]).strip():
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][2] if stack else None
        heading_path = [frame[1] for frame in stack] + [heading]
        chunks = _block_chunks(lines, start, end, markdown=markdown)
        first_id: str | None = None
        for chunk_index, (chunk_start, chunk_end) in enumerate(chunks):
            content = "\n".join(lines[chunk_start:chunk_end])
            section_id = _identifier(document_id, str(version), str(chunk_start), content)
            first_id = first_id or section_id
            section = DocumentSection(
                id=section_id,
                document_id=document_id,
                document_title=title,
                version=version,
                authoritative=authoritative,
                parent_id=parent if chunk_index == 0 else first_id,
                level=level if chunk_index == 0 else level + 1,
                ordinal=len(sections),
                heading_path=heading_path,
                content_type=_content_type(content, markdown),
                content=content,
                source=SourceCard(
                    id=section_id,
                    type="documentation",
                    title=title,
                    path=source.path,
                    start_line=chunk_start + 1,
                    end_line=chunk_end,
                    heading_path=heading_path,
                    excerpt=content[:4_000],
                    page=next(
                        (
                            page
                            for page, first, last in source.page_ranges
                            if first <= chunk_start < last
                        ),
                        None,
                    ),
                    source_snapshot_id=source.checksum,
                    document_version=version,
                ),
            )
            sections.append(section)
            if len(sections) > MAX_SECTIONS:
                raise ValueError("Document exceeds the bounded section count")
        if first_id and level:
            stack.append((level, heading, first_id))
    return ParsedDocument(
        sections=sections,
        parser="native_pdf"
        if source.page_ranges
        else "native_markdown"
        if markdown
        else "native_text",
    )


def _block_chunks(
    lines: list[str],
    start: int,
    end: int,
    *,
    markdown: bool,
) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    block_start = start
    fence_char = ""
    fence_width = 0
    for index in range(start, end):
        marker = FENCE.match(lines[index]) if markdown else None
        if marker:
            run = marker.group(1)
            if not fence_char:
                fence_char, fence_width = run[0], len(run)
            elif run[0] == fence_char and len(run) >= fence_width:
                fence_char = ""
        if not lines[index].strip() and not fence_char:
            if index + 1 > block_start:
                blocks.append((block_start, index + 1))
            block_start = index + 1
    if block_start < end:
        blocks.append((block_start, end))
    chunks: list[tuple[int, int]] = []
    chunk_start = start
    chunk_end = start
    size = 0
    for first, last in blocks:
        block_size = sum(len(line) + 1 for line in lines[first:last])
        if block_size > MAX_BLOCK_CHARS:
            raise ValueError("A document block exceeds 64,000 characters; split it at a boundary")
        if size and size + block_size > MAX_SECTION_CHARS:
            chunks.append((chunk_start, chunk_end))
            chunk_start, size = first, 0
        chunk_end = last
        size += block_size
    if chunk_end > chunk_start:
        chunks.append((chunk_start, chunk_end))
    return chunks


def _content_type(content: str, markdown: bool) -> Literal["text", "code", "table", "mixed"]:
    if not markdown:
        return "text"
    code = any(FENCE.match(line) for line in content.splitlines())
    table = bool(re.search(r"(?m)^\s*\|?.+\|.+$", content))
    if code and table:
        return "mixed"
    return "code" if code else "table" if table else "text"
