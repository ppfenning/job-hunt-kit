#!/usr/bin/env python3
"""One-shot migration: YAML seeds (or a built index.html) -> state.db.

SQLite is the source of truth now, so the corpus has to get in there once.
Two sources, because the two live in different places:

  --profile <dir>   the YAML seeds, if you still have them
  --from-html <f>   a previously built index.html, which carries the whole
                    seed as an inlined JSON blob plus the rendered chrome

The HTML path exists because a deployed tracker is often the only copy of the
data that is actually current — the seeds sit on whichever laptop last ran a
build, and the deployment is what has been edited since.

Chrome (title, lede, spec chips, footer notes) is recovered from a built file
by aligning it against app/template.html: wherever the template has a
`{{PLACEHOLDER}}`, the built file has the value, and the literal text either
side of the placeholder is the anchor. Verify a migration by rebuilding and
diffing against the original — they should differ only in the seed line.

Idempotent: re-running replaces rows by (kind, id), so a second pass over the
same source is a no-op rather than a duplicate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
import seedlib  # noqa: E402
import state_server as srv  # noqa: E402

TEMPLATE = os.path.join(ROOT, "app", "template.html")

# Placeholders recovered from a built file. TRACK_CSS and TRACK_FILTERS are
# omitted on purpose — both are pure functions of `tracks`, which arrives
# structured in the seed, so re-deriving them beats parsing them back.
CHROME_FIELDS = {
    "TITLE": "title",
    "EYEBROW": "eyebrow",
    "HEADLINE": "headline",
    "LEDE": "lede",
    "SPEC_CHIPS": "specChipsHtml",
    "SKILLS_NOTE": "skillsNote",
    "COMP_OK_LABEL": "compOkLabel",
    "COMP_WARN_LABEL": "compWarnLabel",
    "FOOTER_NOTES": "footerNotesHtml",
    "SIGNATURE": "signature",
    "PREP_INTRO": "prepIntro",
}

SEED_FILES = {
    "profile.yml": {"skillsHave": "skillsHave", "skillsGap": "skillsGap"},
    "roles.yml": {"roles": "roles"},
    "intel.yml": {"intel": "intel"},
    "prep.yml": {"behavioral": "behavioral", "flashcards": "flashcards",
                 "companyPrep": "companyPrep", "sysdesign": "sysdesign"},
    "recruiters.yml": {"recruiters": "recruiters"},
    "contract.yml": {"contractLeads": "contractLeads",
                     "contractPlaybook": "contractPlaybook"},
}


# ---------------------------------------------------------------- sources

def seed_from_yaml(profile_dir: str) -> tuple[dict, dict]:
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML is required for --profile:  pip install pyyaml")

    def load(name):
        path = os.path.join(profile_dir, name)
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    profile = load("profile.yml")
    if not profile:
        sys.exit(f"error: no profile.yml in {profile_dir}")

    seed: dict = {}
    for fname, mapping in SEED_FILES.items():
        data = load(fname)
        for seed_key, yaml_key in mapping.items():
            seed[seed_key] = data.get(yaml_key) or ({} if seed_key == "intel" else [])

    tracks = profile.get("tracks") or [{"id": "all", "label": "All roles"}]
    for i, t in enumerate(tracks):
        t.setdefault("color",
                     seedlib.DEFAULT_TRACK_COLORS[i % len(seedlib.DEFAULT_TRACK_COLORS)])
    seed["tracks"] = tracks
    seed["fitWeights"] = profile.get("fitWeights") or seedlib.DEFAULT_FIT_WEIGHTS
    seed["postingsSurveyed"] = profile.get("postingsSurveyed") or len(seed["roles"])

    chrome = {
        "title": profile.get("title", "Job Hunt"),
        "eyebrow": profile.get("eyebrow", ""),
        "headline": profile.get("headline", "Roles matched to your profile"),
        "lede": profile.get("lede", ""),
        "spec": profile.get("spec") or [],
        "skillsNote": profile.get("skillsNote", ""),
        "compOkLabel": (profile.get("comp") or {}).get("okLabel", "meets target"),
        "compWarnLabel": (profile.get("comp") or {}).get("warnLabel", "caveat"),
        "notes": profile.get("notes") or [],
        "signature": profile.get("signature", ""),
        "prepIntro": profile.get("prepIntro", ""),
        "owner": profile.get("owner", ""),
    }
    return seed, chrome


def extract_chrome(html: str, template: str) -> dict:
    """Recover substituted placeholder values by unifying template with build.

    The template is a sequence of literal runs separated by placeholders. Walk
    both files forward together: each literal run is matched in the built file,
    and whatever sits between two consecutive runs is the value that replaced
    the placeholder between them. Scanning in order — rather than searching for
    each placeholder independently — is what keeps a short anchor like `<h1>`
    from matching the wrong element.
    """
    parts = re.split(r"\{\{([A-Z_]+)\}\}", template)
    literals, names = parts[0::2], parts[1::2]

    values: dict[str, str] = {}
    cursor = html.find(literals[0])
    if cursor == -1:
        print("  ! chrome: built file does not share the template's preamble",
              file=sys.stderr)
        return {}
    cursor += len(literals[0])

    for name, following in zip(names, literals[1:]):
        # Match the whole literal run, not a prefix of it: a short prefix like
        # `</p>\n    <h1>` recurs all over the document, and matching one of
        # those earlier occurrences silently swallows the next few values.
        # The final run holds the seed injection, which the built file has
        # already replaced, so it is truncated at that marker.
        probe = following.split("/*__SEED__*/")[0]
        end = html.find(probe, cursor) if probe else len(html)
        if end == -1:
            print(f"  ! chrome {name}: lost alignment, skipping the rest",
                  file=sys.stderr)
            break
        values[name] = html[cursor:end]
        cursor = end + len(probe)

    return {CHROME_FIELDS[n]: v for n, v in values.items() if n in CHROME_FIELDS}


def seed_from_html(html_path: str) -> tuple[dict, dict]:
    html = open(html_path, encoding="utf-8").read()
    template = open(TEMPLATE, encoding="utf-8").read()

    m = re.search(r'const SEED\s*=\s*', html)
    start = html.index("{", m.end()) if m else html.index('{"roles"')
    depth = 0
    for j in range(start, len(html)):
        if html[j] == "{":
            depth += 1
        elif html[j] == "}":
            depth -= 1
            if depth == 0:
                blob = html[start:j + 1]
                break
    else:
        sys.exit("error: could not find the inlined SEED object")
    seed = json.loads(blob.replace("<\\/", "</"))

    chrome = extract_chrome(html, template)

    # Reverse the two rendered lists back into structured form so they stay
    # editable; the raw HTML is kept as a fallback for anything that does not
    # match the shape build.py emits.
    chips = re.findall(r"<span>(.*?)\s*<b>(.*?)</b></span>",
                       chrome.get("specChipsHtml", ""))
    if chips:
        chrome["spec"] = [{"icon": i.strip(), "label": l} for i, l in chips]
    notes = re.findall(r"<li>(?:<b>(.*?)\.</b>\s*)?(.*?)</li>",
                       chrome.get("footerNotesHtml", ""), re.S)
    if notes:
        chrome["notes"] = [{"title": t or "", "body": b.strip()} for t, b in notes]
    return seed, chrome


# ---------------------------------------------------------------- sink

def write_db(seed: dict, chrome: dict, db_path: str, dry_run: bool = False) -> None:
    seedlib.assign_ids(seed)
    seedlib.normalize_seed(seed)
    problems = seedlib.validate_seed(seed)
    if problems:
        sys.exit("refusing to migrate — seed problems:\n  - " + "\n  - ".join(problems))

    counts: dict[str, int] = {}
    rows: list[tuple] = []
    for kind in seedlib.ENTITY_KINDS:
        items = seed.get(kind)
        if kind == "intel":
            pairs = list((k, v) for k, v in (items or {}).items())
        else:
            pairs = [(item["id"], item) for item in items or []]
        counts[kind] = len(pairs)
        for pos, (ent_id, item) in enumerate(pairs):
            rows.append((kind, ent_id, pos, json.dumps(item, ensure_ascii=False)))

    cfg = {
        "tracks": seed.get("tracks") or [],
        "fitWeights": seed.get("fitWeights") or seedlib.DEFAULT_FIT_WEIGHTS,
        "skillsHave": seed.get("skillsHave") or [],
        "skillsGap": seed.get("skillsGap") or [],
        "postingsSurveyed": seed.get("postingsSurveyed") or counts.get("roles", 0),
        "profile": chrome,
    }

    print(f"  entities: " + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    print(f"  config:   " + ", ".join(sorted(cfg)))
    if dry_run:
        print("  (dry run — nothing written)")
        return

    srv.init_db(db_path)
    con = srv.connect(db_path)
    try:
        now = srv.now_iso()
        con.executemany(
            "INSERT INTO entity(kind, id, pos, data, updated_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT(kind, id) DO UPDATE SET"
            " pos=excluded.pos, data=excluded.data, updated_at=excluded.updated_at",
            [(k, i, p, d, now) for k, i, p, d in rows],
        )
        con.executemany(
            "INSERT INTO config(key, value, updated_at) VALUES (?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET"
            " value=excluded.value, updated_at=excluded.updated_at",
            [(k, json.dumps(v, ensure_ascii=False), now) for k, v in cfg.items()],
        )
        con.commit()
    finally:
        con.close()
    print(f"  wrote {len(rows)} entities + {len(cfg)} config rows -> {db_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--profile", help="directory holding the seed YAML files")
    src.add_argument("--from-html", help="a previously built index.html")
    ap.add_argument("--db", default="state.db", help="sqlite file to write")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.profile:
        print(f"reading YAML seeds from {args.profile}")
        seed, chrome = seed_from_yaml(args.profile)
    else:
        print(f"reading inlined seed from {args.from_html}")
        seed, chrome = seed_from_html(args.from_html)

    write_db(seed, chrome, args.db, args.dry_run)


if __name__ == "__main__":
    main()
