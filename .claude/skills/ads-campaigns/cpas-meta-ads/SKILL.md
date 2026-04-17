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
| `status` | string | `"OK"` / `"NO_INSIGHT"` / `"OK_NO_META"` — flag insight (lihat penjelasan) |
| `_status` | string | Meta `effective_status`: `ACTIVE`, `PAUSED`, `CAMPAIGN_PAUSED`, `ADSET_PAUSED`, `PENDING_REVIEW`, `DISAPPROVED`, `WITH_ISSUES`, `IN_PROCESS`, dst |
| `_hierarchy_ok` | boolean | `false` kalau `campaign_id`/`adset_id` di insight berbeda dengan struktur di `/ads` endpoint (biasanya karena ad dipindah antar adset) |
| `thumbnail_url` | string\|null | |
| `image_url` | string\|null | |

## Cara Interpret Data

### `status` (flag insight)
- `"OK"` — ad ada di hasil insights Meta DAN masih ada di `/ads` endpoint (struktur sekarang). Ini kondisi normal untuk ad yang serving pada tanggal itu.
- `"NO_INSIGHT"` — ad ada di `/ads` tapi tidak ada insight pada tanggal itu (spend=0, semua metric=0). Biasanya ad yang belum serving atau di-pause sebelum tanggal.
- `"OK_NO_META"` — ad punya insight (spend tercatat) tapi **tidak ditemukan di `/ads` endpoint** (kemungkinan ad sudah dihapus/archived antara tanggal insight dan saat fetch). `_status` untuk row ini akan `"UNKNOWN"`, thumbnail null.

### `_status` (Meta effective_status)
Status efektif yang sudah memperhitungkan parent pause + billing + policy. Nilainya berbeda dengan kolom "Delivery" di dashboard Meta Ads Manager (UI me-mapping label lebih ramah, mis. `CAMPAIGN_PAUSED` → "Campaign off").

### `_hierarchy_ok`
- `true` → `insight.adset_id`/`campaign_id` cocok dengan struktur `/ads` saat ini
- `false` → ada mismatch, biasanya ad dipindah antar adset/campaign setelah spend tercatat. Canonical ID yang disimpan di row **mengikuti `/ads`** (struktur saat ini), bukan insight.

### `token_warning`
- `null` → token masih aman (> 14 hari)
- ada isi → jalankan `/cpas-meta-ads-rotate-token` segera

### Filter data di n8n
Untuk hanya mendapatkan ads yang benar-benar belanja:
```
status = "OK" AND spend > 0
```

⚠️ **PENTING untuk dashboard/query**:
- Kalau filter "hanya yang serving" → pakai `status = "OK" AND spend > 0`.
- Kalau sebelumnya pakai `_status = "OK"` → **itu salah** (no rows akan match karena `_status` berisi `ACTIVE`/`PAUSED`/dll, tidak pernah `"OK"`). Update query agar pakai `status` (tanpa underscore).
- Untuk filter ad yang aktif di Meta → pakai `_status = "ACTIVE"`.

## Arsitektur

```
n8n (1 HTTP Request)  ────────────────┐
                                      │  POST /fetch_meta_ads
Modal Cron (07:00 WIB × 15 brand) ────┤  Authorization: Bearer
                                      │
                                      ▼
                          Modal Endpoint (modal_app.py)
                                      │
                          4 parallel calls:
                            A. insights (ads yang serve)
                            B. adsets (objective lookup)
                            C. ads ACTIVE (status + creative)
                            D. campaigns (name fallback NO_INSIGHT)
                                      │
                          1 sequential:
                            E. debug_token (expiry check, non-blocking)
                                      │
                          merge & normalize (build_rows)
                                      │
                                      ▼
                          JSON response → n8n → Supabase → Lovable
```

### Alur Alert (Point 6)

```
Cron gagal >3 brand  ──┐
                       ├──→ _send_alert() ──→ ALERT_WEBHOOK_URL (Slack/Discord)
Token ≤7 hari/expired ─┘
```

Jika `ALERT_WEBHOOK_URL` kosong, alert tetap di-log ke Modal console (tidak fail).

## ⚠️ Metric Additivity — WAJIB DIBACA sebelum agregasi

Output flat (1 row = 1 ad/hari) didesain untuk roll-up bebas di level
campaign/adset/ad, tapi **tidak semua metric bisa di-`SUM()` langsung**.

### ✅ Additive — boleh di-SUM
| Field | Contoh agregasi benar |
|-------|-----------------------|
| `spend` | `SUM(spend) GROUP BY campaign_id` |
| `impressions` | `SUM(impressions)` |
| `link_click` | `SUM(link_click)` |
| `atc_value`, `purchase_value` | `SUM(purchase_value)` |
| `atc_qty`, `purchase_qty` | `SUM(purchase_qty)` |

