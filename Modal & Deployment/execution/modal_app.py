"""
CPAS Meta Ads Backend — Modal Deployment
=========================================
Endpoint HTTP + Cron scheduler harian.

Endpoint: POST /fetch_meta_ads
  Input:  { "brand_name": "ATRIA" }
  Output: Array of normalized ad rows (1 row = 1 ad, 1 hari)

Cron: daily_fetch_all_brands
  Jadwal: 07:00 WIB (00:00 UTC) setiap hari
  Proses: Fetch semua 15 brand sequential → kirim ke webhook n8n
"""

import modal
from fastapi import Header, HTTPException

app = modal.App("cpas-meta-ads")
image = modal.Image.debian_slim().pip_install("httpx", "fastapi")

API_VERSION = "v21.0"

# ── Brand Map ────────────────────────────────────────────────────
BRAND_MAP = {
    "AMK":              {"account_id": "act_2254667594733384", "brand_id": "72e713fd-5979-4b92-b3d7-701b934cfe63"},
    "ARSY":             {"account_id": "act_1140721503928141", "brand_id": "f8de8004-5472-4682-a8df-64fbfc7b641d"},
    "ATRIA":            {"account_id": "act_1592215248050848", "brand_id": "c311087d-34de-4e34-bee7-42da8fa89c36"},
    "BALLOONABLE":      {"account_id": "act_993783415450547",  "brand_id": "49ef95dd-757a-4f54-8c14-512516ce5bd3"},
    "CHANIRA":          {"account_id": "act_781609353137420",  "brand_id": "852ddd26-cdf2-4753-9d56-9414d2e1207a"},
    "GOODS A FOOTWEAR": {"account_id": "act_1358465195212355", "brand_id": "c393db9c-ac48-426d-905e-a02498f8ad2f"},
    "HLS":              {"account_id": "act_292145753233324",  "brand_id": "48fe8387-a987-436c-b8ef-06c238f2be08"},
    "KAUFAZ":           {"account_id": "act_1263527284960054", "brand_id": "9f4980bf-d2f0-4d53-a5d1-090de718a5bc"},
    "LILIS":            {"account_id": "act_1192337178724256", "brand_id": "8c268c08-0cfb-4ee9-8de2-1871470441e8"},
    "MENLIVING":        {"account_id": "act_245299254049235",  "brand_id": "6311d20e-55f8-47af-9376-e07d71781294"},
    "PORTS JOURNAL":    {"account_id": "act_2757030064615005", "brand_id": "4eead26d-466c-43e5-ae19-04d3a90b1f0e"},
    "RTSR":             {"account_id": "act_952026815689114",  "brand_id": "6589b89f-63e5-47b3-ba0b-c876beb83db9"},
    "URBAN EXCHANGE":   {"account_id": "act_2129466137258989", "brand_id": "84b85184-29ab-4eef-b8ac-aeb1d7d5632c"},
    "FRSCARVES":        {"account_id": "act_408177362250144",  "brand_id": "0df14aed-cd65-4927-81bd-124ec21d435a"},
    "WELLBORN":         {"account_id": "act_3390310847721143", "brand_id": "3d4eda32-700f-4ea3-a900-0ba2da6afde2"},
}


# ═══════════════════════════════════════════════════════════════════
# Shared Logic — dipakai oleh HTTP endpoint DAN cron function
# ═══════════════════════════════════════════════════════════════════

async def fetch_with_retry(client, url, max_retries=3):
    """Fetch URL dengan exponential backoff untuk transient errors."""
    import asyncio
    import httpx

    for attempt in range(max_retries):
        try:
            resp = await client.get(url, timeout=30.0)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = (2 ** attempt) + 0.5
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 300:
                body = resp.json()
                if "error" in body:
                    err = body["error"]
                    raise Exception(f"Meta API Error ({err.get('code')}): {err.get('message')}")
            raise Exception(f"Meta API HTTP {resp.status_code}: {resp.text}")
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                wait = (2 ** attempt) + 0.5
                await asyncio.sleep(wait)
                continue
            raise Exception(f"Meta API timeout setelah {max_retries} percobaan")
        except httpx.ConnectError:
            if attempt < max_retries - 1:
                wait = (2 ** attempt) + 0.5
                await asyncio.sleep(wait)
                continue
            raise Exception(f"Meta API connection error setelah {max_retries} percobaan")
    raise Exception("Unexpected retry loop exit")


async def fetch_all_pages(client, url):
    """Fetch semua halaman dari Meta API (handle pagination)."""
    results = []
    next_url = url
    page = 0
    max_pages = 50
    while next_url:
        if page >= max_pages:
            raise Exception(f"Pagination melebihi batas {max_pages} halaman.")
        resp = await fetch_with_retry(client, next_url)
        body = resp.json()
        results.extend(body.get("data", []))
        next_url = body.get("paging", {}).get("next")
        page += 1
    return results


