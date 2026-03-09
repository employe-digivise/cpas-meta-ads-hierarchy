// ============================================================
// Meta API Client
//
// Menggantikan semua HTTP Request nodes di n8n:
//   - Get Campaign (insights level=campaign) → tidak lagi dibutuhkan
//   - Get Adset Insight → diganti: get all adsets dari account level
//   - Get Ads Insight1  → diganti: get all insights level=ad dari account level
//   - Get Ads Status    → diganti: get all ads dari account level
//   - Get Ads Insight2  → digabung dengan Get Ads Status
//
// Semua 3 calls dijalankan secara PARALLEL menggunakan Promise.all
// ============================================================

import axios, { AxiosError } from "axios";

const META_BASE = "https://graph.facebook.com";
const API_VERSION = process.env.META_API_VERSION ?? "v21.0";
const ACCESS_TOKEN = process.env.META_ACCESS_TOKEN ?? "";

// ---- Types ----

export interface MetaActionValue {
  action_type: string;
  value: string;
}

export interface AdInsightRaw {
  campaign_id: string;
  campaign_name: string;
  adset_id: string;
  adset_name: string;
  ad_id: string;
  ad_name: string;
  spend?: string;
  reach?: string;
  frequency?: string;
  impressions?: string;
  inline_link_clicks?: string;
  cpm?: string;
  inline_link_click_ctr?: string;
  cost_per_inline_link_click?: string;
  catalog_segment_value?: MetaActionValue[];
  catalog_segment_actions?: MetaActionValue[];
  date_start?: string;
  date_stop?: string;
}

export interface AdsetRaw {
  id: string;
  name: string;
  campaign_id: string;
  optimization_goal?: string;
  promoted_object?: {
    custom_event_type?: string;
    [key: string]: unknown;
  };
}

export interface AdRaw {
  id: string;
  name: string;
  adset_id: string;
  campaign_id: string;
  effective_status: string;
  creative?: {
    thumbnail_url?: string;
    image_url?: string;
  };
}

export interface MetaFetchResult {
  insights: AdInsightRaw[];
  adsets: AdsetRaw[];
  ads: AdRaw[];
}

// ---- Helpers ----

// Fetch semua halaman dari Meta API (handle pagination via next cursor)
interface MetaPagedResponse<T> {
  data: T[];
  paging?: { next?: string };
}

async function fetchAllPages<T>(url: string, maxPages = 50): Promise<T[]> {
  const results: T[] = [];
  let nextUrl: string | null = url;
  let page = 0;

  while (nextUrl) {
    if (page >= maxPages) {
      throw new Error(`Pagination melebihi batas ${maxPages} halaman. Kemungkinan loop tak terbatas.`);
    }

    try {
      const res = await axios.get<MetaPagedResponse<T>>(nextUrl);
      const body: MetaPagedResponse<T> = res.data;

      if (Array.isArray(body.data)) {
        results.push(...body.data);
      }

      nextUrl = body.paging?.next ?? null;
      page++;
    } catch (err) {
      const axiosErr = err as AxiosError<{ error?: { message: string; code: number } }>;
      const metaError = axiosErr.response?.data?.error;

      if (metaError) {
        // Jika error dari Meta API (misalnya token expired, rate limit)
        throw new Error(`Meta API Error (${metaError.code}): ${metaError.message}`);
      }

      throw err;
    }
  }

  return results;
}

// ---- Main Fetch Function ----

export async function fetchMetaAdsData(
  accountId: string,
  dateRange: { since: string; until: string }
): Promise<MetaFetchResult> {
  const token = ACCESS_TOKEN;

  if (!token) {
    throw new Error("META_ACCESS_TOKEN belum diset di environment variables");
  }

  const timeRange = JSON.stringify(dateRange);

  // ================================================================
  // Call A: Ad-level insights
  // Menggantikan loop: Get Campaign → Get Adset → Get Ads Insight1
  // Langsung ambil semua insights level=ad dari account level
  // ================================================================
  const insightsUrl =
    `${META_BASE}/${API_VERSION}/${accountId}/insights` +
    `?level=ad` +
    `&fields=campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,` +
    `spend,reach,frequency,impressions,inline_link_clicks,cpm,inline_link_click_ctr,cost_per_inline_link_click,` +
    `catalog_segment_value,catalog_segment_actions` +
    `&time_range=${encodeURIComponent(timeRange)}` +
    `&time_zone=Asia/Jakarta` +
    `&limit=500` +
    `&access_token=${token}`;

  // ================================================================
  // Call B: All adsets in account (untuk objective/optimization_goal)
  // Menggantikan: Get Adset Insight (/{campaign_id}/adsets)
  // ================================================================
  const adsetsUrl =
    `${META_BASE}/${API_VERSION}/${accountId}/adsets` +
    `?fields=id,name,optimization_goal,promoted_object,campaign_id` +
    `&limit=500` +
    `&access_token=${token}`;

  // ================================================================
  // Call C: All ads in account (status + creative)
  // Menggantikan: Get Ads Status + Get Ads Insight2 (creative)
  // ================================================================
  const adsUrl =
    `${META_BASE}/${API_VERSION}/${accountId}/ads` +
    `?fields=id,name,adset_id,campaign_id,effective_status,` +
    `creative{thumbnail_url,image_url}` +
    `&limit=500` +
    `&access_token=${token}`;

  // Jalankan ketiga call SECARA PARALLEL
  // Total request: 3 (vs ratusan di n8n workflow)
  console.log(`[MetaClient] Fetching data for ${accountId}, date: ${dateRange.since}`);
  console.log(`[MetaClient] Running 3 parallel API calls...`);

  const [insights, adsets, ads] = await Promise.all([
    fetchAllPages<AdInsightRaw>(insightsUrl),
    fetchAllPages<AdsetRaw>(adsetsUrl),
    fetchAllPages<AdRaw>(adsUrl),
  ]);

  console.log(
    `[MetaClient] Done. insights=${insights.length}, adsets=${adsets.length}, ads=${ads.length}`
  );

  return { insights, adsets, ads };
}
