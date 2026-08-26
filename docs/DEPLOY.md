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
