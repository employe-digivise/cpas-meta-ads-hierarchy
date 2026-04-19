#!/bin/bash
# ============================================================
# CPAS Meta Ads — Curl Commands
# Endpoint aktif per deploy terakhir: 2026-03-05
# ============================================================

# Load token dari .env (copy .env.example → .env dan isi API_AUTH_TOKEN)
if [ -f "$(dirname "$0")/.env" ]; then
  set -a; . "$(dirname "$0")/.env"; set +a
fi

ENDPOINT="${CPAS_ENDPOINT:-https://aliefianislami--cpas-meta-ads-fetch-meta-ads.modal.run}"
TOKEN="${API_AUTH_TOKEN:?API_AUTH_TOKEN belum di-set — copy .env.example ke .env dan isi tokennya}"

# ============================================================
# PENGGUNAAN DASAR
# Ambil data iklan kemarin (default) untuk satu brand
# ============================================================

# ATRIA — kemarin (default)
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ATRIA"}' | python3 -m json.tool


# ============================================================
# DENGAN TANGGAL SPESIFIK
# Format: YYYY-MM-DD
# ============================================================

# ATRIA — tanggal tertentu
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ATRIA", "date": "2026-03-04"}' | python3 -m json.tool


# ============================================================
# CEK TOKEN EXPIRY (tanpa data iklan)
# Lihat field: token_days_left, token_expires_on, token_warning
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
# SEMUA BRAND YANG TERSEDIA
# ============================================================
# AMK
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "AMK"}' | python3 -m json.tool

# ARSY
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "ARSY"}' | python3 -m json.tool

# BALLOONABLE
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "BALLOONABLE"}' | python3 -m json.tool

# CHANIRA
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "CHANIRA"}' | python3 -m json.tool

# GOODS A FOOTWEAR
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "GOODS A FOOTWEAR"}' | python3 -m json.tool

# HLS
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "HLS"}' | python3 -m json.tool

# KAUFAZ
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "KAUFAZ"}' | python3 -m json.tool

# LILIS
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "LILIS"}' | python3 -m json.tool

# MENLIVING
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "MENLIVING"}' | python3 -m json.tool

# PORTS JOURNAL
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "PORTS JOURNAL"}' | python3 -m json.tool

# RTSR
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "RTSR"}' | python3 -m json.tool

# URBAN EXCHANGE
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "URBAN EXCHANGE"}' | python3 -m json.tool

# FRSCARVES
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "FRSCARVES"}' | python3 -m json.tool

# WELLBORN
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"brand_name": "WELLBORN"}' | python3 -m json.tool
