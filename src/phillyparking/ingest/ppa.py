"""Parking Authority export -> occupancy panel by segment, calendar period and hour of week.

Three tables come in, each read through the column mapping in `config/ppa_ingest.yaml`:
paid sessions, the meter inventory (spaces served, rate area, optional block face), and the
rate schedule with effective dates. Out comes a panel the scenario runner and the elasticity
model consume:

    segment_id, zone_id, period, hour_of_week, occupancy, paid_occupancy,
    price_usd_per_hr, paid_minutes, n_sessions, n_days

**Calendar periods.** The schedule's effective dates cut the observation window into
periods; within one period every zone has one posted rate. `price_usd_per_hr` is that rate,
so a zone observed across a rate change (1 July 2025) carries two prices, which is what the
elasticity model needs to identify a price response (audit finding 5).

**Occupancy.** For each segment, period and hour of week:

    paid_occupancy = paid minutes in that clock hour, summed over the period's days
                     / (spaces x 60 x number of that weekday's dates in the period)
    occupancy      = paid_occupancy / (1 - unpaid_share[zone])

A session is split across the clock hours it spans. The denominator counts calendar dates,
so a weekday with no sessions still counts as observed (zero). `unpaid_share` is an explicit,
documented parameter (`unpaid_use` in the config), never a default in code.

**Failing loudly.** A missing mapped column, an unmapped rate-area label, a location with no
spaces, a session with no end or a negative or over-long duration, more than the allowed share
of sessions with no inventory match or with a posted rate the schedule contradicts, a period
in which a zone has no scheduled rate or no paid session at all (a gap in the export, not zero
demand), and occupancy over capacity all raise `PPAIngestError`. Counts of everything dropped are in the returned report.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from phillyparking._config import load_config, project_root

log = logging.getLogger(__name__)

HOURS_OF_WEEK = 168
REQUIRED = {
    "sessions": ("start_time", "location_id"),
    "inventory": ("location_id", "spaces", "zone_label"),
    "rates": ("zone_label", "effective_from", "rate_usd_per_hr"),
}


class PPAIngestError(ValueError):
    """The export cannot be turned into a panel without guessing."""


@dataclass
class IngestResult:
    panel: pd.DataFrame
    segments: pd.DataFrame
    periods: pd.DataFrame
    report: dict = field(default_factory=dict)


def ingest_config(cfg: Mapping | None = None) -> dict:
    return dict(cfg) if cfg is not None else dict(load_config("ppa_ingest"))


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else project_root() / p


def read_table(path: str | Path) -> pd.DataFrame:
    """CSV, Excel or parquet, every column read as text (types are parsed after mapping)."""
    p = _resolve(path)
    if not p.exists():
        raise FileNotFoundError(p)
    suf = p.suffix.lower()
    if suf == ".parquet":
        return pd.read_parquet(p)
    if suf in (".xlsx", ".xls"):
        return pd.read_excel(p, dtype=str)
    return pd.read_csv(p, dtype=str)


def map_columns(df: pd.DataFrame, table: str, columns: Mapping[str, str | None]) -> pd.DataFrame:
    """Rename export columns to canonical names; raise on a required or mapped-but-absent one."""
    need = [c for c in REQUIRED[table] if not columns.get(c)]
    if need:
        raise PPAIngestError(f"{table}: the mapping leaves required column(s) {need} null")
    absent = {canon: src for canon, src in columns.items() if src and src not in df.columns}
    if absent:
        raise PPAIngestError(f"{table}: mapped column(s) {absent} not in the file; the file has "
                             f"{list(df.columns)}")
    ren = {src: canon for canon, src in columns.items() if src}
    return df[list(ren)].rename(columns=ren)


def _times(s: pd.Series, fmt: str | None, tz: str | None, what: str) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        t = s
    else:
        t = pd.to_datetime(s, format=fmt if fmt else "ISO8601", errors="coerce")
    bad = t.isna() & s.notna()
    if bad.any():
        raise PPAIngestError(f"{what}: {int(bad.sum())} values do not parse with format "
                             f"{fmt!r}, e.g. {s[bad].head(3).tolist()}")
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert(tz or "America/New_York").dt.tz_localize(None)
    return t


def _number(s: pd.Series, what: str) -> pd.Series:
    v = pd.to_numeric(s.astype(str).str.replace(r"[$,\s]", "", regex=True)
                      if not pd.api.types.is_numeric_dtype(s) else s, errors="coerce")
    bad = v.isna() & s.notna()
    if bad.any():
        raise PPAIngestError(f"{what}: {int(bad.sum())} values are not numbers, e.g. "
                             f"{s[bad].head(3).tolist()}")
    return v


def _zone(labels: pd.Series, zone_map: Mapping[str, str], what: str) -> pd.Series:
    zm = {str(k).strip(): v for k, v in (zone_map or {}).items()}
    lab = labels.astype(str).str.strip()
    unknown = sorted(set(lab) - set(zm))
    if unknown:
        raise PPAIngestError(f"{what}: rate-area label(s) {unknown} are not in "
                             f"inventory.zone_map; add them to config/ppa_ingest.yaml")
    return lab.map(zm)


def load_inventory(path: str | Path | None = None, cfg: Mapping | None = None) -> pd.DataFrame:
    """Meter inventory with canonical columns: location_id, spaces, zone_id, segment_id, ..."""
    cfg = ingest_config(cfg)
    icfg = cfg["inventory"]
    inv = map_columns(read_table(path or icfg["path"]), "inventory", icfg["columns"])
    inv["location_id"] = inv["location_id"].astype(str).str.strip()
    if inv["location_id"].duplicated().any():
        dup = inv.loc[inv["location_id"].duplicated(), "location_id"].head(3).tolist()
        raise PPAIngestError(f"inventory: location ids repeat, e.g. {dup}")
    inv["spaces"] = _number(inv["spaces"], "inventory.spaces")
    bad = inv["spaces"].isna() | (inv["spaces"] <= 0)
    if bad.any():
        raise PPAIngestError(f"inventory: {int(bad.sum())} locations have no positive space "
                             f"count, e.g. {inv.loc[bad, 'location_id'].head(3).tolist()}")
    inv["zone_id"] = _zone(inv["zone_label"], icfg.get("zone_map"), "inventory")
    if "segment_id" not in inv.columns or inv["segment_id"].isna().all():
        inv["segment_id"] = inv["location_id"]
    else:
        miss = inv["segment_id"].isna()
        if miss.any():
            raise PPAIngestError(f"inventory: {int(miss.sum())} locations have no segment_id")
        inv["segment_id"] = inv["segment_id"].astype(str).str.strip()
    for c in ("lon", "lat"):
        if c in inv.columns:
            inv[c] = _number(inv[c], f"inventory.{c}")
    return inv


def inventory_points(inv: pd.DataFrame) -> gpd.GeoDataFrame:
    """Inventory locations as EPSG:4326 points (requires lon / lat in the mapping)."""
    if not {"lon", "lat"} <= set(inv.columns):
        raise PPAIngestError("inventory has no lon / lat columns mapped")
    return gpd.GeoDataFrame(inv.copy(), geometry=gpd.points_from_xy(inv["lon"], inv["lat"]),
                            crs=4326)


def load_rates(path: str | Path | None = None, cfg: Mapping | None = None) -> pd.DataFrame:
    """Rate schedule: zone_id, effective_from (date), rate_usd_per_hr; one row per change."""
    cfg = ingest_config(cfg)
    rcfg = cfg["rates"]
    r = map_columns(read_table(path or rcfg["path"]), "rates", rcfg["columns"])
    r["zone_id"] = _zone(r["zone_label"], cfg["inventory"].get("zone_map"), "rates")
    r["effective_from"] = _times(r["effective_from"], rcfg.get("date_format"), None,
                                 "rates.effective_from").dt.normalize()
    r["rate_usd_per_hr"] = _number(r["rate_usd_per_hr"], "rates.rate_usd_per_hr")
    dup = r.duplicated(["zone_id", "effective_from"], keep=False)
    if dup.any():
        conflict = r[dup].groupby(["zone_id", "effective_from"])["rate_usd_per_hr"].nunique()
        if (conflict > 1).any():
            raise PPAIngestError(f"rates: conflicting rates on the same date: "
                                 f"{conflict[conflict > 1].index.tolist()}")
        r = r.drop_duplicates(["zone_id", "effective_from"])
    return r[["zone_id", "effective_from", "rate_usd_per_hr"]].sort_values(
        ["zone_id", "effective_from"]).reset_index(drop=True)


def load_sessions(path: str | Path | None = None, cfg: Mapping | None = None) -> pd.DataFrame:
    """Sessions: location_id, start_time, end_time (local, naive) and any optional fields."""
    cfg = ingest_config(cfg)
    scfg = cfg["sessions"]
    cols = dict(scfg["columns"])
    if not cols.get("end_time") and not cols.get("duration_minutes"):
        raise PPAIngestError("sessions: map end_time or duration_minutes")
    s = map_columns(read_table(path or scfg["path"]), "sessions", cols)
    fmt, tz = scfg.get("datetime_format"), scfg.get("timezone")
    s["location_id"] = s["location_id"].astype(str).str.strip()
    s["start_time"] = _times(s["start_time"], fmt, tz, "sessions.start_time")
    if "end_time" in s.columns:
        s["end_time"] = _times(s["end_time"], fmt, tz, "sessions.end_time")
    else:
        dur = _number(s["duration_minutes"], "sessions.duration_minutes")
        s["end_time"] = s["start_time"] + pd.to_timedelta(dur, unit="m")
    for c in ("amount_paid_usd", "posted_rate_usd_per_hr"):
        if c in s.columns:
            s[c] = _number(s[c], f"sessions.{c}")
    if s["start_time"].isna().any() or s["end_time"].isna().any():
        raise PPAIngestError("sessions: some sessions have no start or no end")
    dur_h = (s["end_time"] - s["start_time"]) / pd.Timedelta(hours=1)
    if (dur_h <= 0).any():
        raise PPAIngestError(f"sessions: {int((dur_h <= 0).sum())} sessions end at or before "
                             f"their start")
    max_h = float(scfg.get("max_session_hours", 24))
    if (dur_h > max_h).any():
        raise PPAIngestError(f"sessions: {int((dur_h > max_h).sum())} sessions are longer than "
                             f"max_session_hours={max_h}")
    return s


def define_periods(rates: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Cut [start, end] (dates, inclusive) at every effective date inside it.

    Returns period (label = its first date, ISO), period_start, period_end (inclusive).
    """
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    cuts = sorted({d for d in rates["effective_from"] if start < d <= end})
    starts = [start, *cuts]
    ends = [c - pd.Timedelta(days=1) for c in cuts] + [end]
    return pd.DataFrame({"period": [s.date().isoformat() for s in starts],
                         "period_start": starts, "period_end": ends})


