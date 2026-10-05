# Dedicated repository bots

User direction recorded on 2026-10-03. This refines the original master plan; it describes planned behavior, not completed implementation.

Implementation update, 2026-10-04: the dedicated bot records, pages, scoped conversations, request-only OpenAI keys, branch/PR proposals, and documentation watcher are in the source. Compilation and startup evidence are recorded in `BUILD_REPORT.md`. User-repository and model validation remain deferred.

## Confirmed requirements

- The owner selects which repositories get bots.
- Access is private to the owner initially.
- Each bot has its own stable link and repository identity.
- Each bot explains code, teaches the project, and can make code changes.
- Each bot keeps its knowledge, conversations, instructions, and working state scoped to its repository. Cross-repository access requires an explicit future feature.
- Each user supplies their own OpenAI API key to power bot inference. External controller credentials are not requested.
- Code changes use separate branches and pull requests for owner review.
- Documentation changes accompany code changes in the same pull request. Changes made by others trigger a documentation review and a separate documentation proposal when needed.

## Proposed design

1. Add a persistent bot record linked to one repository, with a stable identifier, name, instructions, and model configuration.
2. Add a private bot page and creation flow for selected repositories.
3. Store conversations and reviewed project memory per bot.
4. Retrieve relevant code, documentation, and graph context for each request, with file citations and indexed commit identity.
5. Refresh repository knowledge after changes; display stale indexing state.
6. Accept an OpenAI key in request memory for AI operations. Keep it out of persistent browser storage, database records, logs, and repository files.
7. Add isolated change workspaces and a reviewable diff, then branch and pull-request delivery.
8. Continuously detect repository changes and queue documentation reviews. Use the user's key when they generate a queued proposal; unattended generation needs a separately agreed credential strategy.

Bots can share an inference model while keeping project state isolated. Separate process/container deployment is a further isolation option to clarify before deployment.

## Training strategy

Start with repository retrieval and project-specific instructions. No training or fine-tuning is required to implement dedicated bots. Consider fine-tuning only after reviewed examples and evaluations demonstrate a recurring behavior gap. Saved conversations alone do not retrain the model.

## Pending decisions

- What isolation level is expected beyond separate project data and permissions?
- Which model and hosting configuration should serve the bots? The model is editable per bot; no inference account or OVH deployment has been connected.

Managed GitHub clones use periodic fetch and fast-forward when clean. Local external checkouts are detected after the owner updates them. Repository knowledge is refreshed on commit changes. Optional automatic documentation drafting requires an open bot page and an entered key; continuous unattended AI generation requires a separately agreed credential strategy.

The earlier test deferral and 90% five-hour quota ceiling remain in effect until changed by the owner.
