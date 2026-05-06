#!/bin/bash
# ============================================================
# CPAS Meta Ads — Curl Commands
# Endpoint VPS: http://31.97.222.83:9008/fetch_meta_ads
# ============================================================

# Load token dari .env (copy .env.example → .env dan isi API_AUTH_TOKEN)
if [ -f "$(dirname "$0")/.env" ]; then
  set -a; . "$(dirname "$0")/.env"; set +a
fi

ENDPOINT="${CPAS_ENDPOINT:-http://31.97.222.83:9008/fetch_meta_ads}"
TOKEN="${API_AUTH_TOKEN:?API_AUTH_TOKEN belum di-set — copy .env.example ke .env dan isi tokennya}"

# ============================================================
# HEALTH CHECK
# ============================================================
# curl http://31.97.222.83:9008/health
# Expected: {"status":"ok"}


# ============================================================
# PENGGUNAAN DASAR — kemarin (default)
# ============================================================

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ATRIA"}' | python3 -m json.tool


# ============================================================
# DENGAN TANGGAL SPESIFIK (single day)
# ============================================================

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ATRIA", "date": "2026-03-04"}' | python3 -m json.tool


# ============================================================
# DATE RANGE (level=campaign)
# ============================================================

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ATRIA", "date_start": "2026-02-01", "date_end": "2026-02-28"}' | python3 -m json.tool


# ============================================================
# CEK TOKEN EXPIRY (tanpa data iklan)
# ============================================================

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ATRIA"}' \
  | python3 -c "
import sys, json
r = json.load(sys.stdin)
print('token_days_left :', r.get('token_days_left'))
print('token_expires_on:', r.get('token_expires_on'))
print('token_warning   :', r.get('token_warning') or 'OK')
"


# ============================================================
# SEMUA BRAND
# ============================================================

for BRAND in AMK ARSY ATRIA BALLOONABLE CHANIRA "GOODS A FOOTWEAR" HLS KAUFAZ LILIS MENLIVING "PORTS JOURNAL" RTSR "URBAN EXCHANGE" FRSCARVES WELLBORN; do
  echo "=== $BRAND ==="
  curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"brand_name\": \"$BRAND\"}" \
    | python3 -c "import sys,json;r=json.load(sys.stdin);print('  total_ads:',r.get('total_ads'),'with_insight:',r.get('total_with_insight'))"
done
