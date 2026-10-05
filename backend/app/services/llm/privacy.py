"""Deterministic outbound evidence policy; no automatic cloud escalation."""

import json
import logging
import re
from typing import Any
from urllib.parse import urlsplit

from backend.app.config import Settings
from backend.app.services.project_brain.sources import redact_source_text

audit = logging.getLogger("project_brain.providers")
METADATA_KEYS = {
    "id", "node_id", "type", "name", "symbol_id", "file_path", "language",
    "start_line", "end_line", "source_id", "target_id", "source", "target",
    "confidence", "is_inferred", "project_type", "graph_snapshot_id",
    "related_nodes", "related_edges", "seed_nodes", "expanded_nodes", "nodes", "edges",
    "question",
}


def is_local_destination(settings: Settings, endpoint: str | None) -> bool:
    parsed = urlsplit(endpoint or "")
    hosts = {item.strip().lower() for item in settings.local_llm_hosts.split(",") if item.strip()}
    return parsed.scheme in {"http", "https"} and parsed.hostname in hosts


def _redact_values(value: Any) -> Any:
    if isinstance(value, str):
        return redact_source_text(value)
    if isinstance(value, list):
        return [_redact_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_values(item) for key, item in value.items()}
    return value


def _metadata(value: Any) -> Any:
    if isinstance(value, list):
        return [_metadata(item) for item in value]
    if isinstance(value, dict):
        return {
            key: (
                redact_source_text(re.sub(r"```[\s\S]*?```", "[Code omitted]", str(item)))[:1000]
                if key == "question" else _metadata(item)
            )
            for key, item in value.items() if key in METADATA_KEYS
        }
    if isinstance(value, str):
        return redact_source_text(value)[:300]
    return value


def prepare_messages(
    settings: Settings, messages: list[dict[str, str]], *, model: str, endpoint: str | None,
) -> list[dict[str, str]]:
    local = is_local_destination(settings, endpoint)
    if not local and (settings.local_only or settings.privacy_mode == "local_only"):
        raise ValueError("Local Only blocks external project evidence sharing.")
    mode = "local_only" if local else settings.privacy_mode
    prepared: list[dict[str, str]] = []
    remaining = settings.external_excerpt_max_chars
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        label, separator, payload_text = content.partition(":\n")
        try:
            payload = json.loads(payload_text if separator else content)
        except (ValueError, TypeError):
            payload = None
        if not local and mode == "sanitized":
            if role == "system":
                # Services create system instructions separately from retrieved project text.
                clean = redact_source_text(content)[:4000] + (
                    "\nPrivacy mode supplies a redacted user question and graph metadata only. "
                    "Source excerpts are omitted; implementation behavior remains unverified."
                )
            elif payload is not None:
                clean = "Project graph metadata:\n" + json.dumps(_metadata(payload), ensure_ascii=False)
            else:
                clean = "Source text omitted by sanitized privacy mode."
        else:
            if payload is not None:
                body = json.dumps(_redact_values(payload), ensure_ascii=False)
                clean = (label + ":\n" if separator else "") + body
            else:
                clean = redact_source_text(content)
        if not local and mode in {"sanitized", "relevant_excerpts"}:
            # Bound all outbound message text; truncation is explicit in the prompt.
            if remaining <= 0:
                break
            if len(clean) > remaining:
                suffix = "\n[Evidence truncated by privacy budget]"
                clean = clean[:max(0, remaining - len(suffix))] + suffix[:remaining]
            remaining -= len(clean)
        prepared.append({"role": role, "content": clean})
    audit.info("model=%s external=%s privacy_mode=%s message_chars=%d",
               model, not local, mode, sum(len(item["content"]) for item in prepared))
    return prepared


def prepare_embeddings(settings: Settings, texts: list[str], *, endpoint: str | None) -> list[str]:
    if not is_local_destination(settings, endpoint):
        # Embedding an entire index is a different operation from sending selected chat excerpts.
        raise ValueError("Project embeddings require an explicitly configured local endpoint.")
    return [redact_source_text(text) for text in texts]
