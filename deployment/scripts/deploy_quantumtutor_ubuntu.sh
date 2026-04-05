#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

QT_REPO_SRC="${QT_REPO_SRC:-${REPO_ROOT}}"
QT_APP_DIR="${QT_APP_DIR:-/opt/quantum_tutor/current}"
QT_VENV="${QT_VENV:-/opt/quantum_tutor/venv}"
QT_ENV_DIR="${QT_ENV_DIR:-/etc/quantum-tutor}"
QT_ENV_FILE="${QT_ENV_FILE:-/etc/quantum-tutor/quantum_tutor.env}"
QT_TUNNEL_NAME="${QT_TUNNEL_NAME:-quantumtutor-cl-prod}"
QT_TUNNEL_CONFIG="${QT_TUNNEL_CONFIG:-/etc/cloudflared/quantumtutor-cl.yml}"
QT_TUNNEL_CREDS="${QT_TUNNEL_CREDS:-/etc/cloudflared/quantumtutor-cl-prod.json}"
QT_TUNNEL_ID="${QT_TUNNEL_ID:-}"
QT_CLOUDFLARED_STATE_DIR="${QT_CLOUDFLARED_STATE_DIR:-${HOME}/.cloudflared}"

ACTION="${1:-all}"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  printf '\n[ERROR] %s\n' "$*" >&2
  exit 1
}

