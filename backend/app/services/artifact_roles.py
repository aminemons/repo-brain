"""Deterministic roles for build, deployment, schema and test knowledge."""

from pathlib import PurePosixPath


def artifact_kind(path: str) -> str:
    file = PurePosixPath(path.lower())
    name, parts = file.name, set(file.parts)
    if ".github" in parts and "workflows" in parts:
        return "ci"
    if name in {".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml"}:
        return "ci"
    if name.startswith(("dockerfile", "docker-compose", "compose.")) or (
        parts & {"deploy", "deployment", "kubernetes", "k8s", "helm", "terraform"}
        and file.suffix in {".yml", ".yaml", ".tf", ".hcl", ".sh", ".json"}
    ):
        return "deployment"
    if name in {"makefile", "cmakelists.txt", "build.gradle", "pom.xml", "package.json",
                "pyproject.toml", "cargo.toml", "go.mod", "requirements.txt"}:
        return "build"
    if file.suffix in {".sql", ".proto", ".graphql", ".prisma"} or name.startswith("openapi."):
        return "schema"
    if parts & {"test", "tests", "__tests__", "spec", "specs"} or (
        name.startswith("test_") or ".test." in name or ".spec." in name
    ):
        return "test"
    if name.startswith("readme") or file.suffix in {".md", ".markdown", ".rst", ".txt"}:
        return "documentation"
    if file.suffix in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}:
        return "configuration"
    return "source"
