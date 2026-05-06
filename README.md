# CPAS Meta Ads — Hierarchy Backend

Backend fetch data **Meta Ads (CPAS)** untuk 15 brand Digivise. Di-deploy di
**VPS** sebagai HTTP endpoint (FastAPI/uvicorn) + daily cron (APScheduler in-process),
lalu dikonsumsi oleh n8n → Supabase → dashboard Lovable.

- **Endpoint:** `POST http://31.97.222.83:9008/fetch_meta_ads`
- **Health:** `GET http://31.97.222.83:9008/health`
- **Cron:** 07:00 WIB tiap hari (fetch semua 15 brand, push ke n8n webhook)
- **Output:** flat rows (1 row = 1 ad × 1 hari) — siap di-upsert ke Supabase

---

## Struktur Folder

```
cpas_meta_ads_hierarchy/
├── .claude/skills/                         # Skills Claude Code (auto-load)
│
├── Modal & Deployment/
│   └── execution/
│       ├── modal_app.py                    # FastAPI app + APScheduler cron
│       ├── requirements.txt                # Runtime dependencies
│       ├── config_loader.py                # Load .env untuk CLI script
│       ├── check_token.py                  # Cek sisa hari Meta Access Token
│       ├── rotate_token.py                 # Rotasi long-lived token (.env + restart)
│       ├── test_endpoint.py                # Smoke test endpoint live
│       ├── deploy/
│       │   ├── README.md                   # Panduan VPS deploy lengkap
│       │   ├── install.sh                  # First-time install di VPS
│       │   ├── update.sh                   # Pull code + restart service
│       │   └── cpas-meta-ads.service       # Systemd unit
│       └── tests/                          # Unit tests (pytest)
│
├── CURL_COMMANDS.sh                        # Contoh curl
├── .env.example
└── README.md
```

> Catatan: nama folder `Modal & Deployment/` dipertahankan untuk minimize churn,
> tapi project sekarang **tidak lagi pakai Modal** — runtime sepenuhnya VPS.

---

## Komponen Utama

### `modal_app.py`
- HTTP endpoint `POST /fetch_meta_ads` — fetch 1 brand (default kemarin) atau date range.
- Endpoint `GET /health` — untuk monitoring.
- Cron `daily_fetch_all_brands` — jalan 00:00 UTC (07:00 WIB) via APScheduler in-process.
- Alert via `ALERT_WEBHOOK_URL` kalau >3 brand gagal atau token ≤7 hari.
- Strategi fetch: insights dulu → batch metadata `?ids=...` untuk ad spent-but-not-active
  (preserves status PAUSED/ARCHIVED untuk ads yang sempat spend).

---

## Deploy

Lihat panduan lengkap di [Modal & Deployment/execution/deploy/README.md](Modal%20%26%20Deployment/execution/deploy/README.md).

### Quick deploy (di VPS sebagai root)
```bash
# First time
ssh root@31.97.222.83
mkdir -p /tmp/cpas-install && cd /tmp/cpas-install
curl -sO https://raw.githubusercontent.com/employe-digivise/cpas-meta-ads-hierarchy/main/Modal%20%26%20Deployment/execution/deploy/install.sh
bash install.sh

# Setelah commit baru
ssh root@31.97.222.83
bash /root/digivise/cpas-meta-ads/Modal\ \&\ Deployment/execution/deploy/update.sh
```

### Cek service
```bash
systemctl status cpas-meta-ads
journalctl -u cpas-meta-ads -f
curl http://31.97.222.83:9008/health
```

### Cek Token
```bash
python execution/check_token.py
# exit 0 → OK (>14 hari), 1 → warning/expired, 2 → error
```

### Rotasi Token
```bash
# Local (laptop)
python execution/rotate_token.py <NEW_META_TOKEN>

# Di VPS — otomatis restart service
ssh root@31.97.222.83
cd /root/digivise/cpas-meta-ads
.venv/bin/python "Modal & Deployment/execution/rotate_token.py" <NEW_META_TOKEN>
```

### Test Endpoint
```bash
bash CURL_COMMANDS.sh
pytest "Modal & Deployment/execution/tests/"
```

---

## Output Schema (ringkas)

Setiap row di `data[]` berisi: `brand`, `brand_id`, `date_start`, `date_stop`,
`campaign_id/name`, `adset_id/name`, `ad_id/name`, `objective`, metric CPAS
(`spend`, `reach`, `impressions`, `link_click`, `cpm`, `ctr`, `cpc`,
`atc_value/qty`, `purchase_value/qty`, `roas`), flag (`status`, `_status`,
`_adset_status`, `_campaign_status`, `_hierarchy_ok`), dan creative
(`thumbnail_url`, `image_url`).

Detail lengkap + aturan additivity (⚠️ `cpm`/`ctr`/`cpc`/`roas` **tidak boleh**
di-`SUM()`) ada di [`.claude/skills/ads-campaigns/cpas-meta-ads/SKILL.md`](.claude/skills/ads-campaigns/cpas-meta-ads/SKILL.md).

---

## Arsitektur

```
n8n (1 HTTP Request)  ────────────────┐
                                      │  POST /fetch_meta_ads
APScheduler (07:00 WIB × 15 brand)────┤  Authorization: Bearer
                                      ▼
                          VPS:9008 (uvicorn → modal_app.py)
                                      │
                          insights → batch metadata → normalize
                                      │
                                      ▼
                          JSON response → n8n → Supabase → Lovable
```

---

## Environment / Secrets

Dikelola via `.env` di VPS (`/root/digivise/cpas-meta-ads/.env`) — di-load oleh
systemd via `EnvironmentFile`. **Tidak pernah di-commit.**

| Key | Keterangan |
|--------|-----------|
| `META_ACCESS_TOKEN` | Long-lived Meta Graph API token (60 hari) |
| `API_AUTH_TOKEN` | Bearer token untuk endpoint `/fetch_meta_ads` |
| `N8N_WEBHOOK_URL` | Tujuan push hasil cron harian |
| `ALERT_WEBHOOK_URL` | Opsional — Slack/Discord alert |
| `HOST` / `PORT` | Default `0.0.0.0` / `9008` |

---

## Link Terkait

- Repo: `employe-digivise/cpas-meta-ads-hierarchy`
- VPS: `31.97.222.83` (sharing dengan WhatsApp service di port 9004)
- Dashboard konsumer: Lovable (via Supabase `meta_ads_flat`)