need_root() {
  [[ "${EUID}" -eq 0 ]] || die "Run this script as root."
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

as_quantum() {
  runuser -u quantum -- "$@"
}

ensure_cloudflare_repo() {
  install -d -m 0755 /usr/share/keyrings
  if [[ ! -f /usr/share/keyrings/cloudflare-main.gpg ]]; then
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
  fi
  if [[ ! -f /etc/apt/sources.list.d/cloudflared.list ]]; then
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" > /etc/apt/sources.list.d/cloudflared.list
  fi
}

install_packages() {
  need_command apt
  need_command curl
  need_command tee
  log "Installing system packages"
  export DEBIAN_FRONTEND=noninteractive
  apt update
  apt install -y nginx python3 python3-venv python3-pip curl ca-certificates gnupg rsync
  ensure_cloudflare_repo
  apt update
  apt install -y cloudflared
}

prepare_users_and_dirs() {
  log "Preparing users and directories"
  getent group www-data >/dev/null 2>&1 || groupadd --system www-data
  id quantum >/dev/null 2>&1 || useradd --system --home /opt/quantum_tutor --shell /usr/sbin/nologin quantum
  id cloudflared >/dev/null 2>&1 || useradd --system --home /var/lib/cloudflared --shell /usr/sbin/nologin cloudflared
  usermod -a -G www-data quantum || true

  install -d -o quantum -g www-data /opt/quantum_tutor
  install -d -o quantum -g www-data "${QT_APP_DIR}"
  install -d -o quantum -g www-data "${QT_VENV}"
  install -d -o root -g quantum "${QT_ENV_DIR}"
  install -d -o root -g cloudflared /etc/cloudflared
}

sync_app() {
  [[ -d "${QT_REPO_SRC}" ]] || die "QT_REPO_SRC not found: ${QT_REPO_SRC}"
  [[ -f "${QT_REPO_SRC}/requirements.txt" ]] || die "requirements.txt not found under ${QT_REPO_SRC}"
  log "Syncing repository to ${QT_APP_DIR}"
  rsync -a --delete "${QT_REPO_SRC}/" "${QT_APP_DIR}/"
  chown -R quantum:www-data /opt/quantum_tutor
}

create_venv_and_install() {
  need_command python3
  need_command runuser
  log "Creating virtualenv and installing Python dependencies"
  if [[ ! -x "${QT_VENV}/bin/python" ]]; then
    as_quantum python3 -m venv "${QT_VENV}"
  fi
  as_quantum "${QT_VENV}/bin/pip" install --upgrade pip setuptools wheel
  as_quantum "${QT_VENV}/bin/pip" install -r "${QT_APP_DIR}/requirements.txt"
}

install_env_template_if_missing() {
  local template="${QT_APP_DIR}/deployment/env/quantum_tutor.env.example"
  [[ -f "${template}" ]] || die "Missing env template: ${template}"
  log "Installing env template if needed"
  if [[ ! -f "${QT_ENV_FILE}" ]]; then
    install -m 0640 -o root -g quantum "${template}" "${QT_ENV_FILE}"
  fi
}

validate_env_file() {
  [[ -f "${QT_ENV_FILE}" ]] || die "Missing env file: ${QT_ENV_FILE}"
  if grep -Eqi 'replace-with|your-domain|REPLACE_WITH|TU_API_KEY|TU_CLIENT_ID' "${QT_ENV_FILE}"; then
    die "Env file still contains placeholder values: ${QT_ENV_FILE}"
  fi
}

cloudflare_login() {
  need_command cloudflared
  log "Starting cloudflared login"
  cloudflared tunnel login
}

create_tunnel_if_needed() {
  need_command cloudflared
  if cloudflared tunnel list | grep -Fq "${QT_TUNNEL_NAME}"; then
    log "Tunnel already exists: ${QT_TUNNEL_NAME}"
  else
    log "Creating cloudflared tunnel: ${QT_TUNNEL_NAME}"
    cloudflared tunnel create "${QT_TUNNEL_NAME}"
  fi
}

install_tunnel_credentials() {
  [[ -n "${QT_TUNNEL_ID}" ]] || die "Set QT_TUNNEL_ID to the Cloudflare tunnel UUID."
  local source_json="${QT_CLOUDFLARED_STATE_DIR}/${QT_TUNNEL_ID}.json"
  [[ -f "${source_json}" ]] || die "Tunnel credential not found: ${source_json}"
  log "Installing tunnel credentials"
  install -m 0640 -o cloudflared -g cloudflared "${source_json}" "${QT_TUNNEL_CREDS}"
}

render_tunnel_config() {
  [[ -n "${QT_TUNNEL_ID}" ]] || die "Set QT_TUNNEL_ID before rendering the tunnel config."
  [[ -f "${QT_TUNNEL_CREDS}" ]] || die "Tunnel credential file missing: ${QT_TUNNEL_CREDS}"
  log "Rendering cloudflared config"
  cat > "${QT_TUNNEL_CONFIG}" <<EOF
tunnel: ${QT_TUNNEL_NAME}
credentials-file: ${QT_TUNNEL_CREDS}

ingress:
  - hostname: quantumtutor.cl
    service: http://localhost:8080
  - hostname: admin.quantumtutor.cl
    service: http://localhost:8080
  - hostname: api.quantumtutor.cl
    service: http://localhost:8080
  - service: http_status:404
EOF
  chown root:cloudflared "${QT_TUNNEL_CONFIG}"
  chmod 0640 "${QT_TUNNEL_CONFIG}"
}

route_dns() {
  need_command cloudflared
  log "Routing DNS records through the tunnel"
  cloudflared tunnel route dns "${QT_TUNNEL_NAME}" quantumtutor.cl
  cloudflared tunnel route dns "${QT_TUNNEL_NAME}" api.quantumtutor.cl
  cloudflared tunnel route dns "${QT_TUNNEL_NAME}" admin.quantumtutor.cl
}

install_nginx_site() {
  local source_conf="${QT_APP_DIR}/deployment/nginx/quantum_tutor.conf"
  [[ -f "${source_conf}" ]] || die "Missing Nginx config: ${source_conf}"
  log "Installing Nginx site"
  install -m 0644 "${source_conf}" /etc/nginx/sites-available/quantum_tutor.conf
  ln -sfn /etc/nginx/sites-available/quantum_tutor.conf /etc/nginx/sites-enabled/quantum_tutor.conf
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl restart nginx
}

install_systemd_units() {
  log "Installing systemd units"
  install -m 0644 "${QT_APP_DIR}/deployment/systemd/quantum-tutor-api.service" /etc/systemd/system/quantum-tutor-api.service
  install -m 0644 "${QT_APP_DIR}/deployment/systemd/quantum-tutor-ui.service" /etc/systemd/system/quantum-tutor-ui.service
  install -m 0644 "${QT_APP_DIR}/deployment/systemd/cloudflared.service" /etc/systemd/system/cloudflared.service
  systemctl daemon-reload
}

start_services() {
  validate_env_file
  [[ -f "${QT_TUNNEL_CONFIG}" ]] || die "Missing tunnel config: ${QT_TUNNEL_CONFIG}"
  [[ -f "${QT_TUNNEL_CREDS}" ]] || die "Missing tunnel credentials: ${QT_TUNNEL_CREDS}"
  log "Enabling and starting services"
  systemctl enable --now quantum-tutor-api.service
  systemctl enable --now quantum-tutor-ui.service
  systemctl enable --now cloudflared.service
}

show_status() {
  log "Service status"
  systemctl --no-pager --full status nginx quantum-tutor-api.service quantum-tutor-ui.service cloudflared.service
}

smoke_test() {
  validate_env_file
  log "Running smoke test"
  as_quantum "${QT_VENV}/bin/python" "${QT_APP_DIR}/deployment/scripts/smoke_check.py" \
    --ui-url https://quantumtutor.cl \
    --api-url https://api.quantumtutor.cl
}

preflight() {
  validate_env_file
  need_command curl
  need_command ss
  need_command systemctl
  need_command nginx

  log "Checking Nginx configuration"
  nginx -t

  log "Checking service activation"
  systemctl is-active nginx quantum-tutor-api.service quantum-tutor-ui.service cloudflared.service >/dev/null

  log "Checking listening sockets"
  ss -ltn | grep -F "127.0.0.1:8000" >/dev/null || die "FastAPI is not listening on 127.0.0.1:8000"
  ss -ltn | grep -F "127.0.0.1:8501" >/dev/null || die "Streamlit is not listening on 127.0.0.1:8501"
  ss -ltn | grep -F "127.0.0.1:8080" >/dev/null || die "Nginx is not listening on 127.0.0.1:8080"

  log "Checking local FastAPI health"
  curl --silent --show-error --fail http://127.0.0.1:8000/health >/dev/null

  log "Checking local Nginx -> API routing"
  curl --silent --show-error --fail -H "Host: api.quantumtutor.cl" http://127.0.0.1:8080/health >/dev/null

  log "Checking local Nginx -> public UI routing"
  curl --silent --show-error --fail -H "Host: quantumtutor.cl" http://127.0.0.1:8080/ >/dev/null

  log "Checking local Nginx -> admin UI routing"
  curl --silent --show-error --fail -H "Host: admin.quantumtutor.cl" http://127.0.0.1:8080/ >/dev/null

  log "Preflight OK"
}

print_next_steps() {
  cat <<EOF

Next manual Cloudflare steps if not already completed:
  1. cloudflared tunnel login
  2. export QT_TUNNEL_ID=<tunnel-uuid>
  3. ${0} configure-tunnel
  4. Configure Cloudflare Access only for admin.quantumtutor.cl
EOF
}

run_all() {
  install_packages
  prepare_users_and_dirs
  sync_app
  create_venv_and_install
  install_env_template_if_missing
  install_nginx_site
  install_systemd_units
  print_next_steps
}

run_bootstrap() {
  install_packages
  prepare_users_and_dirs
  sync_app
  create_venv_and_install
  install_env_template_if_missing
  install_nginx_site
  install_systemd_units
}

run_configure_tunnel() {
  create_tunnel_if_needed
  install_tunnel_credentials
  render_tunnel_config
  route_dns
}

run_start() {
  start_services
  show_status
}

usage() {
  cat <<EOF
Usage: $0 <action>

Actions:
  all               Install packages, sync app, install nginx/systemd, and print next steps.
  bootstrap         Same as all, without tunnel routing.
  cloudflare-login  Run 'cloudflared tunnel login'.
  configure-tunnel  Install tunnel credentials, render config, and route DNS.
  start             Start API, UI, and cloudflared services.
  status            Show systemd status for the stack.
  smoke-test        Run the deployed smoke test.
  preflight         Validate local services, listeners, and Nginx routing before public DNS checks.

Environment overrides:
  QT_REPO_SRC
  QT_APP_DIR
  QT_VENV
  QT_ENV_FILE
  QT_TUNNEL_NAME
  QT_TUNNEL_ID
  QT_TUNNEL_CONFIG
  QT_TUNNEL_CREDS
  QT_CLOUDFLARED_STATE_DIR
EOF
}

main() {
  need_root
  case "${ACTION}" in
    all)
      run_all
      ;;
    bootstrap)
      run_bootstrap
      ;;
    cloudflare-login)
      cloudflare_login
      ;;
    configure-tunnel)
      run_configure_tunnel
      ;;
    start)
      run_start
      ;;
    status)
      show_status
      ;;
    smoke-test)
      smoke_test
      ;;
    preflight)
      preflight
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
