"""
test_endpoint.py — Test endpoint Modal secara deterministik
===========================================================
Urutan:
  1. Load & validasi config
  2. Kirim request ke endpoint
  3. Validasi response (success=True, data exists)
  4. Print summary

Usage:
  python execution/test_endpoint.py [brand_name] [date]

  brand_name : default ATRIA
  date       : default kemarin (YYYY-MM-DD)
"""
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_loader import load_config, require


def yesterday_jakarta() -> str:
    jakarta = timezone(timedelta(hours=7))
    return (datetime.now(jakarta) - timedelta(days=1)).strftime("%Y-%m-%d")


def main() -> None:
    brand = sys.argv[1] if len(sys.argv) > 1 else "ATRIA"
    date  = sys.argv[2] if len(sys.argv) > 2 else yesterday_jakarta()

    # ── Step 1: Config ───────────────────────────────────────
    print(f"[1/3] Config  : brand={brand}, date={date}")
    cfg = load_config()
    require(cfg, "MODAL_ENDPOINT_URL", "API_AUTH_TOKEN")

    url   = cfg["MODAL_ENDPOINT_URL"]
    token = cfg["API_AUTH_TOKEN"]

    # ── Step 2: Request ──────────────────────────────────────
    print(f"[2/3] Request : POST {url}")
    payload = json.dumps({"brand_name": brand, "date": date}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        print(f"[ERROR] HTTP {e.code}: {raw[:300]}")
        raise SystemExit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        raise SystemExit(1)

    # ── Step 3: Validasi ─────────────────────────────────────
    print("[3/3] Validasi response ...")
    if not body.get("success"):
        print(f"[FAIL] success=False. Detail: {body}")
        raise SystemExit(1)

    total      = body.get("total_ads", 0)
    with_ins   = body.get("total_with_insight", 0)
    no_ins     = body.get("total_no_insight", 0)

    print()
    print("=" * 40)
    print(f"  Brand            : {body.get('brand')}")
    print(f"  Date             : {body.get('date')}")
    print(f"  Total ads        : {total}")
    print(f"  Dengan insight   : {with_ins}")
    print(f"  NO_INSIGHT       : {no_ins}")
    print("=" * 40)
    print("TEST PASSED")


if __name__ == "__main__":
    main()
