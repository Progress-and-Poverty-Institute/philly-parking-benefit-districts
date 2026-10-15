"""Tests for revenue allocation logic (statutory order: see revenue/allocation.py)."""
from __future__ import annotations

from phillyparking.revenue.allocation import allocate


def test_no_pbd_share_full_gf_residual_to_sdp():
    a = allocate(total_revenue_usd=50_000_000, pbd_share=0.0)
    assert a.pbd_usd == 0
    assert a.general_fund_usd == 35_000_000
    assert a.school_district_usd == 15_000_000


def test_pbd_share_30_pct_comes_out_of_the_sdp_residual():
    a = allocate(total_revenue_usd=50_000_000, pbd_share=0.30)
    assert a.general_fund_usd == 35_000_000
    assert a.pbd_usd == 15_000_000          # the whole 30% claim fits in the $15M residual
    assert a.school_district_usd == 0
    assert a.pbd_unfunded_usd == 0


def test_pbd_share_larger_than_the_residual_is_capped_and_the_rest_reported():
    a = allocate(total_revenue_usd=40_000_000, pbd_share=0.30)
    assert a.general_fund_usd == 35_000_000
    assert a.pbd_usd == 5_000_000
    assert a.pbd_unfunded_usd == 7_000_000   # 12M claim, 5M above the General Fund minimum
    assert a.school_district_usd == 0


def test_below_gf_minimum_sdp_and_pbd_zero():
    a = allocate(total_revenue_usd=30_000_000, pbd_share=0.30)
    assert a.pbd_usd == 0
    assert a.general_fund_usd == 30_000_000
    assert a.school_district_usd == 0
    assert a.pbd_unfunded_usd == 9_000_000
