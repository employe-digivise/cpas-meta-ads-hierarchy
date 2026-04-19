# CPAS Meta Ads — Hierarchy Backend

Backend fetch data **Meta Ads (CPAS)** untuk 15 brand Digivise. Di-deploy ke
[Modal](https://modal.com/) sebagai HTTP endpoint + daily cron, lalu dikonsumsi
oleh n8n → Supabase → dashboard Lovable.

- **Endpoint aktif:** `POST https://aliefianislami--cpas-meta-ads-fetch-meta-ads.modal.run`
- **Cron:** 07:00 WIB tiap hari (fetch semua 15 brand, push ke n8n webhook)
- **Output:** flat rows (1 row = 1 ad × 1 hari) — siap di-upsert ke Supabase

---

## Struktur Folder

```
cpas_meta_ads_hierarchy/
├── .claude/skills/                         # Skills Claude Code (auto-load)
│   ├── ads-campaigns/cpas-meta-ads/        # Referensi schema, brand map, interpret data
│   └── tools/
│       ├── cpas-meta-ads-deploy/           # /cpas-meta-ads-deploy
│       ├── cpas-meta-ads-check-token/      # /cpas-meta-ads-check-token
│       └── cpas-meta-ads-rotate-token/     # /cpas-meta-ads-rotate-token
│
├── Modal & Deployment/
│   └── execution/
│       ├── modal_app.py                    # App utama — HTTP endpoint + cron scheduler
│       ├── deploy.py                       # Sync secrets + deploy ke Modal
│       ├── check_token.py                  # Cek sisa hari Meta Access Token
│       ├── rotate_token.py                 # Rotasi long-lived token
│       ├── config_loader.py                # Loader config dari .venv/pyvenv.cfg
│       ├── test_endpoint.py                # Smoke test endpoint live
│       └── tests/                          # Unit tests (pytest)
│           ├── conftest.py
│           ├── test_brand_map.py
│           └── test_build_rows.py
│
├── CURL_COMMANDS.sh                        # Contoh curl — penggunaan dasar & date range
├── .gitignore
└── README.md
```

---

## Komponen Utama

### `modal_app.py`
- HTTP endpoint `POST /fetch_meta_ads` — fetch 1 brand (default kemarin) atau
  date range (`date_start` + `date_end`).
- Cron `daily_fetch_all_brands` — jalan 00:00 UTC (07:00 WIB), loop 15 brand
  sequential, kirim hasil ke n8n webhook.
- Alert via `ALERT_WEBHOOK_URL` kalau >3 brand gagal atau token ≤7 hari.
- Normalisasi: 4 parallel fetch (insights, adsets, ads, campaigns) +
  debug_token → merge → `build_rows()` → flat JSON.

### Skills (`.claude/skills/`)
Skills auto-load untuk Claude Code saat kerja di repo ini:
- **cpas-meta-ads** — reference schema, brand map, aturan additivity metric,
  dan audit checklist downstream (n8n + Supabase + Lovable).
- **cpas-meta-ads-deploy / check-token / rotate-token** — task skills untuk
  operasi runtime.

---

## Penggunaan

### Deploy
```bash
cd "Modal & Deployment/execution"
python deploy.py
```

### Cek Token
```bash
python execution/check_token.py
# exit 0 → OK (>14 hari), 1 → warning/expired, 2 → error
```

### Rotasi Token
```bash
python execution/rotate_token.py
```

### Test Endpoint
```bash
bash CURL_COMMANDS.sh          # lihat contoh payload
pytest "Modal & Deployment/execution/tests/"
```

---

## Output Schema (ringkas)

Setiap row di `data[]` berisi: `brand`, `brand_id`, `date_start`, `date_stop`,
`campaign_id/name`, `adset_id/name`, `ad_id/name`, `objective`, metric CPAS
(`spend`, `reach`, `impressions`, `link_click`, `cpm`, `ctr`, `cpc`,
`atc_value/qty`, `purchase_value/qty`, `roas`), flag (`status`, `_status`,
`_hierarchy_ok`), dan creative (`thumbnail_url`, `image_url`).

Detail lengkap + aturan additivity (⚠️ `cpm`/`ctr`/`cpc`/`roas` **tidak boleh**
di-`SUM()`) ada di [`.claude/skills/ads-campaigns/cpas-meta-ads/SKILL.md`](.claude/skills/ads-campaigns/cpas-meta-ads/SKILL.md).

---

## Arsitektur

```
n8n (1 HTTP Request)  ────────────────┐
                                      │  POST /fetch_meta_ads
Modal Cron (07:00 WIB × 15 brand) ────┤  Authorization: Bearer
                                      ▼
                          Modal Endpoint (modal_app.py)
                                      │
                          4 parallel fetch → merge → normalize (build_rows)
                                      │
                                      ▼
                          JSON response → n8n → Supabase → Lovable
```

---

## Environment / Secrets

Dikelola via Modal Secret (di-sync oleh `deploy.py` dari `.venv/pyvenv.cfg`
lokal — **tidak pernah di-commit**):

| Secret | Keterangan |
|--------|-----------|
| `META_ACCESS_TOKEN` | Long-lived Meta Graph API token (60 hari) |
| `API_AUTH_TOKEN` | Bearer token untuk endpoint Modal |
| `N8N_WEBHOOK_URL` | Tujuan push hasil cron harian |
| `ALERT_WEBHOOK_URL` | Opsional — Slack/Discord alert (fail >3 brand / token ≤7 hari) |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | Auth Modal CLI |

---

## Link Terkait

- Project: `employe-digivise/cpas-meta-ads-hierarchy`
- Modal app: `cpas-meta-ads`
- Dashboard konsumer: Lovable (via Supabase `meta_ads_flat`)
