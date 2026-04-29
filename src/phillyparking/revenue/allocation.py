"""Post-revenue political allocation (research doc §4.2)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RevenueAllocation:
    total_revenue_usd: float
    general_fund_minimum_usd: float = 35_000_000
    pbd_share: float = 0.0

    @property
    def pbd_usd(self) -> float:
        return self.total_revenue_usd * self.pbd_share

    @property
    def general_fund_usd(self) -> float:
        residual = self.total_revenue_usd - self.pbd_usd
        return min(residual, self.general_fund_minimum_usd)

    @property
    def school_district_usd(self) -> float:
        residual = self.total_revenue_usd - self.pbd_usd - self.general_fund_usd
        return max(0.0, residual)

    def to_dict(self) -> dict:
        return {
            "total_revenue_usd": self.total_revenue_usd,
            "pbd_usd": self.pbd_usd,
            "general_fund_usd": self.general_fund_usd,
            "school_district_usd": self.school_district_usd,
            "pbd_share": self.pbd_share,
            "general_fund_minimum_usd": self.general_fund_minimum_usd,
        }


def allocate(total_revenue_usd: float, pbd_share: float = 0.0) -> RevenueAllocation:
    return RevenueAllocation(total_revenue_usd=total_revenue_usd, pbd_share=pbd_share)
