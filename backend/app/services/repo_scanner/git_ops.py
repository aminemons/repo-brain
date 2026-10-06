import os
import subprocess
import tempfile
from pathlib import Path

from backend.app.services.repo_scanner.git import (
    git_file_commit_times,
    git_list_files,
    git_metadata,
)


class GitOperations:
    def metadata(self, repo_path: Path) -> tuple[str | None, str | None]:
        return git_metadata(repo_path)

    def file_commit_times(self, repo_path: Path, file_paths: list[str]) -> dict[str, str]:
        return git_file_commit_times(repo_path, file_paths)

    def list_files(self, repo_path: Path) -> list[str] | None:
        return git_list_files(repo_path)

    def clone(self, git_url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix=".clone-", dir=destination.parent) as staging:
                stage = Path(staging).resolve()
                if not stage.is_relative_to(destination.parent.resolve()):
                    raise ValueError("Clone staging directory is outside repository storage.")
                hooks = stage / "hooks"
                hooks.mkdir()
                config = stage / "empty.gitconfig"
                config.touch()
                env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
                env.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never",
                            "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_SYSTEM": str(config),
                            "GIT_SSH_COMMAND": "ssh -oBatchMode=yes -oConnectTimeout=15"})
                command = ["git", "-c", f"core.hooksPath={hooks}", "-c", f"init.templateDir={hooks}"]
                if env.get("GH_TOKEN") or env.get("GITHUB_TOKEN"):
                    command.extend(["-c", "credential.https://github.com.helper=",
                                    "-c", "credential.https://github.com.helper=!gh auth git-credential"])
                checkout = stage / "checkout"
                subprocess.run(
                    [*command, "clone", "--", git_url, str(checkout)],
                    check=True, capture_output=True, text=True, timeout=180, env=env,
                )
                # A failed clone never becomes the checkout used by a bot. Preserve any
                # existing nonempty directory rather than replacing the owner's files.
                if destination.exists():
                    destination.rmdir()
                checkout.rename(destination)
        except FileNotFoundError as exc:
            raise ValueError("Cannot clone Git URL because the git executable was not found.") from exc
        except subprocess.TimeoutExpired:
            raise ValueError("Repository cloning timed out. Check the server connection and retry.") from None
        except subprocess.CalledProcessError:
            raise ValueError("Could not clone the repository. Check its URL, GitHub permissions, and server connection.") from None
        except OSError:
            raise ValueError("Repository storage is unavailable or the destination is already in use.") from None
        return destination.resolve()
