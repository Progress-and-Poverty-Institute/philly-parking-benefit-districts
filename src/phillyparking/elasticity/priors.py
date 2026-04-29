"""Lehner-Peer 2019 elasticity priors.

Encodes the central RP-only meta-analytic prior, the context shifts (CBD,
mixed-use, residential, long-run), the cross-elasticity priors, and the three
named scenarios used by revenue/welfare forecasts.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phillyparking._config import load_config


@dataclass(frozen=True)
class ElasticityPrior:
    mean: float
    sd: float
    distribution: str = "normal"

    def sample(self, size: int, rng: np.random.Generator) -> np.ndarray:
        if self.distribution == "normal":
            return rng.normal(self.mean, self.sd, size=size)
        raise ValueError(f"Unsupported distribution: {self.distribution}")

    def logpdf(self, x: np.ndarray) -> np.ndarray:
        if self.distribution == "normal":
            x = np.asarray(x, dtype=float)
            return -0.5 * np.log(2 * np.pi * self.sd ** 2) - 0.5 * ((x - self.mean) / self.sd) ** 2
        raise ValueError(f"Unsupported distribution: {self.distribution}")


def central_prior(context: str = "cbd") -> ElasticityPrior:
    """Central prior with the appropriate context shift applied."""
    cfg = load_config("elasticity_priors")
    base = cfg["central"]
    shifts = cfg["context_shifts"]
    if context not in shifts:
        raise KeyError(f"Unknown context '{context}'. Known: {list(shifts)}")
    return ElasticityPrior(
        mean=float(base["mean"]) + float(shifts[context]),
        sd=float(base["sd"]),
        distribution=base.get("distribution", "normal"),
    )


def cross_priors() -> dict[str, ElasticityPrior]:
    cfg = load_config("elasticity_priors")["cross"]
    return {
        k: ElasticityPrior(mean=float(v["mean"]), sd=float(v["sd"]))
        for k, v in cfg.items()
    }


def named_scenario(name: str) -> float:
    cfg = load_config("elasticity_priors")["scenarios"]
    if name not in cfg:
        raise KeyError(f"Unknown scenario '{name}'. Known: {list(cfg)}")
    return float(cfg[name])