### ⚠️ Non-additive — HARUS dihitung ulang dari base metric
| Field | ❌ Salah | ✅ Benar |
|-------|---------|---------|
| `cpm` | `SUM(cpm)` / `AVG(cpm)` | `SUM(spend) / SUM(impressions) * 1000` |
| `ctr` | `AVG(ctr)` | `SUM(link_click) / SUM(impressions) * 100` |
| `cpc` | `AVG(cpc)` | `SUM(spend) / NULLIF(SUM(link_click), 0)` |
| `roas` | `AVG(roas)` | `SUM(purchase_value) / NULLIF(SUM(spend), 0)` |
| `frequency` | `AVG(frequency)` | `SUM(impressions) / SUM(reach)` *(approx)* |

### 🚫 `reach` — jangan pernah di-SUM lintas ad/adset
`reach` = jumlah **orang unik**. Audiens bertumpang tindih antar-ad/adset
→ `SUM(reach)` pasti overestimate. Kalau butuh reach level campaign yang
akurat, fetch ulang dari Meta `/insights?level=campaign` (pakai mode
`date_start`/`date_end` → endpoint switch ke campaign-level fetch).

### Contoh SQL view helper (Supabase)
```sql
create or replace view meta_ads_campaign_daily as
select
  brand_id, campaign_id, campaign_name, date_start,
  sum(spend)          as spend,
  sum(impressions)    as impressions,
  sum(link_click)     as link_click,
  sum(purchase_value) as purchase_value,
  sum(purchase_qty)   as purchase_qty,
  sum(spend) / nullif(sum(impressions), 0) * 1000 as cpm,
  sum(link_click) / nullif(sum(impressions), 0) * 100 as ctr,
  sum(spend) / nullif(sum(link_click), 0) as cpc,
  sum(purchase_value) / nullif(sum(spend), 0) as roas
from meta_ads_flat
where status = 'OK'  -- exclude NO_INSIGHT & OK_NO_META
group by brand_id, campaign_id, campaign_name, date_start;
```

---

## Downstream Audit Checklist (n8n + Supabase + Lovable)

Karena sistem melalui chain `Modal → n8n → Supabase → Lovable`, setelah
perubahan schema (tambah `_hierarchy_ok`, nilai baru `OK_NO_META`), tiap
komponen perlu diverifikasi manual. Saya tidak bisa audit otomatis dari repo
ini, tapi checklist di bawah bisa dipakai.

### n8n workflow
- [ ] Filter node yang pakai `_status = "OK"` → **ganti ke `status = "OK"`** (pre-existing bug: `_status` berisi `ACTIVE`/`PAUSED`, tidak pernah `"OK"`)
- [ ] Field mapper — pastikan `_hierarchy_ok` ikut diteruskan ke Supabase (atau dengan sadar di-drop)
- [ ] Supabase insert/upsert — conflict key wajib `(brand_id, ad_id, date_start)` agar re-fetch tidak duplikat

### Supabase schema
- [ ] `ALTER TABLE meta_ads_flat ADD COLUMN _hierarchy_ok BOOLEAN DEFAULT TRUE;` (kalau belum ada)
- [ ] Constraint kolom `status`: kalau ada `CHECK (status IN ('OK','NO_INSIGHT'))`, perlu diperluas ke `('OK','NO_INSIGHT','OK_NO_META')`
- [ ] Unique constraint `(brand_id, ad_id, date_start)` — wajib untuk upsert
- [ ] Query cek sanity: `SELECT status, COUNT(*) FROM meta_ads_flat WHERE date_start > now()-interval '7 days' GROUP BY status;` → harus lihat 3 bucket: OK, NO_INSIGHT, OK_NO_META

### Lovable dashboard
- [ ] Chart/kartu yang aggregation `cpm`/`ctr`/`cpc`/`roas` → harus recompute dari base metric (lihat "Metric Additivity" di atas)
- [ ] Filter "ads aktif": `_status = "ACTIVE"` (bukan `status = "ACTIVE"`)
- [ ] Filter "ads yang serving": `status = "OK" AND spend > 0`
- [ ] Tidak ada `AVG(roas)` atau `SUM(cpm)` di query manapun — recompute dari `SUM(purchase_value)/SUM(spend)` dll

## Skills Terkait

- `/cpas-meta-ads-deploy` — deploy/redeploy endpoint
- `/cpas-meta-ads-check-token` — cek expiry token
- `/cpas-meta-ads-rotate-token` — rotasi token baru
