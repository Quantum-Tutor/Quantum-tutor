#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SOURCE_CONF="${REPO_ROOT}/deployment/nginx/quantum_tutor.conf"
TARGET_NAME="${1:-quantum_tutor.conf}"
TARGET_AVAILABLE="/etc/nginx/sites-available/${TARGET_NAME}"
TARGET_ENABLED="/etc/nginx/sites-enabled/${TARGET_NAME}"

if [[ ! -f "${SOURCE_CONF}" ]]; then
  echo "Missing source config: ${SOURCE_CONF}" >&2
  exit 1
fi

sudo cp "${SOURCE_CONF}" "${TARGET_AVAILABLE}"
sudo ln -sfn "${TARGET_AVAILABLE}" "${TARGET_ENABLED}"
sudo nginx -t
sudo systemctl reload nginx

echo "Installed and reloaded Nginx site: ${TARGET_NAME}"
