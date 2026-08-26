#!/usr/bin/env python3
"""Build a self-contained job-hunt tracker from a profile of YAML seed files.

    python3 build.py --profile profiles/example
    python3 build.py --profile profiles/private/me --out dist/index.html --serve

The output is one HTML file with no external requests, so it works from
file://, a Home Assistant /local/ folder, or any static host.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required:  pip install pyyaml   (or: apt install python3-yaml)")

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT, "app", "template.html")

# seed file -> {key in SEED: yaml top-level key}. Missing files are tolerated so
# a half-seeded profile still builds; the matching view just renders empty.
SEED_FILES = {
    "profile.yml": {"skillsHave": "skillsHave", "skillsGap": "skillsGap"},
    "roles.yml": {"roles": "roles"},
    "intel.yml": {"intel": "intel"},
    "prep.yml": {
        "behavioral": "behavioral",
        "flashcards": "flashcards",
        "companyPrep": "companyPrep",
        "sysdesign": "sysdesign",
    },
    "recruiters.yml": {"recruiters": "recruiters"},
    "contract.yml": {"contractLeads": "contractLeads",
                     "contractPlaybook": "contractPlaybook"},
}

DEFAULT_TRACK_COLORS = ["var(--accent)", "#8E6BB5", "#B7862B", "#2E7D5B", "#B65A34"]

# How a role's fit score breaks down. Keys must match the `fit:` keys used in
# roles.yml; `max` values are what the bars are drawn against.
DEFAULT_FIT_WEIGHTS = [
    {"key": "stack", "label": "Stack", "max": 35},
    {"key": "level", "label": "Level", "max": 20},
    {"key": "comp", "label": "Comp", "max": 20},
    {"key": "ml", "label": "Leverage", "max": 15},
    {"key": "remote", "label": "Remote", "max": 10},
]


def load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def build_seed(profile_dir: str) -> tuple[dict, dict]:
    profile = load_yaml(os.path.join(profile_dir, "profile.yml"))
    if not profile:
        sys.exit(f"error: no profile.yml in {profile_dir}")

    seed: dict = {}
    for fname, mapping in SEED_FILES.items():
        data = load_yaml(os.path.join(profile_dir, fname))
        for seed_key, yaml_key in mapping.items():
            seed[seed_key] = data.get(yaml_key) or ([] if seed_key != "intel" else {})

    tracks = profile.get("tracks") or [{"id": "all", "label": "All roles"}]
    for i, t in enumerate(tracks):
        t.setdefault("color", DEFAULT_TRACK_COLORS[i % len(DEFAULT_TRACK_COLORS)])
    seed["tracks"] = tracks
    seed["fitWeights"] = profile.get("fitWeights") or DEFAULT_FIT_WEIGHTS
    seed["postingsSurveyed"] = profile.get("postingsSurveyed") or len(seed["roles"])

    _normalize(seed)
    _validate(seed)
    return seed, profile


# The renderers call .map() on these directly, so a half-seeded entry would
# throw rather than render empty. Fill them in at build time instead.
LIST_DEFAULTS = {
    "roles": ["stack", "points"],
    "behavioral": ["tags"],
    "companyPrep": ["themes", "yourAngles", "askThem"],
    "sysdesign": ["approach", "tradeoffs"],
    "recruiters": ["submissions"],
}
STR_DEFAULTS = {
    "roles": ["why", "jd", "cv", "comp", "basisTxt", "verif", "level", "remote", "url"],
    "behavioral": ["s", "t", "a", "r", "tip"],
    "companyPrep": ["focus", "theyValue", "watchOut", "role"],
    "sysdesign": ["prompt", "yourEdge"],
    "recruiters": ["email", "phone", "linkedin", "notes", "lastContact", "nextTouch"],
    "contractLeads": ["co", "role", "rate", "structure", "len", "stage",
                      "contact", "notes", "channel"],
}


def _normalize(seed: dict) -> None:
    for key, fields in LIST_DEFAULTS.items():
        for item in seed.get(key) or []:
            for f in fields:
                if not isinstance(item.get(f), list):
                    item[f] = []
    for key, fields in STR_DEFAULTS.items():
        for item in seed.get(key) or []:
            for f in fields:
                item[f] = "" if item.get(f) is None else str(item[f]).strip()
    for r in seed.get("roles") or []:
        r.setdefault("fit", {})
        r.setdefault("basis", "ok")
        r.setdefault("verifState", "ok")
        if "compSort" not in r:
            r["compSort"] = 0
        if "total" not in r["fit"]:
            r["fit"]["total"] = sum(
                v for k, v in r["fit"].items() if isinstance(v, (int, float)))


def _validate(seed: dict) -> None:
    """Catch the seed mistakes that would render as a broken board."""
    problems: list[str] = []
    track_ids = {t["id"] for t in seed["tracks"]}
    fit_keys = [w["key"] for w in seed["fitWeights"]]

    seen: set[str] = set()
    for i, r in enumerate(seed.get("roles") or []):
        where = f"roles[{i}] ({r.get('company', '?')})"
        for req in ("id", "company", "title", "track", "tier"):
            if not r.get(req):
                problems.append(f"{where}: missing required field `{req}`")
        rid = r.get("id")
        if rid in seen:
            problems.append(f"{where}: duplicate id `{rid}` — saved status would collide")
        seen.add(rid)
        if r.get("track") and r["track"] not in track_ids:
            problems.append(
                f"{where}: track `{r['track']}` is not one of {sorted(track_ids)}")
        if r.get("tier") not in ("gold", "silver", "bronze", None):
            problems.append(f"{where}: tier `{r.get('tier')}` must be gold/silver/bronze")
        fit = r.get("fit") or {}
        missing = [k for k in fit_keys if k not in fit]
        if fit and missing:
            problems.append(f"{where}: fit is missing {missing}")

    companies = {r.get("company") for r in seed.get("roles") or []}
    for name in seed.get("intel") or {}:
        if name not in companies:
            problems.append(
                f"intel['{name}'] matches no role company — it will never show")

    if problems:
        sys.exit("seed problems:\n  - " + "\n  - ".join(problems))


def render_spec(profile: dict) -> str:
    out = []
    for chip in profile.get("spec") or []:
        icon = esc(chip.get("icon", ""))
        label = esc(chip.get("label", ""))
        out.append(f"<span>{icon} <b>{label}</b></span>")
    return "".join(out)


def render_track_filters(tracks: list) -> str:
    parts = ['<button data-filter="all" aria-pressed="true">All</button>']
    for t in tracks:
        parts.append(
            f'<button data-filter="{esc(t["id"])}" aria-pressed="false">'
            f'{esc(t["label"])}</button>'
        )
    return "\n        ".join(parts)


def render_track_css(tracks: list) -> str:
    rules = []
    for t in tracks:
        color = t["color"]
        rules.append(
            f'.chip-{t["id"]}{{color:{color};'
            f"background:color-mix(in srgb,{color} 15%,transparent)}}"
        )
    return "\n  ".join(rules)


def render_notes(profile: dict) -> str:
    items = []
    for note in profile.get("notes") or []:
        title = note.get("title", "")
        body = note.get("body", "")
        prefix = f"<b>{esc(title)}.</b> " if title else ""
        items.append(f"<li>{prefix}{body}</li>")
    return "\n      ".join(items)


def auto_signature(seed: dict, profile: dict) -> str:
    roles = seed.get("roles") or []
    bits = [f"{len(roles)} role{'s' if len(roles) != 1 else ''}"]
    counts: dict[str, int] = {}
    for r in roles:
        counts[r.get("track", "")] = counts.get(r.get("track", ""), 0) + 1
    labels = {t["id"]: t["label"] for t in seed["tracks"]}
    if len(counts) > 1:
        bits.append(" / ".join(f"{n} {labels.get(k, k)}" for k, n in counts.items()))
    owner = profile.get("owner")
    if owner:
        bits.append(f"private to {esc(owner)}")
    return " · ".join(bits)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="profiles/example",
                    help="directory holding the seed YAML files")
    ap.add_argument("--out", default="dist/index.html", help="output HTML file")
    ap.add_argument("--serve", action="store_true",
                    help="serve the result on http://127.0.0.1:8899 after building")
    args = ap.parse_args()

    profile_dir = args.profile if os.path.isabs(args.profile) \
        else os.path.join(ROOT, args.profile)
    if not os.path.isdir(profile_dir):
        sys.exit(f"error: no such profile directory: {profile_dir}")

    seed, profile = build_seed(profile_dir)
    tmpl = open(TEMPLATE, encoding="utf-8").read()

    # Copy fields may contain inline HTML (<b>, <span class='hl'>) by design.
    subs = {
        "TITLE": esc(profile.get("title", "Job Hunt")),
        "EYEBROW": profile.get("eyebrow", ""),
        "HEADLINE": profile.get("headline", "Roles matched to your profile"),
        "LEDE": profile.get("lede", ""),
        "SPEC_CHIPS": render_spec(profile),
        "SKILLS_NOTE": profile.get("skillsNote", ""),
        "TRACK_FILTERS": render_track_filters(seed["tracks"]),
        "TRACK_CSS": render_track_css(seed["tracks"]),
        "COMP_OK_LABEL": esc((profile.get("comp") or {}).get("okLabel", "meets target")),
        "COMP_WARN_LABEL": esc((profile.get("comp") or {}).get("warnLabel", "caveat")),
        "FOOTER_NOTES": render_notes(profile),
        "SIGNATURE": profile.get("signature") or auto_signature(seed, profile),
        "PREP_INTRO": profile.get("prepIntro", ""),
    }
    for key, val in subs.items():
        tmpl = tmpl.replace("{{" + key + "}}", val)

    leftover = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", tmpl)))
    if leftover:
        sys.exit(f"error: unresolved placeholders: {', '.join(leftover)}")

    # </script> inside a JSON string would close the block early.
    payload = json.dumps(seed, ensure_ascii=False).replace("</", "<\\/")
    tmpl = tmpl.replace("/*__SEED__*/ null", payload, 1)

    out_path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(tmpl)

    counts = ", ".join(
        f"{k}={len(v)}" for k, v in seed.items()
        if isinstance(v, (list, dict)) and k != "tracks"
    )
    print(f"built {out_path}  ({len(tmpl):,} bytes)")
    print(f"  profile: {os.path.relpath(profile_dir, ROOT)}")
    print(f"  {counts}")

    if args.serve:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        os.execv(sys.executable, [sys.executable,
                                  os.path.join(ROOT, "scripts", "serve.py"),
                                  os.path.dirname(out_path)])


if __name__ == "__main__":
    main()
