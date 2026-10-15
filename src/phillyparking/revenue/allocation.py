"""Allocation of on-street revenue under the statutory waterfall (research doc §4.2).

Order, from 75 Pa.C.S. § 6109(g)(2)-(3) (Act 84 of 2012; citation and retrieval in
`config/allocation.yaml`):

1. The City's General Fund is paid first, up to the statutory minimum ($35M before the
   escalator). Nothing in the statute reduces it, not even operating expenses.
2. A Parking Benefit District's share is paid from what is left after (1).
3. The School District gets whatever remains.

Why the PBD sits after the General Fund minimum. The statute defines two payees only: the
City up to its amount, then the School District for all of the excess. A PBD return of meter
revenue is not in it. If PPA treated the return as an operating cost of the system it would
reduce the "net revenue" the excess is computed from, and because the City's amount stays
fixed when expenses rise (Auditor General, 2017, Finding 1) the whole reduction falls on the
School District. If it were a transfer out of the excess it would fall there too. Either way
a PBD can be paid only from what lies above the City's amount unless § 6109(g) is amended,
so the PBD's payment is capped at that residual. The part of its share the cap leaves
unpaid is reported as `pbd_unfunded_usd` rather than dropped; it is what a PBD would need
the legislature (or a different funding source) for.

Assumptions: `total_revenue_usd` is the model's gross meter revenue, whereas the statute
applies to the whole citywide system's revenue net of operating and administrative expenses
(fines, permits, and so on), and escalates the City's amount with gross revenue. At the
scale of a fixture or a handful of zones the revenue is far below the $35M minimum, so the
General Fund takes all of it and a PBD is paid nothing; read the allocation as the order of
payment, not as a forecast of the dollars, until revenue is at citywide scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from phillyparking._config import load_config


def statutory_general_fund_minimum_usd() -> float:
    return float(load_config("allocation")["general_fund_minimum_usd"])


@dataclass(frozen=True)
class RevenueAllocation:
    total_revenue_usd: float
    general_fund_minimum_usd: float = field(default_factory=statutory_general_fund_minimum_usd)
    pbd_share: float = 0.0

    @property
    def general_fund_usd(self) -> float:
        return min(self.total_revenue_usd, self.general_fund_minimum_usd)

    @property
    def pbd_claim_usd(self) -> float:
        """The PBD's share of total revenue, before the statutory cap."""
        return self.total_revenue_usd * self.pbd_share

    @property
    def pbd_usd(self) -> float:
        residual = self.total_revenue_usd - self.general_fund_usd
        return max(0.0, min(self.pbd_claim_usd, residual))

    @property
    def pbd_unfunded_usd(self) -> float:
        return self.pbd_claim_usd - self.pbd_usd

    @property
    def school_district_usd(self) -> float:
        return max(0.0, self.total_revenue_usd - self.general_fund_usd - self.pbd_usd)

    def to_dict(self) -> dict:
        return {
            "total_revenue_usd": self.total_revenue_usd,
            "pbd_usd": self.pbd_usd,
            "pbd_claim_usd": self.pbd_claim_usd,
            "pbd_unfunded_usd": self.pbd_unfunded_usd,
            "general_fund_usd": self.general_fund_usd,
            "school_district_usd": self.school_district_usd,
            "pbd_share": self.pbd_share,
            "general_fund_minimum_usd": self.general_fund_minimum_usd,
        }


def allocate(total_revenue_usd: float, pbd_share: float = 0.0) -> RevenueAllocation:
    return RevenueAllocation(total_revenue_usd=total_revenue_usd, pbd_share=pbd_share)
