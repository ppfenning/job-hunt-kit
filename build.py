#!/usr/bin/env python3
"""Render the tracker shell from config held in SQLite.

The shell is chrome only — title, lede, spec chips, track colours, footer
notes. No data is baked in: the page fetches `/api/seed` on load and writes
entities back through the same API, so adding a role or a recruiter is a live
call and never a rebuild.

That means this script is rarely needed. Run it when the *template* changes
(new markup, new view) or when the profile chrome changes — not when the job
search changes.

    python3 build.py --db state.db                 # from a local copy
    python3 build.py --from-api https://jobs.lan   # from the live deployment

Config comes from the `config` table's `profile` and `tracks` rows, which
`scripts/migrate_to_sqlite.py` populates on the way in from YAML.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "app"))
import seedlib  # noqa: E402

TEMPLATE = os.path.join(ROOT, "app", "template.html")


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


# ---------------------------------------------------------------- config in

def config_from_db(db_path: str) -> dict:
    if not os.path.exists(db_path):
        sys.exit(f"error: no such database: {db_path}\n"
                 f"       seed one with scripts/migrate_to_sqlite.py")
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT key, value FROM config").fetchall()
    except sqlite3.OperationalError:
        sys.exit(f"error: {db_path} has no config table — is it a v1 state.db?")
    finally:
        con.close()
    return {k: json.loads(v) for k, v in rows}


def config_from_api(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/config"
    ctx = None
    if url.startswith("https"):
        import ssl
        ctx = ssl._create_unverified_context()  # LAN cert, name may not match
    with urllib.request.urlopen(url, timeout=10, context=ctx) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------- renderers

def render_spec(profile: dict) -> str:
    if profile.get("spec"):
        return "".join(
            f"<span>{esc(c.get('icon',''))} <b>{esc(c.get('label',''))}</b></span>"
            for c in profile["spec"])
    return profile.get("specChipsHtml", "")


def render_notes(profile: dict) -> str:
    if profile.get("notes"):
        items = []
        for note in profile["notes"]:
            title = note.get("title", "")
            prefix = f"<b>{esc(title)}.</b> " if title else ""
            items.append(f"<li>{prefix}{note.get('body','')}</li>")
        return "\n      ".join(items)
    return profile.get("footerNotesHtml", "")


def render_track_filters(tracks: list) -> str:
    parts = ['<button data-filter="all" aria-pressed="true">All</button>']
    for t in tracks:
        parts.append(f'<button data-filter="{esc(t["id"])}" aria-pressed="false">'
                     f'{esc(t["label"])}</button>')
    return "\n        ".join(parts)


def render_track_css(tracks: list) -> str:
    return "\n  ".join(
        f'.chip-{t["id"]}{{color:{t["color"]};'
        f'background:color-mix(in srgb,{t["color"]} 15%,transparent)}}'
        for t in tracks)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--db", default="state.db", help="sqlite file holding config")
    src.add_argument("--from-api", help="base URL of a running deployment")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    if args.from_api:
        cfg = config_from_api(args.from_api)
        source = args.from_api
    else:
        db = args.db if os.path.isabs(args.db) else os.path.join(ROOT, args.db)
        cfg = config_from_db(db)
        source = os.path.relpath(db, ROOT)

    profile = cfg.get("profile") or {}
    tracks = cfg.get("tracks") or [
        {"id": "all", "label": "All roles", "color": seedlib.DEFAULT_TRACK_COLORS[0]}]
    for i, t in enumerate(tracks):
        t.setdefault("color",
                     seedlib.DEFAULT_TRACK_COLORS[i % len(seedlib.DEFAULT_TRACK_COLORS)])

    tmpl = open(TEMPLATE, encoding="utf-8").read()

    # Copy fields may contain inline HTML (<b>, <span class='hl'>) by design.
    subs = {
        "TITLE": esc(profile.get("title", "Job Hunt")),
        "EYEBROW": profile.get("eyebrow", ""),
        "HEADLINE": profile.get("headline", "Roles matched to your profile"),
        "LEDE": profile.get("lede", ""),
        "SPEC_CHIPS": render_spec(profile),
        "SKILLS_NOTE": profile.get("skillsNote", ""),
        "TRACK_FILTERS": render_track_filters(tracks),
        "TRACK_CSS": render_track_css(tracks),
        "COMP_OK_LABEL": esc(profile.get("compOkLabel", "meets target")),
        "COMP_WARN_LABEL": esc(profile.get("compWarnLabel", "caveat")),
        "FOOTER_NOTES": render_notes(profile),
        "SIGNATURE": profile.get("signature", ""),
        "PREP_INTRO": profile.get("prepIntro", ""),
    }
    for key, val in subs.items():
        tmpl = tmpl.replace("{{" + key + "}}", val)

    leftover = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", tmpl)))
    if leftover:
        sys.exit(f"error: unresolved placeholders: {', '.join(leftover)}")

    out_path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(tmpl)

    print(f"built {out_path}  ({len(tmpl):,} bytes)")
    print(f"  config from: {source}")
    print(f"  tracks: {', '.join(t['id'] for t in tracks)}")
    print("  data is served from /api/seed — none is inlined")


if __name__ == "__main__":
    main()
