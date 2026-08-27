# Seeding your profile

The tool is only as good as what you put in it. This is the order that gets you
to something useful fastest — roughly 30 minutes for a first pass.

You do **not** need to fill everything in before it's useful. Seed
`profile.yml` and three roles, build it, and add the rest as you go.

```bash
cp -r profiles/example profiles/private/me
python3 build.py --profile profiles/private/me --serve
```

Keep that running in one terminal; rebuild after each edit.

---

## 1. What you're looking for (`profile.yml`)

Start here, because it defines the vocabulary everything else uses.

Decide your **tracks** first — the two or three lanes you're actually pursuing.
Not job titles; lanes. "Backend" and "Platform". "Editorial" and "Content
strategy." If you can't name them, you're searching too broadly, and the board
will tell you that by looking incoherent.

Then set your **`fitWeights`** — the rubric every role gets scored against.
The defaults total 100 across Stack / Level / Comp / Leverage / Remote. Change
the labels and weights to match what actually decides your yes. If comp is the
binding constraint, weight it higher and be honest with yourself about it.

Write your **`comp.okLabel`** as your real floor (`base clears $170K`). Seeing
it on every card is the point — it's the number you should stop negotiating
below.

## 2. Your skill map (`profile.yml`)

Open 10–15 postings you'd genuinely take. Tally which skills keep appearing.

- `skillsHave` — what you can defend in an interview **today**
- `skillsGap` — what keeps coming up that you can't; mark the top two `prio: true`

The honesty here matters more than the completeness. A gap you've named is a
sentence you've rehearsed; a gap you've hidden is a stammer in a screen. If
your résumé doesn't support a claim, it belongs in `skillsGap`, not
`skillsHave` — write down the honest equivalent you *do* have and use that
line when it comes up.

## 3. Roles (`roles.yml`)

Add three to start. For each one, the field that earns its keep is **`why`** —
one paragraph on why *you* are pursuing *this*. If you can't write it, that's
the finding; tier it bronze or drop it.

**`tier` is your pursuit priority, not the company's prestige.** A famous
company you're lukewarm on is bronze.

Give every role a stable `id`. Your saved status and notes key off it, so
renaming an id later loses that role's history.

## 4. Company intel (`intel.yml`)

Do this for gold-tier roles only, at first. Funding status, headcount,
Glassdoor with its sample size, recent news, and your own read on stability.

Date everything and note the source. Intel rots, and the stale number you half
remember is the one you'll quote in a screen.

## 5. Prep (`prep.yml`)

Seed this **before** your first screen, not after you fail one.

- **`behavioral`** — six STAR answers covers most loops. Write them the way
  you'd say them aloud. Two solid ones beat six skeletons.
- **`flashcards`** — the facts you want cold. Group by `cat` into decks.
- **`companyPrep`** — one per company you have an active loop with. `askThem`
  is the field candidates skip and interviewers remember.
- **`sysdesign`** — only if your field has them.

## 6. Recruiters and contract leads

Seed `recruiters.yml` the moment a second recruiter is involved. The
**duplicate-submission warning** exists because two agencies submitting you to
one company can get your application thrown out — and you often won't be told
that's what happened.

`contract.yml` is only worth seeding if you're open to contract work. Delete
the file otherwise; the tab renders empty rather than breaking.

---

## Seeding with an AI assistant

This tool was built alongside an AI coding assistant, and seeding is the part
it helps with most. A workflow that works:

1. Give it your résumé and this repo's `docs/SCHEMA.md`.
2. Ask it to draft `profile.yml` — your tracks, skill map, and fit weights —
   **from the résumé only**, and to list anything it couldn't support.
3. Paste job-posting URLs and ask for `roles.yml` entries scored against your
   rubric, plus `intel.yml` from public sources.
4. Have it interview *you* for the STAR stories, then write them up. Talking
   through them is faster than typing, and the follow-up questions are the
   useful part.

Two rules make the difference:

- **Never let it invent experience.** Tell it explicitly: only claim what the
  résumé supports; everything else goes in `skillsGap` with the honest
  equivalent. An assistant that adds a plausible tool to your stack has
  written you a trap you'll walk into on a live call.
- **Verify comp and posting status yourself.** Scraped or recalled salary
  bands are frequently wrong or stale, and a wrong anchor is expensive.

A ready-made prompt lives in [`../skills/seed-job-hunt/SKILL.md`](../skills/seed-job-hunt/SKILL.md).
It's written for Claude Code but it's just structured instructions — paste it
into any assistant.

Once the board exists, [`../skills/apply-to-role/SKILL.md`](../skills/apply-to-role/SKILL.md)
handles the other half: one posting at a time, end to end — fetch it, research
the company, score it against *your* rubric, draft answers to the application
questions, and append the `roles`/`intel` entries. Seeding fills a board;
this one keeps it current.
