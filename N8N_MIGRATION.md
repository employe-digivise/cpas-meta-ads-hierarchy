# n8n HTTP Request Node — Migration Modal → VPS

## TL;DR

Cuma **1 field yang berubah**: URL. Headers + body + method tetap sama.

| Field | Sebelum (Modal) | Sesudah (VPS) |
|---|---|---|
| **Method** | `POST` | `POST` (sama) |
| **URL** | `https://aliefianislami--cpas-meta-ads-fetch-meta-ads.modal.run` | `http://31.97.222.83:9005/fetch_meta_ads` |
| **Auth Header** | `Authorization: Bearer <API_AUTH_TOKEN>` | `Authorization: Bearer <API_AUTH_TOKEN>` (sama) |
| **Content-Type** | `application/json` | `application/json` (sama) |
| **Body** | `{"brand_name": "ATRIA"}` | `{"brand_name": "ATRIA"}` (sama) |
| **Response shape** | unchanged | unchanged |

## Cara Update di n8n (per workflow)

1. Buka workflow yang manggil Modal
2. Edit **HTTP Request** node:
   - Field **URL** → ganti ke `http://31.97.222.83:9005/fetch_meta_ads`
3. Save + Activate ulang
4. Test 1x manual untuk verifikasi response sama dengan sebelumnya

## Catatan Penting

### HTTPS → HTTP
Endpoint VPS plain HTTP (port 9005). Kalau n8n yang kamu pakai enforce
HTTPS-only outbound (n8n Cloud), VPS perlu reverse proxy nginx + cert
Let's Encrypt. Untuk n8n self-hosted, HTTP mestinya OK.

### Timeout
VPS endpoint sama timeout 60-120s tergantung beban Meta API. Set
**Timeout** di n8n HTTP Request node = `120000` (ms) untuk safety.

### Retry on failure
n8n HTTP Request node punya **Retry On Fail** option. Recommended:
- Max Tries: `3`
- Wait Between Tries: `5000` ms

VPS service punya `Restart=on-failure` di systemd, jadi kalau crash
bakal auto-restart dalam <10 detik.

## Curl Reference (kalau testing manual)

### Health check
```bash
curl http://31.97.222.83:9005/health
# Expected: {"status":"ok"}
```

### Fetch 1 brand (default = kemarin)
```bash
curl -X POST http://31.97.222.83:9005/fetch_meta_ads \
  -H "Authorization: Bearer <API_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"brand_name": "ATRIA"}'
```

### Fetch 1 brand tanggal tertentu
```bash
curl -X POST http://31.97.222.83:9005/fetch_meta_ads \
  -H "Authorization: Bearer <API_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"brand_name": "ATRIA", "date": "2026-03-04"}'
```

### Fetch date range (level campaign)
```bash
curl -X POST http://31.97.222.83:9005/fetch_meta_ads \
  -H "Authorization: Bearer <API_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"brand_name": "ATRIA", "date_start": "2026-02-01", "date_end": "2026-02-28"}'
```

### Loop semua 15 brand
```bash
for BRAND in AMK ARSY ATRIA BALLOONABLE CHANIRA "GOODS A FOOTWEAR" HLS KAUFAZ LILIS MENLIVING "PORTS JOURNAL" RTSR "URBAN EXCHANGE" FRSCARVES WELLBORN; do
  echo "=== $BRAND ==="
  curl -s -X POST http://31.97.222.83:9005/fetch_meta_ads \
    -H "Authorization: Bearer <API_AUTH_TOKEN>" \
    -H "Content-Type: application/json" \
    -d "{\"brand_name\": \"$BRAND\"}" \
    | python3 -c "import sys,json;r=json.load(sys.stdin);print('  total_ads:',r.get('total_ads'),'with_insight:',r.get('total_with_insight'))"
done
```

## Rollback (kalau VPS bermasalah)

VPS dan Modal pakai code base sama (sampai commit `605b92e`). Kalau VPS
gagal dan Modal sudah di-stop:

```bash
# Pakai laptop yang punya modal CLI
cd "Modal & Deployment/execution"
# checkout commit pre-VPS (modal_app.py masih punya @modal.fastapi_endpoint)
git checkout 6689763 -- modal_app.py
# deploy ulang ke Modal
# (note: deploy.py sudah dihapus, perlu manual: modal deploy modal_app.py)
modal deploy modal_app.py
```

Recovery time: ~5 menit. Tapi yang paling rapi tetap fix VPS-nya.

## Verifikasi Response Migration

Response dari VPS punya 2 field tambahan dibanding Modal lama:
- `_adset_status` — status adset (ACTIVE/PAUSED/dll)
- `_campaign_status` — status campaign

Field lain identical. Kalau Supabase column-strict dan reject extra fields,
update schema atau drop field di n8n sebelum upsert.
