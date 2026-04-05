# Cloudflare Tunnel + Access

Recommended production topology:

`Client -> Cloudflare Edge -> cloudflared -> Nginx (localhost:8080) -> FastAPI + Streamlit`

## Hostnames

- `quantumtutor.cl` -> public Streamlit UI
- `api.quantumtutor.cl` -> public FastAPI edge
- `admin.quantumtutor.cl` -> Streamlit UI protected by Cloudflare Access

## Tunnel Config

Use `deployment/cloudflare/cloudflared-config.yml.example` as the base template and install it as:

- `/etc/cloudflared/quantumtutor-cl.yml`

The bundled `cloudflared.service` already points to that path.

## Access Header

Cloudflare Access should inject:

- `CF-Access-Authenticated-User-Email`

Nginx then forwards it to the app as:

- `X-Authenticated-User`

## App Environment

```bash
QT_TRUST_PROXY_HEADERS=true
QT_TRUSTED_PROXY_RANGES=127.0.0.1,::1
QT_ADMIN_HOSTNAMES=admin.quantumtutor.cl
QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false
```

## Notes

- Keep FastAPI and Streamlit private on localhost only.
- Do not terminate TLS in Nginx for this topology; Cloudflare handles the public TLS edge.
- The admin security console is only exposed on `admin.quantumtutor.cl`.
- Correlate Cloudflare logs with `outputs/logs/security_events.jsonl` during incident review or manual unblock.

Detailed policy guidance lives in `deployment/cloudflare/access-policies.md`.
