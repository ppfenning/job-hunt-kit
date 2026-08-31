# Field and storage reference

Every field is optional unless marked **required**. Missing lists render as
empty sections rather than breaking the page.

Text in the data collections (`roles`, `intel`, `prep`, `recruiters`,
`contract`) is HTML-escaped for you — write plain text, including `&`, `<`,
and `>`.

Two exceptions render raw HTML on purpose:

- the prose chrome in `profile` (`lede`, `skillsNote`, `prepIntro`, note bodies)
- a role's **`why`** — so you can use `<span class='hl'>…</span>` to highlight

## Where this lives

SQLite is the source of truth. The YAML filenames below are kept as section
headings because they name the collections and because
`scripts/migrate_to_sqlite.py` still imports from them — but the database is
what the page reads and writes.

| Table | Holds |
|---|---|
| `entity(kind, id, pos, data, updated_at)` | The corpus. One row per item, JSON payload. `kind` is one of `roles`, `recruiters`, `contractLeads`, `contractPlaybook`, `behavioral`, `flashcards`, `companyPrep`, `sysdesign`, `intel` |
| `config(key, value, updated_at)` | `tracks`, `fitWeights`, `skillsHave`, `skillsGap`, `postingsSurveyed`, and `profile` (the page chrome) |
| `state(key, value, updated_at)` | Per-viewer interaction overlay: `jobtracker:v1`, `ipprep:v1`, `contract:v1`, `recruiters:v1`. Keyed by entity id |

`intel` is the one collection that is a map rather than a list; the company
name is the entity id.

Items in `behavioral`, `flashcards`, `companyPrep`, `sysdesign` and
`contractPlaybook` had no `id` in the YAML format. The importer derives one —
from a natural key where there is one (`companyPrep` uses `company`), else a
content hash. Derived ids are deliberately **not** positional: these ids key
the interaction overlay, so an id that shifted when you reordered a list would
silently reattach your notes to a different item.

## The API

| Method | Path | Does |
|---|---|---|
| `GET` | `/api/seed` | The whole corpus, in the shape the page boots from |
| `GET` | `/api/entity/<kind>` | One collection |
| `PUT` | `/api/entity/<kind>/<id>` | Upsert. Validates, then writes. `422` with a `problems` list if it fails |
| `DELETE` | `/api/entity/<kind>/<id>` | Remove one item |
| `POST` | `/api/entity/<kind>/reorder` | `{"ids": [...]}` — sets `pos` |
| `GET` | `/api/config` · `PUT /api/config/<key>` | Read and write config rows |
| `GET` | `/api/state` · `PUT /api/state/<key>` | The interaction overlay |

**Writes are validated by `app/seedlib.py`, and that is the only correctness
gate.** There is no build step left to catch a bad entity, so the rules live
server-side and the browser editor simply renders whatever problems come back.
Adding a new required field or enum means editing `seedlib.py`, not the page.

---

## profile.yml

| Field | Type | Notes |
|---|---|---|
| `owner` | string | Your name; used in the footer signature |
| `title` | string | Browser tab title |
| `eyebrow`, `headline` | string | Header text above the board |
| `lede` | HTML | The paragraph under the headline |
| `spec` | list of `{icon, label}` | Criteria chips under the headline |
| `tracks` | **required**, list of `{id, label, color}` | Your lanes. `id` is what `roles[].track` refers to. `color` accepts any CSS color or var; defaults are assigned if omitted |
| `comp.okLabel` / `comp.warnLabel` | string | Legend text for the green/amber comp dot |
| `postingsSurveyed` | int | Denominator for the skill map's "N/M roles". Defaults to your role count |
| `fitWeights` | list of `{key, label, max}` | The fit rubric. `key` must match the keys under a role's `fit:` |
| `skillsNote`, `prepIntro` | HTML | Intro copy for those sections |
| `notes` | list of `{title, body}` | Footer bullets |
| `signature` | HTML | Footer signature. Auto-generated from role counts if omitted |
| `skillsHave` / `skillsGap` | list of `{nm, ct, note, prio}` | Skill map. `ct` = how many postings mention it; `prio: true` marks a gap worth closing first |

