# Seed file reference

Every field is optional unless marked **required**. Missing lists render as
empty sections rather than breaking the page.

Text in the **data** files (`roles.yml`, `intel.yml`, `prep.yml`,
`recruiters.yml`, `contract.yml`) is HTML-escaped for you — write plain text,
including `&`, `<`, and `>`.

Two exceptions render raw HTML on purpose:

- the prose fields in `profile.yml` (`lede`, `skillsNote`, `prepIntro`, note bodies)
- a role's **`why`** — so you can use `<span class='hl'>…</span>` to highlight

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
