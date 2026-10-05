# Project Brain implementation audit

Audit snapshot: 2026-10-03. This file distinguishes the supplied product plan from facts verified in the available checkout. `outputs/project-brain` is the Project Brain platform foundation; it is not the user's target application repository.

## Executive finding

PorunC/CodeWiki is a sound starting point for the first read-only code brain. The available checkout already has a FastAPI backend, React/TypeScript frontend, Tree-sitter-based parsing, repository and symbol graphs, GraphRAG, source citations, wiki generation, LiteLLM integration, incremental update modules, and SQLite/PostgreSQL support. The target application, its approximately 500-page manual, and OVH host have not been supplied, so language fit, document ingestion, hardware sizing, and deployment readiness remain unverified.

Proceed with bounded foundation work against the pinned base. Treat all claims about the target project and its host as unknown until those inputs arrive. Do not describe the base CodeWiki repository as the target project or claim phases complete based on platform capabilities alone.

## Inputs and verified facts

| Area | Audit result | Consequence |
|---|---|---|
| Target Git repository | Not supplied or accessible in this workspace. | Language/framework inventory, repository scale, canonical commands, and target-specific parser validation are pending. |
| Project documentation | The master plan is available; the separate project manual/corpus is not. Its format, version, hierarchy, scans, tables, and figures are unknown. | Do not select or claim a parser/RAGFlow path yet. |
| OVH host | CPU, RAM, GPU/VRAM, disk, drivers, and network details are unknown. | Keep model IDs and endpoints configurable; make no throughput or local-model claims. |
| Base platform | PorunC/CodeWiki checkout at `7be8f702504cbd69aec6491a2e4e81f5311e0ba6`. | Use this exact snapshot as the current implementation baseline. |
| Base license | The pinned checkout includes its MIT `LICENSE`; the parent audit also verified the upstream license at the pinned revision. | Preserve the license and attribution; record the exact source and SHA in `THIRD_PARTY_NOTICES.md`. |
| Execution policy | The user asked to execute the plan and later directed that testing be skipped for now while building the project/plan. | No tests are run in this work tranche. Test execution and host/target validation remain deferred work, not evidence of success. |
| External source policy | The plan restricts GitNexus to architectural reference, walkthrough to reference-only pending a license, and Open WebUI to conceptual inspiration absent license review. | No implementation code from those sources is copied. Recheck licenses and exact SHAs before any additional upstream source is copied. |

## Platform inventory (available checkout only)

- **Backend:** Python 3.12 / FastAPI under `backend/app/`; HTTP routes are grouped in `backend/app/api/`. Main route registration is in `backend/app/main.py`.
- **Repository analysis:** scanning and Git metadata are under `backend/app/services/repo_scanner/`; parser registry and language augmenters are under `backend/app/services/ast_parsers/`; graph analysis and call resolution are under `backend/app/services/graph/` and `backend/app/services/analysis_pipeline.py`.
- **Retrieval and answers:** GraphRAG is under `backend/app/services/graphrag/`; Q&A and LLM gateway/routing are under `backend/app/services/question_answerer.py` and `backend/app/services/llm/`.
- **Persistence:** SQL schema, store, and repositories are under `backend/app/db/`. SQLite is the current default. PostgreSQL and optional pgvector are supported by the platform.
- **Generated knowledge:** wiki generation, citation checks, Mermaid validation, diagram builders, and incremental update code are under `backend/app/services/wiki/` and `backend/app/services/incremental/`.
- **Frontend:** React/TypeScript source is under `frontend/src/`, including Ask, Graph, Wiki, Repos, and Settings pages. Existing visualizations and wiki/source interactions can be extended, but the full planned artifact protocol and teaching modes are not established by this inventory.
- **Current deployment starter:** root `docker-compose.yml` builds one CodeWiki service and defines optional PostgreSQL. It is a development-oriented starter, not the hardened OVH topology in the plan.
- **Authentication:** the current working tree now contains bearer-token middleware, optional owner/viewer tokens, frontend token propagation through session storage, and role checks. These are new in-progress changes and were not exercised here. Deployment must remain gated on a focused access-control review and later verification.

## Parser compatibility snapshot

This records platform capability, not compatibility with the unavailable target repository.

| Language | Parser/augmenter visible in checkout | Target compatibility |
|---|---|---|
| Python | Tree-sitter parser and Python augmenter | Unknown until target scan |
| TypeScript / JavaScript | ECMA augmenter; TypeScript/TSX and JavaScript/JSX are claimed in the base README | Unknown until target scan |
| Java | Parser and augmenter | Unknown until target scan |
| Go | Parser and augmenter | Unknown until target scan |
| Rust | Parser and augmenter | Unknown until target scan |
| C / C++ / C# | Parser/augmenter modules are present | Unknown until target scan |

The actual target language versions, framework conventions, generated/vendor exclusions, parser coverage, and resolution quality require representative source fixtures and target-specific checks once the repository is available.

## Phase 1 file and module plan

Adapt existing boundaries instead of imposing the conceptual monorepo from the plan.

| Capability | Existing base area to extend | Initial Project Brain work |
|---|---|---|
| One configured project root | `backend/app/services/repo_scanner/`, repo API/services, `backend/app/env_config.py` | Introduce a single-project root configuration and enforce canonical-path confinement at every file/repository boundary. Exclude secrets, binaries, generated/vendor files by default. |
| Code/build/config/test index | `services/repo_scanner/`, `services/ast_parsers/`, `services/graph/`, `services/analysis_pipeline.py` | Preserve source snapshot provenance; verify available artifact/config/test coverage against the target when supplied. |
| Evidence retrieval and answer | `services/graphrag/`, `services/question_answerer.py`, `services/llm/`, `api/ask.py`, `schemas/ask.py` | Keep retrieval output structured and source-linked; make unverified claims explicit; implement local-only provider constraints. |
| Read-only interface | `frontend/src/pages/AskPage.tsx`, `frontend/src/ask/`, `frontend/src/api/`, `api/ask.py` | Add source-backed answer presentation without enabling write tools. |
| PostgreSQL deployment profile | `backend/app/db/`, root Compose starter | Supply a production-oriented deployment overlay/profile only after required secrets, root mounts, auth, and proxy settings are explicit. |
| Audit and operations | LLM run recording, API middleware/config, deployment docs | Record provider use and retrieval trace metadata without logging secrets or unnecessary raw content. |

The first acceptance target should be a small, maintainer-approved benchmark against the real repository. The plan recommends 30–50 questions; those cannot be authored accurately until the target and its maintainers' source of truth are available. No write-capable change mode is in the initial scope.

## License and source decision

The pinned PorunC/CodeWiki MIT checkout is the selected base for this tranche. Its existing `LICENSE` and notices must remain intact. This decision does not authorize copying other repositories. The full source inventory and reuse boundaries are recorded in `THIRD_PARTY_NOTICES.md`; all additional upstream material needs a current license check and exact commit record before copying.

## Decisions still requiring project/host inputs

The following are pending configuration inputs, not reasons to stop platform work:

1. Target repository URL/path, access method, default branch, and commercial-use context.
2. Project manual files, version, and authoritative section/source policy.
3. OVH CPU/RAM/GPU/VRAM/disk/network specifications.
4. Expected concurrent users and canonical build/test/lint/typecheck commands.
5. Whether external model calls may receive metadata only or selected source/document excerpts.
6. Whether the first release should create branches/PRs or provide local diffs only.

Until then, keep deployment and model configuration configurable and mark target-specific functionality as unverified.
