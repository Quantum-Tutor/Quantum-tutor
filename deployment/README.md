# Production Gateway Notes

Quantum Tutor is now wired for this topology:

1. `quantumtutor.cl` -> public Streamlit UI
2. `api.quantumtutor.cl` -> public FastAPI API
3. `admin.quantumtutor.cl` -> Streamlit admin UI protected by Cloudflare Access
4. `cloudflared` -> Nginx on local `127.0.0.1:8080`
5. `systemd` supervising app and tunnel processes

For an automated bootstrap path, use `deployment/scripts/deploy_quantumtutor_ubuntu.sh`.

## Required App Environment

```bash
QT_TRUST_PROXY_HEADERS=true
QT_TRUSTED_PROXY_RANGES=127.0.0.1,::1
QT_ADMIN_HOSTNAMES=admin.quantumtutor.cl
QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false
QT_PROVIDER_BREAKER_NAME=gemini_text
```

## Recommended Flow

- `quantumtutor.cl` serves the public Streamlit UI.
- `admin.quantumtutor.cl` serves the same UI, but the admin security review is only enabled there.
- `api.quantumtutor.cl` serves `/api/*` plus `/health`.
- Cloudflare handles public TLS.
- Nginx stays HTTP-only on the private local hop.
- Persist and review gateway logs together with `outputs/logs/security_events.jsonl`.

## Included Files

- `deployment/env/quantum_tutor.env.example`
- `deployment/nginx/quantum_tutor.conf`
- `deployment/nginx/README.md`
- `deployment/systemd/quantum-tutor-api.service`
- `deployment/systemd/quantum-tutor-ui.service`
- `deployment/systemd/cloudflared.service`
- `deployment/systemd/README.md`
- `deployment/cloudflare/cloudflared-config.yml.example`
- `deployment/cloudflare/README.md`
- `deployment/cloudflare/access-policies.md`
- `deployment/RUNBOOK_quantumtutor_cl_ubuntu.md`
- `deployment/scripts/deploy_quantumtutor_ubuntu.sh`
- `deployment/scripts/install_nginx_site.sh`
- `deployment/scripts/smoke_check.py`

## Minimal Bring-Up Order

1. Copy `deployment/env/quantum_tutor.env.example` to `/etc/quantum-tutor/quantum_tutor.env` and fill secrets.
2. Copy `deployment/cloudflare/cloudflared-config.yml.example` to `/etc/cloudflared/quantumtutor-cl.yml`.
3. Install the `systemd` units from `deployment/systemd/`.
4. Install and enable the Nginx site from `deployment/nginx/quantum_tutor.conf`.
5. Start `quantum-tutor-api.service`, `quantum-tutor-ui.service`, and `cloudflared.service`.
6. Run `sudo bash deployment/scripts/deploy_quantumtutor_ubuntu.sh preflight`.
7. Run `python deployment/scripts/smoke_check.py --ui-url https://quantumtutor.cl --api-url https://api.quantumtutor.cl`.
