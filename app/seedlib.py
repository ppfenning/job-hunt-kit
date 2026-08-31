"""Seed shape: defaults, normalisation, and validation. Stdlib only.

This module is the single definition of what a well-formed seed looks like.
It is imported by three callers with different jobs:

  * `state_server.py` — validates on every write, because with SQLite as the
    source of truth there is no build step left to catch a bad entity.
  * `scripts/migrate_to_sqlite.py` — validates the whole corpus once, on the
    way in from YAML.
  * `build.py` — renders the shell, and still checks what it reads.

It must stay dependency-free: the server runs in a python:3.12-alpine
container with nothing installed. No PyYAML here.
"""
from __future__ import annotations

import hashlib
import json

# Collections stored one row per item in `entity`, keyed by the item's own id.
# `intel` is the odd one out — a dict keyed by company name, not a list — so it
# is stored with the company name as the entity id.
ENTITY_KINDS = (
    "roles",
    "recruiters",
    "contractLeads",
    "contractPlaybook",
    "behavioral",
    "flashcards",
    "companyPrep",
    "sysdesign",
    "intel",
)

# Scalars and small config objects, one row per key in `config`.
CONFIG_KEYS = (
    "tracks",
    "fitWeights",
    "postingsSurveyed",
    "skillsHave",
    "skillsGap",
    "authoritativeSources",
    "profile",
)

DEFAULT_TRACK_COLORS = ["var(--accent)", "#8E6BB5", "#B7862B", "#2E7D5B", "#B65A34"]

DEFAULT_FIT_WEIGHTS = [
    {"key": "stack", "label": "Stack", "max": 35},
    {"key": "level", "label": "Level", "max": 20},
    {"key": "comp", "label": "Comp", "max": 20},
    {"key": "ml", "label": "Leverage", "max": 15},
    {"key": "remote", "label": "Remote", "max": 10},
]

# Provenance. AUTHORITATIVE_SOURCES are boards where the employer enters the
# posting itself, so the band and remote flag are first-hand. The rest are
# retellings — aggregators republish stale bands, and a recruiter's "up to
# $230K" is a sales figure, not a posted range.
AUTHORITATIVE_SOURCES = {"Ashby", "Greenhouse", "Lever", "Direct", "Wellfound"}
SECONDHAND_SOURCES = {"BuiltIn", "LinkedIn", "Recruiter", "Referral", "Other"}
ROLE_SOURCES = AUTHORITATIVE_SOURCES | SECONDHAND_SOURCES

RECRUITER_TYPES = ("Agency", "Internal", "Platform")
RECRUITER_TRACKS = ("FTE", "Contract", "Both")
CONTRACT_CHANNELS = ("Agency", "Direct", "Platform")
CONTRACT_STAGES = ("Lead", "Screening", "Submitted", "Interviewing",
                   "Negotiating", "Won", "Passed")

# The renderers call .map() on these directly, so a half-filled entry would
# throw rather than render empty. Fill them in before they reach the page.
LIST_DEFAULTS = {
    "roles": ["stack", "points"],
    "behavioral": ["tags"],
    "companyPrep": ["themes", "yourAngles", "askThem"],
    "sysdesign": ["approach", "tradeoffs"],
    "recruiters": ["submissions"],
}
STR_DEFAULTS = {
    "roles": ["why", "jd", "cv", "comp", "basisTxt", "verif", "level", "remote",
              "url", "source"],
    "behavioral": ["s", "t", "a", "r", "tip"],
    "companyPrep": ["focus", "theyValue", "watchOut", "role"],
    "sysdesign": ["prompt", "yourEdge"],
    "recruiters": ["email", "phone", "linkedin", "notes", "lastContact", "nextTouch"],
    "contractLeads": ["co", "role", "rate", "structure", "len", "stage",
                      "contact", "notes", "channel"],
}


class SeedError(ValueError):
    """A seed or entity that would render as a broken board."""


# The field that naturally identifies an item, for kinds whose seed format
# carried no `id` of its own.
NATURAL_KEY = {
    "companyPrep": "company",
    "contractPlaybook": "h",
    "sysdesign": "prompt",
    "behavioral": "title",
    "flashcards": "q",
}


def slugify(text: str, limit: int = 48) -> str:
    out, prev_dash = [], False
    for ch in str(text).lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash and out:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")[:limit] or ""


def derive_id(kind: str, item: dict) -> str:
    """A stable id for an item that arrived without one.

    Content-derived rather than positional: these ids key the interaction
    overlay (flashcard progress, per-lead notes), so an id that shifts when you
    reorder a list would silently reattach someone's notes to a different item.
    """
    if item.get("id"):
        return str(item["id"])
    natural = item.get(NATURAL_KEY.get(kind, ""), "")
    slug = slugify(natural)
    if slug and kind != "flashcards":
        return slug
    digest = hashlib.sha1(
        json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:8]
    prefix = slugify(natural, 24)
    return f"{prefix}-{digest}" if prefix else f"{kind}-{digest}"


