from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _read(relative_path: str) -> str:
    return (BASE_DIR / relative_path).read_text(encoding="utf-8")


def test_nginx_conf_uses_expected_quantumtutor_hosts():
    nginx_conf = _read("deployment/nginx/quantum_tutor.conf")

    assert "listen 127.0.0.1:8080" in nginx_conf
    assert "server_name quantumtutor.cl;" in nginx_conf
    assert "server_name admin.quantumtutor.cl;" in nginx_conf
    assert "server_name api.quantumtutor.cl;" in nginx_conf
    assert "X-Quantum-Host-Tier admin" in nginx_conf
    assert "location ~ ^/healthz?$ {" in nginx_conf
    assert "location /api/ {" in nginx_conf


def test_cloudflared_config_routes_all_expected_hostnames():
    cloudflare_conf = _read("deployment/cloudflare/cloudflared-config.yml.example")

    assert "hostname: quantumtutor.cl" in cloudflare_conf
    assert "hostname: admin.quantumtutor.cl" in cloudflare_conf
    assert "hostname: api.quantumtutor.cl" in cloudflare_conf
    assert "service: http://localhost:8080" in cloudflare_conf


def test_env_template_includes_required_runtime_and_gateway_flags():
    env_template = _read("deployment/env/quantum_tutor.env.example")

    assert "ENV=production" in env_template
    assert "API_KEY=" in env_template
    assert "SECRET_KEY=" in env_template
    assert "ALLOWED_HOSTS=quantumtutor.cl,api.quantumtutor.cl,admin.quantumtutor.cl" in env_template
    assert "QT_ADMIN_HOSTNAMES=admin.quantumtutor.cl" in env_template
    assert "QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false" in env_template


def test_deploy_script_exposes_expected_actions_and_paths():
    deploy_script = _read("deployment/scripts/deploy_quantumtutor_ubuntu.sh")

    assert "deploy_quantumtutor_ubuntu.sh" in str(BASE_DIR / "deployment/scripts/deploy_quantumtutor_ubuntu.sh")
    assert 'QT_TUNNEL_CONFIG="${QT_TUNNEL_CONFIG:-/etc/cloudflared/quantumtutor-cl.yml}"' in deploy_script
    assert "configure-tunnel" in deploy_script
    assert "cloudflare-login" in deploy_script
    assert "smoke-test" in deploy_script
    assert "preflight" in deploy_script
    assert "QT_CLOUDFLARED_STATE_DIR" in deploy_script
    assert 'curl --silent --show-error --fail http://127.0.0.1:8000/health' in deploy_script
    assert "quantumtutor.cl" in deploy_script
    assert "api.quantumtutor.cl" in deploy_script
