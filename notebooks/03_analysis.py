# ---
# jupyter:
#   jupytext:
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 03 — Does the duration × return-period ordering hold?
#
# ## The claim under test
#
# From the Conclusions of Hundhausen et al. (2024):
#
# > "Events with short duration and long RPs are expected to change the most."
#
# stated as an AIDA sentence in `nanopubs/drafts/02_aida.md`:
#
# > Under global warming, extreme precipitation events of short duration and
# > long return period intensify proportionally more than events of long
# > duration and short return period.
#
# The claim is about **ordering**, not magnitude — which is what makes it
# transferable to another region, another model and another scenario. Testing
# it therefore needs no warming level at all. The warming level appears once, at
# the end, only to express the magnitude as "% per degree" so it can be set
# beside the paper's reported 6–8.5 % per degree.
#
# ## Method
#
# For each window and duration, a **regional index-flood** analysis: each cell's
# annual-maxima series is divided by its own at-site mean, the standardised
# series are pooled across all cells, and one GEV is fitted to the pool by
# L-moments. Return levels are then the pooled growth factor times each cell's
# index flood.
#
# Pooling is not a shortcut. It is what the original paper does too — "estimates
# for long RP are only possible for pooled spatial information" — and it is why
# a 20-year return level can be estimated from a 20-year window. Return periods
# are capped at 20 years for the same reason: 100 years, as in the paper, would
# be extrapolation here.
#
# The estimator lives in `scripts/extremes.py` and is unit tested against
# `scipy.stats.genextreme` in `tests/test_extremes.py`.

# %%
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

sys.path.insert(0, str(Path("../scripts").resolve()))

import analysis  # noqa: E402
import climatedt  # noqa: E402
import extremes  # noqa: E402

