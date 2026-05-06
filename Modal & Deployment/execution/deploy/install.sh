#!/usr/bin/env bash
# install.sh — first-time setup CPAS Meta Ads di VPS
# Jalankan sebagai root di VPS:
#   bash install.sh
#
# Idempotent: aman dijalankan ulang. Tidak menyentuh service lain.

set -euo pipefail

APP_DIR=/root/digivise/cpas-meta-ads
SERVICE_NAME=cpas-meta-ads

echo "[1/6] Installing system dependencies (python3, venv, git) ..."
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip git >/dev/null

echo "[2/6] Cloning / updating repo ..."
if [ ! -d "$APP_DIR/.git" ]; then
  mkdir -p "$(dirname "$APP_DIR")"
  git clone https://github.com/employe-digivise/cpas-meta-ads-hierarchy.git "$APP_DIR"
else
  cd "$APP_DIR" && git fetch origin main && git reset --hard origin/main
fi

cd "$APP_DIR"
APP_CODE_DIR="$APP_DIR/Modal & Deployment/execution"

echo "[3/6] Creating Python venv ..."
if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --upgrade pip --quiet
"$APP_DIR/.venv/bin/pip" install -r "$APP_CODE_DIR/requirements.txt" --quiet

echo "[4/6] Checking .env file ..."
if [ ! -f "$APP_DIR/.env" ]; then
  echo "  WARNING: $APP_DIR/.env tidak ditemukan."
  echo "  Copy .env.example dan isi nilainya:"
  echo "    cp '$APP_CODE_DIR/.env.example' '$APP_DIR/.env'"
  echo "    nano '$APP_DIR/.env'"
  echo ""
  echo "  Setelah .env diisi, jalankan ulang script ini atau systemctl restart $SERVICE_NAME"
fi

echo "[5/6] Installing systemd service ..."
# Service file mengharapkan modal_app.py ada di WorkingDirectory.
# Karena modal_app.py masih di subfolder, kita symlink agar uvicorn import-nya bersih.
ln -sf "$APP_CODE_DIR/modal_app.py" "$APP_DIR/modal_app.py"

cp "$APP_CODE_DIR/deploy/cpas-meta-ads.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "[6/6] Starting service ..."
if [ -f "$APP_DIR/.env" ]; then
  systemctl restart "$SERVICE_NAME"
  sleep 2
  systemctl status "$SERVICE_NAME" --no-pager -l | head -15
  echo ""
  echo "Health check:"
  curl -s http://localhost:9008/health || echo "  (service belum siap, cek log: journalctl -u $SERVICE_NAME -n 50)"
else
  echo "  Service di-enable tapi belum di-start (menunggu .env)."
fi

echo ""
echo "✓ Install selesai."
echo ""
echo "Useful commands:"
echo "  systemctl status $SERVICE_NAME"
echo "  systemctl restart $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
echo "  tail -f /var/log/cpas-meta-ads.log"
