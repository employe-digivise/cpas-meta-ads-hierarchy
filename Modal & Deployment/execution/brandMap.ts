// ============================================================
// Brand Map
// Mapping brand name → Meta Ads account_id dan brand_id
// Diambil dari node "Set Account ID & Time Range" di n8n
// ============================================================

export interface BrandInfo {
  account_id: string;
  brand_id: string;
  sheet_id: string;
}

export const brandMap: Record<string, BrandInfo> = {
  AMK: {
    account_id: "act_2254667594733384",
    sheet_id: "1OZIK3U_GN4EnMhSo6l-zUp03EMwdqi3frGud18tpzQ4",
    brand_id: "72e713fd-5979-4b92-b3d7-701b934cfe63",
  },
  ARSY: {
    account_id: "act_1140721503928141",
    sheet_id: "11W6rkJRjQpgYDmvF1lFNG-Qbr7nnvNJoglP5wkrG3e8",
    brand_id: "f8de8004-5472-4682-a8df-64fbfc7b641d",
  },
  ATRIA: {
    account_id: "act_1592215248050848",
    sheet_id: "1iuR6AbIvEF8sNKk6ZdcZndl3f8ssJCwK97Xbp1NQ0r4",
    brand_id: "c311087d-34de-4e34-bee7-42da8fa89c36",
  },
  BALLOONABLE: {
    account_id: "act_993783415450547",
    sheet_id: "15ypPmmJ6Bp3_vXN7h8h3CwkDkcMpBXfZXXqhvr-zLWU",
    brand_id: "49ef95dd-757a-4f54-8c14-512516ce5bd3",
  },
  CHANIRA: {
    account_id: "act_781609353137420",
    sheet_id: "1um6XcEClVPb8pU_7zpHIJ6nqvyIhnBfim9rH5Jy0MNA",
    brand_id: "852ddd26-cdf2-4753-9d56-9414d2e1207a",
  },
  "GOODS A FOOTWEAR": {
    account_id: "act_1358465195212355",
    sheet_id: "1q91FVnb1hEg8k29jUsPWxF1QjQ--mpsHERHqWmsm-WI",
    brand_id: "c393db9c-ac48-426d-905e-a02498f8ad2f",
  },
  HLS: {
    account_id: "act_292145753233324",
    sheet_id: "1FufpOeI3riPB4-h1JEVfi1dTPu935HxQFwfMCM6AMns",
    brand_id: "48fe8387-a987-436c-b8ef-06c238f2be08",
  },
  KAUFAZ: {
    account_id: "act_1263527284960054",
    sheet_id: "1O6tnEVc_MJT4ZbpepqNwJmQzb9mLrzbjvnLx7uGm48Y",
    brand_id: "9f4980bf-d2f0-4d53-a5d1-090de718a5bc",
  },
  LILIS: {
    account_id: "act_1192337178724256",
    sheet_id: "1kzHs6ce4DyXnCxOWEAwLKqTn7TY6Srdi7Aja9kp2Ths",
    brand_id: "8c268c08-0cfb-4ee9-8de2-1871470441e8",
  },
  MENLIVING: {
    account_id: "act_245299254049235",
    sheet_id: "1ZHUM3L1MYsUcDYuhIYmPl3l8iVeCzhlYYNQxiGCShOw",
    brand_id: "6311d20e-55f8-47af-9376-e07d71781294",
  },
  "PORTS JOURNAL": {
    account_id: "act_2757030064615005",
    sheet_id: "1W6yjCL9YVNhd7WrPbxyW_70KgHJ5yaNvbY9qJfNd_Fk",
    brand_id: "4eead26d-466c-43e5-ae19-04d3a90b1f0e",
  },
  RTSR: {
    account_id: "act_952026815689114",
    sheet_id: "1vZ153QWQVdWfGpDBfBi6gqehTAnxZUTU7bSsgVRgTvs",
    brand_id: "6589b89f-63e5-47b3-ba0b-c876beb83db9",
  },
  "URBAN EXCHANGE": {
    account_id: "act_2129466137258989",
    sheet_id: "1A4XFigA1tEZy2R4UNsJdDO_IS9SQVv9VAwzeehT1sp8",
    brand_id: "84b85184-29ab-4eef-b8ac-aeb1d7d5632c",
  },
  FRSCARVES: {
    account_id: "act_408177362250144",
    sheet_id: "1e962sShC87oQFO85VErThL7O5CinjKSj5q9Mq6lw1GQ",
    brand_id: "0df14aed-cd65-4927-81bd-124ec21d435a",
  },
  WELLBORN: {
    account_id: "act_3390310847721143",
    sheet_id: "1DgmZWO5bmye3Er2QEwi6pNmnuqlLpQQr1QHaiM3pcoo",
    brand_id: "3d4eda32-700f-4ea3-a900-0ba2da6afde2",
  },
};

export function resolveBrand(brandName: string): BrandInfo & { brand: string } {
  const key = brandName.trim().toUpperCase();
  const info = brandMap[key];

  if (!info) {
    throw new Error(
      `Brand "${brandName}" tidak ditemukan. Brand yang tersedia: ${Object.keys(brandMap).join(", ")}`
    );
  }

  return { brand: brandName.trim(), ...info };
}

// Hitung tanggal kemarin dalam format YYYY-MM-DD (timezone Asia/Jakarta)
export function getYesterdayJakarta(): string {
  const now = new Date();
  // UTC+7
  const jakartaOffset = 7 * 60 * 60 * 1000;
  const jakartaNow = new Date(now.getTime() + jakartaOffset);
  jakartaNow.setUTCDate(jakartaNow.getUTCDate() - 1);
  return jakartaNow.toISOString().slice(0, 10);
}
