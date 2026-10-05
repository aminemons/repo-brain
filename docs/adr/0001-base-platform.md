# ADR 0001: Use the pinned PorunC CodeWiki snapshot as the platform base

- Status: Accepted for the current implementation tranche
- Date: 2026-10-03

## Context

The master plan needs a single-project engineering knowledge platform with repository scanning, AST/code graphs, hybrid retrieval, citations, diagrams, an API, and a web UI. The available checkout already provides a substantial portion of that base. The actual target application and its languages have not yet been supplied, so target compatibility remains unverified.

## Decision

Use PorunC/CodeWiki at commit `7be8f702504cbd69aec6491a2e4e81f5311e0ba6` as the current base. Preserve its MIT license and attribution. Extend its existing module boundaries instead of merging multiple upstream repositories or forcing a new monorepo layout. Keep other projects reference-only unless their exact source revision and license are reviewed before reuse.

## Consequences

- We can build on existing FastAPI/React, parser, graph, GraphRAG, citation, and wiki code.
- The target repository's languages, size, and behavior still need a compatibility audit before calling the platform project-ready.
- Existing multi-repository and development-oriented behaviors must be constrained for a single configured private project.
- Upstream updates require a deliberate diff, license, and migration review; this ADR pins the starting snapshot, not an automatic update policy.
