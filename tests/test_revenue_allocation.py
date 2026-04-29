"""Tests for revenue allocation logic."""
from __future__ import annotations

from phillyparking.revenue.allocation import allocate


def test_no_pbd_share_full_gf_residual_to_sdp():
    a = allocate(total_revenue_usd=50_000_000, pbd_share=0.0)
    assert a.pbd_usd == 0
    assert a.general_fund_usd == 35_000_000
    assert a.school_district_usd == 15_000_000


def test_pbd_share_30_pct_eats_sdp():
    a = allocate(total_revenue_usd=50_000_000, pbd_share=0.30)
    assert a.pbd_usd == 15_000_000
    assert a.general_fund_usd == 35_000_000
    assert a.school_district_usd == 0


def test_below_gf_minimum_sdp_zero():
    a = allocate(total_revenue_usd=30_000_000, pbd_share=0.0)
    assert a.pbd_usd == 0
    assert a.general_fund_usd == 30_000_000
    assert a.school_district_usd == 0
