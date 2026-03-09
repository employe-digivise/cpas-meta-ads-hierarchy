---
name: cpas-meta-ads-rotate-token
description: Rotasi Meta Access Token CPAS yang expired atau akan expired. Gunakan saat check-token menunjukkan sisa ≤ 14 hari atau token_warning muncul di response.
user-invocable: true
allowed-tools: Bash
argument-hint: [new_meta_token]
---

# Rotasi Meta Access Token

## Prasyarat — Generate Token Baru

Sebelum menjalankan script, generate long-lived token baru:

1. Buka [Meta for Developers](https://developers.facebook.com/tools/explorer/)
2. Pilih app yang benar
3. Generate token dengan permission: `ads_read`, `ads_management`
4. Extend ke long-lived token (valid ~60 hari)

## Jalankan Rotasi

```bash
cd "Modal & Deployment"
python3 execution/rotate_token.py <TOKEN_BARU>
```

Script otomatis:
1. Update `META_ACCESS_TOKEN` di `.venv/pyvenv.cfg`
2. Sync secret baru ke Modal (`meta-ads-token`)

## Verifikasi Setelah Rotasi

```bash
# Cek token baru valid
python3 execution/check_token.py

# Test endpoint dengan token baru
python3 execution/test_endpoint.py ATRIA
```

## Redeploy Setelah Rotasi

Token baru otomatis aktif di Modal setelah `rotate_token.py` (tidak perlu redeploy). Namun jika ada perubahan lain di `modal_app.py`, jalankan deploy juga:

```bash
python3 execution/deploy.py
```

## Catatan

- Token Meta berlaku ~60 hari dari tanggal generate
- Set reminder 50 hari setelah rotasi untuk rotasi berikutnya
- Field `token_expires_on` di response endpoint menunjukkan tanggal expired aktual
