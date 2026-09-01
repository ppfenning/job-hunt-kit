---
name: apply-to-role
description: Process one job posting end to end — research it, score fit, draft answers to its application questions, and add it to a job-hunt-kit profile. Use when given a posting URL, "add this to the tracker", "should I apply to this", "help me answer these application questions", or a bare job link with no instructions.
argument-hint: "<job posting URL> [optional: which application questions to answer]"
---

# Processing a single posting

`seed-job-hunt` builds a board from scratch. This skill adds **one role** to a
board that already exists, and does the part seeding doesn't: drafting the
answers to that posting's application form.

Read `docs/SCHEMA.md` for the field reference and the API before writing
anything. The honesty rules in `seed-job-hunt` apply here in full — especially
**never claim experience the résumé does not support**. Everything written here
gets said out loud on a live call.

**Arguments provided:** $ARGUMENTS

## Ground truth (read these, don't reconstruct them)

The board is a running deployment, not a set of files — SQLite behind
`state_server.py`. Read the live state; never reconstruct it from memory or from
the YAML under `profiles/`, which is a stale starting point at best.

Establish these each run, because they move:

- **The board's base URL.** Ask if it isn't obvious. Everything below is
  `$BOARD/api/...`; add `-k` to curl for a LAN certificate.
- **The comp floor** — `curl -sk $BOARD/api/config` and read `profile.compOkLabel`,
  `profile.compWarnLabel`, and the `profile.spec` chips. Do **not** carry a
  remembered number. A floor quietly out of date will greenlight a lateral move
  as if it cleared the bar, which is the single most expensive mistake this
  skill can make.
- **The scoring rubric** — `fitWeights` from the same call. Per-board by design.
- **The résumés** — whatever the board was seeded from. These are the ONLY
  source for claims about the person's experience. Ask if you don't know which.
- **Voice conventions** — ask, or read them from the wiring the caller supplied.
- **Existing entries** — `curl -sk $BOARD/api/entity/roles`, `.../recruiters`,
  `.../intel`.

Two checks before spending anything on research:

1. **Prior rejection or live pipeline.**

   ```bash
   curl -sk $BOARD/api/entity/roles | python3 -c "import json,sys;[print(r['id'],'|',r['company']) for r in json.load(sys.stdin)]"
   curl -sk $BOARD/api/entity/recruiters | python3 -c "import json,sys;[print(r['name'],'->',[s['co'] for s in r['submissions']]) for r in json.load(sys.stdin)]"
   ```

   A company whose other team rejected them last month is a fact to surface up
   front, not to bury. So is a role already being worked by an agency recruiter
   — see *Duplicate submission* below.
2. **Already tracked.** Companies post several near-identical roles and the
   duplicate is easy to miss. If it's already there, decide whether this is
   genuinely distinct or an **update to the existing entry** — a `PUT` to the
   same id updates in place, which is usually what you want.

## Step 1: Fetch the posting

Greenhouse/Lever/Ashby pages render thin. Prefer the JSON APIs:

| Board | URL pattern |
|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/<org>/jobs/<id>?questions=true` |
| Lever | `https://api.lever.co/v0/postings/<org>/<id>` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/<org>?includeCompensation=true`, then match the job id |

**Use `?questions=true`, never `?content=true`.** Greenhouse's `content=true`
payload does not contain the application questions at all — an agent using it
reports "no questions found" and silently skips Step 4. `questions=true` is a
strict superset: it returns `questions`, `compliance`, `demographic_questions`
*and* `content`.

### Aggregators find; the ATS verifies

Wellfound and BuiltIn are both fetchable without a login and are good places to
*discover* a role. They are not where you should read its facts from. Both
republish, and a band that has drifted since the employer changed it is worse
than no band — it becomes an anchor in a negotiation.

So: when an aggregator listing links out to a Greenhouse/Lever/Ashby posting,
**follow the link and fetch the ATS record**, then set `source` to the ATS. The
aggregator was the search engine, not the source.

Two things only the ATS has:

- **The application questions.** No aggregator carries them, and they are what
  Step 4 exists for.
- **Structured remote status.** Ashby's `workplaceType` beats any prose.

**Wellfound is the exception worth knowing.** Many Wellfound roles are posted
in-platform with no ATS behind them — the company enters the listing on
Wellfound directly, and comp is mandatory there. For those, Wellfound *is*
first-hand: set `source: Wellfound`, and expect no questions payload, because
the application is in-platform too.

