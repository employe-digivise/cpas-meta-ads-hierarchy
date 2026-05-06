---
name: cpas-meta-ads-deploy
description: Deploy atau redeploy backend CPAS Meta Ads ke VPS. Gunakan saat ada perubahan di modal_app.py, update brand map, atau perlu sync .env baru.
user-invocable: true
allowed-tools: Read, Edit, Write, Bash
---

# SOP — Deploy CPAS Meta Ads ke VPS

Project ini berjalan di VPS `31.97.222.83` port `9008` (FastAPI/uvicorn + APScheduler).
Tidak lagi pakai Modal.

## Lokasi File

```
cpas_meta_ads_hierarchy/
├── .env                                       ← credentials (lokal saja, tidak di-commit)
└── Modal & Deployment/execution/
    ├── modal_app.py                           ← FastAPI app
    ├── requirements.txt                       ← runtime deps
    └── deploy/
        ├── install.sh                         ← first-time install di VPS
        ├── update.sh                          ← pull + restart (after commit)
        └── cpas-meta-ads.service              ← systemd unit
```

VPS path: `/root/digivise/cpas-meta-ads/` (clone dari GitHub).

## Cara Deploy

### Update setelah commit baru (umum)
```bash
ssh root@31.97.222.83
bash /root/digivise/cpas-meta-ads/Modal\ \&\ Deployment/execution/deploy/update.sh
```

### First-time install
```bash
ssh root@31.97.222.83
mkdir -p /tmp/cpas-install && cd /tmp/cpas-install
curl -sO https://raw.githubusercontent.com/employe-digivise/cpas-meta-ads-hierarchy/main/Modal%20%26%20Deployment/execution/deploy/install.sh
bash install.sh

# Setup .env (sekali saja)
cp "/root/digivise/cpas-meta-ads/Modal & Deployment/execution/.env.example" /root/digivise/cpas-meta-ads/.env
nano /root/digivise/cpas-meta-ads/.env
systemctl restart cpas-meta-ads
```

## Endpoint Aktif

```
POST http://31.97.222.83:9008/fetch_meta_ads
Authorization: Bearer <API_AUTH_TOKEN>
Content-Type: application/json

Body: { "brand_name": "ATRIA" }
      { "brand_name": "ATRIA", "date_start": "2026-02-01", "date_end": "2026-02-28" }

Health: GET http://31.97.222.83:9008/health
```

## Cara Tambah / Edit Brand

Edit `BRAND_MAP` di `Modal & Deployment/execution/modal_app.py`:

```python
BRAND_MAP = {
    "NAMA_BRAND": {
        "account_id": "act_XXXXXXXXXX",
        "brand_id": "uuid-brand-id-dari-supabase"
    },
}
```

Setelah edit → commit + push, lalu di VPS jalankan `update.sh`.

## Environment Variables (di `.env` VPS)

| Key | Keterangan |
|-----|-----------|
| `API_AUTH_TOKEN` | Bearer token untuk endpoint |
| `META_ACCESS_TOKEN` | Meta Graph API access token |
| `N8N_WEBHOOK_URL` | Target webhook cron harian |
| `ALERT_WEBHOOK_URL` | Target alert (opsional, boleh kosong) |
| `HOST` / `PORT` | Default `0.0.0.0` / `9008` |

systemd `EnvironmentFile=/root/digivise/cpas-meta-ads/.env` — load otomatis saat service start.

## Strategi Fetch (sekarang)

```
1. /{account_id}/insights?level=ad           ← daftar ad_id yang punya spend
2 (parallel):
   /{account_id}/adsets                       ← + effective_status
   /{account_id}/ads?status=ACTIVE            ← currently active (untuk NO_INSIGHT row)
   /{account_id}/campaigns                    ← + effective_status

3. Diff: (ad_id di insights) - (ad_id di /ads ACTIVE) = ads yang spent-but-paused
   → batch fetch metadata via /v21.0/?ids=<csv> (TANPA filter status)
   → ads list lengkap + creative + status real
```

Setiap row carry `_status`, `_adset_status`, `_campaign_status` (dari `effective_status`).

## Verifikasi Setelah Deploy

```bash
# Health check
curl http://31.97.222.83:9008/health

# Smoke test 1 brand
python "Modal & Deployment/execution/test_endpoint.py" ATRIA

# Live log
ssh root@31.97.222.83 "journalctl -u cpas-meta-ads -f"
```

## Troubleshooting

### Service gagal start
```bash
ssh root@31.97.222.83 "systemctl status cpas-meta-ads && journalctl -u cpas-meta-ads -n 50"
```

### Meta API Error (190): token expired
```bash
ssh root@31.97.222.83
cd /root/digivise/cpas-meta-ads
.venv/bin/python "Modal & Deployment/execution/rotate_token.py" <TOKEN_BARU>
```

### HTTP 401 dari endpoint
Cek header: `Authorization: Bearer <API_AUTH_TOKEN>` cocok dengan `API_AUTH_TOKEN` di `.env` VPS.

### Cron tidak jalan
APScheduler in-process — kalau service mati, cron juga mati. Pastikan
`systemctl is-active cpas-meta-ads` = `active`.

### Port collision
WhatsApp service sudah pakai 9004. CPAS pakai 9008. Kalau perlu ganti port,
edit `cpas-meta-ads.service` + `.env` (PORT) lalu `systemctl daemon-reload && systemctl restart cpas-meta-ads`.

### Brand tidak ditemukan (HTTP 400)
`brand_name` harus cocok dengan key di `BRAND_MAP` (akan di-uppercase otomatis).
Contoh benar: `"GOODS A FOOTWEAR"` bukan `"Goods A Footwear"`.

## Token Management

- **Cek expiry**: `/cpas-meta-ads-check-token`
- **Rotasi token**: `/cpas-meta-ads-rotate-token`
