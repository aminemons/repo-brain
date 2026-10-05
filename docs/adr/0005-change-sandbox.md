# ADR 0005: Defer write-capable changes until isolated execution is ready

- Status: Accepted
- Date: 2026-10-03

## Context

The plan requires future code changes to run in isolated worktrees or containers, with explicit tool permissions, captured verification, impact review, and human approval. The current base is a read-oriented repository intelligence platform, and the target repository/build commands have not been supplied.

## Decision

Keep the initial Project Brain deployment read-only. Do not expose write or shell tools as part of the first milestone. Before enabling Change mode, create per-session worktrees/containers, confine mounts to the worktree, run non-root with resource/time limits, block network by default, keep credentials out, log commands and file changes, and require human review of the resulting diff.

## Consequences

- The first milestone can validate retrieval and evidence without a code-execution boundary.
- Tests, lint, and build checks are not run in the current user-directed tranche; they remain necessary before the corresponding implementation can be accepted.
- Write mode needs a separate threat-model review and seeded change benchmark before production use.
