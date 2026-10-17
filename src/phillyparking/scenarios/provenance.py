"""Where a saved scenario result came from: segments, configuration, code and elasticity.

Written into each scenario's `meta.json` so a number in `outputs/` can be traced to the
inputs that produced it without rerunning anything.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
from pathlib import Path

from phillyparking._config import config_dir, project_root


def file_sha256(path: Path) -> str:
    """SHA-256 of a text file with CRLF read as LF: a Windows checkout (`core.autocrlf`) and a
    Linux one hold the same file and must give the same hash."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def config_hashes() -> dict[str, str]:
    """SHA-256 of every `config/*.yaml` file in use (the directory `load_config` reads)."""
    return {p.stem: file_sha256(p) for p in sorted(config_dir().glob("*.yaml"))}


def config_mismatches(recorded: dict[str, str]) -> list[str]:
    """Config files whose current hash differs from `recorded` (an artifact's `config_sha256`):
    changed, absent from the tree, or new since. Empty when the artifact was made under the
    config in the tree."""
    now = config_hashes()
    return sorted(
        [f"{k} (changed)" for k in recorded if k in now and recorded[k] != now[k]]
        + [f"{k} (no longer in the tree)" for k in recorded if k not in now]
        + [f"{k} (not recorded by the artifact)" for k in now if k not in recorded]
    )


def git_state() -> dict:
    """Commit the code was run from and whether the tracked tree had uncommitted edits."""
    def _git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args], cwd=project_root(), capture_output=True, text=True,
                timeout=10, check=True,
            )
            return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None

    # A file rewritten with identical content (a generated table, CRLF/LF under autocrlf) has a
    # stale stat entry that `status` reports as modified until the index is refreshed.
    _git("update-index", "-q", "--refresh")
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "dirty": None if status is None else bool(status)}


def segment_source(segments) -> dict:
    """Describe where `segments` came from, as recorded on `segments.attrs["segment_source"]`.

    `make_synthetic_segments` and `load_segments` set it; a frame that lost its `attrs`
    (a merge, a copy through plain pandas) is reported as unknown rather than guessed.
    """
    src = dict(getattr(segments, "attrs", {}).get("segment_source") or {"kind": "unknown"})
    src["n_segments"] = int(len(segments))
    return src


def build_provenance(segments, elasticity, seed: int, segment_source_override: dict | None = None) -> dict:
    """Provenance block for one scenario run. `elasticity` is an `ElasticityScenario`."""
    src = dict(segment_source_override) if segment_source_override else segment_source(segments)
    src.setdefault("n_segments", int(len(segments)))
    return {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "seed": int(seed),
        "segment_source": src,
        "config_sha256": config_hashes(),
        "git": git_state(),
        "elasticity": {
            "scenario": elasticity.name,
            "central": float(elasticity.elasticity),
            "sd": float(elasticity.sd),
        },
    }


def describe_file_source(path: Path) -> dict:
    return {"kind": "file", "path": str(Path(path).resolve())}
