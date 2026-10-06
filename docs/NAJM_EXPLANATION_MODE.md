# Najm explanation mode

**Illustrate** adds a static evidence map to a repository bot answer. Explain and Teach remain available, and renderer failures preserve the cited text answer.

## What the image means

The map shows up to six retrieved source excerpts. Edges appear only when the stored code graph contains a direct, non-inferred relationship between those excerpts. An image is static repository evidence, not an observed runtime trace. Citations remain beside the answer so the developer can inspect the original code.

The first version exports PNG. Animation, video, interactive browser scenes, and model-generated C# are outside this implementation.

## Integration

Repo Brain owns retrieval, OpenAI requests, bot access, and artifact storage. It creates bounded JSON containing labels, citation references, and verified edges. A separate worker maps that data to a fixed C# scene using [Najm](https://github.com/XMinty77/Najm) and its Skia PNG exporter.

The build fetches and verifies Najm commit `6e898a51c7e7e2f0992a194891491fd1253c246e`. The published .NET 10.0.401 SDK builds the adapter from outside Najm's SDK-pinning directory. The container retains the MIT license and bundled font notices.

Rendering runs with a read-only root filesystem, bounded temporary storage, one active render, a 30-second subprocess deadline, and an 8 MiB output limit. The worker's internal network has no outbound access. It receives no repository checkout, model key, or GitHub credential. The server profile enables it; local development leaves it disabled unless configured.

Each artifact manifest records the repository commit, renderer revision, template version, image digest, evidence IDs, bot ID, and message ID. Artifacts describe the repository state at answer time; historical images are not automatically regenerated after a commit. Images require the owner's application token and a message belonging to that bot.

Najm's inspected text implementation supports plain text and hard line breaks with bundled Latin Modern fonts. The template wraps labels itself. Arabic shaping, bidirectional layout, and general font fallback require further work; a failed render leaves the answer available.

## Verification

Focused backend/provider and worker tests use fixtures. The Linux CI server job builds both containers, checks authenticated access and writable repository storage, and renders a real PNG through the restricted worker. Consult the latest CI run for its result; a mocked test or healthy HTTP process alone does not establish that native rendering works.

No fine-tuning is needed to use this mode. Repository retrieval supplies current evidence and the reviewed template controls the drawing.

## Upstream contribution

[Najm PR #1](https://github.com/XMinty77/Najm/pull/1) is a small documentation proposal explaining this relationship. It remains a draft for maintainer review.
