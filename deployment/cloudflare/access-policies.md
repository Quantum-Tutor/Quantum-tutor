# Cloudflare Access Policies For `quantumtutor.cl`

## Selected Topology

- Public UI: `https://quantumtutor.cl`
- Public API: `https://api.quantumtutor.cl`
- Protected admin UI: `https://admin.quantumtutor.cl`

## Recommended Policy Layout

### 1. `quantumtutor.cl`

- No Cloudflare Access policy
- Public site
- Still protected by app-level auth for user sessions

### 2. `api.quantumtutor.cl`

- No Cloudflare Access policy by default
- Protected by:
  - Nginx edge rate limiting
  - FastAPI edge guards
  - abuse scoring
  - circuit breaker and local fallback

If later you want to lock the API to first-party browser clients only, add a stricter Cloudflare rule or WAF policy here instead of Access login.

### 3. `admin.quantumtutor.cl`

- Cloudflare Access enabled
- Include only:
  - explicit admin emails, or
  - an `Admins` identity provider group
- Session duration:
  - `12h` or `24h`

This hostname points to the same Streamlit app, but the admin security console is only exposed when the request comes through the admin hostname.

## Header Contract

Cloudflare Access must provide:

- `CF-Access-Authenticated-User-Email`

Nginx forwards it as:

- `X-Authenticated-User`

It also forwards:

- `X-Quantum-Host-Tier=admin` for `admin.quantumtutor.cl`
- `X-Quantum-Host-Tier=public` for `quantumtutor.cl`
- `X-Quantum-Host-Tier=api` for `api.quantumtutor.cl`

## Incident Review

Correlate these sources during abuse review or manual unblock:

- Cloudflare Access audit logs for `admin.quantumtutor.cl`
- Nginx access log
- `outputs/logs/security_events.jsonl`
