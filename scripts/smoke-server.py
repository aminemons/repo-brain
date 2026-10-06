"""Check the deployed containers without a model key or a user repository."""

import json
import os
import shutil
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request
import zlib
from pathlib import Path

NAJM_REVISION = "6e898a51c7e7e2f0992a194891491fd1253c246e"


def check_png(image: bytes) -> None:
    if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 8 * 1024 * 1024:
        raise ValueError("Invalid or oversized Najm PNG")
    position = 8
    compressed = bytearray()
    dimensions = None
    ended = False
    while position + 12 <= len(image):
        size = struct.unpack_from(">I", image, position)[0]
        tag = image[position + 4:position + 8]
        if position + 12 + size > len(image):
            raise ValueError("Truncated PNG chunk")
        data = image[position + 8:position + 8 + size]
        crc = struct.unpack_from(">I", image, position + 8 + size)[0]
        if zlib.crc32(tag + data) & 0xFFFFFFFF != crc:
            raise ValueError("Invalid PNG checksum")
        if tag == b"IHDR":
            dimensions = struct.unpack_from(">II", data)
        elif tag == b"IDAT":
            compressed.extend(data)
        elif tag == b"IEND":
            ended = True
            break
        position += size + 12
    if not ended or not dimensions or not all(200 <= value <= 4096 for value in dimensions):
        raise ValueError("Missing image data or unexpected dimensions")
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, 64 * 1024 * 1024)
    if not decoder.eof or decoder.unconsumed_tail or len(set(pixels)) < 8:
        raise ValueError("PNG pixels are missing, oversized, or blank")
    print("Najm PNG: verified chunks, decoded pixels, dimensions", dimensions)


def main() -> None:
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/bots",
        headers={"Authorization": "Bearer " + os.environ["CODEWIKI_AUTH_TOKEN"]},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        bots = json.load(response)
    print("Application API and owner authentication: OK")
    print("Registered bots:", len(bots["bots"]))
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/api/bots", timeout=10)
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
    else:
        raise ValueError("Bot API accepted a request without the owner token")
    with urllib.request.urlopen("http://127.0.0.1:8000/bots", timeout=10) as response:
        if b"<html" not in response.read().lower():
            raise ValueError("Frontend build is unavailable")
    with tempfile.TemporaryDirectory(dir="/app/storage") as checkout:
        subprocess.run(["git", "init", "--quiet", checkout], check=True)
        Path(checkout, "README.md").write_text("Server storage check\n", encoding="utf-8")
    print("Frontend and writable Git storage: OK")
    with urllib.request.urlopen("http://najm:8080/health", timeout=10) as response:
        health = json.load(response)
    if health.get("status") != "ok":
        raise ValueError("Najm health check failed")
    graph = {
        "version": 1,
        "title": "Repository evidence",
        "nodes": [
            {"id": "S1", "label": "Entry point", "source_ref": "[S1] src/main.py:1-8"},
            {"id": "S2", "label": "Service", "source_ref": "[S2] src/service.py:10-24"},
        ],
        "edges": [{"source": "S1", "target": "S2", "label": "calls"}],
    }
    request = urllib.request.Request(
        "http://najm:8080/render", data=json.dumps(graph).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.headers.get_content_type() != "image/png":
            raise ValueError("Renderer did not return a PNG")
        if response.headers.get("X-Najm-Revision") != NAJM_REVISION:
            raise ValueError("Renderer revision differs from the reviewed pin")
        image = response.read(8 * 1024 * 1024 + 1)
    check_png(image)
    Path("/tmp/najm-smoke.png").write_bytes(image)
    for name, url in (("OpenAI", "https://api.openai.com/"), ("GitHub", "https://github.com/")):
        try:
            urllib.request.urlopen(url, timeout=10).close()
        except urllib.error.HTTPError:
            pass
        print(name + " DNS/TLS connectivity: OK")
    if not shutil.which("gh"):
        raise ValueError("GitHub CLI is missing from the application image")
    print("GitHub CLI: installed")
    print("No model request was made. Enter your OpenAI key and model ID in a bot to test an answer.")


if __name__ == "__main__":
    main()
