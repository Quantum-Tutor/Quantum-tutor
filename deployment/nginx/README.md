# Nginx Deployment Notes

## Purpose

`quantum_tutor.conf` is the local reverse proxy that sits behind `cloudflared`.

It expects:

- Streamlit on `127.0.0.1:8501`
- FastAPI on `127.0.0.1:8000`
- Nginx listening on `127.0.0.1:8080`

## Host Routing

- `quantumtutor.cl` -> Streamlit public UI
- `admin.quantumtutor.cl` -> Streamlit admin UI
- `api.quantumtutor.cl` -> FastAPI `/api/*` and `/health`

The admin hostname forwards `X-Quantum-Host-Tier=admin`, which the Streamlit app uses to expose `Admin Security Review` only on that host.

## What The Config Already Does

- Publishes `/health` from FastAPI
- Applies gateway rate limiting and connection limiting on `api.quantumtutor.cl`
- Preserves client IP and request id
- Forwards `CF-Access-Authenticated-User-Email` as `X-Authenticated-User`
- Writes structured access logs

## Before Enabling

1. Keep Uvicorn and Streamlit bound to localhost only.
2. Set the app environment:

```bash
QT_TRUST_PROXY_HEADERS=true
QT_TRUSTED_PROXY_RANGES=127.0.0.1,::1
QT_ADMIN_HOSTNAMES=admin.quantumtutor.cl
QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false
QT_PROVIDER_BREAKER_NAME=gemini_text
```

3. Install the site:

```bash
./deployment/scripts/install_nginx_site.sh
```

## Operational Logs

- Access log: `/var/log/nginx/quantum_tutor_access.log`
- Error log: `/var/log/nginx/quantum_tutor_error.log`
- App security log: `outputs/logs/security_events.jsonl`

## Smoke Test

After enabling Nginx and cloudflared, run:

```bash
sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh preflight
python deployment/scripts/smoke_check.py --ui-url https://quantumtutor.cl --api-url https://api.quantumtutor.cl
```
