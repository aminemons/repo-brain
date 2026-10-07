# Master plan execution status

Status snapshot: 2026-10-07. The supplied master plan and the owner's clarified repository-bot workflow guide the implementation. The application builds on PorunC/CodeWiki. Owner GitHub access is available; server access and the separate project manual remain unavailable.

## Phase status

| Plan phase | Status | Evidence / remaining gate |
|---|---|---|
| 0 â€” Repository, document, hardware, license audit | In progress | Base commit and MIT license recorded; implementation audit and notices added. Target repository, separate manual corpus, and OVH specifications are unavailable. |
| 1 â€” Read-only code brain | In progress | Existing AST graph, GraphRAG, source citations, Ask UI, and storage are present in the base. Initial root confinement, sensitive-path filtering, auth/configuration, frontend token support, privacy-mode filtering, and backend query routes are now in the working tree; target validation and benchmark remain. |
| 2 â€” Documentation brain and code/document links | In progress | A read-only document ingestion/search/source API, hierarchy parser, exact-reference linker, and UI are in the working tree. The manual is still unavailable; semantic links/conflict detection and target-based acceptance remain. |
| 3 â€” Rich explanation and artifact UX | In progress | Typed answer/artifact schemas, deterministic graph artifacts, versioned artifact storage, and a learning/artifact UI are in the working tree. Render/source validation and user evaluation remain. |
| 4 â€” Onboarding and teaching | In progress | A deterministic structural walkthrough/learning map is present. It has not been reviewed against the target project or tested with a new developer. |
| 5 â€” Hybrid frontier orchestration | In progress | Local-only enforcement, configurable privacy modes, outbound message filtering, and local-only embeddings are in the working tree. No manager/automatic escalation exists; privacy review and benchmark remain. |
| 6 â€” Safe Change mode | In progress | Dedicated bots generate reviewed file proposals, prepare isolated Git branches, and publish pull requests. Documentation reviews are queued on commit changes. A process sandbox for running project commands and target-repository verification remain. |
| 7 â€” Production hardening | In progress | Governance, auth middleware/UI, configurable project/document roots, local-only model policy, and a TLS deployment template are in the working tree. These changes need build/security review, target/host validation, and recovery evidence before public deployment. |
| 8 â€” Optional fine-tuning | Deferred | Requires reviewed usage examples and a validated baseline; not part of the MVP. |

## User-directed scope

The owner selects repositories, creates one bot per repository, and initially has private access. Each bot has a dedicated link, instructions, model choice, persistent conversations, and repository-scoped evidence. Each user supplies an OpenAI key for AI requests. Changes and documentation updates are delivered through branches and pull requests for review. See `REPOSITORY_BOTS_PLAN.md` and `BOT_USER_GUIDE.md` for the updated workflow.

Focused fixture tests cover repository chat, Git changes, and the Najm worker; deployment and browser checks run on Linux CI. The owner can browse repositories through the server's GitHub account. Each chat checks for code changes; edited or deleted documentation is excluded until refreshed. Pinned JavaScript and TypeScript owner projects are used for additional evidence checks. These checks do not execute project commands or make paid model requests. The current server profile supplies private SSH access, persistent storage, and an isolated Najm PNG renderer. See `deploy/SERVER_SETUP.md` and `NAJM_EXPLANATION_MODE.md`.

## Next acceptance gates

1. Extend the pinned owner-repository evidence checks with maintainer-reviewed questions for each chosen bot. GitHub access is available; every repository still needs its own acceptance criteria.
2. Obtain the separate project manual, identify versions and authoritative sections, then choose the parser based on its actual layout.
3. Record OVH hardware and network facts before selecting a local model or claiming capacity.
4. Verify owner authentication, configured-root confinement, backups, and recovery on the actual server before public exposure. Linux CI already checks authentication and storage in containers.
5. Build a maintainer-reviewed evidence benchmark against the actual project before claiming Phase 1 acceptance.
6. Keep write mode, external evidence sharing, and public production exposure behind their respective security and privacy gates.
