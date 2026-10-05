# ADR 0004: Prefer structured artifacts and isolate freeform content

- Status: Accepted
- Date: 2026-10-03

## Context

The product needs diagrams, source cards, diffs, and interactive walkthroughs. CodeWiki already supports source-linked wiki content and Mermaid validation. The master plan warns that generated HTML/JavaScript can cross the application security boundary.

## Decision

Represent answers and artifacts with validated structured schemas where practical. Generate graph topology from indexed source facts. Prefer native frontend renderers for diagrams, source cards, and callouts. If arbitrary HTML/JS is introduced, render it in a separate sandboxed iframe with a restrictive CSP, blocked outbound network access, no same-origin privileges by default, and no application credentials.

## Consequences

- Artifacts can be validated against real source entities and snapshots.
- Freeform artifacts require additional isolation and browser-policy review.
- Interactive artifact work is not a prerequisite for the read-only evidence milestone.
