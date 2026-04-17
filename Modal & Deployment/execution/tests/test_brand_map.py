"""Port dari backend/tests/brandMap.test.ts ke pytest.

Catatan perbedaan dengan versi TS:
  - BRAND_MAP di Python hanya punya account_id + brand_id (tidak ada sheet_id
    yang di TS brandMap.ts). sheet_id adalah artifact legacy dari n8n flow lama
    yang sudah tidak dipakai di Modal pipeline. Assertion sheet_id dihilangkan.
  - resolve logic Python inlined di fetch_meta_ads endpoint
    (modal_app.py:369-378). Test memvalidasi dict BRAND_MAP langsung.
"""
import re
from datetime import datetime, timezone, timedelta

import pytest

from modal_app import BRAND_MAP


def _resolve_brand(brand_name: str) -> dict:
    """Mirror dari logic di fetch_meta_ads endpoint:
    modal_app.py:369-378 — strip + upper + lookup. Raise KeyError kalau tidak
    ketemu (endpoint production convert jadi HTTPException 400)."""
    key = brand_name.strip().upper()
    if key not in BRAND_MAP:
        raise KeyError(f"Brand '{brand_name}' tidak ditemukan")
    return BRAND_MAP[key]


def _yesterday_jakarta() -> str:
    """Mirror dari daily_fetch_all_brands (modal_app.py) dan test_endpoint.py."""
    jakarta = timezone(timedelta(hours=7))
    return (datetime.now(jakarta) - timedelta(days=1)).strftime("%Y-%m-%d")


class TestResolveBrand:
    def test_resolves_valid_brand_exact_uppercase(self):
        info = _resolve_brand("ATRIA")
        assert info["account_id"] == "act_1592215248050848"
        assert info["brand_id"] == "c311087d-34de-4e34-bee7-42da8fa89c36"

    def test_resolves_brand_case_insensitively(self):
        info = _resolve_brand("atria")
        assert info["account_id"] == "act_1592215248050848"

    def test_trims_whitespace_from_brand_name(self):
        info = _resolve_brand("  ATRIA  ")
        assert info["account_id"] == "act_1592215248050848"

    def test_resolves_brand_with_spaces(self):
        info = _resolve_brand("GOODS A FOOTWEAR")
        assert info["account_id"] == "act_1358465195212355"

    def test_raises_for_unknown_brand(self):
        with pytest.raises(KeyError, match="tidak ditemukan"):
            _resolve_brand("UNKNOWN_BRAND")

    def test_raises_for_empty_brand_name(self):
        with pytest.raises(KeyError, match="tidak ditemukan"):
            _resolve_brand("")

    def test_brand_map_has_15_brands(self):
        assert len(BRAND_MAP) == 15

    def test_every_brand_has_account_id_and_brand_id(self):
        for name, info in BRAND_MAP.items():
            assert info.get("account_id"), f"{name} missing account_id"
            assert info.get("brand_id"), f"{name} missing brand_id"
            assert info["account_id"].startswith("act_"), f"{name} account_id format invalid"


class TestYesterdayJakarta:
    def test_returns_valid_yyyy_mm_dd_string(self):
        result = _yesterday_jakarta()
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result)

    def test_returns_date_in_the_past(self):
        result = _yesterday_jakarta()
        parsed = datetime.strptime(result, "%Y-%m-%d")
        # Yesterday di Jakarta harus <= today (UTC+7 boundary)
        today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        assert parsed <= today_utc + timedelta(days=1)
