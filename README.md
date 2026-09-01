# job-hunt-kit

A private, self-hosted job-search tracker you seed with your own data and run
as **one small Python process over a SQLite file** — no account, no telemetry,
no third-party dependencies.

Four views in one page:

| View | What it holds |
|---|---|
| **Role Shortlist** | Every role you're tracking, grouped gold/silver/bronze, scored 0–100 for fit, with per-company intel, talking points, and which résumé to send |
| **Interview Prep** | STAR behavioral answers, self-testing flashcards, per-company prep, and system-design walkthroughs |
| **Contract** | Freelance/contract leads tracked separately, plus a rate-maths playbook |
| **Recruiters** | A lightweight CRM that flags stale contacts and warns when two recruiters submit you to the same company |

**SQLite is the source of truth.** Roles, recruiters, contract leads and prep
all live in `state.db`; the page ships as a shell with no data baked in,
fetches `/api/seed` on load, and writes edits straight back through the same
API. Adding a recruiter is a live call from the browser — there is no rebuild
step in the loop, and every device sees the same board.

`app/state_server.py` is that server: stdlib `http.server` + `sqlite3`, ~330
lines, nothing to install. It serves the shell and the API from one origin.

Per-viewer interaction state — which flashcards you've rated, your private
notes on a lead — also syncs through it, with `localStorage` as the offline
fallback.

> **This means the server is required.** Earlier versions built a single
> self-contained file that ran from `file://`; that is no longer true, because
> a static file cannot be the thing you edit. If you want a frozen, portable
> artifact, keep a copy of `state.db` — that is the whole search in one file.

---

## Quickstart

```bash
git clone <this repo> && cd job-hunt-kit
python3 scripts/migrate_to_sqlite.py --profile profiles/example --db state.db
python3 build.py --db state.db --out dist/index.html
cp app/state_server.py app/seedlib.py dist/ && cp state.db dist/
python3 dist/state_server.py --root dist --port 8899
```

Open <http://127.0.0.1:8899>. That's the fictional example profile — it exists
so you can see every feature populated before you write a line of your own.

Requires **Python 3.9+**. PyYAML is needed *only* to import the example
profile or your own legacy YAML seeds; the server and the tracker itself have
no dependencies at all.

## Make it yours

**Day to day, you don't touch files at all.** Every board has an `+ Add`
button and every card an `✎ edit` control; saving writes through
`/api/entity/<kind>/<id>` into SQLite. That is the intended way to run it.

To start from something other than an empty database, import a YAML profile
once:

```bash
cp -r profiles/example profiles/private/me     # then edit the six YAML files
python3 scripts/migrate_to_sqlite.py --profile profiles/private/me --db state.db
```

`profiles/private/` is gitignored, so your real search never lands in version
control. The importer is idempotent — re-running it upserts by `(kind, id)`
rather than duplicating — but once the data is in SQLite, the database is
authoritative and the YAML is just a starting point you can delete.

Already have a built tracker and lost the seeds? Import straight from the
deployed page, which carries the whole corpus inline:

```bash
python3 scripts/migrate_to_sqlite.py --from-html dist/index.html --db state.db
```

**Validation moved to write time.** With no build step left to gate the data,
`app/seedlib.py` runs on every API write: a duplicate role id, a `track` that
doesn't exist, a tier that isn't gold/silver/bronze, or a recruiter `type`
outside the enum comes back as a `422` with the specific problems listed, and
the editor shows them above the form. Bad data cannot reach the board.

Rebuild the shell only when the *template* or your profile chrome changes —
not when the job search changes:

```bash
python3 build.py --db state.db            # or --from-api https://your.host
```

**Don't know where to start?** [`docs/SEEDING.md`](docs/SEEDING.md) walks
through seeding from your résumé and a few job links — including doing it
conversationally with an AI assistant, which is how the tool was built.

Full field reference: [`docs/SCHEMA.md`](docs/SCHEMA.md).

## `jhk` — the command line

The API is plain REST, so `curl` is a perfectly good client. `jhk` exists for
the parts curl makes awkward:

```bash
export JHK_BOARD=https://jobs.lan     # default: http://127.0.0.1:8899
export JHK_INSECURE=1                 # LAN self-signed certificate

jhk ls                                # the whole board, summarized
jhk ls recruiters
jhk get roles jellyfish-staff-de      # raw JSON
jhk set roles jellyfish-staff-de tier=gold compSort=230
jhk status jellyfish-staff-de Interview
jhk put recruiters jane-doe-acme -f jane.json
jhk conflicts                         # duplicate-submission check
```

Three things earn it its place over raw curl:

- **`set` and `put --merge` do read-modify-write for you.** A `PUT` replaces the
  entity, so patching one field by hand means fetching it first — and forgetting
  to means silently dropping every field you didn't resend.
- **`status` edits one role in a shared blob.** The interaction overlay is a
  single JSON document keyed by role id, so changing one status by hand is a
  read-modify-write of the whole thing. It also refuses to set a status on a role
  id that doesn't exist, which would otherwise attach to nothing.
- **`conflicts` runs the duplicate-submission check** — two agencies submitting
  the same candidate to one employer can get them rejected by both. It also
  reports agency contacts with *no* submissions recorded, since anything they
  submitted is invisible to the check.

Validation failures come back as the server's own problem list, not an HTTP code:

```
$ jhk put recruiters jane -f bad.json
jhk: the board rejected this entity:
  - recruiters[jane]: type must be one of ['Agency', 'Internal', 'Platform']
```

Stdlib only, like the rest of the runtime.

## Tailoring it beyond a software search

Nothing about the tool is specific to engineering. In `profile.yml`:

- **`tracks`** are your lanes — `Backend`/`Platform`, or `Editorial`/`Design`,
  or `ICU`/`Peds`. You get one filter button per track.
- **`fitWeights`** is the scoring rubric. Rename and re-weight the rows; a
  designer might score `Portfolio fit` where an engineer scores `Stack`.
- **`spec`**, **`comp` labels**, and the footer **`notes`** are all your copy.

## Deploying it somewhere

It needs somewhere that can run a Python process and keep a writable file —
a container, a home-lab LXC, a small VM. Static hosts and `file://` no longer
work, because the page has no data without the API. See
[`docs/DEPLOY.md`](docs/DEPLOY.md) for the options, **and read the warning
there first**: a seeded tracker contains your salary floor and your recruiters'
contact details, and the API is now write-capable, so anything that can reach
it can also change or delete your board. Put authentication in front of it, and
don't put it on the open internet.

## Development

```bash
python3 build.py --db state.db                       # rebuild the shell
python3 scripts/migrate_to_sqlite.py --profile profiles/example --db /tmp/ex.db
```

`scripts/smoke_test.js` executes the page's JavaScript against a stubbed DOM
and reports which panels rendered — it catches the errors that only appear
during a real render pass. Because the page now boots from `/api/seed`,
`scripts/prep_smoke.py` first swaps that bootstrap for a seed snapshot (which
also removes the top-level `await`, so the body runs under `new Function`):

```bash
curl -s http://127.0.0.1:8899/api/seed > /tmp/seed.json
python3 scripts/prep_smoke.py dist/index.html /tmp/seed.json /tmp/page.js
node scripts/smoke_test.js /tmp/page.js
```

`scripts/serve.py` is a static-only preview server and predates the API — it
will serve the shell but every fetch will 404. Use `app/state_server.py`.

## License

MIT — see [LICENSE](LICENSE).
