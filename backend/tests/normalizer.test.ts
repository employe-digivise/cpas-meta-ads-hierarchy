import { describe, it, expect } from "vitest";
import { normalizeData, NormalizedAdRow } from "../../Modal & Deployment/execution/normalizer";
import { MetaFetchResult, AdInsightRaw, AdsetRaw, AdRaw } from "../../Modal & Deployment/execution/metaClient";

const dateRange = { since: "2026-03-08", until: "2026-03-08" };

function makeInsight(overrides: Partial<AdInsightRaw> = {}): AdInsightRaw {
  return {
    campaign_id: "camp_1",
    campaign_name: "Campaign 1",
    adset_id: "adset_1",
    adset_name: "Adset 1",
    ad_id: "ad_1",
    ad_name: "Ad 1",
    spend: "100",
    reach: "5000",
    frequency: "1.5",
    impressions: "7500",
    inline_link_clicks: "200",
    cpm: "13.33",
    inline_link_click_ctr: "2.67",
    cost_per_inline_link_click: "0.50",
    ...overrides,
  };
}

function makeAdset(overrides: Partial<AdsetRaw> = {}): AdsetRaw {
  return {
    id: "adset_1",
    name: "Adset 1",
    campaign_id: "camp_1",
    optimization_goal: "PURCHASE",
    ...overrides,
  };
}

function makeAd(overrides: Partial<AdRaw> = {}): AdRaw {
  return {
    id: "ad_1",
    name: "Ad 1",
    adset_id: "adset_1",
    campaign_id: "camp_1",
    effective_status: "ACTIVE",
    creative: { thumbnail_url: "https://thumb.jpg", image_url: "https://img.jpg" },
    ...overrides,
  };
}

describe("normalizeData", () => {
  it("should normalize a single insight row correctly", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight()],
      adsets: [makeAdset()],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);

    expect(rows).toHaveLength(1);
    const row = rows[0];
    expect(row.brand).toBe("ATRIA");
    expect(row.brand_id).toBe("brand-uuid-1");
    expect(row.date_start).toBe("2026-03-08");
    expect(row.date_stop).toBe("2026-03-08");
    expect(row.campaign_id).toBe("camp_1");
    expect(row.ad_id).toBe("ad_1");
    expect(row.spend).toBe(100);
    expect(row.reach).toBe(5000);
    expect(row.impressions).toBe(7500);
    expect(row.link_click).toBe(200);
    expect(row._status).toBe("OK");
    expect(row.status).toBe("ACTIVE");
    expect(row.thumbnail_url).toBe("https://thumb.jpg");
    expect(row.image_url).toBe("https://img.jpg");
  });

  it("should resolve objective from promoted_object.custom_event_type first", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight()],
      adsets: [makeAdset({
        optimization_goal: "OFFSITE_CONVERSIONS",
        promoted_object: { custom_event_type: "PURCHASE" },
      })],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].objective).toBe("purchase");
  });

  it("should fallback to optimization_goal when no custom_event_type", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight()],
      adsets: [makeAdset({ optimization_goal: "LINK_CLICKS", promoted_object: undefined })],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].objective).toBe("link clicks");
  });

  it("should extract CPAS metrics (catalog_segment_value & actions)", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight({
        catalog_segment_value: [
          { action_type: "add_to_cart", value: "250000" },
          { action_type: "purchase", value: "1500000" },
        ],
        catalog_segment_actions: [
          { action_type: "add_to_cart", value: "10" },
          { action_type: "purchase", value: "3" },
        ],
      })],
      adsets: [makeAdset()],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].atc_value).toBe(250000);
    expect(rows[0].purchase_value).toBe(1500000);
    expect(rows[0].atc_qty).toBe(10);
    expect(rows[0].purchase_qty).toBe(3);
  });

  it("should calculate ROAS correctly", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight({
        spend: "200",
        catalog_segment_value: [{ action_type: "purchase", value: "1000" }],
      })],
      adsets: [makeAdset()],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].roas).toBe(5); // 1000 / 200 = 5
  });

  it("should return ROAS 0 when spend is 0", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight({
        spend: "0",
        catalog_segment_value: [{ action_type: "purchase", value: "1000" }],
      })],
      adsets: [makeAdset()],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].roas).toBe(0);
  });

  it("should create NO_INSIGHT rows for ads without insights", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight({ ad_id: "ad_1" })],
      adsets: [makeAdset()],
      ads: [
        makeAd({ id: "ad_1" }),
        makeAd({ id: "ad_2", name: "Ad Without Insight" }),
      ],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows).toHaveLength(2);

    const okRow = rows.find((r) => r._status === "OK");
    const noInsightRow = rows.find((r) => r._status === "NO_INSIGHT");

    expect(okRow).toBeDefined();
    expect(okRow!.ad_id).toBe("ad_1");

    expect(noInsightRow).toBeDefined();
    expect(noInsightRow!.ad_id).toBe("ad_2");
    expect(noInsightRow!.ad_name).toBe("Ad Without Insight");
    expect(noInsightRow!.spend).toBe(0);
    expect(noInsightRow!.reach).toBe(0);
    expect(noInsightRow!.roas).toBe(0);
  });

  it("should handle empty insights (all ads become NO_INSIGHT)", () => {
    const result: MetaFetchResult = {
      insights: [],
      adsets: [makeAdset()],
      ads: [makeAd({ id: "ad_1" }), makeAd({ id: "ad_2" })],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows).toHaveLength(2);
    expect(rows.every((r) => r._status === "NO_INSIGHT")).toBe(true);
  });

  it("should handle empty result (no insights, no ads)", () => {
    const result: MetaFetchResult = {
      insights: [],
      adsets: [],
      ads: [],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows).toHaveLength(0);
  });

  it("should handle missing/invalid numeric values gracefully", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight({
        spend: undefined,
        reach: undefined,
        impressions: "not_a_number" as any,
      })],
      adsets: [makeAdset()],
      ads: [makeAd()],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].spend).toBe(0);
    expect(rows[0].reach).toBe(0);
    expect(rows[0].impressions).toBe(0);
  });

  it("should handle missing creative (no thumbnail/image)", () => {
    const result: MetaFetchResult = {
      insights: [makeInsight()],
      adsets: [makeAdset()],
      ads: [makeAd({ creative: undefined })],
    };

    const rows = normalizeData(result, "ATRIA", "brand-uuid-1", dateRange);
    expect(rows[0].thumbnail_url).toBeNull();
    expect(rows[0].image_url).toBeNull();
  });
});
