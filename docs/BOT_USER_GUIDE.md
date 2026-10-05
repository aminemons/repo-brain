# Your repository bots

Each bot is tied to one repository. Its link, instructions, conversations, change proposals, and documentation queue belong to that bot. Multiple bots can use the same inference model while keeping project state separate.

## Getting started

1. Add the local checkout of a repository through Repos. Choose only repositories you want to use.
2. Open Bots and create a bot for that repository.
3. Open its dedicated link and enter your own OpenAI API key and a model available to your account.
4. Start a conversation to explain code or teach the project. Refresh the index when the repository changes.

The OpenAI key stays in page memory and is sent to the application's backend only for the requested AI operation. The backend calls OpenAI; selected, redacted project excerpts and conversation context leave your machine for those requests. Clearing the key or reloading the page requires entering it again. The application does not store the key in its database or repository. OpenAI API usage is billed to the supplied key's account.

The original local-only Ask workflow remains available. Bot requests with an explicitly supplied OpenAI key use their own provider path.

Provider requests use the Responses API with `store: false`. This disables stored response application state; provider data handling still follows the account's [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data). See the [Responses API guide](https://developers.openai.com/api/docs/guides/migrate-to-responses) for the request contract.

## Code changes

Ask for a change, review the proposed file changes, then apply them to an isolated branch. Publish that branch as a pull request when ready. Your normal checkout and main branch stay available while the proposal is prepared. Publishing requires a GitHub remote and working Git/GitHub credentials on the server. The OpenAI API key provides model access; GitHub credentials provide repository access.

Review code and documentation together. The bot can propose documentation alongside the implementation. Creating a proposal or a branch does not merge it into your main branch.

Proposals use bounded text context and complete file replacements. Large files, unsupported file types, sensitive paths, or files needing secret redaction may be refused. Project commands and tests are not run by this workflow. Review the diff and use your repository's verification process before merging.

## Documentation maintenance

The watcher checks repository commits periodically and queues documentation review when commits change. It performs no model calls and retains no OpenAI key. Open the bot to generate and review documentation updates using your key. The optional automatic drafting switch can generate a proposal while the bot page is open with your key entered. Applying and publishing remain separate review actions.

Documentation drafts cover a bounded batch of changed files. Remaining files stay in the queue for later drafts. A submitted job leaves the queue only after merge evidence is available. If GitHub access is unavailable, a squashed PR's merge may need a later check once access is restored.

With `CODEWIKI_BOT_GITHUB_SYNC_ENABLED=true`, the watcher can fetch and fast-forward clean GitHub checkouts that the application cloned inside its storage directory. Git credentials must already work on the host. It does not reset dirty or diverged checkouts. Repositories registered from an external local path must be updated by their owner; their commits are detected after that update. Continuous detection and key-driven generation have separate lifecycles.

## Access and deployment

Local development binds to 127.0.0.1. Configure an owner access token and TLS before hosting for remote use. Bot links identify a bot; authentication controls access. Initial access is for one owner, with no individual multi-user accounts.

The deployment template's internal network blocks external inference and GitHub access. To use those services on that deployment, the operator must deliberately enable outbound access. Its read-only repository mount also prevents writing Git metadata; branch creation requires an application-managed checkout inside writable storage. Read `deploy/README.md` before deploying.
