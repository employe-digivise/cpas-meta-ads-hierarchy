# CPAS Meta Ads Backend Service

Backend service yang menggantikan seluruh workflow n8n yang kompleks.
Setelah service ini berjalan, n8n hanya butuh **1 node HTTP Request**.

---

## Arsitektur

```
n8n (1 node)
    │
    │ POST /api/meta-ads/fetch
    │ { "brand_name": "ATRIA" }
    ▼
Backend Service (Node.js/Express)
    │
    ├── 1. Resolve brand → account_id, brand_id
    ├── 2. Hitung date range (yesterday)
    ├── 3. Parallel fetch (3 calls sekaligus):
    │       ├── Call A: /{account_id}/insights?level=ad  → semua metrics
    │       ├── Call B: /{account_id}/adsets             → objective
    │       └── Call C: /{account_id}/ads                → status + creative
    ├── 4. Merge & normalize data di memory
    └── 5. Return JSON array
```

---

## Setup

### 1. Install dependencies

```bash
cd backend
npm install
```

### 2. Konfigurasi environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
PORT=3000
META_ACCESS_TOKEN=EAAZAhMVI5tZBYBQ...  # token dari Meta Ads
META_API_VERSION=v21.0
WEBHOOK_SECRET=otomatisasiN8N
```

### 3. Jalankan (development)

```bash
npm run dev
```

### 4. Build & jalankan (production)

```bash
npm run build
npm start
```

---

## Endpoint

### POST /api/meta-ads/fetch

**Headers:**
```
X-Webhook-Secret: otomatisasiN8N
Content-Type: application/json
```

**Body:**
```json
{
  "brand_name": "ATRIA"
}
```

**Body (dengan custom date):**
```json
{
  "brand_name": "ATRIA",
  "date": "2026-03-04"
}
```

**Response:**
```json
{
  "success": true,
  "brand": "ATRIA",
  "brand_id": "c311087d-34de-4e34-bee7-42da8fa89c36",
  "date": "2026-03-04",
  "total_ads": 142,
  "total_with_insight": 87,
  "total_no_insight": 55,
  "elapsed_ms": 3200,
  "data": [
    {
      "brand": "ATRIA",
      "brand_id": "c311087d-34de-4e34-bee7-42da8fa89c36",
      "date_start": "2026-03-04",
      "date_stop": "2026-03-04",
      "campaign_id": "120213...",
      "campaign_name": "ATRIA | NV | ...",
      "adset_id": "120214...",
      "adset_name": "ATRIA | Adset | ...",
      "ad_id": "120215...",
      "ad_name": "ATRIA | Ad | ...",
      "objective": "purchase",
      "spend": 150000,
      "reach": 12500,
      "frequency": 1.4,
      "impressions": 17500,
      "clicks": 320,
      "cpm": 8571,
      "ctr": 1.82,
      "cpc": 468,
      "atc_value": 450000,
      "purchase_value": 900000,
      "atc_qty": 15,
      "purchase_qty": 6,
      "roas": 6.0,
      "status": "ACTIVE",
      "_status": "OK",
      "thumbnail_url": "https://...",
      "image_url": "https://..."
    }
  ]
}
```

---

## Curl (untuk testing manual)

```bash
curl -X POST http://localhost:3000/api/meta-ads/fetch \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: otomatisasiN8N" \
  -d '{"brand_name": "ATRIA"}'
```

Dengan custom date:
```bash
curl -X POST http://localhost:3000/api/meta-ads/fetch \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: otomatisasiN8N" \
  -d '{"brand_name": "ATRIA", "date": "2026-03-04"}'
```

---

## Konfigurasi n8n

Setelah service berjalan, buat 1 node di n8n:

**Node type**: HTTP Request
**Method**: POST
**URL**: `http://YOUR_SERVER_IP:3000/api/meta-ads/fetch`

**Headers**:
| Name | Value |
|------|-------|
| X-Webhook-Secret | otomatisasiN8N |
| Content-Type | application/json |

**Body** (JSON):
```json
{
  "brand_name": "{{ $json.brand_name }}"
}
```

---

## Struktur File

```
backend/
├── src/
│   ├── index.ts        # Express server & endpoint handler
│   ├── brandMap.ts     # Mapping brand → account_id, brand_id
│   ├── metaClient.ts   # Meta API calls (3 parallel calls)
│   └── normalizer.ts   # Data transformation & merge
├── package.json
├── tsconfig.json
└── .env.example
```

---

## Perbandingan dengan n8n Workflow Lama

| Aspek | n8n lama | Backend baru |
|-------|----------|--------------|
| Jumlah HTTP request | `1 + N_campaign + N_adset × 3` | **3** (parallel) |
| Waktu eksekusi | ~5-15 menit | ~3-10 detik |
| Maintainability | Sulit (banyak node) | Mudah (kode TypeScript) |
| Error handling | Terbatas | Full try/catch + logging |
| Debugging | Sulit | Console log terstruktur |

---

## Brand yang Tersedia

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
| THE NUEPISODE | (belum ada account_id) |
