"""PPA transactions / RPP issuances — synthetic generator with schema-faithful columns.

The real export's format is unknown. `phillyparking.ingest.ppa` reads it through a column
mapping (`config/ppa_ingest.yaml`); `make_known_answer_export` here writes a stub export in a
deliberately different schema, with a known occupancy, to test that stage.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from phillyparking._config import data_dir

load_dotenv()
log = logging.getLogger(__name__)

TX_SCHEMA = {
    "transaction_id": "int64",
    "segment_id": "string",
    "meter_id": "string",
    "start_time": "datetime64[ns]",
    "end_time": "datetime64[ns]",
    "paid_minutes": "int32",
    "paid_amount_usd": "float64",
    "payment_method": "string",
    "rate_usd_per_hr": "float64",
}

RPP_SCHEMA = {
    "permit_id": "string",
    "rpp_zone": "string",
    "issued_date": "datetime64[ns]",
    "expires_date": "datetime64[ns]",
    "vehicle_type": "string",
    "low_income_waiver": "bool",
    "annual_fee_usd": "float64",
}


def _hour_of_week_multiplier(hour_of_week: np.ndarray) -> np.ndarray:
    """Return per-hour Poisson rate multiplier; weekday lunch peak ~3x off-peak."""
    dow = (hour_of_week // 24).astype(int)
    hod = (hour_of_week % 24).astype(int)
    mult = np.full_like(hod, 0.3, dtype=float)
    weekday = dow < 5
    saturday = dow == 5
    sunday = dow == 6
    mult = np.where(weekday & (hod >= 8) & (hod < 12), 1.5, mult)
    mult = np.where(weekday & (hod >= 12) & (hod < 14), 3.0, mult)
    mult = np.where(weekday & (hod >= 14) & (hod < 18), 1.8, mult)
    mult = np.where(weekday & (hod >= 18) & (hod < 20), 1.2, mult)
    mult = np.where(saturday & (hod >= 10) & (hod < 20), 2.0, mult)
    mult = np.where(sunday & (hod >= 11) & (hod < 18), 0.8, mult)
    mult = np.where((hod >= 22) | (hod < 6), 0.1, mult)
    return mult


def generate_transactions(
    segments: gpd.GeoDataFrame,
    n_days: int = 7,
    seed: int = 42,
    base_arrival_per_segment_hour: float = 1.5,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_hours = n_days * 24
    hours = np.arange(n_hours)
    mult = _hour_of_week_multiplier(hours)

    capacity = (
        segments["capacity"].to_numpy()
        if "capacity" in segments.columns
        else np.full(len(segments), 6)
    )
    seg_ids = segments["segment_id"].to_numpy()
    rates = (
        segments["current_rate"].to_numpy()
        if "current_rate" in segments.columns
        else np.full(len(segments), 2.5)
    )
    capacity_factor = np.clip(capacity / 6.0, 0.3, 3.0)

    rows = []
    tid = 0
    start_dt = pd.Timestamp("2024-06-03")  # Monday
    for i, seg_id in enumerate(seg_ids):
        lam = base_arrival_per_segment_hour * mult * capacity_factor[i]
        arrivals = rng.poisson(lam)
        rate_hr = float(rates[i])
        for h, n_arr in enumerate(arrivals):
            if n_arr == 0:
                continue
            offsets = rng.uniform(0, 60, n_arr)
            dwells = np.exp(rng.normal(np.log(45.0), 0.5, n_arr)).clip(5, 480)
            for off, dwell in zip(offsets, dwells):
                start = start_dt + pd.Timedelta(hours=int(h)) + pd.Timedelta(minutes=float(off))
                end = start + pd.Timedelta(minutes=float(dwell))
                paid_min = int(round(dwell))
                rows.append(
                    (
                        tid,
                        str(seg_id),
                        f"M{i:05d}",
                        start,
                        end,
                        paid_min,
                        round(paid_min / 60.0 * rate_hr, 2),
                        "meterup" if rng.random() < 0.5 else "meter",
                        rate_hr,
                    )
                )
                tid += 1

    df = pd.DataFrame(
        rows,
        columns=list(TX_SCHEMA.keys()),
    )
    if len(df):
        df["paid_minutes"] = df["paid_minutes"].astype("int32")
        df["transaction_id"] = df["transaction_id"].astype("int64")
        df["segment_id"] = df["segment_id"].astype("string")
        df["meter_id"] = df["meter_id"].astype("string")
        df["payment_method"] = df["payment_method"].astype("string")
    return df


def generate_rpp_issuances(
    rpp_zones: gpd.GeoDataFrame,
    permits_per_zone: int = 200,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    zone_col = "rpp_zone" if "rpp_zone" in rpp_zones.columns else rpp_zones.columns[0]
    rows = []
    pid = 0
    base_date = pd.Timestamp("2024-01-01")
    for z in rpp_zones[zone_col].astype(str).unique():
        for _ in range(permits_per_zone):
            issued = base_date + pd.Timedelta(days=int(rng.integers(0, 365)))
            expires = issued + pd.Timedelta(days=365)
            vtype = "motorcycle" if rng.random() < 0.05 else "car"
            waiver = bool(rng.random() < 0.1)
            fee = 0.0 if waiver else (50.0 if vtype == "motorcycle" else 75.0)
            rows.append((f"RPP{pid:07d}", str(z), issued, expires, vtype, waiver, fee))
            pid += 1
    return pd.DataFrame(rows, columns=list(RPP_SCHEMA.keys()))


def load_transactions(
    segments: gpd.GeoDataFrame | None = None, refresh: bool = False
) -> pd.DataFrame:
    """Stub transactions, or the real file when `PPA_DATA_SOURCE=real`.

    With `PPA_DATA_SOURCE=real` a missing file raises; it never falls back to the stub. Real
    exports go through `phillyparking.ingest.ppa`, which maps their columns and builds the
    occupancy panel; this function only serves the notebook's display of the stub.
    """
    src = os.environ.get("PPA_DATA_SOURCE", "stub").lower()
    if src == "real":
        path = (
            Path(os.environ.get("PPA_DATA_PATH", str(data_dir() / "raw" / "ppa")))
            / "transactions.parquet"
        )
        if not path.exists():
            raise FileNotFoundError(f"PPA_DATA_SOURCE=real but {path} does not exist")
        return pd.read_parquet(path)
    if src != "stub":
        raise ValueError(f"PPA_DATA_SOURCE must be 'stub' or 'real', not {src!r}")
    if segments is None:
        from phillyparking.spatial.segments import load_segments

        segments = load_segments()
    return generate_transactions(segments)


# --- Known-answer stub export for the ingestion stage (phillyparking.ingest.ppa) -------------

KNOWN_ANSWER_WINDOW = ("2025-06-02", "2025-07-13")  # Monday to Sunday, straddles 1 July 2025
KNOWN_ANSWER_PERIODS = ("2025-06-02", "2025-07-01")
_FMT = "%m/%d/%Y %H:%M"


def make_known_answer_export() -> dict[str, pd.DataFrame]:
    """A small export in an export-like schema whose occupancy is known exactly.

    Four block faces (column names as in `config/ppa_ingest.yaml`): `BF-CCC-1` (Center City
    Core, meters M001 with 4 spaces and M002 with 2), `BF-UC-1` (University City, M003, 5
    spaces), `BF-CCA-1` (Center City Area, M004, 3 spaces, no sessions at all) and `BF-CCA-2`
    (Center City Area, M005, 4 spaces). Rates:
    Core $3.00 -> $4.00 and Area $2.50 -> $3.50 on 1 July 2025, University City $2.00
    throughout. Sessions, on every date of the window:

    - BF-CCC-1, weekdays: 3 cars 12:00-14:00 before 1 July, 2 after (alternating meters), so
      paid occupancy 3/6 then 2/6 at hours 12 and 13; and 1 car 09:30-10:15, so 30/360 at
      hour 9 and 15/360 at hour 10, in both periods.
    - BF-UC-1, Saturdays: 5 cars 10:00-12:00 (occupancy 1.0 at hours 10 and 11); Fridays:
      1 car 23:30 to Saturday 00:30 (30/300 in Friday hour 23 and Saturday hour 0).
    - BF-CCA-2, weekdays: 1 car 08:00-11:00 (occupancy 1/4 at hours 8, 9, 10).

    Returns {"sessions", "inventory", "rates", "expected"}; `expected` lists every nonzero
    cell as (segment_id, period, hour_of_week, paid_occupancy). Every other cell is 0.
    """
    inventory = pd.DataFrame({
        "MeterNumber": ["M001", "M002", "M003", "M004", "M005"],
        "BlockFace": ["BF-CCC-1", "BF-CCC-1", "BF-UC-1", "BF-CCA-1", "BF-CCA-2"],
        "Spaces": ["4", "2", "5", "3", "4"],
        "RateArea": ["Center City Core", "Center City Core", "University City",
                     "Center City Area", "Center City Area"],
        "Longitude": ["-75.1600", "-75.1601", "-75.1950", "-75.1700", "-75.1720"],
        "Latitude": ["39.9520", "39.9521", "39.9530", "39.9400", "39.9405"],
    })
    rates = pd.DataFrame({
        "RateArea": ["Center City Core", "Center City Core", "Center City Area",
                     "Center City Area", "University City"],
        "EffectiveDate": ["2025-01-01", "2025-07-01", "2025-01-01", "2025-07-01", "2025-01-01"],
        "HourlyRate": ["3.00", "4.00", "2.50", "3.50", "2.00"],
    })
    rate = {("M001", 0): 3.0, ("M001", 1): 4.0, ("M002", 0): 3.0, ("M002", 1): 4.0,
            ("M003", 0): 2.0, ("M003", 1): 2.0, ("M005", 0): 2.5, ("M005", 1): 3.5}
    cut = pd.Timestamp("2025-07-01")
    rows = []

    def add(meter: str, start: pd.Timestamp, minutes: int) -> None:
        r = rate[(meter, int(start >= cut))]
        end = start + pd.Timedelta(minutes=minutes)
        rows.append({"MeterNumber": meter, "SessionStart": start.strftime(_FMT),
                     "SessionEnd": end.strftime(_FMT),
                     "AmountPaid": f"{r * minutes / 60:.2f}", "RateApplied": f"{r:.2f}",
                     "PaymentChannel": "meterUP" if len(rows) % 2 else "kiosk"})

    for day in pd.date_range(*KNOWN_ANSWER_WINDOW, freq="D"):
        dow = day.dayofweek
        if dow < 5:
            for k in range(3 if day < cut else 2):
                add("M001" if k % 2 == 0 else "M002", day + pd.Timedelta(hours=12), 120)
            add("M001", day + pd.Timedelta(hours=9, minutes=30), 45)
            add("M005", day + pd.Timedelta(hours=8), 180)
        if dow == 5:
            for _ in range(5):
                add("M003", day + pd.Timedelta(hours=10), 120)
        if dow == 4 and day < pd.Timestamp(KNOWN_ANSWER_WINDOW[1]):
            add("M003", day + pd.Timedelta(hours=23, minutes=30), 60)
    sessions = pd.DataFrame(rows)

    exp = []
    for period, cars in zip(KNOWN_ANSWER_PERIODS, (3, 2)):
        for d in range(5):
            exp += [("BF-CCC-1", period, d * 24 + 12, cars / 6),
                    ("BF-CCC-1", period, d * 24 + 13, cars / 6),
                    ("BF-CCC-1", period, d * 24 + 9, 30 / 360),
                    ("BF-CCC-1", period, d * 24 + 10, 15 / 360),
                    ("BF-CCA-2", period, d * 24 + 8, 0.25),
                    ("BF-CCA-2", period, d * 24 + 9, 0.25),
                    ("BF-CCA-2", period, d * 24 + 10, 0.25)]
        exp += [("BF-UC-1", period, 5 * 24 + 10, 1.0), ("BF-UC-1", period, 5 * 24 + 11, 1.0),
                ("BF-UC-1", period, 4 * 24 + 23, 0.1), ("BF-UC-1", period, 5 * 24 + 0, 0.1)]
    expected = pd.DataFrame(exp, columns=["segment_id", "period", "hour_of_week",
                                          "paid_occupancy"])
    return {"sessions": sessions, "inventory": inventory, "rates": rates, "expected": expected}


def write_known_answer_export(out_dir: Path) -> dict[str, Path]:
    """Write the known-answer export as CSVs (sessions, inventory, rates) under `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = make_known_answer_export()
    paths = {}
    for name in ("sessions", "inventory", "rates"):
        paths[name] = out_dir / f"{name}.csv"
        tables[name].to_csv(paths[name], index=False)
    return paths
