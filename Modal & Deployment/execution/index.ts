// ============================================================
// CPAS Meta Ads Backend Service
//
// Menggantikan seluruh workflow n8n yang kompleks.
// n8n hanya perlu 1 HTTP Request node yang memanggil endpoint ini.
//
// POST /api/meta-ads/fetch
// Body: { "brand_name": "ATRIA" }
//
// Response: Array of NormalizedAdRow (1 row = 1 ad, 1 hari)
// ============================================================

import dotenv from "dotenv";
import path from "path";
dotenv.config({ path: path.join(__dirname, ".env") });

import express, { Request, Response, NextFunction } from "express";
import { resolveBrand, getYesterdayJakarta } from "./brandMap";
import { fetchMetaAdsData } from "./metaClient";
import { normalizeData } from "./normalizer";

const app = express();
const PORT = process.env.PORT ?? 3000;
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET;

if (!WEBHOOK_SECRET) {
  console.error("[Server] FATAL: WEBHOOK_SECRET belum diset di .env");
  process.exit(1);
}

app.use(express.json());

// ---- Auth Middleware ----
// Validasi X-Webhook-Secret header (sama dengan secret di n8n)
function requireSecret(req: Request, res: Response, next: NextFunction): void {
  const secret = req.headers["x-webhook-secret"];
  if (secret !== WEBHOOK_SECRET) {
    res.status(401).json({ error: "Unauthorized: X-Webhook-Secret tidak valid" });
    return;
  }
  next();
}

// ---- Health Check ----
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// ================================================================
// Main Endpoint
// POST /api/meta-ads/fetch
//
// Menggantikan SELURUH workflow n8n:
//   - Set Account ID & Time Range
//   - Get Campaign → Split Out → Get Adset Insight → Split Out6
//   - Loop Over Items1 → Get Ads Insight1 → Split Out7 → Code in JavaScript1
//   - Loop Over Items  → Get Ads Status   → Split Out1 → Code in JavaScript3
//   - Loop Over Items4 → Get Ads Insight2 → Split Out10 → Edit Fields
//   - Merge1, Merge, Code in JavaScript2
//   - HTTP Request5, HTTP Request1, HTTP Request4
// ================================================================
app.post("/api/meta-ads/fetch", requireSecret, async (req: Request, res: Response) => {
  const startTime = Date.now();

  try {
    const { brand_name, date } = req.body as { brand_name?: string; date?: string };

    // 1. Validasi input
    if (!brand_name) {
      res.status(400).json({ error: "Field brand_name wajib diisi" });
      return;
    }

    // 2. Resolve brand → account_id, brand_id
    const brandInfo = resolveBrand(brand_name);

    if (!brandInfo.account_id) {
      res.status(400).json({
        error: `Brand "${brand_name}" tidak memiliki account_id. Kemungkinan belum aktif.`,
      });
      return;
    }

    // 3. Hitung date range
    // Jika ada parameter `date` di body, gunakan itu. Jika tidak, gunakan kemarin.
    const targetDate = date ?? getYesterdayJakarta();
    const dateRange = { since: targetDate, until: targetDate };

    console.log(
      `[API] Request: brand=${brandInfo.brand}, account=${brandInfo.account_id}, date=${targetDate}`
    );

    // 4. Fetch data dari Meta API (3 parallel calls)
    const metaData = await fetchMetaAdsData(brandInfo.account_id, dateRange);

    // 5. Normalize & merge data
    const rows = normalizeData(metaData, brandInfo.brand, brandInfo.brand_id, dateRange);

    const elapsed = Date.now() - startTime;
    console.log(`[API] Done. rows=${rows.length}, elapsed=${elapsed}ms`);

    // 6. Return response
    res.json({
      success: true,
      brand: brandInfo.brand,
      brand_id: brandInfo.brand_id,
      date: targetDate,
      total_ads: rows.length,
      total_with_insight: rows.filter((r) => r._status === "OK").length,
      total_no_insight: rows.filter((r) => r._status === "NO_INSIGHT").length,
      elapsed_ms: elapsed,
      data: rows,
    });
  } catch (err) {
    const error = err as Error;
    console.error(`[API] Error:`, error.message);
    res.status(500).json({
      success: false,
      error: error.message,
    });
  }
});

// ---- Start Server ----
app.listen(PORT, () => {
  console.log(`[Server] CPAS Meta Ads Backend berjalan di port ${PORT}`);
  console.log(`[Server] Endpoint: POST http://localhost:${PORT}/api/meta-ads/fetch`);
});

export default app;
