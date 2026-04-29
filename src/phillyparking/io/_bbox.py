"""Shared bbox utility for offline fallbacks."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def philly_bbox() -> tuple[float, float, float, float]:
    """Return (west, south, east, north) for Philadelphia, from env or defaults."""
    return (
        float(os.environ.get("PHL_BBOX_WEST", -75.28)),
        float(os.environ.get("PHL_BBOX_SOUTH", 39.87)),
        float(os.environ.get("PHL_BBOX_EAST", -74.95)),
        float(os.environ.get("PHL_BBOX_NORTH", 40.14)),
    )
