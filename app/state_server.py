#!/usr/bin/env python3
"""Tiny same-origin static file server + JSON state-sync API for a deployed
job-hunt-kit tracker.

Serves the built index.html (and anything else in --root) exactly like a
plain static host, plus one small API so the interactive state that used to
live only in the browser's localStorage — per-role status/star/notes,
interview-prep flashcard progress, contract-lead notes, recruiter notes —
can sync across devices instead of being siloed per browser origin.

Stdlib only (http.server + sqlite3), so it needs nothing beyond Python 3.9+.
No authentication — this is meant to sit behind whatever access control (or
lack of it) already protects the deployment; it does not add its own.

Storage mirrors localStorage's own shape 1:1: one row per top-level state
key (jobtracker:v1, ipprep:v1, contract:v1, recruiters:v1), value = the raw
JSON blob the page already used to keep in localStorage.

Usage:
    python3 state_server.py --root /opt/dashboard/jobhunt --port 80
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ALLOWED_KEYS = {"jobtracker:v1", "ipprep:v1", "contract:v1", "recruiters:v1"}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def init_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS state ("
        " key TEXT PRIMARY KEY,"
        " value TEXT NOT NULL,"
        " updated_at TEXT NOT NULL"
        ")"
    )
    con.commit()
    con.close()


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


class Handler(BaseHTTPRequestHandler):
    root = "."
    db_path = "state.db"
    server_version = "job-hunt-kit-state/1.0"

    def _json(self, obj, status=200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> None:
        fs_path = "/index.html" if path == "/" else path
        full = os.path.normpath(os.path.join(self.root, fs_path.lstrip("/")))
        if not full.startswith(os.path.abspath(self.root)):
            self.send_error(403)
            return
        if not os.path.isfile(full):
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1]
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            con = sqlite3.connect(self.db_path)
            rows = con.execute("SELECT key, value, updated_at FROM state").fetchall()
            con.close()
            out = {k: {"value": json.loads(v), "updatedAt": u} for k, v, u in rows}
            self._json(out)
            return
        self._static(path)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/api/state/"):
            self.send_error(404)
            return
        key = unquote(path[len("/api/state/"):])
        if key not in ALLOWED_KEYS:
            self._json({"error": f"unknown key {key!r}"}, 400)
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            value = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._json({"error": "invalid json body"}, 400)
            return
        updated_at = now_iso()
        con = sqlite3.connect(self.db_path)
        con.execute(
            "INSERT INTO state(key, value, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value), updated_at),
        )
        con.commit()
        con.close()
        self._json({"ok": True, "updatedAt": updated_at})

    def log_message(self, fmt: str, *args) -> None:  # quieter, timestamped, to stderr
        sys.stderr.write(f"{self.log_date_time_string()} {self.address_string()} {fmt % args}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="directory to serve static files from")
    ap.add_argument("--db", default="state.db", help="sqlite filename, relative to --root")
    ap.add_argument("--port", type=int, default=80)
    args = ap.parse_args()

    Handler.root = os.path.abspath(args.root)
    Handler.db_path = os.path.join(Handler.root, args.db)
    init_db(Handler.db_path)

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"serving {Handler.root} + /api/state on :{args.port}  (db={Handler.db_path})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
