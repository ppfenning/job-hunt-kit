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
>   the URL sees everything.
> - Anything reachable without a password is readable by everything on that
>   network, including guests, IoT devices, and anyone on your VPN.
> - The build sets `noindex, nofollow`, which discourages honest crawlers and
>   stops nobody else.
>
> If you want it reachable from your phone, put it behind a VPN (Tailscale,
> WireGuard) or an authenticating proxy — not behind a hard-to-guess URL.

The output is one self-contained HTML file with no external requests, so
every option below is just "serve a static file."

---

## Local only (recommended default)

```bash
python3 build.py --profile profiles/private/me --serve
```

Serves on `127.0.0.1:8899` — loopback only, unreachable from the rest of the
network. Opening `dist/index.html` directly as a `file://` URL also works;
localStorage persists per-origin, so saved state carries across rebuilds.

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

Technically trivial, and **the option most likely to leak your data.** Every
one of these is public-by-default; a "private" repo does not make a deployed
site private. Only do this behind the host's real access control (Cloudflare
Access, Netlify password protection, an S3 bucket policy), and assume the URL
will eventually be discovered.

For most people the honest answer is: keep it local, and use a VPN when you
need it on your phone.

---

## Backing it up

Two things live in different places:

- **Your seed files** — `profiles/private/me/`. Back these up. They're small,
  they're text, and they're the actual work. Consider a *private* git repo or
  an encrypted folder.
- **Your saved state** — status, stars, notes, flashcard progress. These live
  in the **browser's localStorage**, not in any file. Clearing site data
  loses them, and they don't follow you to another browser or device.

If your notes matter, promote them into `roles.yml` periodically. The
localStorage layer is designed for in-flight state, not as your record.
