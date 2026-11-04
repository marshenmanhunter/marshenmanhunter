"""Robust price statistics. Medians and percentiles, never means: eBay prices have wild tails."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime

MAD_TO_SIGMA = 1.4826
# Floor for the spread estimate, as a share of the median. Stops a market where every
# listing sits at the same price from flagging a $1 difference as a huge outlier.
MIN_SCALE_SHARE = 0.02
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def percentile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation percentile (same as numpy's default). Input must be sorted."""
    if not sorted_vals:
        raise ValueError("no values")
    k = (len(sorted_vals) - 1) * q
    lo = math.floor(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


@dataclass
class Summary:
    n: int
    median: float
    p10: float
    p25: float
    p75: float
    p90: float
    min: float
    max: float
    mad: float

    @property
    def scale(self) -> float:
        """Robust standard deviation estimate with a floor."""
        return max(MAD_TO_SIGMA * self.mad, MIN_SCALE_SHARE * self.median)


def summarize(values: list[float]) -> Summary | None:
    if not values:
        return None
    s = sorted(values)
    med = percentile(s, 0.5)
    mad = percentile(sorted(abs(v - med) for v in s), 0.5)
    return Summary(
        n=len(s),
        median=med,
        p10=percentile(s, 0.10),
        p25=percentile(s, 0.25),
        p75=percentile(s, 0.75),
        p90=percentile(s, 0.90),
        min=s[0],
        max=s[-1],
        mad=mad,
    )


def robust_z(value: float, summary: Summary) -> float:
    """How many robust standard deviations below the median a price sits. Positive = cheaper."""
    return (summary.median - value) / summary.scale


def daily_medians(rows: list[tuple[str, float]]) -> list[tuple[date, float]]:
    """Collapse per-run medians into one median per UTC day."""
    by_day: dict[date, list[float]] = {}
    for ts, med in rows:
        if med is None:
            continue
        d = datetime.fromisoformat(ts).date()
        by_day.setdefault(d, []).append(med)
    return [(d, percentile(sorted(v), 0.5)) for d, v in sorted(by_day.items())]


def pct_change(series: list[tuple[date, float]], days: int) -> float | None:
    """Change from the value `days` ago (or the closest earlier day) to the latest value."""
    if len(series) < 2:
        return None
    last_day, last_val = series[-1]
    past = [v for d, v in series if (last_day - d).days >= days]
    if not past:
        return None
    ref = past[-1]
    return (last_val - ref) / ref if ref else None


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK_CHARS[3] * len(values)
    step = (hi - lo) / (len(SPARK_CHARS) - 1)
    return "".join(SPARK_CHARS[round((v - lo) / step)] for v in values)
