"""
CPAS Meta Ads Backend — VPS Deployment (FastAPI + APScheduler)
==============================================================
Endpoint HTTP + Cron scheduler harian (in-process via APScheduler).

Endpoint: POST /fetch_meta_ads
  Input:  { "brand_name": "ATRIA" }
         atau dengan date range:
         { "brand_name": "ATRIA", "date_start": "2026-02-01", "date_end": "2026-02-28" }
  Output: Array of normalized ad rows (1 row = 1 ad per date range)

Cron: daily_fetch_all_brands
  Jadwal: 07:00 WIB (00:00 UTC) setiap hari
  Proses: Fetch semua 15 brand sequential → kirim ke webhook n8n

Run lokal:
  uvicorn modal_app:app --host 0.0.0.0 --port 9005

Run via systemd (production VPS): lihat deploy/cpas-meta-ads.service
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
# Shared Logic — dipakai oleh HTTP endpoint DAN scheduler
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


async def _batch_fetch_by_ids(client, graph_root, ids, fields, access_token, batch_size=50):
    """Fetch metadata untuk kumpulan IDs via Graph batch endpoint (?ids=...).

    Dipakai untuk ambil metadata ad/adset/campaign yang spesifik TANPA filter
    effective_status — berguna untuk "spent-but-not-currently-active" ads
    (iklan yang punya spend di date range tapi sekarang sudah di-pause/archived).

    Meta API: GET /v21.0/?ids=<csv> mengembalikan dict {id: {...}}. Batch
    dibatasi ~50 IDs per request; gunakan asyncio.gather untuk IDs > 50.
    ID yang tidak dikembalikan Meta (biasanya karena entity sudah dihapus
    permanen) di-skip diam-diam — nanti akan jatuh ke OK_NO_META di build_rows.
    """
    import asyncio

    if not ids:
        return []

    ids_list = list(ids)
    batches = [ids_list[i:i + batch_size] for i in range(0, len(ids_list), batch_size)]

    async def _one_batch(batch):
        ids_param = ",".join(batch)
        url = f"{graph_root}/?ids={ids_param}&fields={fields}&access_token={access_token}"
        resp = await fetch_with_retry(client, url)
        body = resp.json()
        return [v for v in body.values() if isinstance(v, dict) and v.get("id")]

    nested = await asyncio.gather(*[_one_batch(b) for b in batches])
    return [item for batch_result in nested for item in batch_result]


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


async def fetch_all_data(account_id, access_token, date_start, date_end=None, is_range=False):
    """Fetch insights, adsets, ads, dan token expiry secara parallel.

    Args:
        date_start: Tanggal awal (YYYY-MM-DD)
        date_end: Tanggal akhir (YYYY-MM-DD). Jika None, sama dengan date_start (single day).
        is_range: Jika True, fetch di level=campaign (tanpa adset/ad breakdown).
    """
    import asyncio
    import httpx
    import json

    if date_end is None:
        date_end = date_start

    base = f"https://graph.facebook.com/{API_VERSION}/{account_id}"
    graph_root = f"https://graph.facebook.com/{API_VERSION}"
    time_range = json.dumps({"since": date_start, "until": date_end})

    if is_range:
        insights_url = (
            f"{base}/insights?level=campaign&fields=campaign_id,campaign_name,"
            f"spend,reach,frequency,impressions,inline_link_clicks,cpm,"
            f"inline_link_click_ctr,cost_per_inline_link_click,"
            f"catalog_segment_value,catalog_segment_actions"
            f"&time_range={time_range}&time_zone=Asia/Jakarta&limit=500&access_token={access_token}"
        )
    else:
        insights_url = (
            f"{base}/insights?level=ad&fields=campaign_id,campaign_name,adset_id,adset_name,"
            f"ad_id,ad_name,spend,reach,frequency,impressions,inline_link_clicks,cpm,"
            f"inline_link_click_ctr,cost_per_inline_link_click,"
            f"catalog_segment_value,catalog_segment_actions"
            f"&time_range={time_range}&time_zone=Asia/Jakarta&limit=500&access_token={access_token}"
        )

    async with httpx.AsyncClient() as client:
        if is_range:
            insights = await fetch_all_pages(client, insights_url)
            adsets, ads, campaigns = [], [], []
        else:
            adsets_url = (
                f"{base}/adsets?fields=id,name,optimization_goal,promoted_object,campaign_id,effective_status"
                f"&limit=500&access_token={access_token}"
            )
            ads_filter = json.dumps([{"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}])
            ads_url = (
                f"{base}/ads?fields=id,name,adset_id,campaign_id,effective_status,"
                f"creative{{thumbnail_url,image_url}}"
                f"&filtering={ads_filter}&limit=500&access_token={access_token}"
            )
            campaigns_url = (
                f"{base}/campaigns?fields=id,name,objective,effective_status"
                f"&limit=500&access_token={access_token}"
            )
            insights, adsets, ads, campaigns = await asyncio.gather(
                fetch_all_pages(client, insights_url),
                fetch_all_pages(client, adsets_url),
                fetch_all_pages(client, ads_url),
                fetch_all_pages(client, campaigns_url),
            )

            # Cari ad_ids yang punya spend (di insights) tapi TIDAK ada di list
            # ads-aktif — biasanya karena di-pause/archived/rejected setelah
            # spend tercatat. Fetch metadata mereka tanpa filter status agar
            # row punya creative + effective_status yang benar (bukan UNKNOWN).
            active_ad_ids = {a["id"] for a in ads if a.get("id")}
            spent_ad_ids = {e["ad_id"] for e in insights if e.get("ad_id")}
            missing_ad_ids = spent_ad_ids - active_ad_ids
            if missing_ad_ids:
                extra_ads = await _batch_fetch_by_ids(
                    client, graph_root, missing_ad_ids,
                    "id,name,adset_id,campaign_id,effective_status,creative{thumbnail_url,image_url}",
                    access_token,
                )
                ads.extend(extra_ads)

        token_info = await get_token_expiry(client, access_token)
    return insights, adsets, ads, campaigns, token_info


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


def build_rows(brand_name, brand_id, date_start, insights, adsets, ads, campaigns=None, date_end=None, is_range=False):
    """Normalize & merge data menjadi rows.

    Jika is_range=True: 1 row = 1 campaign (level campaign).
    Jika is_range=False: 1 row = 1 ad (level ad).
    """
    if date_end is None:
        date_end = date_start
    if campaigns is None:
        campaigns = []

    # ── Campaign-level (date range) ──────────────────────────
    if is_range:
        rows = []
        for entry in insights:
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
                "date_start": date_start, "date_stop": date_end,
                "campaign_id": entry.get("campaign_id"),
                "campaign_name": entry.get("campaign_name", "N/A"),
                "adset_id": None, "adset_name": None,
                "ad_id": None, "ad_name": None,
                "objective": None,
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
                "_status": "N/A",
                "_adset_status": "N/A",
                "_campaign_status": "N/A",
                "_hierarchy_ok": True,
                "thumbnail_url": None,
                "image_url": None,
            })
        return rows

    # ── Ad-level (single date) ───────────────────────────────
    adset_map = {a["id"]: a for a in adsets}
    ads_map = {a["id"]: a for a in ads}
    campaign_map = {c["id"]: c for c in campaigns}

    # Fallback name map dari insights, dipakai kalau campaign_map/adset_map kosong
    # (misal /campaigns atau /adsets tidak mengembalikan campaign/adset tertentu)
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
        ad_meta = ads_map.get(ad_id, {})
        creative = ad_meta.get("creative", {})

        # Hierarchy consistency check: insight vs /ads (source of truth).
        # Mismatch biasanya terjadi saat ad dipindah antar adset/campaign
        # setelah spend tercatat. Pilih adMeta sebagai canonical agar dashboard
        # konsisten dengan struktur saat ini.
        hierarchy_ok = True
        if ad_meta:
            if entry.get("adset_id") != ad_meta.get("adset_id"):
                hierarchy_ok = False
                print(f"[Normalizer] adset_id mismatch ad={ad_id}: "
                      f"insight={entry.get('adset_id')} ads={ad_meta.get('adset_id')}")
            if entry.get("campaign_id") != ad_meta.get("campaign_id"):
                hierarchy_ok = False
                print(f"[Normalizer] campaign_id mismatch ad={ad_id}: "
                      f"insight={entry.get('campaign_id')} ads={ad_meta.get('campaign_id')}")

        canonical_adset_id = ad_meta.get("adset_id") or entry.get("adset_id")
        canonical_campaign_id = ad_meta.get("campaign_id") or entry.get("campaign_id")
        adset_meta = adset_map.get(canonical_adset_id, {})
        campaign_meta = campaign_map.get(canonical_campaign_id, {})

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
            "date_start": date_start, "date_stop": date_end,
            "campaign_id": canonical_campaign_id,
            "campaign_name": entry.get("campaign_name") or campaign_meta.get("name") or "N/A",
            "adset_id": canonical_adset_id,
            "adset_name": entry.get("adset_name") or adset_meta.get("name") or "N/A",
            "ad_id": ad_id,
            "ad_name": entry.get("ad_name") or ad_meta.get("name") or "N/A",
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
            "status": "OK" if ad_meta else "OK_NO_META",
            "_status": ad_meta.get("effective_status", "UNKNOWN"),
            "_adset_status": adset_meta.get("effective_status", "UNKNOWN"),
            "_campaign_status": campaign_meta.get("effective_status", "UNKNOWN"),
            "_hierarchy_ok": hierarchy_ok,
            "thumbnail_url": creative.get("thumbnail_url"),
            "image_url": creative.get("image_url"),
        })

    for ad in ads:
        ad_id = ad.get("id")
        if ad_id in ad_ids_with_insight:
            continue
        adset_meta = adset_map.get(ad.get("adset_id"), {})
        campaign_meta = campaign_map.get(ad.get("campaign_id"), {})
        creative = ad.get("creative", {})
        rows.append({
            "brand": brand_name, "brand_id": brand_id,
            "date_start": date_start, "date_stop": date_end,
            "campaign_id": ad.get("campaign_id"),
            "campaign_name": campaign_meta.get("name") or campaign_name_map.get(ad.get("campaign_id"), "N/A"),
            "adset_id": ad.get("adset_id"),
            "adset_name": adset_meta.get("name") or adset_name_map.get(ad.get("adset_id"), "N/A"),
            "ad_id": ad_id, "ad_name": ad.get("name", "N/A"),
            "objective": _resolve_objective(adset_meta),
            "spend": 0.0, "reach": 0.0, "frequency": 0.0,
            "impressions": 0.0, "link_click": 0.0, "cpm": 0.0,
            "ctr": 0.0, "cpc": 0.0,
            "atc_value": 0.0, "purchase_value": 0.0,
            "atc_qty": 0.0, "purchase_qty": 0.0, "roas": 0.0,
            "status": "NO_INSIGHT",
            "_status": ad.get("effective_status", "UNKNOWN"),
            "_adset_status": adset_meta.get("effective_status", "UNKNOWN"),
            "_campaign_status": campaign_meta.get("effective_status", "UNKNOWN"),
            "_hierarchy_ok": True,
            "thumbnail_url": creative.get("thumbnail_url"),
            "image_url": creative.get("image_url"),
        })

    return rows


# ═══════════════════════════════════════════════════════════════════
# Alerting
# ═══════════════════════════════════════════════════════════════════

async def _send_alert(message: str, context: dict | None = None):
    """Kirim alert ke ALERT_WEBHOOK_URL (Slack incoming webhook, Discord, atau
    generic webhook). Silent fail kalau env var tidak di-set atau request gagal
    — alert tidak boleh menggagalkan cron utama.
    """
    import httpx

    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if not webhook_url:
        print(f"[ALERT] (not sent, ALERT_WEBHOOK_URL not set): {message}")
        return

    payload = {"text": f"🚨 CPAS Meta Ads Alert\n{message}"}
    if context:
        payload["context"] = context

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=payload, timeout=10.0)
            if resp.status_code >= 400:
                print(f"[ALERT] Webhook returned HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[ALERT] Failed to send alert: {e}")


# ═══════════════════════════════════════════════════════════════════
# Cron job — fetch semua brand setiap hari 07:00 WIB → kirim ke webhook
# ═══════════════════════════════════════════════════════════════════

async def daily_fetch_all_brands():
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
    token_info_last = {}

    for brand_name, brand_info in BRAND_MAP.items():
        account_id = brand_info["account_id"]
        brand_id = brand_info["brand_id"]
        brand_start = time.time()
        success = False
        error_msg = None

        for attempt in range(4):
            try:
                if attempt > 0:
                    wait = 30 + (attempt * 10)
                    print(f"[CRON] {brand_name}: retry {attempt}/3, waiting {wait}s...")
                    await asyncio.sleep(wait)

                print(f"[CRON] {brand_name}: fetching (attempt {attempt + 1}/4)...")
                insights, adsets, ads, campaigns, token_info = await fetch_all_data(
                    account_id, access_token, date_str
                )
                token_info_last = token_info
                rows = build_rows(brand_name, brand_id, date_str, insights, adsets, ads, campaigns)

                payload = {
                    "success": True,
                    "brand": brand_name,
                    "brand_id": brand_id,
                    "date": date_str,
                    "total_ads": len(rows),
                    "total_with_insight": sum(1 for r in rows if r["status"] == "OK"),
                    "total_no_insight": sum(1 for r in rows if r["status"] == "NO_INSIGHT"),
                    "token_days_left": token_info.get("days_left"),
                    "token_expires_on": token_info.get("expires_on"),
                    "data": rows,
                }

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

    # ── Alerting ──────────────────────────────────────────────
    failed_brands = [r["brand"] for r in results_summary if not r["success"]]
    days_left = token_info_last.get("days_left")
    expires_on = token_info_last.get("expires_on")

    if failed >= 3:
        lines = "\n".join([f"  • {r['brand']}: {r['error']}" for r in results_summary if not r["success"]])
        await _send_alert(
            f"Cron daily_fetch_all_brands: {failed}/{len(BRAND_MAP)} brand GAGAL pada {date_str}\n{lines}",
            context={"date": date_str, "failed_brands": failed_brands},
        )
    elif failed >= 1:
        print(f"[CRON] WARN: {failed} brand gagal tapi di bawah threshold alert ({failed_brands})")

    if days_left is not None:
        if days_left <= 0:
            await _send_alert(
                f"Token Meta EXPIRED sejak {expires_on}. Seluruh cron akan gagal sampai token di-rotate. "
                f"Jalankan rotate_token.py segera.",
                context={"days_left": days_left, "expires_on": expires_on},
            )
        elif days_left <= 7:
            await _send_alert(
                f"Token Meta akan expired dalam {days_left} hari ({expires_on}). "
                f"Jalankan rotate_token.py secepatnya.",
                context={"days_left": days_left, "expires_on": expires_on},
            )

    return {
        "date": date_str,
        "total_brands": len(BRAND_MAP),
        "succeeded": succeeded,
        "failed": failed,
        "total_seconds": round(total_elapsed, 1),
        "token_days_left": days_left,
        "token_expires_on": expires_on,
        "details": results_summary,
    }


# ═══════════════════════════════════════════════════════════════════
# FastAPI App + APScheduler (in-process cron) — VPS deployment
# ═══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(_app: FastAPI):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone="UTC")
    # 00:00 UTC = 07:00 WIB — sama dengan jadwal Modal sebelumnya
    scheduler.add_job(
        daily_fetch_all_brands,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_fetch_all_brands",
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    print(f"[STARTUP] APScheduler started: daily_fetch_all_brands @ 00:00 UTC (07:00 WIB)")
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        print("[SHUTDOWN] APScheduler stopped")


app = FastAPI(title="CPAS Meta Ads Backend", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/fetch_meta_ads")
async def fetch_meta_ads(data: dict, authorization: str = Header(...)):
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
    def _validate_date(value, field_name):
        value = value.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            raise HTTPException(status_code=400, detail=f"Format {field_name} tidak valid: '{value}'. Gunakan format YYYY-MM-DD (contoh: 2026-03-08)")
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Tanggal {field_name} tidak valid: '{value}'. Pastikan tanggal benar (contoh: 2026-03-08)")

    date_start_raw = data.get("date_start")
    date_end_raw = data.get("date_end")
    date_raw = data.get("date")

    if date_start_raw:
        dt_start = _validate_date(date_start_raw, "date_start")
        if date_end_raw:
            dt_end = _validate_date(date_end_raw, "date_end")
        else:
            dt_end = dt_start
        if dt_end < dt_start:
            raise HTTPException(status_code=400, detail=f"date_end ({date_end_raw}) tidak boleh lebih awal dari date_start ({date_start_raw})")
        if (dt_end - dt_start).days > 93:
            raise HTTPException(status_code=400, detail="Range maksimal 93 hari (± 3 bulan) untuk menghindari timeout Meta API")
        date_start = dt_start.strftime("%Y-%m-%d")
        date_end = dt_end.strftime("%Y-%m-%d")
    elif date_raw:
        _validate_date(date_raw, "date")
        date_start = date_raw.strip()
        date_end = date_start
    else:
        jakarta_tz = timezone(timedelta(hours=7))
        date_start = (datetime.now(jakarta_tz) - timedelta(days=1)).strftime("%Y-%m-%d")
        date_end = date_start

    # ── Fetch & build ─────────────────────────────────────────
    is_range = (date_start != date_end)
    access_token = os.environ.get("META_ACCESS_TOKEN")
    try:
        insights, adsets, ads, campaigns, token_info = await fetch_all_data(
            account_id, access_token, date_start, date_end, is_range=is_range
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

    rows = build_rows(brand_name, brand_id, date_start, insights, adsets, ads, campaigns, date_end, is_range=is_range)
    total_ok = sum(1 for r in rows if r["status"] == "OK")

    return {
        "success": True,
        "brand": brand_name,
        "brand_id": brand_id,
        "date_start": date_start,
        "date_end": date_end,
        "level": "campaign" if is_range else "ad",
        "total_campaigns" if is_range else "total_ads": len(rows),
        "total_with_insight": total_ok,
        "total_no_insight": len(rows) - total_ok,
        "token_days_left": days_left,
        "token_expires_on": token_info.get("expires_on"),
        "token_warning": token_warning,
        "data": rows,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "modal_app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "9005")),
        log_level="info",
    )
