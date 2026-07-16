#!/usr/bin/env bash
# deploy/vps40-deploy.sh - Deploy the Toronto Pixel Deal Score API to VPS-40.
#
# Idempotent: safe to re-run. Sets up uv venv, installs deps, seeds the DB
# with offline sample data, installs+starts a systemd service on port 8100.
#
# Target: VPS-40 (Oracle Cloud free tier, 1GB RAM), Tailscale IP 100.71.95.75.
# The VPS already runs the LLM gateway on :8000 (Tailscale-only). This API
# uses :8100 to avoid that conflict. uvicorn runs with --workers 1 because
# SQLite is a single-writer store (see the ponytail note in src/api.py).
#
# Usage (from the laptop):
#   bash deploy/vps40-deploy.sh
# The script detects whether it is already running on the VPS. If not, it
# copies itself over SSH and runs remotely. To do it manually instead:
#   scp -i ~/.ssh/oracle.key deploy/vps40-deploy.sh ubuntu@100.71.95.75:~/pd-deploy.sh
#   ssh -i ~/.ssh/oracle.key ubuntu@100.71.95.75 'bash ~/pd-deploy.sh'
#
# Firewall note: VPS-40 only exposes :8000 to Tailscale (100.64.0.0/10) today.
# To reach :8100 from other Tailscale peers, open it:
#   sudo iptables -I INPUT -p tcp --dport 8100 -s 100.64.0.0/10 -j ACCEPT
#   sudo netfilter-persistent save
# Or reverse-proxy :8100 through the existing gateway. This script does NOT
# touch iptables -- that is a user decision documented here only.
set -euo pipefail

VPS_IP="100.71.95.75"
SSH_USER="ubuntu"
SSH_KEY="${HOME}/.ssh/oracle.key"
REPO_DIR="${HOME}/toronto-pixel-deals"
SERVICE_NAME="pixel-deals-api"
PORT="8100"

# Detect whether we are already running on the VPS by checking if the
# Tailscale IP is bound to a local interface (more reliable than hostname).
on_vps() {
  ip -o addr 2>/dev/null | grep -qw "${VPS_IP}" && return 0
  hostname -I 2>/dev/null | tr ' ' '\n' | grep -qw "${VPS_IP}" && return 0
  return 1
}

# If not on the VPS, ship this script over and run it there.
if ! on_vps; then
  echo "Not on VPS-40 (${VPS_IP}). Copying this script over SSH and running it remotely..."
  if [[ ! -f "${SSH_KEY}" ]]; then
    echo "ERROR: SSH key not found at ${SSH_KEY}" >&2
    exit 1
  fi
  remote_tmp="\$(mktemp)/pd-deploy.sh"
  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new "$0" "${SSH_USER}@${VPS_IP}:/tmp/pd-deploy.sh"
  ssh -i "${SSH_KEY}" "${SSH_USER}@${VPS_IP}" 'bash /tmp/pd-deploy.sh'
  exit $?
fi

echo ">> Running on VPS-40 (${VPS_IP}). Starting deploy."

# --- 1. Clone or pull the repo ---
if [[ -d "${REPO_DIR}/.git" ]]; then
  echo ">> Repo exists, pulling latest..."
  git -C "${REPO_DIR}" pull --ff-only || echo "WARN: pull failed (maybe no upstream), continuing with current tree."
else
  echo ">> Cloning repo into ${REPO_DIR}..."
  git clone https://github.com/ons96/toronto-pixel-deals.git "${REPO_DIR}"
fi

cd "${REPO_DIR}"

# --- 2. uv venv + deps ---
if ! command -v uv >/dev/null 2>&1; then
  echo ">> uv not found, installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo ">> Creating venv (python 3.12) and installing deps..."
uv venv .venv --python 3.12
uv pip install -r requirements.txt

# --- 3. Seed the DB with offline sample data ---
echo ">> Seeding DB with offline sample data (specs + sample Reddit listings)..."
uv run python -m src.fetch --sample-reddit
echo ">> DB counts:"
uv run python -c "from src.db import counts, init_db; init_db(); print(counts())"

# --- 4. Install systemd unit ---
echo ">> Installing systemd unit ${SERVICE_NAME}.service..."
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
cat > /tmp/${SERVICE_NAME}.service <<UNIT
[Unit]
Description=Toronto Pixel Deal Score API (FastAPI/uvicorn)
After=network.target

[Service]
Type=simple
User=${SSH_USER}
WorkingDirectory=${REPO_DIR}
Environment=PATH=${REPO_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${REPO_DIR}/.venv/bin/uvicorn src.api:app --host 0.0.0.0 --port ${PORT} --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo cp /tmp/${SERVICE_NAME}.service "${UNIT_PATH}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
sudo systemctl restart "${SERVICE_NAME}.service"

# --- 5. Wait for it to come up, then smoke test ---
echo ">> Waiting for service to bind :${PORT}..."
for i in $(seq 1 15); do
  if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo
echo "================ SMOKE TEST ================"
echo "-- /health (no auth, not counted):"
curl -s "http://localhost:${PORT}/health" ; echo
echo "-- /deals/top?n=5 (demo free key):"
curl -s -H "X-API-Key: demo-free-key" "http://localhost:${PORT}/deals/top?n=5" ; echo
echo "-- /specs (demo free key):"
curl -s -H "X-API-Key: demo-free-key" "http://localhost:${PORT}/specs" ; echo
echo "==========================================="
echo
echo "Deploy done. Service: sudo systemctl status ${SERVICE_NAME}"
echo "Docs:       http://${VPS_IP}:${PORT}/docs  (from a Tailscale peer, once :${PORT} is opened)"
echo "Logs:       sudo journalctl -u ${SERVICE_NAME} -f"
