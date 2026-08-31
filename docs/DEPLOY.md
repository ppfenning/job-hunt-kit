# Deploying your tracker

> ## Read this first
>
> A seeded tracker contains **your salary floor, your negotiation anchors, your
> recruiters' names and email addresses, and your private read on companies
> that are currently interviewing you.**
>
> Treat it like your password manager, not like your portfolio site.
>
> - **Never put it on the public internet.** There is no login — anyone with
>   the URL sees everything, **and since the API is write-capable, anything
>   that can reach it can also edit or delete your board.** SQLite is the
>   source of truth now, so an unauthenticated write path is a data-loss path,
>   not just a disclosure one.
> - Anything reachable without a password is readable by everything on that
>   network, including guests, IoT devices, and anyone on your VPN.
> - The build sets `noindex, nofollow`, which discourages honest crawlers and
>   stops nobody else.
>
> If you want it reachable from your phone, put it behind a VPN (Tailscale,
> WireGuard) or an authenticating proxy — not behind a hard-to-guess URL.

The tracker is a small Python process over a SQLite file. Every option below
is "run `state_server.py` somewhere and point a browser at it" — it serves the
shell and the API from one origin, so there is nothing to configure between
them.

A deployment is four files in one directory:

```
index.html        built by build.py
state_server.py   the server
seedlib.py        validation — imported by the server, must sit alongside it
state.db          your entire job search
```

---

## Local only (recommended default)

```bash
python3 build.py --db state.db --out dist/index.html
cp app/state_server.py app/seedlib.py state.db dist/
python3 dist/state_server.py --root dist --port 8899
```

Serves on `0.0.0.0:8899`; bind it to loopback with a firewall rule or an
`ssh -L` tunnel if you want it unreachable from the rest of the network.

`file://` no longer works: the page has no data of its own and cannot fetch
`/api/seed` from a file origin.

## Home Assistant (`/local/`)

HA serves anything in `config/www/` at `/local/`. Quick, but **unauthenticated
by default** — `/local/` does not require an HA login, so anyone on your LAN
can read it.

```bash
scp dist/index.html homeassistant.local:/config/www/jobs.html
```

Then browse to `http://<ha-host>:8123/local/jobs.html`.

To put it behind HA's login instead, add it as a sidebar panel in
`configuration.yaml`:

```yaml
panel_iframe:
  jobhunt:
    title: "Job Hunt"
    icon: mdi:briefcase-search
    url: "/local/jobs.html"
    require_admin: true
```

Restart HA afterwards. Note the honest caveat: the panel is behind auth, but
the underlying `/local/jobs.html` URL still isn't. Treat this as tidier
navigation, not as access control.

## Home-lab reverse proxy

If you already run a proxy (Nginx Proxy Manager, Caddy, Traefik) with internal
DNS, serve the file from any always-on host and add a proxy host for it:

1. Put `index.html` somewhere a web server can reach it.
2. Add a DNS entry pointing your chosen hostname at the proxy.
3. Create the proxy host, and **add HTTP basic auth or forward-auth** — this is
   the step that makes this option better than `/local/`.
4. Issue a certificate if you terminate TLS internally.

A tiny container is enough:

```bash
docker run -d --name jobhunt --restart unless-stopped \
  -p 8080:80 -v /srv/jobhunt:/usr/share/nginx/html:ro nginx:alpine
```

Redeploying is `scp dist/index.html` over the mounted file — no rebuild, no
restart.

## Cross-device sync

By default, status/star/notes/flashcard progress live in the browser's
`localStorage` — per browser, per device. Open the tracker on your phone
after updating a status on your desktop and you'll see the defaults, not
what you set. That's not a bug, it's the tradeoff of "no server, no
account": there's nowhere shared to put that state.

If you want it shared across your own devices anyway, swap the plain
`nginx:alpine` container above for `app/state_server.py` — stdlib-only
(`http.server` + `sqlite3`, no pip installs), and it serves `index.html`
exactly like nginx did, plus one small JSON API:

```bash
docker run -d --name jobhunt --restart unless-stopped \
  -p 8080:80 -v /srv/jobhunt:/data -w /data \
  python:3.12-alpine python3 /data/state_server.py --root /data --port 80
```

Copy `app/state_server.py` into `/srv/jobhunt/` alongside `index.html` first.
It creates `/srv/jobhunt/state.db` (SQLite) on first run, storing one row per
top-level state key (`jobtracker:v1`, `ipprep:v1`, `contract:v1`,
`recruiters:v1`) — the same shape `localStorage` already used, just shared
instead of per-device. `template.html`'s JS opportunistically pushes to
`/api/state` (debounced) and pulls on load, and silently falls back to
`localStorage`-only if `/api/state` isn't there — so this is fully optional
and every other deployment mode above is unaffected whether you add it or
not.

**This changes your risk profile, not just your convenience.** Every other
option on this page is read-only once deployed — worst case, someone reads
your data. `state_server.py` adds a write path: anything that can reach the
port can also overwrite your tracked statuses. Auth on this one matters more
than "add it if you feel like it" — if you're putting this behind a reverse
proxy, add basic auth or forward-auth to it same as you would `/local/`,
unless you've deliberately decided (like a solo LAN-only deployment) that the
write exposure is an acceptable trade for not needing a login. Restarting the
container is required after `state_server.py` itself changes (unlike
`index.html`, which it reads fresh on every request); `state.db` on the bind
mount survives a restart or recreate either way.

## Static hosts (Netlify, Pages, S3)

**No longer possible.** These serve files; they cannot run the API the page
depends on, and there is nowhere for a write to land. Use anything that runs a
process and keeps a writable volume — a container, an LXC, a small VM.

This is a real loss of portability, and it was the deliberate price of making
the board editable in place. If you want a portable artifact, copy `state.db`:
it is small, it is the whole search, and any checkout of this repo can serve
it.

For most people the honest answer is still: keep it local, and use a VPN when
you need it on your phone.

---

## Backing it up

**Back up `state.db`. That is the whole job.** Roles, recruiters, contract
leads, prep, and your saved statuses and notes are all in it. It is a single
small file, so this is easy — and it is now the *only* copy, which makes it
the thing to actually verify rather than assume.

```bash
sqlite3 state.db ".backup /path/to/backups/state-$(date +%F).db"
```

Use `.backup` rather than copying the file: the server runs in WAL mode, and a
plain `cp` of a database being written to can capture a torn page.

Two things worth checking, not assuming:

- **That the backup covers this file.** If the tracker runs in a container, a
  host-level backup of a config repo does not necessarily include its data
  volume.
- **That you have more than one destination.** A nightly copy to one NAS is a
  single point of failure for the entire search.

Legacy YAML seeds under `profiles/private/` are no longer authoritative — the
database has diverged from them the moment you edit anything in the browser.
Keep them if you like, but back up the database.
