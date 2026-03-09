---
name: cpas-meta-ads
description: Referensi sistem CPAS Meta Ads — endpoint aktif, output schema, brand map, dan cara interpret data. Auto-load saat bekerja dengan project ini.
user-invocable: false
---

# CPAS Meta Ads — Reference

## Endpoint Aktif

```
POST https://aliefianislami--cpas-meta-ads-fetch-meta-ads.modal.run
Authorization: Bearer c2f058da6462d04c24cbf190289df6a4761977b34a1c08efe50bd3bf092159e4
Content-Type: application/json
```

Request body:
```json
{ "brand_name": "ATRIA" }
{ "brand_name": "ATRIA", "date": "2026-03-04" }
```

## Brand Map (15 brand aktif)

| Brand | Account ID |
|-------|-----------|
| AMK | act_2254667594733384 |
| ARSY | act_1140721503928141 |
| ATRIA | act_1592215248050848 |
| BALLOONABLE | act_993783415450547 |
| CHANIRA | act_781609353137420 |
| GOODS A FOOTWEAR | act_1358465195212355 |
| HLS | act_292145753233324 |
| KAUFAZ | act_1263527284960054 |
| LILIS | act_1192337178724256 |
| MENLIVING | act_245299254049235 |
| PORTS JOURNAL | act_2757030064615005 |
| RTSR | act_952026815689114 |
| URBAN EXCHANGE | act_2129466137258989 |
| FRSCARVES | act_408177362250144 |
| WELLBORN | act_3390310847721143 |

## Output Schema — Response Root

```json
{
  "success": true,
  "brand": "ATRIA",
  "brand_id": "uuid",
  "date": "2026-03-04",
  "total_ads": 164,
  "total_with_insight": 64,
  "total_no_insight": 100,
  "token_days_left": 42,
  "token_expires_on": "2026-04-16",
  "token_warning": null,
  "data": [ ... ]
}
```

## Output Schema — Setiap Row (`data[]`)

Setiap row = 1 ad, 1 hari.

| Field | Type | Keterangan |
|-------|------|------------|
| `brand` | string | Nama brand |
| `brand_id` | string | UUID untuk Supabase |
| `date_start` | string | YYYY-MM-DD |
| `date_stop` | string | YYYY-MM-DD |
| `campaign_id` | string | |
| `campaign_name` | string | |
| `adset_id` | string | |
| `adset_name` | string | |
| `ad_id` | string | |
| `ad_name` | string | |
| `objective` | string\|null | Dari promoted_object atau optimization_goal |
| `spend` | number | IDR |
| `reach` | number | |
| `frequency` | number | |
| `impressions` | number | |
| `link_click` | number | inline_link_clicks |
| `cpm` | number | IDR |
| `ctr` | number | % |
| `cpc` | number | IDR |
| `atc_value` | number | CPAS: nilai add-to-cart (IDR) |
| `purchase_value` | number | CPAS: nilai purchase (IDR) |
| `atc_qty` | number | CPAS: jumlah add-to-cart |
| `purchase_qty` | number | CPAS: jumlah purchase |
| `roas` | number | purchase_value / spend |
| `status` | string | effective_status dari Meta |
| `_status` | string | `"OK"` atau `"NO_INSIGHT"` |
| `thumbnail_url` | string\|null | |
| `image_url` | string\|null | |

## Cara Interpret Data

### `_status`
- `"OK"` — ad ada di hasil insights Meta (serving/spend pada tanggal itu)
- `"NO_INSIGHT"` — ad ACTIVE tapi tidak ada aktivitas pada tanggal itu (spend=0, semua metrics=0)

### `token_warning`
- `null` → token masih aman (> 14 hari)
- ada isi → jalankan `/cpas-meta-ads-rotate-token` segera

### Filter data di n8n
Untuk hanya mendapatkan ads yang benar-benar belanja:
```
_status = "OK" AND spend > 0
```

## Arsitektur

```
n8n (1 HTTP Request)
    ↓ POST /fetch_meta_ads
Modal Endpoint (modal_app.py)
    ↓ 4 parallel calls
    A. insights (semua ads yang serving)
    B. adsets (objective lookup)
    C. ads ACTIVE (status + creative)
    D. debug_token (expiry check)
    ↓ merge & normalize
JSON response → n8n
```

## Skills Terkait

- `/cpas-meta-ads-deploy` — deploy/redeploy endpoint
- `/cpas-meta-ads-check-token` — cek expiry token
- `/cpas-meta-ads-rotate-token` — rotasi token baru
