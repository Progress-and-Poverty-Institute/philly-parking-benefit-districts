"""Tests for elasticity priors."""
from __future__ import annotations

import numpy as np
import pytest

from phillyparking._config import load_config
from phillyparking.elasticity.priors import (
    ElasticityPrior,
    central_prior,
    cross_priors,
    named_scenario,
)


def test_cbd_central_mean():
    cfg = load_config("elasticity_priors")["central"]
    p = central_prior("cbd")
    assert p.mean == pytest.approx(float(cfg["mean"]))
    assert p.sd == pytest.approx(float(cfg["sd"]))


def test_central_prior_is_the_central_scenario():
    # The prior's mean and the named central scenario are one number (an occupancy elasticity).
    assert central_prior("cbd").mean == pytest.approx(named_scenario("central"))


def test_context_shifts_apply():
    cfg = load_config("elasticity_priors")
    for ctx, shift in cfg["context_shifts"].items():
        assert central_prior(ctx).mean == pytest.approx(float(cfg["central"]["mean"]) + float(shift))


def test_unknown_context_raises():
    with pytest.raises(KeyError):
        central_prior("mars")


def test_sample_shape_and_logpdf_sign():
    p = ElasticityPrior(mean=-0.4, sd=0.15)
    rng = np.random.default_rng(0)
    s = p.sample(500, rng)
    assert s.shape == (500,)
    assert abs(s.mean() - (-0.4)) < 0.05
    lp = p.logpdf(np.array([-0.4]))
    assert lp[0] > 0  # peak of normal density with sd=0.15 has logpdf > 0


def test_named_scenarios():
    cfg = load_config("elasticity_priors")["scenarios"]
    for name, value in cfg.items():
        assert named_scenario(name) == pytest.approx(float(value))
    # ordered by size of response, and the central prior's plus/minus 2 sd is about the bracket's width
    assert named_scenario("pessimistic") < named_scenario("central") < named_scenario("optimistic") < 0
    sd = float(load_config("elasticity_priors")["central"]["sd"])
    width = named_scenario("optimistic") - named_scenario("pessimistic")
    assert 4 * sd == pytest.approx(width, abs=0.25 * width)


def test_dwell_time_is_not_read_by_the_pipeline():
    # EPD is carried in the config for reference only (EPO = EPD + EPV): nothing under src/ reads it.
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "src"
    assert not [f for f in src.rglob("*.py") if "dwell_time" in f.read_text(encoding="utf-8")]


def test_cross_priors_keys():
    cp = cross_priors()
    assert set(cp) == {"curb_to_garage", "curb_to_transit", "curb_to_rideshare", "curb_to_forgo"}
    assert cp["curb_to_garage"].mean == pytest.approx(0.30)
