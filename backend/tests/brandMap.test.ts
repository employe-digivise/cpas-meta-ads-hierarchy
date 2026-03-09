import { describe, it, expect } from "vitest";
import { resolveBrand, getYesterdayJakarta, brandMap } from "../../Modal & Deployment/execution/brandMap";

describe("resolveBrand", () => {
  it("should resolve a valid brand (exact uppercase)", () => {
    const result = resolveBrand("ATRIA");
    expect(result.account_id).toBe("act_1592215248050848");
    expect(result.brand_id).toBe("c311087d-34de-4e34-bee7-42da8fa89c36");
    expect(result.brand).toBe("ATRIA");
  });

  it("should resolve brand case-insensitively", () => {
    const result = resolveBrand("atria");
    expect(result.account_id).toBe("act_1592215248050848");
  });

  it("should trim whitespace from brand name", () => {
    const result = resolveBrand("  ATRIA  ");
    expect(result.account_id).toBe("act_1592215248050848");
  });

  it("should resolve brands with spaces", () => {
    const result = resolveBrand("GOODS A FOOTWEAR");
    expect(result.account_id).toBe("act_1358465195212355");
  });

  it("should throw error for unknown brand", () => {
    expect(() => resolveBrand("UNKNOWN_BRAND")).toThrow("tidak ditemukan");
  });

  it("should throw error for empty brand name", () => {
    expect(() => resolveBrand("")).toThrow("tidak ditemukan");
  });

  it("should have all 15 brands in the map", () => {
    expect(Object.keys(brandMap)).toHaveLength(15);
  });

  it("every brand should have account_id, brand_id, and sheet_id", () => {
    for (const [name, info] of Object.entries(brandMap)) {
      expect(info.account_id, `${name} missing account_id`).toBeTruthy();
      expect(info.brand_id, `${name} missing brand_id`).toBeTruthy();
      expect(info.sheet_id, `${name} missing sheet_id`).toBeTruthy();
    }
  });
});

describe("getYesterdayJakarta", () => {
  it("should return a valid YYYY-MM-DD string", () => {
    const result = getYesterdayJakarta();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("should return a date in the past (not today or future)", () => {
    const result = getYesterdayJakarta();
    const yesterday = new Date(result);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    expect(yesterday.getTime()).toBeLessThan(today.getTime() + 86400000);
  });
});