CLEAN_DIR = Path("../data/clean")
RESULTS_DIR = Path("../results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

N_BOOTSTRAP = 400
BOOTSTRAP_SEED = 20260906

# %% [markdown]
# ## Inputs: one dataset per grid
#
# `02_data_clean.py` writes the annual maxima on the HEALPix grid **as
# delivered** (defined on a sphere) and, when `healpix-resample` is available,
# on the **WGS84 ellipsoid**. The whole analysis runs on each, so the effect of
# the coordinate correction on the conclusion is measured rather than assumed.

# %%
GRID_FILES = {"native": "annual_maxima.nc", "ellipsoid": "annual_maxima_ellipsoid.nc"}
grids = {
    name: xr.open_dataset(CLEAN_DIR / fname)
    for name, fname in GRID_FILES.items()
    if (CLEAN_DIR / fname).exists()
}
if not grids:
    raise FileNotFoundError(f"no annual-maxima file in {CLEAN_DIR}; run 02_data_clean.py")
print(f"grids available: {list(grids)}")

ds = grids["native"]
PROVENANCE = ds.attrs.get("provenance", "unknown")
WINDOW_LABELS = json.loads(ds.attrs.get("window_labels", "{}"))
windows = [str(w) for w in ds["window"].values]
durations = [int(d) for d in ds["duration"].values]
rps = np.array(climatedt.RETURN_PERIODS_Y)

print(f"provenance : {PROVENANCE}")
print(f"windows    : {windows}  {WINDOW_LABELS}")
print(f"durations  : {durations} h")
print(f"return per.: {list(rps)} y")
print(f"cells      : {ds.sizes['cell']}, blocks per window: {ds.sizes['block']}")
if PROVENANCE != "destine-climate-dt":
    print(
        "\nWARNING — SYNTHETIC INPUT. Every number below is a smoke test of the\n"
        "pipeline and must not be reported as a replication result."
    )


# %% [markdown]
# ## Fit each grid
#
# One pooled index-flood GEV per (window, duration), then the change matrix and
# the ordering tests. `scripts/analysis.py` does the work and is unit tested in
# `tests/test_analysis.py` against matrices whose right answer is known by
# construction — including that a flat matrix, or one favourable column among
# unfavourable ones, must NOT read as support for the claim.

# %%
per_grid = {}
for name, grid_ds in grids.items():
    print(f"fitting {name} grid ({grid_ds.sizes['cell']} cells) ...", flush=True)
    per_grid[name] = analysis.analyse(grid_ds, windows, durations, rps)

result = per_grid["native"]
pct, pct_lo, pct_hi = result["pct"], result["pct_lo"], result["pct_hi"]
fits = result["fits"]
return_levels = result["return_levels"]
index_floods = result["index_floods"]
hist_window, future_window = windows[0], windows[1]

# %% [markdown]
# ### The fitted growth curves
#
# The shape parameter *k* is worth reading directly: a more negative *k* is a
# heavier tail, so a shape that becomes more negative from the historical to the
# scenario window is itself evidence of the long-return-period end changing most.

# %%
rows = []
for window in windows:
    for duration in durations:
        xi, alpha, k = fits[(window, duration)]
        index_flood = index_floods[(window, duration)]
        growth = extremes.return_level(rps, xi, alpha, k)
        rows.append({
            "window": window,
            "duration_h": duration,
            "gev_location": xi,
            "gev_scale": alpha,
            "gev_shape_k": k,
            "n_cells_used": int(np.sum(np.isfinite(index_flood))),
            "median_index_flood_mm": float(np.nanmedian(index_flood)),
            **{f"growth_rp{int(r)}": float(g) for r, g in zip(rps, growth)},
        })
fits_df = pd.DataFrame(rows)
print(fits_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

# %% [markdown]
# ## The change matrix
#
# For every (duration, return period), the change in return level between the
# two windows — taken as the **median over cells of the per-cell ratio**, not
# the ratio of medians, so each cell's own climatology stays out of it.

# %%
matrix = pd.DataFrame(
    pct, index=pd.Index(durations, name="duration_h"),
    columns=[f"RP{int(r)}y" for r in rps],
)
print("Change in return level, scenario vs historical (%):")
print(matrix.to_string(float_format=lambda v: f"{v:+.2f}"))

# %% [markdown]
# ## Testing the ordering
#
# Three readings of the same claim, reported together because they can disagree
# and a single number would hide that.
#
# 1. **Duration effect** — Kendall's tau of the change against duration, at each
#    return period. The claim predicts a **negative** tau: shorter durations
#    change more.
# 2. **Return-period effect** — tau against return period, at each duration. The
#    claim predicts **positive**.
# 3. **The corner test** — the claim's own words taken literally.

# %%
print("Kendall tau of change vs DURATION (claim predicts negative):")
for key, v in result["kendall_tau_vs_duration"].items():
    print(f"  {key:>7s}  tau = {v['tau']:+.3f}   p = {v['p']:.4f}")
print("\nKendall tau of change vs RETURN PERIOD (claim predicts positive):")
for key, v in result["kendall_tau_vs_return_period"].items():
    print(f"  {key:>7s}  tau = {v['tau']:+.3f}   p = {v['p']:.4f}")

corner = result["corner_test"]
print(
    f"\nCorner test: {corner['short_duration_long_rp']['duration_h']} h / "
    f"{int(corner['short_duration_long_rp']['rp_y'])} y changes by "
    f"{corner['short_duration_long_rp']['change_pct']:+.2f} %, "
    f"{corner['long_duration_short_rp']['duration_h']} h / "
    f"{int(corner['long_duration_short_rp']['rp_y'])} y by "
    f"{corner['long_duration_short_rp']['change_pct']:+.2f} % — a difference of "
    f"{corner['difference_pct_points']:+.2f} percentage points."
)

# %% [markdown]
# ## Verdict
#
# The claim is about **where the largest change sits**, not about monotonicity
# everywhere in the matrix. The paper's Conclusions say "events with short
# duration and long RPs are expected to change the most"; the AIDA says such
# events "intensify proportionally more than events of long duration and short
# return period". So the verdict rests on the two things actually asserted:
# the corner comparison, and whether the matrix maximum is at that corner.
#
# The Kendall taus above describe the surface *between* the corners. They are
# reported because a reversal there is worth knowing — but requiring full
# monotonicity would score the paper against a stronger statement than it made,
# and would turn a confirmation into a "partially supported".

# %%
verdict = result["verdict"]
peak = result["maximum"]
print(f"corner test  short/long > long/short : {result['corner_test_holds']}")
print(f"largest change in the matrix         : {peak['change_pct']:+.2f}% "
      f"at {peak['duration_h']} h / RP {int(peak['rp_y'])} y")
print(f"...and that is the claimed corner    : {result['maximum_at_corner']}")
print(f"\nVERDICT (native grid): {verdict.upper()}")
print("\nStructure between the corners (reported, not decisive):")
print(f"  change falls monotonically with duration at every RP : {result['duration_ordering_holds']}")
print(f"  change rises monotonically with RP at every duration  : {result['return_period_ordering_holds']}")
if not result["return_period_ordering_holds"]:
    offenders = [k for k, v in result["kendall_tau_vs_return_period"].items() if v["tau"] < 0]
    print(f"  reverses at: {', '.join(offenders)} — rarer events change LESS there")

# %% [markdown]
# ### Does the ellipsoid correction change the answer?
#
# If the two grids disagree, that is itself a result and belongs in the
# Replication Study's deviations rather than being quietly resolved in favour of
# whichever is more convenient.

# %%
if len(per_grid) > 1:
    print(f"{'grid':<12} {'verdict':<20} {'1h/RP20':>9} {'24h/RP2':>9}")
    for name, res in per_grid.items():
        print(
            f"{name:<12} {res['verdict']:<20} "
            f"{res['pct'][0, -1]:>+8.2f}% {res['pct'][-1, 0]:>+8.2f}%"
        )
    agree = len({res["verdict"] for res in per_grid.values()}) == 1
    print(f"\ngrids agree on the verdict: {agree}")
    biggest = np.nanmax(np.abs(per_grid["native"]["pct"] - per_grid["ellipsoid"]["pct"]))
    print(f"largest disagreement in any matrix cell: {biggest:.2f} percentage points")
else:
    agree = None
    print("only one grid available — no comparison")

# %% [markdown]
# ## Magnitude, for comparison with the paper
#
# The paper reports 6–8.5 % per degree of global warming. That number is a
# property of one ensemble over one domain and cannot be *tested* elsewhere,
# only re-measured — which is exactly why it is not the claim. It is recorded
# here as supporting evidence for the Outcome.

# %%
delta_t = ds.attrs.get("delta_t_k")
if delta_t:
    per_degree = pct / float(delta_t)
    per_degree_df = pd.DataFrame(
        per_degree, index=pd.Index(durations, name="duration_h"),
        columns=[f"RP{int(r)}y" for r in rps],
    )
    print(f"Warming between windows: {float(delta_t):.3f} K")
    print("Change per degree of global warming (% / K):")
    print(per_degree_df.to_string(float_format=lambda v: f"{v:+.2f}"))
else:
    per_degree = None
    print("No warming level available — magnitude per degree not computed.")

# %% [markdown]
# ## Write the results

# %%
long_rows = []
for i, duration in enumerate(durations):
    for j, rp in enumerate(rps):
        long_rows.append(
            {
                "duration_h": duration,
                "return_period_y": float(rp),
                "return_level_hist_mm": float(
                    np.nanmedian(return_levels[(hist_window, duration)][j])
                ),
                "return_level_future_mm": float(
                    np.nanmedian(return_levels[(future_window, duration)][j])
                ),
                "change_pct": float(pct[i, j]),
                "change_pct_ci_lo": float(pct_lo[i, j]),
                "change_pct_ci_hi": float(pct_hi[i, j]),
                "change_pct_per_k": float(per_degree[i, j]) if per_degree is not None else None,
            }
        )
summary = pd.DataFrame(long_rows)
summary.to_csv(RESULTS_DIR / "summary.csv", index=False)
fits_df.to_csv(RESULTS_DIR / "gev_fits.csv", index=False)

rl_ds = xr.Dataset(
    {
        "return_level": (
            ("window", "duration", "return_period", "cell"),
            np.stack([
                np.stack([return_levels[(w, d)] for d in durations])
                for w in windows
            ]).astype("float32"),
        )
    },
    coords={
        "window": windows,
        "duration": durations,
        "return_period": rps,
        "cell": ds["cell"].values,
        "latitude": ds["latitude"],
        "longitude": ds["longitude"],
    },
    attrs={
        "provenance": PROVENANCE,
        "units": "mm",
        "created_by": "notebooks/03_analysis.py",
        **climatedt.attribution_attrs(),
    },
)
rl_ds.to_netcdf(RESULTS_DIR / "return_levels.nc")

claim_test = {
    "data_provenance": PROVENANCE,
    "attribution": climatedt.DESTINE_ATTRIBUTION,
    "licence_note": climatedt.DESTINE_LICENCE_NOTE,
    "claim": (
        "Under global warming, extreme precipitation events of short duration and long "
        "return period intensify proportionally more than events of long duration and "
        "short return period."
    ),
    "grid": "native",
    "grids_analysed": list(per_grid),
    "verdict": verdict,
    "duration_ordering_holds": result["duration_ordering_holds"],
    "return_period_ordering_holds": result["return_period_ordering_holds"],
    "corner_test_holds": result["corner_test_holds"],
    "maximum_at_corner": result["maximum_at_corner"],
    "maximum": result["maximum"],
    "kendall_tau_vs_duration": result["kendall_tau_vs_duration"],
    "kendall_tau_vs_return_period": result["kendall_tau_vs_return_period"],
    "corner_test": corner,
    # The same test on the WGS84-ellipsoid grid, so the coordinate correction's
    # effect on the conclusion is on the record next to the conclusion itself.
    "by_grid": {
        name: {
            "verdict": res["verdict"],
            "duration_ordering_holds": res["duration_ordering_holds"],
            "return_period_ordering_holds": res["return_period_ordering_holds"],
            "corner_test_holds": res["corner_test_holds"],
            "maximum_at_corner": res["maximum_at_corner"],
            "change_matrix_pct": res["pct"].tolist(),
        }
        for name, res in per_grid.items()
    },
    "grids_agree_on_verdict": agree,
    "windows": WINDOW_LABELS,
    "durations_h": durations,
    "return_periods_y": [float(r) for r in rps],
    "n_cells": int(ds.sizes["cell"]),
    "n_years_per_window": int(ds.sizes["block"]),
    "warming_k": float(delta_t) if delta_t else None,
    "bootstrap": {"n": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED, "unit": "cells"},
    "ellipsoid_mask_sensitivity": json.loads(
        ds.attrs.get("ellipsoid_mask_sensitivity", "{}")
    ),
}
with open(RESULTS_DIR / "claim_test.json", "w") as f:
    json.dump(claim_test, f, indent=2)

# One summary.csv per grid, so a reader can redo the comparison without rerunning.
for name, res in per_grid.items():
    if name == "native":
        continue
    other = pd.DataFrame(
        res["pct"], index=pd.Index(durations, name="duration_h"),
        columns=[f"RP{int(r)}y" for r in rps],
    )
    other.to_csv(RESULTS_DIR / f"change_matrix_{name}.csv")
    print(f"wrote {RESULTS_DIR / f'change_matrix_{name}.csv'}")

print(f"wrote {RESULTS_DIR / 'summary.csv'}")
print(f"wrote {RESULTS_DIR / 'gev_fits.csv'}")
print(f"wrote {RESULTS_DIR / 'return_levels.nc'}")
print(f"wrote {RESULTS_DIR / 'claim_test.json'}")
