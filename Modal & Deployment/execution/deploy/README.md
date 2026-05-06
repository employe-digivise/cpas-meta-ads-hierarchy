# VPS Deployment — CPAS Meta Ads Backend

Service: FastAPI (uvicorn) + APScheduler (in-process cron)
VPS: `31.97.222.83`
Port: `9008` (terpisah dari WhatsApp service di `9004`)
Path: `/root/digivise/cpas-meta-ads/`

## First-time install (di VPS, sebagai root)

```bash
# 1. SSH ke VPS
ssh root@31.97.222.83

# 2. Download install script (atau clone repo dulu manual)
mkdir -p /tmp/cpas-install && cd /tmp/cpas-install
curl -sO https://raw.githubusercontent.com/employe-digivise/cpas-meta-ads-hierarchy/main/Modal%20%26%20Deployment/execution/deploy/install.sh
bash install.sh
```

Script akan:
1. Install `python3`, `python3-venv`, `pip`, `git` (apt)
2. Clone repo ke `/root/digivise/cpas-meta-ads/`
3. Buat venv di `.venv/` + install `requirements.txt`
4. Cek `.env` — kalau belum ada, kasih instruksi untuk dibuat
5. Install systemd service `cpas-meta-ads.service`
6. Enable + start service (kalau `.env` sudah ada)

## Setup `.env` (sekali saja, tidak di-commit)

```bash
cd /root/digivise/cpas-meta-ads
cp "Modal & Deployment/execution/.env.example" .env
nano .env   # isi: API_AUTH_TOKEN, META_ACCESS_TOKEN, N8N_WEBHOOK_URL, ALERT_WEBHOOK_URL
systemctl restart cpas-meta-ads
```

## Update setelah ada perubahan code

```bash
ssh root@31.97.222.83
cd /root/digivise/cpas-meta-ads
bash "Modal & Deployment/execution/deploy/update.sh"
```

Script: `git pull` + `pip install -r requirements.txt` + `systemctl restart`.

## Cek status & log

```bash
systemctl status cpas-meta-ads
journalctl -u cpas-meta-ads -f          # live tail
tail -f /var/log/cpas-meta-ads.log      # alternative log file
```

## Test endpoint

```bash
# Health
curl http://31.97.222.83:9008/health

# Fetch data brand
curl -X POST http://31.97.222.83:9008/fetch_meta_ads \
  -H "Authorization: Bearer <API_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"brand_name": "ATRIA"}'
```

## Manage service

```bash
systemctl start cpas-meta-ads
systemctl stop cpas-meta-ads
systemctl restart cpas-meta-ads
systemctl disable cpas-meta-ads   # disable autostart on boot
```

## Cron schedule

Cron `daily_fetch_all_brands` jalan **in-process** via APScheduler (bukan crontab OS).
Jadwal: `02:00 UTC` = `09:00 WIB` setiap hari.

Untuk men-trigger manual (testing tanpa nunggu jadwal):
```bash
cd /root/digivise/cpas-meta-ads
.venv/bin/python -c "import asyncio; from modal_app import daily_fetch_all_brands; asyncio.run(daily_fetch_all_brands())"
```

## Firewall (kalau perlu)

Pastikan port `9008` open kalau client di luar VPS perlu akses:
```bash
ufw allow 9008/tcp   # kalau ufw aktif
```

## Migrasi dari Modal

Setelah VPS service running stable + n8n sudah pointing ke `http://31.97.222.83:9008`:
1. Test endpoint VPS dengan brand sample
2. Update `VITE_API_URL` di Lovable frontend (kalau ada)
3. Update `webhook URL` di n8n workflow (yang manggil `/fetch_meta_ads`)
4. Disable cron Modal: `modal app stop cpas-meta-ads`
5. (Optional) Hapus app Modal: `modal app delete cpas-meta-ads`

## Troubleshooting

| Masalah | Solusi |
|---|---|
| `Cannot find module 'fastapi'` | Pip install belum jalan: `.venv/bin/pip install -r requirements.txt` |
| Service `failed (Result: exit-code)` | Cek log: `journalctl -u cpas-meta-ads -n 50` |
| `Port 9008 already in use` | Cek dengan `lsof -i :9008`, ganti port di systemd service |
| Cron tidak jalan | Cek `systemctl is-active cpas-meta-ads` (cron in-process butuh service hidup) |
| `.env` tidak ke-load | EnvironmentFile harus path absolut tanpa quotes; cek `systemctl cat cpas-meta-ads` |
