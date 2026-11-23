"""The public site, simulated locally: a folder served over HTTP on 127.0.0.1.

Publishing writes files into the folder; verifying fetches them back over HTTP, exactly as an outside
consumer would, so "the file exists" is never mistaken for "the file is published correctly".
"""

from __future__ import annotations

import functools
import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # keep demo output readable
        pass


@contextmanager
def serve(folder: str | Path):
    """Serve `folder` on a free local port for the duration of the block; yields the base URL."""
    handler = functools.partial(_QuietHandler, directory=str(folder))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def fetch(url: str, timeout: float = 5.0) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def read_pointer(site: Path) -> dict | None:
    pointer = site / "latest.json"
    if not pointer.exists():
        return None
    return json.loads(pointer.read_text(encoding="utf-8"))
