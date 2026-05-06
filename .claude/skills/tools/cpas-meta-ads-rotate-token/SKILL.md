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

### Local (laptop)
```bash
python "Modal & Deployment/execution/rotate_token.py" <TOKEN_BARU>
```
Ini hanya update `.env` lokal. Untuk update VPS, lihat di bawah.

### Di VPS (production — otomatis restart service)
```bash
ssh root@31.97.222.83
cd /root/digivise/cpas-meta-ads
.venv/bin/python "Modal & Deployment/execution/rotate_token.py" <TOKEN_BARU>
```

Script otomatis:
1. Update `META_ACCESS_TOKEN` di `/root/digivise/cpas-meta-ads/.env`
2. Restart `cpas-meta-ads` systemd service

## Verifikasi Setelah Rotasi

```bash
# Cek token baru valid
python "Modal & Deployment/execution/check_token.py"

# Test endpoint dengan token baru
python "Modal & Deployment/execution/test_endpoint.py" ATRIA

# Cek service di VPS jalan
curl http://31.97.222.83:9005/health
```

## Catatan

- Token Meta berlaku ~60 hari dari tanggal generate
- Set reminder 50 hari setelah rotasi untuk rotasi berikutnya
- Field `token_expires_on` di response endpoint menunjukkan tanggal expired aktual
- Setelah rotate di VPS, cron harian otomatis pakai token baru (tidak perlu redeploy)
