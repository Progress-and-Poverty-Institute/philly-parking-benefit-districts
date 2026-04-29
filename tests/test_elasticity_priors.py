"""Tests for elasticity priors."""
from __future__ import annotations

import numpy as np
import pytest

from phillyparking.elasticity.priors import (
    ElasticityPrior,
    central_prior,
    cross_priors,
    named_scenario,
)


def test_cbd_central_mean():
    p = central_prior("cbd")
    assert p.mean == pytest.approx(-0.40)
    assert p.sd == pytest.approx(0.15)


def test_context_shifts_apply():
    assert central_prior("mixed_use").mean == pytest.approx(-0.45)
    assert central_prior("residential").mean == pytest.approx(-0.50)
    assert central_prior("long_run").mean == pytest.approx(-0.70)


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
    assert named_scenario("pessimistic") == pytest.approx(-0.70)
    assert named_scenario("central") == pytest.approx(-0.40)
    assert named_scenario("optimistic") == pytest.approx(-0.20)


def test_cross_priors_keys():
    cp = cross_priors()
    assert set(cp) == {"curb_to_garage", "curb_to_transit", "curb_to_rideshare", "curb_to_forgo"}
    assert cp["curb_to_garage"].mean == pytest.approx(0.30)
