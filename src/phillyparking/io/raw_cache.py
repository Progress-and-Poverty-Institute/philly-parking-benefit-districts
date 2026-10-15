"""Cache for public layers under `data/raw/`, with a provenance marker beside every file.

Every file written under `data/raw/` gets a sidecar `<file>.provenance.json` holding the
layer name, `kind` ("real" or "synthetic"), the source, the URL, the UTC fetch time, and for
a synthetic stand-in the reason the real fetch failed.

- A real fetch is cached under the layer's own filename.
- A synthetic stand-in is generated only when the caller opts in (`allow_synthetic=True`, or
  `PHILLYPARKING_ALLOW_SYNTHETIC=1`), and only under `<stem>.synthetic<suffix>`, never under
  the real name.
- A cache file with no marker is of unknown origin and is refused, not read. Before markers
  existed, every loader wrote its synthetic fallback under the real filename, so an unmarked
  file cannot be told apart from one of those. Refetch with `refresh=True`.
- A failed fetch is retried, then raises `LayerFetchError` unless a stand-in was allowed.

Every object returned carries its marker: `obj.attrs["provenance"]` for a (Geo)DataFrame,
`G.graph["provenance"]` for a networkx graph.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

SYNTHETIC_ENV = "PHILLYPARKING_ALLOW_SYNTHETIC"


class LayerFetchError(RuntimeError):
    """A real fetch failed and no synthetic stand-in was allowed."""


class UnknownProvenanceError(RuntimeError):
    """A cache file under a real layer name has no provenance marker saying it is real."""


def synthetic_allowed(flag: bool | None = None) -> bool:
    """The explicit flag if given, else the `PHILLYPARKING_ALLOW_SYNTHETIC` environment switch."""
    if flag is not None:
        return bool(flag)
    return os.environ.get(SYNTHETIC_ENV, "").strip().lower() in {"1", "true", "yes"}


def marker_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.name + ".provenance.json")


def synthetic_path(path: Path) -> Path:
    """Where a synthetic stand-in for the layer cached at `path` is written."""
    path = Path(path)
    return path.with_name(f"{path.stem}.synthetic{path.suffix}")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def write_marker(path: Path, *, layer: str, kind: str, source: str, url: str | None,
                 reason: str | None = None, **extra) -> dict:
    if kind not in ("real", "synthetic"):
        raise ValueError(f"kind must be 'real' or 'synthetic', not {kind!r}")
    marker = {"layer": layer, "kind": kind, "source": source, "url": url,
              "fetched_utc": now_utc(), "file": Path(path).name}
    if reason is not None:
        marker["reason"] = reason
    marker.update(extra)
    marker_path(path).write_text(json.dumps(marker, indent=2, default=str), encoding="utf-8")
    return marker


def read_marker(path: Path) -> dict | None:
    mp = marker_path(path)
    if not mp.exists():
        return None
    return json.loads(mp.read_text(encoding="utf-8"))


def tag(obj: Any, marker: dict) -> Any:
    """Attach a provenance marker to the object a loader returns."""
    if hasattr(obj, "attrs") and isinstance(getattr(obj, "attrs"), dict):
        obj.attrs["provenance"] = dict(marker)
    elif hasattr(obj, "graph") and isinstance(getattr(obj, "graph"), dict):
        obj.graph["provenance"] = dict(marker)
    return obj


def provenance_of(obj: Any) -> dict | None:
    if hasattr(obj, "attrs") and isinstance(getattr(obj, "attrs"), dict):
        return obj.attrs.get("provenance")
    if hasattr(obj, "graph") and isinstance(getattr(obj, "graph"), dict):
        return obj.graph.get("provenance")
    return None


@dataclass
class Layer:
    """One public layer: where it is cached, where it comes from, and how to read and write it."""

    name: str
    path: Path
    source: str
    url: str | None
    fetch: Callable[[], Any]
    write: Callable[[Any, Path], None]
    read: Callable[[Path], Any]
    synth: Callable[[], Any] | None = None


def load_layer(layer: Layer, refresh: bool = False, allow_synthetic: bool | None = None,
               retries: int = 3, backoff_s: float = 2.0) -> Any:
    """Return the layer from cache or the network; see the module docstring for the rules."""
    allow = synthetic_allowed(allow_synthetic)
    path = Path(layer.path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not refresh:
        if path.exists():
            marker = read_marker(path)
            if marker is None:
                raise UnknownProvenanceError(
                    f"{layer.name}: {path} has no provenance marker, so it may be a synthetic "
                    f"layer saved under the real name by an older loader. Refetch it "
                    f"(scripts/01_download_public_data.py --refresh) or delete it."
                )
            if marker.get("kind") != "real":
                raise UnknownProvenanceError(
                    f"{layer.name}: the marker for {path} says kind={marker.get('kind')!r} "
                    f"under the real filename; refetch it."
                )
            return tag(layer.read(path), marker)
        spath = synthetic_path(path)
        if allow and layer.synth is not None and spath.exists():
            marker = read_marker(spath)
            if marker is not None and marker.get("kind") == "synthetic":
                log.warning("%s: using the cached SYNTHETIC stand-in %s (%s)", layer.name, spath,
                            marker.get("reason"))
                return tag(layer.read(spath), marker)

    last: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            obj = layer.fetch()
        except Exception as exc:  # noqa: BLE001 - every failure is reported, then raised below
            last = exc
            log.warning("%s: fetch attempt %d of %d failed: %s", layer.name, attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff_s * attempt)
            continue
        layer.write(obj, path)
        marker = write_marker(path, layer=layer.name, kind="real", source=layer.source,
                              url=layer.url)
        return tag(obj, marker)

    if allow and layer.synth is not None:
        obj = layer.synth()
        spath = synthetic_path(path)
        layer.write(obj, spath)
        marker = write_marker(spath, layer=layer.name, kind="synthetic",
                              source=f"synthetic stand-in for {layer.source}", url=None,
                              reason=f"real fetch failed: {last!r}")
        log.warning("%s: real fetch failed; wrote a SYNTHETIC stand-in to %s", layer.name, spath)
        return tag(obj, marker)
    raise LayerFetchError(
        f"{layer.name}: real fetch from {layer.url or layer.source} failed after {retries} "
        f"attempt(s): {last!r}. No synthetic stand-in was written; pass allow_synthetic=True "
        f"(or set {SYNTHETIC_ENV}=1) to get one under a .synthetic filename."
    ) from last
