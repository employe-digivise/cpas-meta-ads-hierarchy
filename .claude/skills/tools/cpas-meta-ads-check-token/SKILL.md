---
name: cpas-meta-ads-check-token
description: Cek sisa hari Meta Access Token CPAS. Gunakan sebelum deploy atau saat ada warning token_warning di response endpoint.
user-invocable: true
allowed-tools: Bash
---

# Cek Expiry Meta Access Token

## Jalankan

```bash
cd "Modal & Deployment"
python3 execution/check_token.py
```

## Interpretasi Hasil

| Exit Code | Status | Tindakan |
|-----------|--------|----------|
| `0` | ✅ Token OK (> 14 hari) | Tidak perlu tindakan |
| `1` | ⚠️ Tinggal ≤ 14 hari atau expired | Jalankan `/cpas-meta-ads-rotate-token` segera |
| `2` | ❌ Error koneksi | Cek internet / Meta API status |

## Kapan Dijalankan

- **Sebelum deploy** — pastikan token masih valid
- **Saat `token_warning` muncul di response** — response endpoint menyertakan field `token_warning` jika sisa ≤ 14 hari
- **Rutin** — idealnya dijalankan tiap minggu via cron atau reminder manual

## Monitoring Otomatis via Endpoint

Setiap request ke endpoint `/fetch_meta_ads` sudah menyertakan:
```json
{
  "token_days_left": 7,
  "token_expires_on": "2026-03-13",
  "token_warning": "⚠️ Token Meta expired 7 hari lagi. Segera jalankan rotate_token.py"
}
```

Jika `token_warning` tidak `null` → jalankan `/cpas-meta-ads-rotate-token`.
