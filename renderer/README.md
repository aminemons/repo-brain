# Najm graph renderer

This service renders RepoBrain graph payloads as PNG files through Najm's offline Skia raster
backend. The Docker build fetches the reviewed Najm source commit
`6e898a51c7e7e2f0992a194891491fd1253c246e` and publishes a fixed C# scene. The HTTP process accepts
only graph data; it cannot provide or execute C# code.

## HTTP API

- `GET /health` returns `{"status":"ok","najm_revision":"6e898a51c7e7e2f0992a194891491fd1253c246e"}`.
- `POST /render` accepts `application/json` and returns `image/png`.
- Both successful routes include `X-Najm-Revision` with the pinned commit SHA.

The version 1 body is:

```json
{
  "version": 1,
  "title": "Repository map",
  "nodes": [
    {"id": "S1", "label": "HTTP entry point", "source_ref": "backend/app/api/graph.py:20"}
  ],
  "edges": []
}
```

The worker limits JSON to 32 KiB, six nodes, twelve edges, 120 title characters, 80 characters per
label, 160 characters per source reference, and one active render. It rejects unknown schema fields,
duplicate IDs, and edge endpoints absent from `nodes`. The render subprocess has a 30 second timeout;
the response must be a PNG no larger than 8 MiB.

## Source and notices

The renderer uses Najm's `Typesetter`, `TypesetRequest`, `IDrawContext2D.DrawText`,
`SkiaExport.Png`, and CPU raster surface. The inspected Najm text slice currently supports plain text,
hard line breaks, and its bundled Latin Modern faces; automatic wrapping, bidi, script itemization,
and general font fallback are not implemented. This template inserts line breaks itself and limits
its content to the graph contract.

The container copies Najm's MIT license, its third-party notice, and both bundled font license texts
to `/app/notices/`. Font assets retain the GUST Font License and remain separate from Najm's MIT
license. Najm's `THIRD-PARTY-NOTICES.md` documents the HarfBuzzSharp and font provenance.

The service is intended to run in Docker. It does not install .NET or clone Najm into the RepoBrain
working tree on the host.
