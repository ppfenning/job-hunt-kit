#!/usr/bin/env python3
"""Static file server + JSON data API for a deployed job-hunt-kit tracker.

SQLite is the source of truth. The page ships as a shell with no data baked
in, fetches `/api/seed` on load, and writes entities back through the same
API — so adding a recruiter or a role is a live call, not a rebuild.

Three tables, three jobs:

  entity(kind, id, pos, data, updated_at)
      The corpus: roles, recruiters, contractLeads, contractPlaybook,
      behavioral, flashcards, companyPrep, sysdesign, intel. One row per item,
      JSON payload, so heterogeneous shapes (a recruiter's submissions[], a
      role's fit{}) need no schema of their own.

  config(key, value, updated_at)
      tracks, fitWeights, skillsHave/Gap, postingsSurveyed, and the profile
      chrome (title, lede, spec chips, footer notes).

  state(key, value, updated_at)
      Unchanged: the per-viewer interaction overlay the page used to keep in
      localStorage — per-role status/star/notes, flashcard progress, and the
      free-text notes on contract leads and recruiters. Keyed by entity id, so
      it survives an entity edit and is discarded when the entity is deleted.

Writes are validated against `seedlib` before they land. With no build step
left, this is the only gate between a typo and a board that renders broken.

Stdlib only (http.server + sqlite3) — it runs in a bare python:3.12-alpine
container. No authentication: it sits behind whatever access control already
protects the deployment, and adds none of its own.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seedlib  # noqa: E402

ALLOWED_STATE_KEYS = {"jobtracker:v1", "ipprep:v1", "contract:v1", "recruiters:v1"}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    return con


def init_db(path: str) -> None:
    con = connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS state ("
        " key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS entity ("
        " kind TEXT NOT NULL, id TEXT NOT NULL, pos INTEGER NOT NULL DEFAULT 0,"
        " data TEXT NOT NULL, updated_at TEXT NOT NULL,"
        " PRIMARY KEY (kind, id))"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS config ("
        " key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    con.commit()
    con.close()


def read_entities(con: sqlite3.Connection, kind: str) -> list:
    rows = con.execute(
        "SELECT data FROM entity WHERE kind=? ORDER BY pos, id", (kind,)
    ).fetchall()
    return [json.loads(r[0]) for r in rows]


def read_config(con: sqlite3.Connection) -> dict:
    return {k: json.loads(v)
            for k, v in con.execute("SELECT key, value FROM config")}


def assemble_seed(con: sqlite3.Connection) -> dict:
    """The payload the page boots from — same shape the build step used to inline."""
    seed: dict = {}
    for kind in seedlib.ENTITY_KINDS:
        if kind == "intel":
            rows = con.execute(
                "SELECT id, data FROM entity WHERE kind='intel' ORDER BY pos, id"
            ).fetchall()
            seed["intel"] = {rid: json.loads(d) for rid, d in rows}
        else:
            seed[kind] = read_entities(con, kind)

    cfg = read_config(con)
    seed["tracks"] = cfg.get("tracks") or [{"id": "all", "label": "All roles",
                                            "color": seedlib.DEFAULT_TRACK_COLORS[0]}]
    seed["fitWeights"] = cfg.get("fitWeights") or seedlib.DEFAULT_FIT_WEIGHTS
    seed["skillsHave"] = cfg.get("skillsHave") or []
    seed["skillsGap"] = cfg.get("skillsGap") or []
    seed["postingsSurveyed"] = cfg.get("postingsSurveyed") or len(seed["roles"])
    seed["authoritativeSources"] = sorted(seedlib.AUTHORITATIVE_SOURCES)
    seed["profile"] = cfg.get("profile") or {}
    return seed


def next_pos(con: sqlite3.Connection, kind: str) -> int:
    row = con.execute("SELECT COALESCE(MAX(pos), -1) FROM entity WHERE kind=?",
                      (kind,)).fetchone()
    return int(row[0]) + 1


class Handler(BaseHTTPRequestHandler):
    root = "."
    db_path = "state.db"
    server_version = "job-hunt-kit-data/2.0"

    # ---------- plumbing ----------

    def _json(self, obj, status=200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw)

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
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type",
                         CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---------- reads ----------

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        parts = [unquote(p) for p in path.strip("/").split("/")]

        if path == "/api/seed":
            con = connect(self.db_path)
            try:
                self._json(assemble_seed(con))
            finally:
                con.close()
            return

        if path == "/api/state":
            con = connect(self.db_path)
            rows = con.execute("SELECT key, value, updated_at FROM state").fetchall()
            con.close()
            self._json({k: {"value": json.loads(v), "updatedAt": u}
                        for k, v, u in rows})
            return

        if path == "/api/config":
            con = connect(self.db_path)
            try:
                self._json(read_config(con))
            finally:
                con.close()
            return

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "entity":
            kind = parts[2]
            if kind not in seedlib.ENTITY_KINDS:
                self._json({"error": f"unknown kind {kind!r}"}, 404)
                return
            con = connect(self.db_path)
            try:
                self._json(read_entities(con, kind))
            finally:
                con.close()
            return

        self._static(path)

    # ---------- writes ----------

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        parts = [unquote(p) for p in path.strip("/").split("/")]
        try:
            body = self._body()
        except json.JSONDecodeError:
            self._json({"error": "invalid json body"}, 400)
            return

        # /api/state/<key> — the per-viewer overlay, unchanged from v1.
        if len(parts) == 3 and parts[:2] == ["api", "state"]:
            key = parts[2]
            if key not in ALLOWED_STATE_KEYS:
                self._json({"error": f"unknown key {key!r}"}, 400)
                return
            return self._upsert("state", key, body)

        # /api/config/<key>
        if len(parts) == 3 and parts[:2] == ["api", "config"]:
            key = parts[2]
            if key not in seedlib.CONFIG_KEYS:
                self._json({"error": f"unknown config key {key!r}"}, 400)
                return
            return self._upsert("config", key, body)

        # /api/entity/<kind>/<id>
        if len(parts) == 4 and parts[:2] == ["api", "entity"]:
            return self._put_entity(parts[2], parts[3], body)

        self.send_error(404)

    def _upsert(self, table: str, key: str, value) -> None:
        updated_at = now_iso()
        con = connect(self.db_path)
        try:
            con.execute(
                f"INSERT INTO {table}(key, value, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                " value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value), updated_at),
            )
            con.commit()
        finally:
            con.close()
        self._json({"ok": True, "updatedAt": updated_at})

    def _put_entity(self, kind: str, ent_id: str, body) -> None:
        if kind not in seedlib.ENTITY_KINDS:
            self._json({"error": f"unknown kind {kind!r}"}, 404)
            return
        if not isinstance(body, dict):
            self._json({"error": "entity body must be a JSON object"}, 400)
            return

        con = connect(self.db_path)
        try:
            if kind == "intel":
                item, problems = body, []
            else:
                item = seedlib.normalize_item(kind, dict(body, id=ent_id))
                # Validate against the corpus so track ids and fit keys are real.
                problems = seedlib.validate_item(kind, item, assemble_seed(con))
            if problems:
                self._json({"error": "validation failed", "problems": problems}, 422)
                return

            row = con.execute("SELECT pos FROM entity WHERE kind=? AND id=?",
                              (kind, ent_id)).fetchone()
            pos = row[0] if row else next_pos(con, kind)
            updated_at = now_iso()
            con.execute(
                "INSERT INTO entity(kind, id, pos, data, updated_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(kind, id) DO UPDATE SET"
                " data=excluded.data, updated_at=excluded.updated_at",
                (kind, ent_id, pos, json.dumps(item), updated_at),
            )
            con.commit()
        finally:
            con.close()
        self._json({"ok": True, "created": row is None, "updatedAt": updated_at,
                    "item": item})

    def do_POST(self) -> None:
        """Reorder a kind: POST /api/entity/<kind>/reorder  {"ids": [...]}"""
        path = urlparse(self.path).path
        parts = [unquote(p) for p in path.strip("/").split("/")]
        if not (len(parts) == 4 and parts[:2] == ["api", "entity"]
                and parts[3] == "reorder"):
            self.send_error(404)
            return
        kind = parts[2]
        if kind not in seedlib.ENTITY_KINDS:
            self._json({"error": f"unknown kind {kind!r}"}, 404)
            return
        try:
            ids = (self._body() or {}).get("ids") or []
        except json.JSONDecodeError:
            self._json({"error": "invalid json body"}, 400)
            return
        con = connect(self.db_path)
        try:
            for pos, ent_id in enumerate(ids):
                con.execute("UPDATE entity SET pos=? WHERE kind=? AND id=?",
                            (pos, kind, ent_id))
            con.commit()
        finally:
            con.close()
        self._json({"ok": True, "count": len(ids)})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        parts = [unquote(p) for p in path.strip("/").split("/")]
        if not (len(parts) == 4 and parts[:2] == ["api", "entity"]):
            self.send_error(404)
            return
        kind, ent_id = parts[2], parts[3]
        if kind not in seedlib.ENTITY_KINDS:
            self._json({"error": f"unknown kind {kind!r}"}, 404)
            return
        con = connect(self.db_path)
        try:
            cur = con.execute("DELETE FROM entity WHERE kind=? AND id=?",
                              (kind, ent_id))
            con.commit()
            deleted = cur.rowcount
        finally:
            con.close()
        if not deleted:
            self._json({"error": "not found"}, 404)
            return
        self._json({"ok": True, "deleted": ent_id})

    def log_message(self, fmt: str, *args) -> None:  # quieter, timestamped, to stderr
        sys.stderr.write(
            f"{self.log_date_time_string()} {self.address_string()} {fmt % args}\n")


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
    print(f"serving {Handler.root} + /api on :{args.port}  (db={Handler.db_path})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
