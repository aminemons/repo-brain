# Third-party notices

This project is currently based on the MIT-licensed PorunC/CodeWiki source snapshot below. Keep the upstream license and attribution with redistributed copies. This file records the implementation source actually present in this checkout; it does not claim that every runtime or development dependency has received a separate legal review.

## Product source

| Component | Use | License / source | Revision | Action |
|---|---|---|---|---|
| PorunC/CodeWiki | Base FastAPI/React application, AST/code graph, GraphRAG, wiki/citations, LiteLLM integration, storage and frontend | MIT; <https://github.com/PorunC/CodeWiki> | `7be8f702504cbd69aec6491a2e4e81f5311e0ba6` | Preserve the repository `LICENSE` and upstream notices. This is the pinned base selected by the implementation audit. |

## Najm renderer

The renderer Docker build fetches Najm from <https://github.com/XMinty77/Najm> at commit `6e898a51c7e7e2f0992a194891491fd1253c246e`. Najm is MIT licensed, copyright Abdelhadi BOUZIANI. Its scene, text, and Skia libraries provide the PNG renderer. The image preserves Najm's `LICENSE` and `THIRD-PARTY-NOTICES.md` under `/app/notices/`.

Najm's bundled Latin Modern Roman and Math fonts retain their GUST Font License; both license texts and font READMEs are copied to that directory. Najm's own notices describe its HarfBuzzSharp dependency and font provenance. The fixed adapter source is in `renderer/`; upstream Najm is fetched during the container build rather than vendored into this source archive.

## Planned or reference-only projects

No source from these projects is recorded as copied into the current product snapshot. The plan's research notes are not a substitute for a current license review at the exact revision before reuse.

| Project | Intended role | Current handling |
|---|---|---|
| FSoft-AI4Code/CodeWiki | Potential selective MIT algorithm reuse for hierarchical decomposition, artifact awareness, and incremental updates | No copied source recorded; recheck license, revision, attribution, and relevant tests before porting. |
| GitNexus | Architecture reference for impact, trace, process, and change intelligence | Reference-only. Plan records PolyForm Noncommercial 1.0.0 at its research date; do not copy or vendor without a new legal review and permission if required. |
| alexanderop/walkthrough | UX reference for interactive walkthroughs | Reference-only. Plan found no visible license at research time; reimplement the interaction pattern. |
| DocAgent | Verification and hierarchical-generation reference | No copied source recorded; recheck exact revision and license before reuse. |
| RAGFlow | Optional document parser/sidecar | Not included as a required dependency in this snapshot. Recheck license, version, resource needs, and deployment requirements before adoption. |
| DeepWiki-Open | Wiki/codemap reference | Reference-only. Do not inherit unsafe filesystem or clone behavior. Recheck current security posture before any integration. |
| Open WebUI | Artifact-panel and sandbox security reference | Reference-only. Plan notes custom license terms; do not copy UI/source absent an approved license review. |
| OpenHands | Optional sandbox/agent-runtime reference | No copied source recorded; recheck exact revision, license, and threat model before integration. |
| AnythingLLM, Tabby | Future/reference only | Not part of the current implementation base. Review license boundaries before adoption. |

## Dependency inventory

The checked-in package manifests and lockfiles are the authoritative list of runtime and development dependencies. They may include transitive third-party packages with their own licenses. A complete dependency-license report has not been generated in this work tranche. Generate and review one before a public/commercial distribution or before adding substantial dependencies.

## Update procedure

For each copied or vendored upstream source change, record its project, exact commit/tag, license, files or algorithms reused, required attribution, and any retained tests. Keep license files and notices intact. Mark architecture-only references clearly so they are not mistaken for approved source reuse.
