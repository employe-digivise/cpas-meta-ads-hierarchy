#!/usr/bin/env bash
# update.sh — pull latest code + restart service.
# Jalankan setelah git push perubahan baru:
#   bash update.sh

set -euo pipefail

APP_DIR=/root/digivise/cpas-meta-ads
SERVICE_NAME=cpas-meta-ads
APP_CODE_DIR="$APP_DIR/Modal & Deployment/execution"

cd "$APP_DIR"
echo "[1/3] Pulling latest code ..."
git fetch origin main
git reset --hard origin/main

echo "[2/3] Updating dependencies ..."
"$APP_DIR/.venv/bin/pip" install -r "$APP_CODE_DIR/requirements.txt" --quiet --upgrade

echo "[3/3] Restarting service ..."
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl status "$SERVICE_NAME" --no-pager -l | head -10

echo ""
echo "Health check:"
curl -s http://localhost:9005/health && echo ""
