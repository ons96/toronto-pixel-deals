#!/usr/bin/env bash
# Private-staging deploy only. It binds the API to loopback and seeds fixtures.
set -euo pipefail

SSH_USER="${VPS40_USER:-ubuntu}"
SSH_KEY="${VPS40_SSH_KEY:-${HOME}/.ssh/oracle.key}"
VPS_HOST="${VPS40_HOST:-}"
REPO_DIR="${PIXEL_REPO_DIR:-${HOME}/toronto-pixel-deals}"
SERVICE_NAME="pixel-deals-api"
PORT="8100"
BIND_HOST="127.0.0.1"
SCRIPT_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"

if [[ "${PIXEL_DEPLOY_REMOTE:-}" != "1" ]]; then
  [[ -n "${VPS_HOST}" ]] || {
    echo "ERROR: set VPS40_HOST to a pre-verified SSH host or alias" >&2
    exit 1
  }
  [[ -f "${SSH_KEY}" ]] || {
    echo "ERROR: SSH key not found at ${SSH_KEY}" >&2
    exit 1
  }

  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=yes "${SCRIPT_PATH}" \
    "${SSH_USER}@${VPS_HOST}:/tmp/pixel-deals-deploy.sh"
  ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=yes "${SSH_USER}@${VPS_HOST}" \
    'PIXEL_DEPLOY_REMOTE=1 bash /tmp/pixel-deals-deploy.sh'
  exit $?
fi

[[ -d "${REPO_DIR}/.git" ]] || {
  echo "ERROR: expected an existing repository at ${REPO_DIR}" >&2
  exit 1
}
# uv's standard per-user install directory is absent from non-interactive SSH PATH.
[[ -x "${HOME}/.local/bin/uv" ]] && export PATH="${HOME}/.local/bin:${PATH}"
command -v uv >/dev/null 2>&1 || {
  echo "ERROR: install a verified uv binary before deployment" >&2
  exit 1
}

echo ">> Updating private staging source..."
git -C "${REPO_DIR}" pull --ff-only origin main
cd "${REPO_DIR}"

echo ">> Creating venv and installing dependencies..."
uv venv .venv --python 3.12 --allow-existing
uv pip install -r requirements.txt

# ponytail: fixture-only staging avoids unreviewed source data; replace only
# after each source has documented public/commercial rights and provenance.
echo ">> Replacing the staging database with bundled fixtures..."
sudo systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
rm -f data/deals.db data/deals.db-shm data/deals.db-wal
uv run python -c 'from src.kimovil import seed_static; from src.reddit import load_sample_data; seed_static(); load_sample_data()'
uv run python -c 'from src.db import counts; print(counts())'

echo ">> Installing ${SERVICE_NAME}.service..."
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
cat > "/tmp/${SERVICE_NAME}.service" <<UNIT
[Unit]
Description=Toronto Pixel Deal Score API (private staging)
After=network.target

[Service]
Type=simple
User=${SSH_USER}
WorkingDirectory=${REPO_DIR}
Environment=PATH=${REPO_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${REPO_DIR}/.venv/bin/uvicorn src.api:app --host ${BIND_HOST} --port ${PORT} --workers 1
Restart=on-failure
RestartSec=5
MemoryHigh=100M
MemoryMax=120M
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT

sudo install -m 0644 "/tmp/${SERVICE_NAME}.service" "${UNIT_PATH}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
sudo systemctl restart "${SERVICE_NAME}.service"

echo ">> Waiting for local service health..."
ready=""
for _ in $(seq 1 15); do
  if curl -fsS "http://${BIND_HOST}:${PORT}/health" >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
[[ -n "${ready}" ]] || {
  sudo systemctl status "${SERVICE_NAME}.service" --no-pager >&2 || true
  echo "ERROR: service failed health check" >&2
  exit 1
}

echo "-- /health:"
curl -fsS "http://${BIND_HOST}:${PORT}/health"; echo
echo "-- /deals/top?n=5:"
curl -fsS -H "X-API-Key: demo-free-key" "http://${BIND_HOST}:${PORT}/deals/top?n=5"; echo
refresh_status="$(curl -sS -o /dev/null -w '%{http_code}' -H "X-API-Key: demo-free-key" "http://${BIND_HOST}:${PORT}/deals/refresh")"
[[ "${refresh_status}" == "503" ]] || {
  echo "ERROR: expected disabled refresh to return 503, got ${refresh_status}" >&2
  exit 1
}
sudo ss -ltnH "sport = :${PORT}" | grep -q "${BIND_HOST}:${PORT}" || {
  echo "ERROR: ${SERVICE_NAME} is not loopback-only" >&2
  exit 1
}

echo "Deploy complete: private loopback staging only."
echo "Logs: sudo journalctl -u ${SERVICE_NAME} -f"