## roles.yml → `roles:`

| Field | Type | Notes |
|---|---|---|
| `id` | **required**, string | Unique and **stable** — your saved status/star/notes key off it. Changing an id loses that role's saved state |
| `company` | **required**, string | Must match the `intel.yml` key exactly to show intel |
| `title` | **required**, string | |
| `track` | **required**, string | Must be one of your `tracks[].id` |
| `tier` | **required**, `gold`\|`silver`\|`bronze` | Your pursuit priority, not their prestige |
| `level`, `remote` | string | Shown as metadata chips |
| `comp` | string | Displayed range, e.g. `$185K–225K` |
| `compSort` | number | Sort key for "Sort: Comp" — use the midpoint in $K |
| `basis` | `ok`\|`warn` | Green or amber dot next to comp |
| `basisTxt` | string | e.g. `base · posted`, `OTE · estimated` |
| `verif` / `verifState` | string / `ok`\|`warn` | When you last confirmed the posting is live |
| `url` | string | Link to the posting |
| `source` | string | Where the entry's facts came from. One of `Ashby`, `Greenhouse`, `Lever`, `Direct`, `Wellfound` (the employer enters these itself, so the band and remote flag are first-hand) or `BuiltIn`, `LinkedIn`, `Recruiter`, `Referral`, `Other` (a retelling — rendered with a warning chip). An unrecognised value fails the build. If a Wellfound or BuiltIn listing links out to an ATS, record **the ATS**, not the aggregator |
| `cv` | string | Which résumé variant to send |
| `stack` | list of strings | Also searched by the search box |
| `why` | **HTML** | Your one-paragraph case for pursuing it |
| `jd` | string | Condensed job description |
| `fit` | map | One key per `fitWeights[].key`, plus `total`. `total` is summed for you if omitted |
| `points` | list of strings | Talking points and things to ask |

## intel.yml → `intel:`

Keyed by company name — **must match a role's `company` exactly**, or the build
fails rather than silently never showing it.

| Field | Notes |
|---|---|
| `status` | Funding, ownership, age |
| `headcount` | With source and date |
| `glassdoor` | Rating and sample size |
| `signal` | Recent news worth knowing |
| `stability` | Your read; rendered as **Read:** below the grid |

## prep.yml

**`behavioral:`** — `{id, q, tags[], s, t, a, r, tip}`. `s`/`t`/`a`/`r` are
Situation, Task, Action, Result. `tip` renders as coaching under the answer.

**`flashcards:`** — `{cat, q, a}`. `cat` groups cards into decks.

**`companyPrep:`** — `{company, role, focus, themes[], theyValue,
yourAngles[], askThem[], watchOut}`.

**`sysdesign:`** — `{title, prompt, approach[], yourEdge, tradeoffs[]}`.

## recruiters.yml → `recruiters:`

`{id, name, firm, type, track, email, phone, linkedin, lastContact,
nextTouch, submissions[], notes}`

- `type`: `Agency` | `Internal` | `Platform`
- `track`: `FTE` | `Contract` | `Both`
- `lastContact` / `nextTouch`: `YYYY-MM-DD`. Contacts go **stale after 21 days**
- `submissions`: `[{co, date, outcome}]`. Two recruiters listing the same `co`
  raises a conflict warning — that's the situation that can void an application

## contract.yml

**`contractLeads:`** — `{id, co, channel, role, rate, structure, len, stage,
contact, notes}`

- `channel`: `Agency` | `Direct` | `Platform`
- `structure`: `W-2` | `C2C` | `1099`
- `stage`: `Lead` | `Screening` | `Submitted` | `Interviewing` | `Negotiating` | `Won` | `Passed`

**`contractPlaybook:`** — `{h, stub}`, rendered as reference cards above the board.
