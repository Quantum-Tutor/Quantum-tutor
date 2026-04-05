# systemd Services

These units assume:

- Repo checkout at `/opt/quantum_tutor/current`
- Python virtualenv at `/opt/quantum_tutor/venv`
- Environment file at `/etc/quantum-tutor/quantum_tutor.env`
- Service user `quantum`
- Runtime caches redirected under `/opt/quantum_tutor/current/outputs`
- Cloudflare tunnel config at `/etc/cloudflared/quantumtutor-cl.yml`

## Units

- `quantum-tutor-api.service`: serves FastAPI on `127.0.0.1:8000`
- `quantum-tutor-ui.service`: serves Streamlit on `127.0.0.1:8501`
- `cloudflared.service`: optional tunnel process in front of Nginx

## Install Example

```bash
sudo cp deployment/systemd/quantum-tutor-api.service /etc/systemd/system/
sudo cp deployment/systemd/quantum-tutor-ui.service /etc/systemd/system/
sudo cp deployment/systemd/cloudflared.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quantum-tutor-api.service
sudo systemctl enable --now quantum-tutor-ui.service
sudo systemctl enable --now cloudflared.service
```

## Validate

```bash
sudo systemctl status quantum-tutor-api.service
sudo systemctl status quantum-tutor-ui.service
sudo journalctl -u quantum-tutor-api.service -n 100 --no-pager
sudo journalctl -u quantum-tutor-ui.service -n 100 --no-pager
```

Tune paths and usernames before applying on the target host.
