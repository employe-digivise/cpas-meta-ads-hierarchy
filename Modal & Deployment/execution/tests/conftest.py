"""Shared pytest fixtures + stubs.

modal_app.py mengimport `modal` dan `fastapi` di module level untuk mendefinisikan
App + decorator endpoint. Di environment CI/lokal tanpa Modal SDK terinstall,
kita stub keduanya dengan MagicMock agar test bisa mengimport modul tanpa
menjalankan Modal. Stub dipasang SEBELUM import modal_app di file test.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Pastikan folder execution/ ada di sys.path sehingga `import modal_app` bekerja
EXECUTION_DIR = Path(__file__).resolve().parent.parent
if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))

# Stub modal + fastapi sebelum test manapun mengimport modal_app
sys.modules.setdefault("modal", MagicMock(name="modal"))
_fastapi_stub = MagicMock(name="fastapi")
sys.modules.setdefault("fastapi", _fastapi_stub)


# ── Fixtures builder (mirror dari backend/tests/normalizer.test.ts) ────────

@pytest.fixture
def date_range():
    return {"since": "2026-03-08", "until": "2026-03-08"}


@pytest.fixture
def make_insight():
    def _make(**overrides):
        base = {
            "campaign_id": "camp_1",
            "campaign_name": "Campaign 1",
            "adset_id": "adset_1",
            "adset_name": "Adset 1",
            "ad_id": "ad_1",
            "ad_name": "Ad 1",
            "spend": "100",
            "reach": "5000",
            "frequency": "1.5",
            "impressions": "7500",
            "inline_link_clicks": "200",
            "cpm": "13.33",
            "inline_link_click_ctr": "2.67",
            "cost_per_inline_link_click": "0.50",
        }
        base.update(overrides)
        return base
    return _make


@pytest.fixture
def make_adset():
    def _make(**overrides):
        base = {
            "id": "adset_1",
            "name": "Adset 1",
            "campaign_id": "camp_1",
            "optimization_goal": "PURCHASE",
        }
        base.update(overrides)
        return base
    return _make


@pytest.fixture
def make_ad():
    def _make(**overrides):
        base = {
            "id": "ad_1",
            "name": "Ad 1",
            "adset_id": "adset_1",
            "campaign_id": "camp_1",
            "effective_status": "ACTIVE",
            "creative": {"thumbnail_url": "https://thumb.jpg", "image_url": "https://img.jpg"},
        }
        base.update(overrides)
        return base
    return _make


@pytest.fixture
def make_campaign():
    def _make(**overrides):
        base = {"id": "camp_1", "name": "Campaign 1"}
        base.update(overrides)
        return base
    return _make