**BuiltIn is always a republisher.** Set `source: BuiltIn` only if you genuinely
cannot find the underlying posting, and treat the band as unconfirmed.

**Nothing behind a login is reachable.** Web fetches run server-side with no
access to the user's browser session, so being signed in changes nothing —
saved jobs, profile-gated listings, and LinkedIn generally are all out of reach.
LinkedIn InMail in particular can only be read via the notification emails it
sends. When a role only exists behind a login, ask for the text to be pasted.

Ashby exposes `workplaceType` as a structured enum (`Remote`/`Hybrid`/`OnSite`).
Trust that field over any prose in the description — remote status is often
role-by-role rather than company-wide.

Extract: exact title, level, posted comp range **verbatim**, remote policy and
any state or timezone restriction, the full named stack, responsibilities,
required vs nice-to-have quals, and **every free-text application question,
verbatim**. The questions are the highest-value part of the fetch and the
easiest to miss — they live on the form, not in the JD body.

If a field is absent, record "not stated". Never infer a salary range that
isn't posted.

## Step 2: Research

Two independent lines of work — run them in parallel if the harness allows:

1. **Posting digest** — the Step 1 extraction as structured fields.
2. **Company brief** — product and market, headcount, ownership (PE/VC/public/
   bootstrapped), funding and layoff history, engineering stack signals, public
   AI stance, Glassdoor rating **with review count and date**, recurring review
   themes both good and bad, and red flags.

Require a source URL for each non-obvious claim, and require that whatever
could **not** be verified is named. Company marketing copy is not evidence; say
when a claim comes only from the company's own site. Glassdoor and G2 routinely
403 automated fetches — a rating quoted as fact when it actually came from a
search snippet is the kind of false precision that makes a board untrustworthy.

## Step 3: Score fit

Score against the profile's own `fitWeights`, not a remembered rubric. Read the
keys and maxima out of `/api/config` (`fitWeights`); they're per-board by design.

- Score comp against the floor you read in Ground truth. No posted range means
  a low comp score and `basis: warn`.
- **Not fully remote** (or outside their stated geography) still gets an entry:
  score `remote` low, set `verifState: warn`, and put the constraint in `flag`.
  The entry's job is to record *why not*, so it isn't re-researched in a month.
- **Posting 404s or has been pulled** — don't invent an entry. Report it, and if
  the company is already tracked, update that entry's `verif`.
- **Tier is a judgment call, not a formula.** A high score with a fatal flaw
  (not actually remote, comp below floor, prior rejection) is not gold. Read the
  neighbouring entries before assigning one, so the new role is consistent with
  what's already on the board.

## Step 4: Draft answers to the open questions

For each free-text question on the form, draft an answer in **their voice**:

- First person, plain, concrete. Lead with a specific system they actually built.
- Follow the profile's voice conventions (`positioning.md`). For Pat's profile
  that means **no em dashes**.
- No corporate filler, no restating the question, no pitching the company's
  values back at them.
- Ground every claim in the résumé. If a persuasive number isn't there, either
  leave it out or mark it `[CONFIRM: <number> — from <source>, unverified]`.
- One specific story fully told beats three name-dropped ones.

**Never fabricate a metric, a tool they haven't used, or an outcome.** If the
strongest possible answer would need an unsupported claim, say so rather than
writing it. A claim the posting invites that they can't back is a real finding.

## Step 5: Write it to the board

One `PUT` per entity, straight to the API. The write *is* the deploy — there is
no build step and nothing to copy anywhere, and the change is live on every
device the moment it returns.

```bash
curl -sk -X PUT "$BOARD/api/entity/roles/<id>" \
  -H 'Content-Type: application/json' --data-binary @role.json
```

Text is HTML-escaped for you, so write a literal `&`, `<`, `>` and never an
entity. The one field that renders raw HTML is a role's `why` (use
`<span class='hl'>` for emphasis).

**The server validates every write** and is the only correctness gate — there is
no build left to catch anything. A bad entity comes back `422` with a `problems`
list naming each fault. Read it and fix the entity; do not hand-check what the
server already checks, and do not retry the same body hoping for a different
answer.

**`roles`** — one entity. See `docs/SCHEMA.md` for the full field list.
The ones most often got wrong:

- **`id`** — unique and **stable**. Saved status, stars, and notes key off it;
  changing an id silently loses that role's saved state.
- **`company`** — must match the `intel` entity's id **exactly**, or the
  company brief never renders against the role.
- **`compSort`** — the **midpoint** of the posted range in $K, rounded
  (`$213–300K` → `256`). It drives the Sort-by-Comp view, so using the ceiling
  misorders the board.
