# ADR 0003: Route model calls through the existing LiteLLM integration

- Status: Accepted; local-only deployment defaults are being implemented
- Date: 2026-10-03

## Context

The product plan requires local-first operation, provider flexibility, explicit privacy choices, and no routine transmission of the full repository. The base platform already routes model calls through LiteLLM-compatible configuration. OVH accelerator specifications and the eventual local model are unknown.

## Decision

Use the existing model gateway/configuration as the single application interface. Default deployment to local-only behavior. Keep local model host allowlists and model names configurable; do not select a production model or claim its capacity before benchmarking on the OVH host. External providers remain opt-in and must not receive evidence outside the configured privacy policy.

## Consequences

- Application code can remain provider-neutral.
- The UI and audit trail must make external calls visible when hybrid mode is later enabled.
- Local endpoint restrictions, missing-provider behavior, secrets handling, and actual local model quality require implementation and operational review.
