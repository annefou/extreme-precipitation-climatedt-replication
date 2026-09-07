"""Global-mean 2 m temperature per window: the per-degree normalisation.

    pixi run warming-levels

The claim under test is about the **ordering** of change across durations and
return periods, and needs no temperature at all. This exists only so the
magnitude can be expressed as "% per degree of global warming" and set beside
the 6-8.5 %/K the original paper reports.

Read from the monthly-mean (`clmn`) stream at `standard` resolution: a global
mean does not need 6 km cells, and 12 fields per year is a few seconds.

Two things here are not obvious:

* `.to_xarray()` fails on this GRIB with "Input does not form a full hypercube.
  Expected number of fields ... 36 != 12". `.to_fieldlist().to_numpy()` returns
  the 12 monthly fields cleanly, so that is the path used.
* HEALPix cells are equal-area, so the global mean is the plain unweighted mean
  over cells -- no cosine-latitude weighting. Months ARE weighted by their
  length, since a 28-day February should not count as much as a 31-day January.
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import climatedt  # noqa: E402


def annual_global_mean(window: str, year: int) -> float:
    """Day-weighted global mean 2 m temperature for one year, in kelvin."""
    fields = climatedt.retrieve(
        climatedt.clmn_global_request(window, year)
    ).to_fieldlist()
    values = fields.to_numpy()  # (12, n_cells)
    if values.shape[0] != 12:
        raise RuntimeError(f"{window} {year}: expected 12 monthly fields, got {values.shape[0]}")
    days = np.array([calendar.monthrange(year, m)[1] for m in range(1, 13)], dtype=float)
    monthly = np.nanmean(values, axis=1)  # equal-area cells -> plain mean
    return float(np.sum(monthly * days) / days.sum())


def compute(out_path: Path) -> dict:
    gmst, per_year = {}, {}
    for window, spec in climatedt.WINDOWS.items():
        first, last = spec["years"]
        series = []
        for year in range(first, last + 1):
            t0 = time.time()
            value = annual_global_mean(window, year)
            series.append(value)
            print(f"  {window} {year}: {value:.4f} K  [{time.time() - t0:.0f}s]", flush=True)
        per_year[window] = series
        gmst[window] = float(np.mean(series))
        print(f"{window}: {len(series)}-year mean {gmst[window]:.4f} K", flush=True)

    windows = list(climatedt.WINDOWS)
    doc = {
        "provenance": "destine-climate-dt",
        "gmst_k": gmst,
        "per_year_k": per_year,
        "delta_t_k": gmst[windows[1]] - gmst[windows[0]],
        "method": (
            "Day-weighted mean of monthly-mean avg_2t from the clmn stream at "
            "standard resolution (HEALPix level 7, 196608 equal-area cells), "
            "averaged over each window's years."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2)
    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/raw/warming_levels.json"))
    args = parser.parse_args()

    if not climatedt.have_credentials():
        print("No DestinE credential found. Run `pixi run check-destine`.")
        return 1
    doc = compute(args.out)
    print(f"\nwarming between windows: {doc['delta_t_k']:.4f} K")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
