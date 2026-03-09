---
name: cpas-meta-ads-deploy
description: Deploy atau redeploy backend CPAS Meta Ads ke Modal. Gunakan saat ada perubahan di modal_app.py, update brand map, atau perlu sync secrets.
user-invocable: true
allowed-tools: Read, Edit, Write, Bash
---

# SOP — Deploy CPAS Meta Ads ke Modal

## Lokasi File
```
cpas_meta_ads_hierarchy/
└── Modal & Deployment/
    ├── .venv/pyvenv.cfg          ← credentials (MODAL_TOKEN, META_TOKEN, dll)
    └── execution/
        ├── modal_app.py          ← kode utama endpoint
        ├── config_loader.py      ← loader credentials
        └── deploy.py             ← script deploy otomatis
```

## Cara Deploy (Gunakan Script)

```bash
cd "Modal & Deployment"
python3 execution/deploy.py
```

Script ini otomatis:
1. Load config dari `.venv/pyvenv.cfg`
2. Verifikasi modal CLI tersedia
3. Sync secrets ke Modal (`meta-ads-token`, `api-auth-token`)
4. Deploy `modal_app.py`

## Endpoint Aktif

```
POST https://aliefianislami--cpas-meta-ads-fetch-meta-ads.modal.run
Authorization: Bearer <API_AUTH_TOKEN>
Content-Type: application/json

Body: { "brand_name": "ATRIA" }
      { "brand_name": "ATRIA", "date": "2026-03-04" }  ← optional date
```

URL tidak berubah selama nama app (`cpas-meta-ads`) dan nama fungsi (`fetch_meta_ads`) tidak diubah.

## Cara Tambah / Edit Brand

Edit `brand_map` di `Modal & Deployment/execution/modal_app.py`:

```python
brand_map = {
    "NAMA_BRAND": {
        "account_id": "act_XXXXXXXXXX",
        "brand_id": "uuid-brand-id-dari-supabase"
    },
}
```

Setelah edit → **wajib redeploy** via `python3 execution/deploy.py`.

## Secrets di Modal

| Modal Secret Name | Env Variable        | Keterangan                  |
|-------------------|---------------------|-----------------------------|
| `api-auth-token`  | `API_AUTH_TOKEN`    | Bearer token untuk auth n8n |
| `meta-ads-token`  | `META_ACCESS_TOKEN` | Meta Graph API access token |

Secrets di-sync otomatis saat deploy. Update manual jika diperlukan:
```bash
modal secret create --force meta-ads-token META_ACCESS_TOKEN="TOKEN_BARU"
```

## Call API yang Dilakukan (4 Parallel)

```
A. /{account_id}/insights?level=ad   ← metrics + CPAS (semua ads yang serve)
B. /{account_id}/adsets              ← objective lookup
C. /{account_id}/ads?status=ACTIVE   ← status + creative (hanya ACTIVE)
D. debug_token                        ← cek expiry token
```

## Setelah Deploy — Verifikasi

```bash
cd "Modal & Deployment"
python3 execution/test_endpoint.py ATRIA
```

Atau lihat response field `token_warning` — jika ada isinya, token perlu segera dirotasi.

## Token Management

- **Cek expiry**: gunakan `/cpas-meta-ads-check-token`
- **Rotasi token**: gunakan `/cpas-meta-ads-rotate-token`

## Troubleshooting

### Meta API Error (190): token expired
```bash
cd "Modal & Deployment"
python3 execution/rotate_token.py <TOKEN_BARU>
```

### HTTP 401 dari endpoint
Cek header: `Authorization: Bearer <API_AUTH_TOKEN>`
Nilai token ada di `.venv/pyvenv.cfg` key `API_AUTH_TOKEN`.

### Endpoint tidak merespons
```bash
modal app list
modal app logs cpas-meta-ads
```

### Brand tidak ditemukan (HTTP 400)
`brand_name` harus cocok dengan key di `brand_map` (akan di-uppercase otomatis).
Contoh benar: `"GOODS A FOOTWEAR"` bukan `"Goods A Footwear"`.