async def get_token_expiry(client, access_token):
    """Cek sisa hari token Meta. Tidak menggagalkan request jika error."""
    from datetime import datetime, timezone

    try:
        url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={access_token}"
        resp = await client.get(url, timeout=10.0)
        body = resp.json()
        expires_at = body.get("data", {}).get("expires_at", 0)
        if expires_at == 0:
            return {"days_left": None, "expires_on": None}
        expiry_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        days_left = (expiry_dt - datetime.now(timezone.utc)).days
        return {"days_left": days_left, "expires_on": expiry_dt.strftime("%Y-%m-%d")}
    except Exception:
        return {"days_left": None, "expires_on": None}


async def fetch_all_data(account_id, access_token, date_str):
    """Fetch insights, adsets, ads, dan token expiry secara parallel."""
    import asyncio
    import httpx
    import json

    base = f"https://graph.facebook.com/{API_VERSION}/{account_id}"
    time_range = json.dumps({"since": date_str, "until": date_str})

    insights_url = (
        f"{base}/insights?level=ad&fields=campaign_id,campaign_name,adset_id,adset_name,"
        f"ad_id,ad_name,spend,reach,frequency,impressions,inline_link_clicks,cpm,"
        f"inline_link_click_ctr,cost_per_inline_link_click,"
        f"catalog_segment_value,catalog_segment_actions"
        f"&time_range={time_range}&time_zone=Asia/Jakarta&limit=500&access_token={access_token}"
    )
    adsets_url = (
        f"{base}/adsets?fields=id,name,optimization_goal,promoted_object,campaign_id"
        f"&limit=500&access_token={access_token}"
    )
    ads_filter = json.dumps([{"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}])
    ads_url = (
        f"{base}/ads?fields=id,name,adset_id,campaign_id,effective_status,"
        f"creative{{thumbnail_url,image_url}}"
        f"&filtering={ads_filter}&limit=500&access_token={access_token}"
    )

    async with httpx.AsyncClient() as client:
        insights, adsets, ads = await asyncio.gather(
            fetch_all_pages(client, insights_url),
            fetch_all_pages(client, adsets_url),
            fetch_all_pages(client, ads_url),
        )
        token_info = await get_token_expiry(client, access_token)
    return insights, adsets, ads, token_info


def _to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _clean_objective(v):
    if not isinstance(v, str):
        return v
    return " ".join(v.lower().replace("_", " ").split())


def _resolve_objective(adset):
    raw = adset.get("promoted_object", {}).get("custom_event_type") or adset.get("optimization_goal")
    return _clean_objective(raw)


def build_rows(brand_name, brand_id, date_str, insights, adsets, ads):
    """Normalize & merge data menjadi rows. 1 row = 1 ad, 1 hari."""
    adset_map = {a["id"]: a for a in adsets}
    ads_map = {a["id"]: a for a in ads}
    campaign_name_map = {}
    adset_name_map = {}
    for entry in insights:
        cid = entry.get("campaign_id")
        aid = entry.get("adset_id")
        if cid:
            campaign_name_map[cid] = entry.get("campaign_name", "N/A")
        if aid:
            adset_name_map[aid] = entry.get("adset_name", "N/A")

    rows = []
    ad_ids_with_insight = set()

    for entry in insights:
        ad_id = entry.get("ad_id")
        ad_ids_with_insight.add(ad_id)
        adset_meta = adset_map.get(entry.get("adset_id"), {})
        ad_meta = ads_map.get(ad_id, {})
        creative = ad_meta.get("creative", {})

        atc_value = 0.0
        purchase_value = 0.0
        for v in (entry.get("catalog_segment_value") or []):
            if v.get("action_type") == "add_to_cart":
                atc_value = _to_num(v.get("value"))
            elif v.get("action_type") == "purchase":
                purchase_value = _to_num(v.get("value"))

        atc_qty = 0.0
        purchase_qty = 0.0
        for v in (entry.get("catalog_segment_actions") or []):
            if v.get("action_type") == "add_to_cart":
                atc_qty = _to_num(v.get("value"))
            elif v.get("action_type") == "purchase":
                purchase_qty = _to_num(v.get("value"))

        spend = _to_num(entry.get("spend"))
        roas = purchase_value / spend if spend > 0 else 0.0

        rows.append({
            "brand": brand_name, "brand_id": brand_id,
            "date_start": date_str, "date_stop": date_str,
            "campaign_id": entry.get("campaign_id"),
            "campaign_name": entry.get("campaign_name", "N/A"),
            "adset_id": entry.get("adset_id"),
            "adset_name": entry.get("adset_name", "N/A"),
            "ad_id": ad_id, "ad_name": entry.get("ad_name", "N/A"),
            "objective": _resolve_objective(adset_meta),
            "spend": spend, "reach": _to_num(entry.get("reach")),
            "frequency": _to_num(entry.get("frequency")),
            "impressions": _to_num(entry.get("impressions")),
            "link_click": _to_num(entry.get("inline_link_clicks")),
            "cpm": _to_num(entry.get("cpm")),
            "ctr": _to_num(entry.get("inline_link_click_ctr")),
            "cpc": _to_num(entry.get("cost_per_inline_link_click")),
            "atc_value": atc_value, "purchase_value": purchase_value,
            "atc_qty": atc_qty, "purchase_qty": purchase_qty,
            "roas": roas,
            "status": "OK",
            "_status": ad_meta.get("effective_status", "UNKNOWN"),
            "thumbnail_url": creative.get("thumbnail_url"),
            "image_url": creative.get("image_url"),
        })

    for ad in ads:
        ad_id = ad.get("id")
        if ad_id in ad_ids_with_insight:
            continue
        adset_meta = adset_map.get(ad.get("adset_id"), {})
        creative = ad.get("creative", {})
        rows.append({
            "brand": brand_name, "brand_id": brand_id,
            "date_start": date_str, "date_stop": date_str,
            "campaign_id": ad.get("campaign_id"),
            "campaign_name": campaign_name_map.get(ad.get("campaign_id"), "N/A"),
            "adset_id": ad.get("adset_id"),
            "adset_name": adset_name_map.get(ad.get("adset_id"), "N/A"),
            "ad_id": ad_id, "ad_name": ad.get("name", "N/A"),
            "objective": _resolve_objective(adset_meta),
            "spend": 0.0, "reach": 0.0, "frequency": 0.0,
            "impressions": 0.0, "link_click": 0.0, "cpm": 0.0,
            "ctr": 0.0, "cpc": 0.0,
            "atc_value": 0.0, "purchase_value": 0.0,
            "atc_qty": 0.0, "purchase_qty": 0.0, "roas": 0.0,
            "status": "NO_INSIGHT",
            "_status": ad.get("effective_status", "UNKNOWN"),
            "thumbnail_url": creative.get("thumbnail_url"),
            "image_url": creative.get("image_url"),
        })

    return rows


# ═══════════════════════════════════════════════════════════════════
# HTTP Endpoint — dipanggil oleh n8n / external client
# ═══════════════════════════════════════════════════════════════════

@app.function(image=image, secrets=[modal.Secret.from_name("api-auth-token"), modal.Secret.from_name("meta-ads-token")], timeout=300)
@modal.fastapi_endpoint(method="POST")
async def fetch_meta_ads(data: dict, authorization: str = Header(...)):
    import os
    import asyncio
    import re
    from datetime import datetime, timezone, timedelta

    # ── Auth ──────────────────────────────────────────────────
    expected_token = os.environ.get("API_AUTH_TOKEN")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if authorization.replace("Bearer ", "").strip() != expected_token:
        raise HTTPException(status_code=403, detail="Invalid authentication token")

    # ── Validasi brand ────────────────────────────────────────
    brand_name = data.get("brand_name", "").strip().upper()
    if brand_name not in BRAND_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Brand '{brand_name}' tidak ditemukan. Tersedia: " + ", ".join(BRAND_MAP.keys()),
        )

    brand_info = BRAND_MAP[brand_name]
    account_id = brand_info["account_id"]
    brand_id = brand_info["brand_id"]

    # ── Tanggal ───────────────────────────────────────────────
    date_str = data.get("date")
    if date_str:
        date_str = date_str.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise HTTPException(status_code=400, detail=f"Format date tidak valid: '{date_str}'. Gunakan format YYYY-MM-DD (contoh: 2026-03-08)")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Tanggal tidak valid: '{date_str}'. Pastikan tanggal benar (contoh: 2026-03-08)")
    else:
        jakarta_tz = timezone(timedelta(hours=7))
        date_str = (datetime.now(jakarta_tz) - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Fetch & build ─────────────────────────────────────────
    access_token = os.environ.get("META_ACCESS_TOKEN")
    try:
        insights, adsets, ads, token_info = await asyncio.to_thread(
            asyncio.run, fetch_all_data(account_id, access_token, date_str)
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # ── Token warning ─────────────────────────────────────────
    days_left = token_info.get("days_left")
    token_warning = None
    if days_left is not None:
        if days_left <= 0:
            token_warning = f"TOKEN EXPIRED sejak {token_info.get('expires_on')}. Jalankan rotate_token.py segera!"
        elif days_left <= 14:
            token_warning = f"Token Meta expired {days_left} hari lagi ({token_info.get('expires_on')}). Segera jalankan rotate_token.py"

    rows = build_rows(brand_name, brand_id, date_str, insights, adsets, ads)
    total_ok = sum(1 for r in rows if r["_status"] == "OK")

    return {
        "success": True,
        "brand": brand_name,
        "brand_id": brand_id,
        "date": date_str,
        "total_ads": len(rows),
        "total_with_insight": total_ok,
        "total_no_insight": len(rows) - total_ok,
        "token_days_left": days_left,
        "token_expires_on": token_info.get("expires_on"),
        "token_warning": token_warning,
        "data": rows,
    }


# ═══════════════════════════════════════════════════════════════════
# Cron — fetch semua brand setiap hari 07:00 WIB → kirim ke webhook
# ═══════════════════════════════════════════════════════════════════

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("meta-ads-token"),
        modal.Secret.from_name("n8n-webhook-url"),
    ],
    timeout=1800,
    schedule=modal.Cron("0 0 * * *"),  # 00:00 UTC = 07:00 WIB
)
async def daily_fetch_all_brands():
    import os
    import asyncio
    import httpx
    import time
    from datetime import datetime, timezone, timedelta

    access_token = os.environ.get("META_ACCESS_TOKEN")
    webhook_url = os.environ.get("N8N_WEBHOOK_URL")
    jakarta_tz = timezone(timedelta(hours=7))
    date_str = (datetime.now(jakarta_tz) - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[CRON] Starting daily fetch for {len(BRAND_MAP)} brands, date={date_str}")

    results_summary = []
    total_start = time.time()

    for brand_name, brand_info in BRAND_MAP.items():
        account_id = brand_info["account_id"]
        brand_id = brand_info["brand_id"]
        brand_start = time.time()
        success = False
        error_msg = None

        # 4 attempts: 1 awal + 3 retry
        for attempt in range(4):
            try:
                if attempt > 0:
                    wait = 30 + (attempt * 10)  # 40s, 50s, 60s
                    print(f"[CRON] {brand_name}: retry {attempt}/3, waiting {wait}s...")
                    await asyncio.sleep(wait)

                print(f"[CRON] {brand_name}: fetching (attempt {attempt + 1}/4)...")
                insights, adsets, ads, token_info = await fetch_all_data(
                    account_id, access_token, date_str
                )
                rows = build_rows(brand_name, brand_id, date_str, insights, adsets, ads)

                payload = {
                    "success": True,
                    "brand": brand_name,
                    "brand_id": brand_id,
                    "date": date_str,
                    "total_ads": len(rows),
                    "total_with_insight": sum(1 for r in rows if r["_status"] == "OK"),
                    "total_no_insight": sum(1 for r in rows if r["_status"] == "NO_INSIGHT"),
                    "token_days_left": token_info.get("days_left"),
                    "token_expires_on": token_info.get("expires_on"),
                    "data": rows,
                }

                # Kirim ke webhook n8n
                async with httpx.AsyncClient() as client:
                    resp = await client.post(webhook_url, json=payload, timeout=60.0)
                    if resp.status_code >= 400:
                        raise Exception(f"Webhook HTTP {resp.status_code}: {resp.text[:200]}")

                success = True
                elapsed = time.time() - brand_start
                print(f"[CRON] {brand_name}: OK ({len(rows)} ads, {elapsed:.1f}s)")
                break

            except Exception as e:
                error_msg = str(e)
                print(f"[CRON] {brand_name}: attempt {attempt + 1}/4 failed — {error_msg}")

        results_summary.append({
            "brand": brand_name,
            "success": success,
            "error": error_msg if not success else None,
            "elapsed_seconds": round(time.time() - brand_start, 1),
        })

    # ── Summary ───────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    succeeded = sum(1 for r in results_summary if r["success"])
    failed = sum(1 for r in results_summary if not r["success"])

    print(f"\n[CRON] ========== SUMMARY ==========")
    print(f"[CRON] Date: {date_str}")
    print(f"[CRON] Total time: {total_elapsed:.1f}s")
    print(f"[CRON] Succeeded: {succeeded}/{len(BRAND_MAP)}")
    print(f"[CRON] Failed: {failed}/{len(BRAND_MAP)}")
    if failed > 0:
        for r in results_summary:
            if not r["success"]:
                print(f"[CRON]   FAILED: {r['brand']} — {r['error']}")
    print(f"[CRON] ================================\n")

    return {
        "date": date_str,
        "total_brands": len(BRAND_MAP),
        "succeeded": succeeded,
        "failed": failed,
        "total_seconds": round(total_elapsed, 1),
        "details": results_summary,
    }
