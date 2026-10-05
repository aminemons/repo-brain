"""Shared project confinement and provider policy for HTTP, CLI and MCP."""

from pathlib import Path
from urllib.parse import urlsplit

from backend.app.config import Settings, get_settings


def validate_project_root(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    allowed = get_settings().project_root
    if allowed is not None and resolved != allowed.expanduser().resolve():
        raise ValueError("Repository is outside the configured project root.")
    return resolved


def is_sensitive_path(path: Path | str) -> bool:
    parts = Path(path).parts
    if any(part.lower() in {
        ".git", ".ssh", ".aws", ".gnupg", ".docker", ".kube", ".azure", ".gcloud",
        "gcloud", "secrets",
    } for part in parts):
        return True
    name = Path(path).name.lower()
    if name in {".env.example", ".env.sample", ".env.template"}:
        return False
    return (
        name == ".env" or name.startswith(".env.")
        or name in {
            "id_rsa", "id_ed25519", "credentials", "credentials.json", ".npmrc", ".pypirc",
            ".netrc", "_netrc", ".git-credentials", ".s3cfg", "service-account.json",
            "application_default_credentials.json",
        }
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
    )


def confined_repo_file(
    repo_root: Path | str, relative_path: Path | str, *, max_bytes: int = 2_000_000
) -> Path:
    root = validate_project_root(repo_root)
    relative = Path(relative_path)
    if (
        relative.is_absolute() or relative.drive or ":" in relative.as_posix()
        or ".." in relative.parts or is_sensitive_path(relative)
    ):
        raise ValueError("Source path must be a safe relative project file.")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Source path escapes the project root.")
    if is_sensitive_path(candidate.relative_to(root)):
        raise ValueError("Source path resolves to an excluded credential file.")
    if not candidate.is_file():
        raise ValueError("Source file does not exist.")
    if candidate.stat().st_size > max_bytes:
        raise ValueError("Source file exceeds the configured size limit.")
    return candidate


def validate_model_destination(
    settings: Settings, *, model: str, endpoint: str | None, provider_type: str | None
) -> None:
    if not model or model.startswith("provider/"):
        raise ValueError("Configure a local model and endpoint before using AI answers.")
    if not settings.local_only and settings.privacy_mode != "local_only":
        return
    provider = (provider_type or model.partition("/")[0]).lower()
    if provider not in {"ollama", "ollama_chat", "openai", "hosted_vllm"}:
        raise ValueError("Local Only blocks this model provider. Configure a local endpoint.")
    parsed = urlsplit(endpoint or "")
    hosts = {host.strip().lower() for host in settings.local_llm_hosts.split(",") if host.strip()}
    if (
        parsed.scheme not in {"http", "https"} or parsed.hostname not in hosts
        or parsed.username is not None or parsed.password is not None
        or parsed.fragment or parsed.query
    ):
        raise ValueError("Local Only requires an explicit endpoint on an allowed local model host.")