def posted_rates(rates: pd.DataFrame, periods: pd.DataFrame, zones) -> pd.DataFrame:
    """Rate in effect per (zone, period): the latest schedule row on or before the period start."""
    rows = []
    for z in sorted(set(zones)):
        rz = rates[rates["zone_id"] == z]
        for p in periods.itertuples(index=False):
            eff = rz[rz["effective_from"] <= p.period_start]
            if eff.empty:
                raise PPAIngestError(f"rates: zone {z!r} has no rate in effect on "
                                     f"{p.period_start.date()} (period {p.period})")
            rows.append({"zone_id": z, "period": p.period,
                         "price_usd_per_hr": float(eff["rate_usd_per_hr"].iloc[-1])})
    return pd.DataFrame(rows)


def days_per_weekday(periods: pd.DataFrame) -> pd.DataFrame:
    """Number of calendar dates of each weekday (0 = Monday) in each period."""
    rows = []
    for p in periods.itertuples(index=False):
        dows = pd.date_range(p.period_start, p.period_end, freq="D").dayofweek
        counts = np.bincount(dows, minlength=7)
        rows += [{"period": p.period, "dow": d, "n_days": int(counts[d])} for d in range(7)]
    return pd.DataFrame(rows)


def explode_to_hours(start: pd.Series, end: pd.Series) -> pd.DataFrame:
    """One row per (session, clock hour it overlaps): session index, hour start, minutes."""
    s = start.to_numpy("datetime64[ns]")
    e = end.to_numpy("datetime64[ns]")
    hour = np.timedelta64(1, "h")
    h0 = s.astype("datetime64[h]").astype("datetime64[ns]")
    h_last = (e - np.timedelta64(1, "ns")).astype("datetime64[h]").astype("datetime64[ns]")
    n = ((h_last - h0) // hour).astype(np.int64) + 1
    idx = np.repeat(np.arange(len(s)), n)
    first = np.repeat(np.cumsum(n) - n, n)
    offset = np.arange(int(n.sum())) - first
    bucket = h0[idx] + offset * hour
    lo = np.maximum(s[idx], bucket)
    hi = np.minimum(e[idx], bucket + hour)
    minutes = (hi - lo) / np.timedelta64(1, "m")
    return pd.DataFrame({"session": idx, "offset": offset, "bucket": bucket,
                         "minutes": minutes.astype(float)})


def build_panel(sessions: pd.DataFrame, inventory: pd.DataFrame, rates: pd.DataFrame,
                cfg: Mapping | None = None, window: tuple | None = None) -> IngestResult:
    """Sessions + inventory + rate schedule -> `IngestResult` (see the module docstring).

    `window` = (first date, last date) observed, inclusive; default the sessions' own range.
    """
    cfg = ingest_config(cfg)
    checks = cfg.get("checks", {})
    unpaid = (cfg.get("unpaid_use") or {}).get("unpaid_share")
    if not isinstance(unpaid, Mapping) or "default" not in unpaid:
        raise PPAIngestError("unpaid_use.unpaid_share must be a mapping with a 'default' (state "
                             "0.0 explicitly to use paid occupancy)")
    report: dict = {"sessions_in": int(len(sessions))}

    known = sessions["location_id"].isin(set(inventory["location_id"]))
    share_unmatched = float((~known).mean()) if len(sessions) else 0.0
    report["sessions_unmatched"] = int((~known).sum())
    if share_unmatched > float(checks.get("max_unmatched_session_share", 0.0)):
        ex = sessions.loc[~known, "location_id"].drop_duplicates().head(5).tolist()
        raise PPAIngestError(f"{share_unmatched:.2%} of sessions have a location not in the "
                             f"inventory (e.g. {ex})")
    s = sessions[known].merge(inventory[["location_id", "segment_id", "zone_id"]],
                              on="location_id", how="left")

    if window is None:
        window = (s["start_time"].min(), s["end_time"].max())
    w0, w1 = pd.Timestamp(window[0]).normalize(), pd.Timestamp(window[1]).normalize()
    periods = define_periods(rates, w0, w1)
    seg = (inventory.groupby("segment_id")
           .agg(zone_id=("zone_id", "first"), n_zones=("zone_id", "nunique"),
                capacity=("spaces", "sum"), n_locations=("location_id", "size"))
           .reset_index())
    if (seg["n_zones"] > 1).any():
        raise PPAIngestError(f"segments span more than one rate area: "
                             f"{seg.loc[seg['n_zones'] > 1, 'segment_id'].head(5).tolist()}")
    seg = seg.drop(columns="n_zones")
    prices = posted_rates(rates, periods, seg["zone_id"])

    # Hours: split sessions over clock hours, keep the window, assign periods.
    hrs = explode_to_hours(s["start_time"], s["end_time"])
    hrs["segment_id"] = s["segment_id"].to_numpy()[hrs["session"]]
    day = hrs["bucket"].dt.normalize()
    inwin = (day >= w0) & (day <= w1)
    report["session_minutes_outside_window"] = float(hrs.loc[~inwin, "minutes"].sum())
    hrs = hrs[inwin]
    pidx = np.searchsorted(periods["period_start"].to_numpy(), hrs["bucket"].dt.normalize()
                           .to_numpy(), side="right") - 1
    hrs["period"] = periods["period"].to_numpy()[pidx]
    hrs["hour_of_week"] = hrs["bucket"].dt.dayofweek * 24 + hrs["bucket"].dt.hour
    hrs["started"] = (hrs["offset"] == 0).astype(int)
    agg = (hrs.groupby(["segment_id", "period", "hour_of_week"])
           .agg(paid_minutes=("minutes", "sum"), n_sessions=("started", "sum")).reset_index())

    # Posted-rate cross-check, per session against the schedule for its start's period.
    if "posted_rate_usd_per_hr" in s.columns:
        sp = np.searchsorted(periods["period_start"].to_numpy(),
                             s["start_time"].dt.normalize().to_numpy(), side="right") - 1
        ok = (sp >= 0) & (s["start_time"].dt.normalize() <= w1).to_numpy()
        chk = pd.DataFrame({"zone_id": s["zone_id"].to_numpy()[ok],
                            "period": periods["period"].to_numpy()[sp[ok]],
                            "posted": s["posted_rate_usd_per_hr"].to_numpy()[ok]})
        chk = chk.merge(prices, on=["zone_id", "period"], how="left")
        has = chk["posted"].notna()
        mism = has & ((chk["posted"] - chk["price_usd_per_hr"]).abs() > 0.005)
        share = float(mism.sum() / max(1, has.sum()))
        report["sessions_rate_mismatch"] = int(mism.sum())
        if share > float(checks.get("max_rate_mismatch_share", 0.0)):
            ex = chk[mism].drop_duplicates(["zone_id", "period"]).head(5).to_dict("records")
            raise PPAIngestError(f"{share:.2%} of sessions carry a posted rate the schedule "
                                 f"contradicts, e.g. {ex}")

    # Full grid: every segment x period x hour of week, zero where nobody paid.
    grid = (seg[["segment_id", "zone_id", "capacity"]]
            .merge(periods[["period"]], how="cross")
            .merge(pd.DataFrame({"hour_of_week": np.arange(HOURS_OF_WEEK)}), how="cross"))
    grid["dow"] = grid["hour_of_week"] // 24
    grid = grid.merge(days_per_weekday(periods), on=["period", "dow"], how="left")
    panel = grid.merge(agg, on=["segment_id", "period", "hour_of_week"], how="left")
    panel[["paid_minutes", "n_sessions"]] = panel[["paid_minutes", "n_sessions"]].fillna(0)
    denom = panel["capacity"] * 60.0 * panel["n_days"]
    if (panel.loc[panel["paid_minutes"] > 0, "n_days"] == 0).any():
        raise PPAIngestError("paid minutes fall on a weekday the period has no dates of")
    panel["paid_occupancy"] = np.where(denom > 0, panel["paid_minutes"] / denom.where(denom > 0), 0.0)
    u = panel["zone_id"].map({k: v for k, v in unpaid.items() if k != "default"}).fillna(
        float(unpaid["default"])).astype(float)
    if ((u < 0) | (u >= 1)).any():
        raise PPAIngestError("unpaid_share must lie in [0, 1)")
    panel["occupancy"] = panel["paid_occupancy"] / (1.0 - u)
    tol = float(checks.get("over_capacity_tolerance", 1.0))
    over = panel["occupancy"] > tol
    report["cells_over_capacity"] = int(over.sum())
    if float(over.mean()) > float(checks.get("max_over_capacity_share", 0.0)):
        ex = panel.loc[over, ["segment_id", "period", "hour_of_week", "occupancy"]].head(5)
        raise PPAIngestError(f"{int(over.sum())} cells exceed capacity x {tol} (spaces too low "
                             f"in the inventory, or unpaid_share too high):\n{ex.to_string()}")
    zp = panel.groupby(["zone_id", "period"])["paid_minutes"].sum()
    empty = zp[zp <= 0].index.tolist()
    if empty:
        raise PPAIngestError(f"(zone, period) with no paid session at all: {empty}. That is a "
                             f"gap in the export, not zero demand; drop the zone from the "
                             f"inventory or narrow --window")
    report["segment_periods_without_sessions"] = int(
        (panel.groupby(["segment_id", "period"])["paid_minutes"].sum() <= 0).sum())
    report["cells_clipped_to_1"] = int((panel["occupancy"] > 1.0).sum())
    panel["occupancy"] = panel["occupancy"].clip(upper=1.0)
    panel = panel.merge(prices, on=["zone_id", "period"], how="left")
    panel = panel[["segment_id", "zone_id", "period", "hour_of_week", "occupancy",
                   "paid_occupancy", "price_usd_per_hr", "paid_minutes", "n_sessions",
                   "n_days", "capacity"]].sort_values(["segment_id", "period", "hour_of_week"])

    report.update({
        "window": [w0.date().isoformat(), w1.date().isoformat()],
        "periods": periods["period"].tolist(),
        "segments": int(len(seg)), "locations": int(len(inventory)),
        "unpaid_share": dict(unpaid), "unpaid_source": (cfg.get("unpaid_use") or {}).get("source"),
    })
    seg_out = seg.copy()
    if {"lon", "lat"} <= set(inventory.columns):
        xy = inventory.groupby("segment_id")[["lon", "lat"]].mean()
        seg_out = gpd.GeoDataFrame(seg_out, geometry=gpd.points_from_xy(
            seg_out["segment_id"].map(xy["lon"]), seg_out["segment_id"].map(xy["lat"])), crs=4326)
    return IngestResult(panel=panel.reset_index(drop=True), segments=seg_out, periods=periods,
                        report=report)


def ingest(cfg: Mapping | None = None, sessions_path=None, inventory_path=None, rates_path=None,
           window: tuple | None = None) -> IngestResult:
    """Read the three tables through the mapping and build the panel."""
    cfg = ingest_config(cfg)
    inv = load_inventory(inventory_path, cfg)
    rates = load_rates(rates_path, cfg)
    sessions = load_sessions(sessions_path, cfg)
    return build_panel(sessions, inv, rates, cfg, window)


def runner_inputs(result: IngestResult, period: str | None = None,
                  check_current_rates: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(segments, typical-week panel) for `run_scenario`, from one calendar period.

    Default period: the latest. The runner prices the status quo at `zones.yaml`'s
    `current_rate_usd_per_hr`; if the chosen period's posted rate differs for a zone, the
    status quo would be priced at a rate the data were not observed under, so this raises.
    """
    periods = result.periods["period"].tolist()
    period = period or periods[-1]
    if period not in periods:
        raise PPAIngestError(f"period {period!r} not in {periods}")
    p = result.panel[result.panel["period"] == period]
    if check_current_rates:
        cur = {z["id"]: float(z["current_rate_usd_per_hr"]) for z in load_config("zones")["zones"]}
        posted = p.groupby("zone_id")["price_usd_per_hr"].first()
        bad = {z: (r, cur.get(z)) for z, r in posted.items()
               if z in cur and abs(r - cur[z]) > 0.005}
        if bad:
            raise PPAIngestError(f"period {period}: posted rate differs from zones.yaml "
                                 f"current_rate_usd_per_hr (posted, config): {bad}")
    seg = result.segments.copy()
    seg.attrs["segment_source"] = {"kind": "ppa_inventory", "period": period,
                                   "n_locations": int(seg["n_locations"].sum())}
    return seg, p[["segment_id", "hour_of_week", "occupancy"]].reset_index(drop=True)
