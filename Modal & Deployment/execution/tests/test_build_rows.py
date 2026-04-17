"""Port dari backend/tests/normalizer.test.ts ke pytest.

Test target: `build_rows()` di modal_app.py — ad-level normalization.

Schema ground truth (production Python, dibaca oleh n8n/Supabase/Lovable):
  - status  = "OK" / "NO_INSIGHT" / "OK_NO_META"   (flag insight)
  - _status = Meta effective_status               (ACTIVE / PAUSED / dll)
  - _hierarchy_ok = bool                           (insight IDs match /ads)

Catatan: semantik `status` / `_status` di Python TERBALIK dari versi TS lama.
Downstream tergantung versi Python.
"""
from modal_app import build_rows


class TestBuildRowsSingleInsight:
    def test_normalizes_single_insight_row_correctly(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight()],
            adsets=[make_adset()],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert len(rows) == 1
        r = rows[0]
        assert r["brand"] == "ATRIA"
        assert r["brand_id"] == "brand-uuid-1"
        assert r["date_start"] == "2026-03-08"
        assert r["date_stop"] == "2026-03-08"
        assert r["campaign_id"] == "camp_1"
        assert r["ad_id"] == "ad_1"
        assert r["spend"] == 100
        assert r["reach"] == 5000
        assert r["impressions"] == 7500
        assert r["link_click"] == 200
        assert r["status"] == "OK"
        assert r["_status"] == "ACTIVE"
        assert r["_hierarchy_ok"] is True
        assert r["thumbnail_url"] == "https://thumb.jpg"
        assert r["image_url"] == "https://img.jpg"


class TestObjectiveResolution:
    def test_resolves_objective_from_promoted_object_custom_event_type_first(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight()],
            adsets=[make_adset(
                optimization_goal="OFFSITE_CONVERSIONS",
                promoted_object={"custom_event_type": "PURCHASE"},
            )],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["objective"] == "purchase"

    def test_falls_back_to_optimization_goal_when_no_custom_event_type(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        adset = make_adset(optimization_goal="LINK_CLICKS")
        adset.pop("promoted_object", None)
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight()],
            adsets=[adset],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["objective"] == "link clicks"


class TestCpasMetrics:
    def test_extracts_cpas_catalog_segment_value_and_actions(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight(
                catalog_segment_value=[
                    {"action_type": "add_to_cart", "value": "250000"},
                    {"action_type": "purchase", "value": "1500000"},
                ],
                catalog_segment_actions=[
                    {"action_type": "add_to_cart", "value": "10"},
                    {"action_type": "purchase", "value": "3"},
                ],
            )],
            adsets=[make_adset()],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["atc_value"] == 250000
        assert rows[0]["purchase_value"] == 1500000
        assert rows[0]["atc_qty"] == 10
        assert rows[0]["purchase_qty"] == 3


class TestRoasCalculation:
    def test_calculates_roas_correctly(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight(
                spend="200",
                catalog_segment_value=[{"action_type": "purchase", "value": "1000"}],
            )],
            adsets=[make_adset()],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["roas"] == 5.0  # 1000 / 200

    def test_returns_roas_zero_when_spend_is_zero(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight(
                spend="0",
                catalog_segment_value=[{"action_type": "purchase", "value": "1000"}],
            )],
            adsets=[make_adset()],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["roas"] == 0.0


class TestNoInsight:
    def test_creates_no_insight_rows_for_ads_without_insights(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight(ad_id="ad_1")],
            adsets=[make_adset()],
            ads=[
                make_ad(id="ad_1"),
                make_ad(id="ad_2", name="Ad Without Insight"),
            ],
            campaigns=[make_campaign()],
        )
        assert len(rows) == 2
        ok_row = next(r for r in rows if r["status"] == "OK")
        no_insight_row = next(r for r in rows if r["status"] == "NO_INSIGHT")
        assert ok_row["ad_id"] == "ad_1"
        assert no_insight_row["ad_id"] == "ad_2"
        assert no_insight_row["ad_name"] == "Ad Without Insight"
        assert no_insight_row["spend"] == 0.0
        assert no_insight_row["reach"] == 0.0
        assert no_insight_row["roas"] == 0.0

    def test_handles_empty_insights_all_ads_become_no_insight(
        self, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[],
            adsets=[make_adset()],
            ads=[make_ad(id="ad_1"), make_ad(id="ad_2")],
            campaigns=[make_campaign()],
        )
        assert len(rows) == 2
        assert all(r["status"] == "NO_INSIGHT" for r in rows)

    def test_handles_empty_result(self, date_range):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[], adsets=[], ads=[], campaigns=[],
        )
        assert len(rows) == 0


class TestEdgeCases:
    def test_handles_missing_invalid_numeric_values(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        insight = make_insight()
        insight["spend"] = None
        insight["reach"] = None
        insight["impressions"] = "not_a_number"
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[insight],
            adsets=[make_adset()],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["spend"] == 0.0
        assert rows[0]["reach"] == 0.0
        assert rows[0]["impressions"] == 0.0

    def test_handles_missing_creative(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        ad = make_ad()
        ad["creative"] = {}  # no thumbnail_url / image_url keys
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight()],
            adsets=[make_adset()],
            ads=[ad],
            campaigns=[make_campaign()],
        )
        assert rows[0]["thumbnail_url"] is None
        assert rows[0]["image_url"] is None


class TestHierarchyAndNames:
    def test_fills_campaign_and_adset_name_on_no_insight_via_lookup_maps(
        self, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[],
            adsets=[make_adset(id="adset_9", name="Adset Nine", campaign_id="camp_9")],
            ads=[make_ad(id="ad_9", name="Ad Nine", adset_id="adset_9", campaign_id="camp_9")],
            campaigns=[make_campaign(id="camp_9", name="Campaign Nine")],
        )
        assert len(rows) == 1
        r = rows[0]
        assert r["status"] == "NO_INSIGHT"
        assert r["campaign_name"] == "Campaign Nine"
        assert r["adset_name"] == "Adset Nine"
        assert r["ad_name"] == "Ad Nine"
        assert r["_hierarchy_ok"] is True

    def test_flags_hierarchy_not_ok_when_insight_adset_differs_from_ads(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight(adset_id="adset_old", adset_name="Adset Old")],
            adsets=[
                make_adset(id="adset_old", name="Adset Old", campaign_id="camp_1"),
                make_adset(id="adset_new", name="Adset New", campaign_id="camp_1"),
            ],
            ads=[make_ad(adset_id="adset_new")],
            campaigns=[make_campaign()],
        )
        assert len(rows) == 1
        assert rows[0]["_hierarchy_ok"] is False
        # canonical dari /ads (struktur saat ini)
        assert rows[0]["adset_id"] == "adset_new"

    def test_hierarchy_ok_true_when_insight_matches_ads(
        self, make_insight, make_adset, make_ad, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight()],
            adsets=[make_adset()],
            ads=[make_ad()],
            campaigns=[make_campaign()],
        )
        assert rows[0]["_hierarchy_ok"] is True

    def test_marks_status_ok_no_meta_when_insight_orphan(
        self, make_insight, make_adset, make_campaign, date_range
    ):
        rows = build_rows(
            "ATRIA", "brand-uuid-1", date_range["since"],
            insights=[make_insight(ad_id="ad_orphan")],
            adsets=[make_adset()],
            ads=[],  # ad sudah dihapus/archived
            campaigns=[make_campaign()],
        )
        assert rows[0]["status"] == "OK_NO_META"
        assert rows[0]["_status"] == "UNKNOWN"
