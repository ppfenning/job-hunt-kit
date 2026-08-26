---
name: seed-job-hunt
description: Seed or extend a job-hunt-kit profile from a résumé, target criteria, and job-posting links. Use when someone wants to set up their job tracker, add roles to their board, research a company for it, or draft STAR answers and prep material into their seed files.
---

# Seeding a job-hunt-kit profile

Turn a résumé, a sense of what someone wants, and some job links into the YAML
seed files this tool builds from. Read `docs/SCHEMA.md` for the field
reference before writing anything.

## The one rule that matters

**Never claim experience the résumé does not support.**

Everything you write here gets said out loud in an interview. A plausible-
looking tool added to someone's stack is a trap they walk into on a live call.

When a role wants something they don't have:

- put it in `skillsGap`, not `skillsHave`
- write the honest equivalent they *do* have, as a sentence they can say:
  *"Orchestration for me has been Step Functions and Batch rather than
  Airflow — the DAG and scheduling concepts transfer, but I haven't run
  Airflow in production."*
- surface it in the role's `points` so it isn't a surprise

If you're unsure whether something is claimable, **ask** rather than assume.
Then record the answer, so the question isn't re-litigated later.

## Order of work

Work in this order and build after each step, so there's something usable
early rather than a perfect thing late.

### 1. `profile.yml`

Read the résumé first. Then establish, asking where it isn't inferable:

- **Tracks** — the two or three lanes they're pursuing. Push back if they name
  five; that's an unfocused search and the board will look incoherent.
- **Comp floor and target.** Set `comp.okLabel` to the real floor. Ask for the
  current number and target separately; anchoring advice depends on the gap.
- **`fitWeights`** — the rubric. Adjust labels and weights to what actually
  decides their yes. Don't leave a `Leverage` row that means nothing to them.
- **Skill map.** Tally against real postings, not from memory. Mark the two
  highest-ROI gaps `prio: true`.

Report anything in the résumé you could not verify or found contradictory.

### 2. `roles.yml`

For each posting URL: fetch the JD, then write the entry.

- Score `fit` against **their** rubric, and make the numbers defensible — if
  `stack` is 30/35, be able to say which 5 points are missing.
- `why` is the field that earns its keep: one paragraph on why *this* person
  should pursue *this* role. If you can't write it honestly, say so and
  suggest bronze or dropping it.
- `tier` is pursuit priority, not prestige.
- **Verify comp from the posting itself.** Never carry over a remembered band.
  If it isn't posted, mark `basis: warn` and say it's an estimate.
- `id` must be unique and stable — saved status keys off it. Never renumber
  existing ids.

### 3. `intel.yml`

Gold-tier companies first. Funding, headcount, Glassdoor **with sample size**,
recent signal, and a stability read.

Date every claim and name its source. Flag thin evidence as thin — a 2.6
Glassdoor from 40 reviews is not the same fact as one from 400. Keys must
match `roles[].company` exactly or the build fails.

### 4. `prep.yml`

Interview the person for STAR stories rather than inventing them. Ask what
actually happened, what broke, what they personally did, and what the measured
result was. The follow-up questions are where the good material comes from.

- `behavioral` — aim for six covering incident, conflict, influence,
  ownership, failure, and scope
- `flashcards` — the facts they want cold, grouped by `cat`
- `companyPrep` — one per active loop; don't skip `askThem`
- `sysdesign` — only if their field has them

### 5. `recruiters.yml` / `contract.yml`

Seed recruiters as soon as a second one is involved — the duplicate-submission
warning is the whole point. Skip contract entirely unless they're open to it.

## Finishing

Always end by building and reporting honestly:

```bash
python3 build.py --profile profiles/private/<name>
```

The build validates ids, tracks, tiers, and intel keys. Fix what it reports.

Then tell them, plainly:

- what you seeded, and the counts
- **what you could not verify** and what you left out on purpose
- which gaps are worth closing first, and the honest line to use meanwhile
- anything they still need to confirm themselves (comp bands, whether a
  posting is still live, whether a submission actually happened)

Never write the seed files into a tracked directory. They belong in
`profiles/private/`, which is gitignored.
