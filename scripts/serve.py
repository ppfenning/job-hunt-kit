#!/usr/bin/env python3
"""Loopback preview server that declares UTF-8 and never caches.

    python3 scripts/serve.py dist [port]

Bound to 127.0.0.1 on purpose: a seeded tracker holds your salary targets and
recruiter contacts, so it should not be reachable from the rest of the network
without a deliberate decision (see docs/DEPLOY.md).
"""
import functools
import http.server
import socketserver
import sys

DIRECTORY = sys.argv[1] if len(sys.argv) > 1 else "dist"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8899


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(Handler, directory=DIRECTORY)
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"→ http://127.0.0.1:{PORT}/   (serving {DIRECTORY}, Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