- **`source`** — where these facts came from, from the enum in `docs/SCHEMA.md`.
  An unrecognised value is rejected on write. Record the **ATS**, not the aggregator
  you found it through; use `Recruiter` when the numbers are recruiter-stated
  and no posting was seen. It renders as a warning chip for secondhand sources,
  so an entry built on a sales figure is visibly distinct from one built on a
  posted band.
- **`flag`** — the fatal-flaw badge. Any role with a disqualifier needs one; a
  badly-scoring entry with no `flag` reads as an unexplained low score.
- **`track`** must be one of the profile's `tracks[].id`.
- **`fit`** needs one key per `fitWeights[].key`. `total` is summed for you.
- **`jd`** is a 1–2 sentence third-person précis; **`points`** is 3–6 items of
  second-person tactical advice. Match the voice of the neighbouring entries.

**`intel`** — the company entry, `PUT /api/entity/intel/<Company Name>`. The id
*is* the company name, matching the role's `company` exactly. Adding a role
without its intel is the most common silent omission: they are one operation,
not two. `stability` is where the honest risk read goes — name the mechanism
(PE margin phase, customer concentration, RTO risk), not a vibe. Say which
numbers are snippet-derived.

**`companyPrep`** — only once they're actually interviewing. Carry unverified
claims into `watchOut` with the `[CONFIRM: ...]` convention.

**`recruiters`** — if the role came in through an agency, write the recruiter
now, not later, with the submission recorded in `submissions[]`.

> **Duplicate submission is the risk that costs the job.** Two agencies
> submitting the same candidate to the same employer can get them rejected by
> both. Before adding an agency-sourced role, check the existing recruiters for
> another already working that company, and flag the collision rather than
> quietly adding a second entry. The board runs this check itself and shows a
> warning banner, but only over submissions that were actually recorded — so an
> unrecorded submission is invisible to it, and an agency that won't name the
> client cannot be conflict-checked at all.

## Step 6: Verify and report

Nothing to build and nothing to deploy — but confirm the write actually landed
rather than trusting a `200`:

```bash
curl -sk "$BOARD/api/entity/roles" | python3 -c "import json,sys;print([r['id'] for r in json.load(sys.stdin)])"
```

> **Know what you just did.** The write is live immediately, for everyone with
> access to that board. On a deployment without authentication — which is the
> common case for this tool — a board holds a salary floor, negotiation anchors,
> recruiter names and email addresses, and private reads on companies currently
> interviewing. Recruiter contacts in particular are *third-party personal data*.
> Say so before writing newly-added personal contacts, not after.

Then report plainly:

- what was added, and the fit score with the reasoning behind the tier
- **what could not be verified**, and what was deliberately left out
- which application questions still need a decision from them
- anything they have to confirm themselves — comp bands, whether the posting is
  still live, whether a submission actually happened

## Guardrails

- **Never submit an application, fill a form field, or send anything to an
  employer.** This skill drafts; they send. Applying is always their action.
- **Never edit a résumé as a side effect** of processing a posting. If the
  posting reveals a gap, report it and let them decide.
- **Never write to a board you were not asked to write to**, and never commit
  `state.db` or anything under `profiles/private/` — both are gitignored on
  purpose, and the database is the whole search.
- **A `PUT` to an existing id overwrites it.** Read the entity first and merge;
  don't send a partial body and silently drop fields that were already there.
- When editing existing entries, grep to confirm the replacement hit every
  occurrence. The same claim recurs across `roles`, flashcards, and prep.
- Report what research could not confirm. An unverified Glassdoor number
  presented as fact is worse than "couldn't verify".

## Common mistakes

| Mistake | Fix |
|---|---|
| Carrying a remembered comp floor | Read it from `/api/config` every time |
| Missing the form's application questions | They're on the form, not the JD body; use `questions=true` |
| Computing tier from the fit total | Tier is judgment; read neighbouring entries |
| Adding a role with no `intel` entry | One operation, not two — the brief silently never renders |
| Treating a 422 as a transport error | It's the validator; read `problems` and fix the entity |
| Sending a partial body to an existing id | PUT replaces — read, merge, then write |
| `compSort` from the top of the range | Use the midpoint |
| HTML entities in escaped fields | Write plain `&`, `<`, `>` |
| Renaming an `id` to tidy it up | Loses that role's saved state in the browser |
| Inventing a metric to strengthen an answer | Mark `[CONFIRM: ...]` or omit it |
