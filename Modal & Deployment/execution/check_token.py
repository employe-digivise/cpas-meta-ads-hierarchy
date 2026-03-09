"""
check_token.py — Cek sisa hari Meta Access Token
==================================================
Panggil kapan saja untuk tahu apakah token hampir expired.
Cocok dijalankan via cron harian atau sebelum deploy.

Usage:
  python execution/check_token.py

Exit codes:
  0 → token OK (> 14 hari)
  1 → token akan expired ≤ 14 hari, atau sudah expired
  2 → error / tidak bisa cek expiry
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config, require

WARN_DAYS = 14  # mulai warning jika sisa ≤ 14 hari


def main() -> None:
    cfg = load_config()
    require(cfg, "META_ACCESS_TOKEN")
    token = cfg["META_ACCESS_TOKEN"]

    print("Mengecek Meta Access Token ...")

    url = f"https://graph.facebook.com/debug_token?input_token={token}&access_token={token}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.read().decode()[:200]}")
        raise SystemExit(2)
    except Exception as e:
        print(f"[ERROR] Tidak bisa menghubungi Meta API: {e}")
        raise SystemExit(2)

    if "error" in body:
        err = body["error"]
        print(f"[ERROR] Meta API: {err.get('message')}")
        raise SystemExit(2)

    data = body.get("data", {})
    expires_at = data.get("expires_at", 0)

    print(f"  App ID        : {data.get('app_id', '-')}")
    print(f"  User ID       : {data.get('user_id', '-')}")
    print(f"  Is valid      : {data.get('is_valid', False)}")

    if not data.get("is_valid", False):
        print("  Status        : ❌ TOKEN TIDAK VALID")
        print("  Action        : Generate token baru di Meta for Developers, lalu jalankan rotate_token.py")
        raise SystemExit(1)

    if expires_at == 0:
        print("  Expires       : Tidak punya expiry (permanent / system user token)")
        print("  Status        : ✅ OK")
        raise SystemExit(0)

    expiry_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    jakarta_tz = timezone(timedelta(hours=7))
    expiry_local = expiry_dt.astimezone(jakarta_tz)
    days_left = (expiry_dt - datetime.now(timezone.utc)).days

    print(f"  Expires       : {expiry_local.strftime('%Y-%m-%d %H:%M')} WIB ({days_left} hari lagi)")

    if days_left <= 0:
        print("  Status        : ❌ TOKEN SUDAH EXPIRED")
        print("  Action        : Generate token baru, lalu jalankan:")
        print("                  python execution/rotate_token.py <NEW_TOKEN>")
        raise SystemExit(1)
    elif days_left <= WARN_DAYS:
        print(f"  Status        : ⚠️  PERLU DIROTASI — tinggal {days_left} hari")
        print("  Action        : Generate token baru di Meta for Developers, lalu jalankan:")
        print("                  python execution/rotate_token.py <NEW_TOKEN>")
        raise SystemExit(1)
    else:
        print("  Status        : ✅ OK")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
