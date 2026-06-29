#!/usr/bin/env python3
"""Tiny HTTP server for cloud runner health checks."""
import http.server
import os
import socketserver

PORT = int(os.environ.get("PORT", "8080"))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"OK - megaplan cloud container alive\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002, N802
        pass  # keep logs quiet


with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print(f"healthserver listening on :{PORT}", flush=True)
    httpd.serve_forever()
