// ============================================================
// Data Normalizer
//
// Menggantikan node-node transformasi di n8n:
//   - Code in JavaScript1  (flatten insights + CPAS metrics)
//   - Code in JavaScript2  (fallback campaign_name / adset_name)
//   - Code in JavaScript3  (flatten ads status sebagai NO_INSIGHT rows)
//
// Logic:
//   1. Build adsetMap dari Call B (objective lookup)
//   2. Build adsMap dari Call C (status + creative lookup)
//   3. Loop insights (Call A) → buat row dengan metrics
//   4. Loop ads (Call C) → ads tanpa insight → row kosong _status=NO_INSIGHT
//   5. Return array semua rows
// ============================================================

import { AdRaw, AdsetRaw, MetaFetchResult } from "./metaClient";

// ---- Output Type ----

export interface NormalizedAdRow {
  // meta
  brand: string;
  brand_id: string;
  date_start: string;
  date_stop: string;

  // identity
  campaign_id: string | null;
  campaign_name: string;
  adset_id: string | null;
  adset_name: string;
  ad_id: string | null;
  ad_name: string;

  // objective (dari adset)
  objective: string | null;

  // performance metrics
  spend: number;
  reach: number;
  frequency: number;
  impressions: number;
  link_click: number;
  cpm: number;
  ctr: number;
  cpc: number;

  // CPAS metrics
  atc_value: number;
  purchase_value: number;
  atc_qty: number;
  purchase_qty: number;

  // calculated
  roas: number;

  // status
  status: string;
  _status: string;

  // creative (untuk thumbnail webhook)
  thumbnail_url: string | null;
  image_url: string | null;
}

// ---- Helpers ----

function num(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

// Sama persis dengan cleanObjective di n8n Code in JavaScript1
function cleanObjective(v: unknown): string | null {
  if (!v || typeof v !== "string") return null;
  return v
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function resolveObjective(adset: AdsetRaw | undefined): string | null {
  if (!adset) return null;
  const raw =
    adset.promoted_object?.custom_event_type ??
    adset.optimization_goal ??
    null;
  return cleanObjective(raw);
}

function getImageUrl(ad: AdRaw | undefined): string | null {
  return ad?.creative?.image_url ?? null;
}

// ---- Main Normalizer ----

export function normalizeData(
  result: MetaFetchResult,
  brand: string,
  brand_id: string,
  dateRange: { since: string; until: string }
): NormalizedAdRow[] {
  const { insights, adsets, ads } = result;

  // ==========================================
  // Build lookup maps
  // ==========================================

  // adsetMap: adset_id → adset info (untuk objective)
  const adsetMap = new Map<string, AdsetRaw>();
  for (const a of adsets) {
    adsetMap.set(a.id, a);
  }

  // adsMap: ad_id → ad info (untuk status + creative)
  const adsMap = new Map<string, AdRaw>();
  for (const ad of ads) {
    adsMap.set(ad.id, ad);
  }

  // Lacak ad_id yang sudah punya insight (untuk deteksi NO_INSIGHT)
  const adIdsWithInsight = new Set<string>();

  const rows: NormalizedAdRow[] = [];

  // ==========================================
  // Step 1: Process ads yang punya insight
  // (dari Call A - insights)
  // ==========================================
  for (const entry of insights) {
    const adId = entry.ad_id;
    adIdsWithInsight.add(adId);

    const adsetMeta = adsetMap.get(entry.adset_id);
    const adMeta = adsMap.get(adId);

    // CPAS metrics dari catalog_segment_value (value/revenue)
    let atc_value = 0;
    let purchase_value = 0;
    if (Array.isArray(entry.catalog_segment_value)) {
      for (const v of entry.catalog_segment_value) {
        if (v.action_type === "add_to_cart") atc_value = num(v.value);
        if (v.action_type === "purchase") purchase_value = num(v.value);
      }
    }

    // CPAS metrics dari catalog_segment_actions (quantity)
    let atc_qty = 0;
    let purchase_qty = 0;
    if (Array.isArray(entry.catalog_segment_actions)) {
      for (const a of entry.catalog_segment_actions) {
        if (a.action_type === "add_to_cart") atc_qty = num(a.value);
        if (a.action_type === "purchase") purchase_qty = num(a.value);
      }
    }

    const spend = num(entry.spend);
    const roas = spend > 0 && purchase_value > 0 ? purchase_value / spend : 0;

    rows.push({
      brand,
      brand_id,
      date_start: entry.date_start ?? dateRange.since,
      date_stop: entry.date_stop ?? dateRange.until,

      campaign_id: entry.campaign_id ?? null,
      campaign_name: entry.campaign_name ?? "N/A",
      adset_id: entry.adset_id ?? null,
      adset_name: entry.adset_name ?? "N/A",
      ad_id: adId ?? null,
      ad_name: entry.ad_name ?? "N/A",

      objective: resolveObjective(adsetMeta),

      spend,
      reach: num(entry.reach),
      frequency: num(entry.frequency),
      impressions: num(entry.impressions),
      link_click: num(entry.inline_link_clicks),
      cpm: num(entry.cpm),
      ctr: num(entry.inline_link_click_ctr),
      cpc: num(entry.cost_per_inline_link_click),

      atc_value,
      purchase_value,
      atc_qty,
      purchase_qty,
      roas,

      status: adMeta?.effective_status ?? "UNKNOWN",
      _status: "OK",

      thumbnail_url: adMeta?.creative?.thumbnail_url ?? null,
      image_url: getImageUrl(adMeta),
    });
  }

  // ==========================================
  // Step 2: Ads tanpa insight (NO_INSIGHT rows)
  // Sama dengan Code in JavaScript3 di n8n
  // ==========================================
  for (const ad of ads) {
    if (adIdsWithInsight.has(ad.id)) continue; // sudah punya insight, skip

    rows.push({
      brand,
      brand_id,
      date_start: dateRange.since,
      date_stop: dateRange.until,

      campaign_id: ad.campaign_id ?? null,
      campaign_name: "N/A",
      adset_id: ad.adset_id ?? null,
      adset_name: "N/A",
      ad_id: ad.id ?? null,
      ad_name: ad.name ?? "N/A",

      objective: resolveObjective(adsetMap.get(ad.adset_id)),

      spend: 0,
      reach: 0,
      frequency: 0,
      impressions: 0,
      link_click: 0,
      cpm: 0,
      ctr: 0,
      cpc: 0,

      atc_value: 0,
      purchase_value: 0,
      atc_qty: 0,
      purchase_qty: 0,
      roas: 0,

      status: ad.effective_status ?? "UNKNOWN",
      _status: "NO_INSIGHT",

      thumbnail_url: ad.creative?.thumbnail_url ?? null,
      image_url: getImageUrl(ad),
    });
  }

  return rows;
}
