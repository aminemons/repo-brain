"""Safe repository metadata returned by GitHub discovery."""

from pydantic import BaseModel


class GitHubRepository(BaseModel):
    full_name: str
    name: str
    url: str
    private: bool
    default_branch: str
    language: str | None
    archived: bool
    repo_id: str | None = None
    bot_id: str | None = None


class GitHubRepositoriesResponse(BaseModel):
    configured: bool
    account: str | None = None
    repositories: list[GitHubRepository] = []
    next_page: int | None = None
