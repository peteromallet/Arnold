#!/usr/bin/env python3
"""Tiny HTTP proxy that strips ``null``-valued JSON fields from request bodies
before forwarding to Fireworks (or any strict OpenAI-compatible endpoint).

Why: DeepSeek's native API tolerates explicit ``"tools": null`` /
``"tool_choice": null`` in the chat-completions / responses body, but stricter
endpoints (e.g. Fireworks GLM) reject them with HTTP 400
``"Input should be a valid list, field: 'tools', value: None"``. The OpenAI
convention is "omit the field when null", so dropping null top-level keys is
always safe. This sits at the HTTP layer so it works regardless of which SDK
method arnold uses to build the request.

Streaming (SSE) is forwarded chunk-by-chunk.

Usage:
    python scripts/fireworks_null_strip_proxy.py \\
        --listen 127.0.0.1:8765 \\
        --upstream https://api.fireworks.ai/inference/v1

Point the agent runtime at it with:
    VIBECOMFY_OPENROUTER_BASE_URL=http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin

import httpx


class ProxyHandler(BaseHTTPRequestHandler):
    upstream: str = ""
    # Hop-by-hop headers that must not be forwarded verbatim.
    _HOP = {
        "host", "content-length", "connection", "keep-alive", "transfer-encoding",
        "te", "trailers", "upgrade", "proxy-authorization", "proxy-authenticate",
    }

    def log_message(self, fmt, *args):  # quieter
        sys.stderr.write("[proxy] " + (fmt % args) + "\n")

    def _forward(self, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""

        # Strip null top-level fields from JSON bodies.
        if body and self.headers.get("Content-Type", "").startswith("application/json"):
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    parsed = {k: v for k, v in parsed.items() if v is not None}
                    body = json.dumps(parsed).encode("utf-8")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # leave body untouched if not valid JSON

        # Build upstream URL: preserve path + query.
        path = self.path
        upstream_url = self.upstream.rstrip("/") + path

        # Forward headers, minus hop-by-hop and host.
        fwd_headers = {
            k: v for k, v in self.headers.items() if k.lower() not in self._HOP
        }
        if body:
            fwd_headers["Content-Length"] = str(len(body))

        is_stream = b'"stream":true' in body or b'"stream": true' in body
        timeout = httpx.Timeout(connect=30.0, read=600.0, write=120.0, pool=30.0)

        try:
            if is_stream:
                with httpx.stream(method, upstream_url, headers=fwd_headers, content=body, timeout=timeout) as up:
                    self._write_head(up)
                    for chunk in up.iter_raw():
                        if chunk:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    self.wfile.flush()
            else:
                with httpx.Client(timeout=timeout) as client:
                    up = client.request(method, upstream_url, headers=fwd_headers, content=body)
                self._write_head(up)
                self.wfile.write(up.content)
                self.wfile.flush()
        except Exception as exc:  # noqa: BLE001
            self.log_message("upstream error: %r", exc)
            try:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                msg = json.dumps({"error": {"message": f"proxy upstream error: {exc}"}}).encode()
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _write_head(self, up) -> None:
        self.send_response(up.status_code)
        for k, v in up.headers.items():
            if k.lower() in self._HOP:
                continue
            self.send_header(k, v)
        # Force chunked for streaming so the client decodes incrementally.
        self.end_headers()

    def do_GET(self): self._forward("GET")
    def do_POST(self): self._forward("POST")
    def do_PUT(self): self._forward("PUT")
    def do_DELETE(self): self._forward("DELETE")
    def do_PATCH(self): self._forward("PATCH")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", default="127.0.0.1:8765")
    ap.add_argument("--upstream", required=True)
    args = ap.parse_args()
    host, _, port = args.listen.rpartition(":")
    ProxyHandler.upstream = args.upstream
    httpd = ThreadingHTTPServer((host or "127.0.0.1", int(port or 8765)), ProxyHandler)
    print(f"[proxy] listening on {args.listen} -> {args.upstream}", file=sys.stderr, flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