def assign_ids(seed: dict) -> dict:
    """Give every item an id, in place, before anything validates it."""
    for kind in ENTITY_KINDS:
        if kind == "intel":
            continue
        for item in seed.get(kind) or []:
            item["id"] = derive_id(kind, item)
    return seed


def normalize_item(kind: str, item: dict) -> dict:
    """Fill in the defaults a renderer assumes. Returns the same dict."""
    for field in LIST_DEFAULTS.get(kind, []):
        if not isinstance(item.get(field), list):
            item[field] = []
    for field in STR_DEFAULTS.get(kind, []):
        item[field] = "" if item.get(field) is None else str(item[field]).strip()
    if kind == "roles":
        item.setdefault("fit", {})
        item.setdefault("basis", "ok")
        item.setdefault("verifState", "ok")
        item.setdefault("compSort", 0)
        if "total" not in item["fit"]:
            item["fit"]["total"] = sum(
                v for k, v in item["fit"].items() if isinstance(v, (int, float)))
    return item


def normalize_seed(seed: dict) -> dict:
    for kind in ENTITY_KINDS:
        if kind == "intel":
            continue
        for item in seed.get(kind) or []:
            normalize_item(kind, item)
    return seed


def validate_item(kind: str, item: dict, seed: dict | None = None) -> list[str]:
    """Problems with one entity. `seed` enables the cross-entity checks."""
    seed = seed or {}
    where = f"{kind}[{item.get('id', '?')}]"
    problems: list[str] = []

    if not item.get("id"):
        problems.append(f"{where}: missing required field `id`")

    if kind == "roles":
        for req in ("company", "title", "track", "tier"):
            if not item.get(req):
                problems.append(f"{where}: missing required field `{req}`")
        track_ids = {t["id"] for t in (seed.get("tracks") or [])}
        if track_ids and item.get("track") and item["track"] not in track_ids:
            problems.append(
                f"{where}: track `{item['track']}` is not one of {sorted(track_ids)}")
        if item.get("tier") not in ("gold", "silver", "bronze", None):
            problems.append(f"{where}: tier `{item.get('tier')}` must be gold/silver/bronze")
        if item.get("source") and item["source"] not in ROLE_SOURCES:
            problems.append(
                f"{where}: source `{item['source']}` is not one of {sorted(ROLE_SOURCES)}")
        fit_keys = [w["key"] for w in (seed.get("fitWeights") or [])]
        fit = item.get("fit") or {}
        missing = [k for k in fit_keys if k not in fit]
        if fit_keys and fit and missing:
            problems.append(f"{where}: fit is missing {missing}")

    elif kind == "recruiters":
        if not item.get("name"):
            problems.append(f"{where}: missing required field `name`")
        if item.get("type") and item["type"] not in RECRUITER_TYPES:
            problems.append(f"{where}: type must be one of {list(RECRUITER_TYPES)}")
        if item.get("track") and item["track"] not in RECRUITER_TRACKS:
            problems.append(f"{where}: track must be one of {list(RECRUITER_TRACKS)}")
        for sub in item.get("submissions") or []:
            if not sub.get("co"):
                problems.append(f"{where}: a submission is missing `co`")

    elif kind == "contractLeads":
        if item.get("stage") and item["stage"] not in CONTRACT_STAGES:
            problems.append(f"{where}: stage must be one of {list(CONTRACT_STAGES)}")
        if item.get("channel") and item["channel"] not in CONTRACT_CHANNELS:
            problems.append(f"{where}: channel must be one of {list(CONTRACT_CHANNELS)}")

    return problems


def validate_seed(seed: dict) -> list[str]:
    """Every problem in an assembled seed, in the order a reader would hit them."""
    problems: list[str] = []

    seen: set[str] = set()
    for item in seed.get("roles") or []:
        problems += validate_item("roles", item, seed)
        rid = item.get("id")
        if rid and rid in seen:
            problems.append(
                f"roles[{rid}]: duplicate id — saved status would collide")
        seen.add(rid)

    for kind in ENTITY_KINDS:
        if kind in ("roles", "intel"):
            continue
        for item in seed.get(kind) or []:
            problems += validate_item(kind, item, seed)

    companies = {r.get("company") for r in seed.get("roles") or []}
    for name in seed.get("intel") or {}:
        if name not in companies:
            problems.append(
                f"intel['{name}'] matches no role company — it will never show")

    return problems


def assert_valid_seed(seed: dict) -> None:
    problems = validate_seed(seed)
    if problems:
        raise SeedError("seed problems:\n  - " + "\n  - ".join(problems))
