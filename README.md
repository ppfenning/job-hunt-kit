# job-hunt-kit

A private, self-hosted job-search tracker you seed with your own data and build
into **one self-contained HTML file** — no server, no account, no telemetry.

Four views in one page:

| View | What it holds |
|---|---|
| **Role Shortlist** | Every role you're tracking, grouped gold/silver/bronze, scored 0–100 for fit, with per-company intel, talking points, and which résumé to send |
| **Interview Prep** | STAR behavioral answers, self-testing flashcards, per-company prep, and system-design walkthroughs |
| **Contract** | Freelance/contract leads tracked separately, plus a rate-maths playbook |
| **Recruiters** | A lightweight CRM that flags stale contacts and warns when two recruiters submit you to the same company |

Status, stars, notes, and flashcard progress save to **your browser's
localStorage** by default. Nothing is uploaded, because there is nothing to
upload to. If localStorage isn't enough — the same tracker open on your phone
and your desktop, wanting the same statuses on both — there's an optional tiny
same-origin sync server (`app/state_server.py`, stdlib only) you can run
instead of a plain static host; see [Cross-device sync](docs/DEPLOY.md#cross-device-sync)
in the deploy guide. It's opt-in: skip it and the page behaves exactly as
described above.

---

## Quickstart

```bash
git clone <this repo> && cd job-hunt-kit
python3 build.py --profile profiles/example --serve
```

Open <http://127.0.0.1:8899>. That's the fictional example profile — it exists
so you can see every feature populated before you write a line of your own.

Requires **Python 3.9+** and **PyYAML** (`pip install pyyaml`, or
`apt install python3-yaml`). Nothing else.

## Make it yours

```bash
cp -r profiles/example profiles/private/me
```

`profiles/private/` is gitignored, so your real search never lands in version
control. Then edit the six seed files:

| File | Holds |
|---|---|
| `profile.yml` | Who you are, what you're targeting, your tracks, your skill map |
| `roles.yml` | The roles on your board |
| `intel.yml` | Company research, keyed by company name |
| `prep.yml` | Behavioral answers, flashcards, per-company and system-design prep |
| `recruiters.yml` | Recruiter contacts and submissions |
| `contract.yml` | Contract leads and the rate playbook |

Rebuild whenever you change them:

```bash
python3 build.py --profile profiles/private/me --serve
```

The build validates as it goes — duplicate role ids, a `track` that doesn't
exist, a tier that isn't gold/silver/bronze, or company intel that matches no
role all fail loudly rather than rendering a quietly broken board.

**Don't know where to start?** [`docs/SEEDING.md`](docs/SEEDING.md) walks
through seeding from your résumé and a few job links — including doing it
conversationally with an AI assistant, which is how the tool was built.

Full field reference: [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Tailoring it beyond a software search

Nothing about the tool is specific to engineering. In `profile.yml`:

- **`tracks`** are your lanes — `Backend`/`Platform`, or `Editorial`/`Design`,
  or `ICU`/`Peds`. You get one filter button per track.
- **`fitWeights`** is the scoring rubric. Rename and re-weight the rows; a
  designer might score `Portfolio fit` where an engineer scores `Stack`.
- **`spec`**, **`comp` labels**, and the footer **`notes`** are all your copy.

## Deploying it somewhere

It's a single file with no external requests, so anywhere that serves static
HTML works — including `file://`. See [`docs/DEPLOY.md`](docs/DEPLOY.md) for
local, Home Assistant, home-lab reverse-proxy, and cloud options, **and read
the warning there first**: a seeded tracker contains your salary floor and your
recruiters' contact details. Don't put it on the open internet.

## Development

```bash
python3 build.py --profile profiles/example          # build only
node scripts/smoke_test.js <(...)                    # optional, see below
```

`scripts/smoke_test.js` executes the built page's JavaScript against a stubbed
DOM and reports which panels rendered — it catches a half-seeded profile that
would throw in a browser. It needs Node and the extracted `<script>` body:

```bash
python3 - <<'PY'
import re; t=open('dist/index.html',encoding='utf-8').read()
open('/tmp/page.js','w',encoding='utf-8').write(re.search(r'<script>(.*)</script>',t,re.S).group(1))
PY
node scripts/smoke_test.js /tmp/page.js
```

## License

MIT — see [LICENSE](LICENSE).
