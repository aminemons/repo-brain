# Project Brain acceptance checklist

Use this checklist with the phase tracker. A checked box means there is reviewable evidence attached to the change or release. Do not mark a phase accepted because the base platform has a similarly named feature.

## Phase 0 — Inputs and license audit

- [ ] Record the target repository URL/path, branch, snapshot commit, commercial-use context, and access owner.
- [ ] Inventory languages/frameworks, repository size, generated/vendor areas, manifests, database/config/build/CI files, and canonical test commands.
- [ ] Record the documentation files, versions, page/section structure, scans, tables, figures, and authoritative sources.
- [ ] Record OVH CPU, RAM, GPU/VRAM, drivers, disk, and expected concurrent users.
- [ ] Record upstream projects copied, exact revisions, licenses, attribution, and tests preserved.
- [ ] Document unresolved inputs as unknown; do not guess model sizing or source-of-truth policy.

## Phase 1 — Read-only code brain

- [ ] Every repository/file operation is confined to the configured project root, including symlink cases.
- [ ] Secret paths, generated/vendor paths, binaries, and oversized files follow documented exclusions.
- [ ] Target language parsers produce source references that resolve to the recorded snapshot.
- [ ] Maintainer-approved location, call-flow, dependency, route, and configuration questions retrieve expected evidence.
- [ ] Every project-specific claim has supporting evidence or an explicit unverified status.
- [ ] Viewer and owner roles are enforced server-side; viewer POST access is limited to approved read-query endpoints.
- [ ] Local-only mode rejects external model endpoints and embeddings. Any hybrid mode obeys its configured privacy budget.
- [ ] Sanitized mode preserves the redacted user question and removes code/source excerpts; selected privacy modes are logged without logging message bodies.
- [ ] Local-only override and configured hybrid modes behave as documented, with no automatic provider escalation.
- [ ] No write or shell tools are available in Ask/Teach/read-only modes.

## Phase 2 — Documentation intelligence

- [ ] Ingestion preserves document version, heading hierarchy, page ranges, and table/figure boundaries.
- [ ] Retrieval returns the expected section/page for maintainer-approved questions.
- [ ] Exact doc-code links have source provenance; semantic links remain marked inferred until reviewed.
- [ ] Known documentation/implementation disagreements are surfaced as conflicts.
- [ ] Document-only and code-only behavior remain distinguishable in answers.

## Phase 3 — Explanations and artifacts

- [ ] Typed answer/artifact responses validate against server and frontend schemas.
- [ ] Graph-derived diagrams use actual indexed nodes and edges.
- [ ] Every source path/line resolves to the indexed snapshot.
- [ ] Artifact previews are isolated and have restrictive content/network policies.
- [ ] A new developer can follow one maintainer-reviewed feature explanation end to end.

## Later phases

- [ ] Phase 4 onboarding path has maintainer review and follows actual project dependencies.
- [ ] Phase 5 privacy modes and external provider calls are visible and benchmarked against local-only results.
- [ ] Phase 6 change mode uses isolated worktrees/sandboxes, captures commands and verification, and requires approval.
- [ ] Phase 7 deployment has verified TLS, auth, backups/restore, egress policy, health/recovery procedures, and dependency review.
- [ ] Phase 8 fine-tuning is considered only with reviewed data and measured grounding against a baseline.

## Verification record

For each accepted phase, record the snapshot/commit, benchmark dataset version, commands run, results, known failures, reviewer, and date. Keep deferred checks visibly pending rather than marking them as passes.
