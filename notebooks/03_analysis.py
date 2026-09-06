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

import climatedt  # noqa: E402
import extremes  # noqa: E402

CLEAN_DIR = Path("../data/clean")
RESULTS_DIR = Path("../results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

N_BOOTSTRAP = 400
BOOTSTRAP_SEED = 20260906

# %%
ds = xr.open_dataset(CLEAN_DIR / "annual_maxima.nc")
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
# ## Pooled growth curves
#
# One GEV per (window, duration). The fitted shape parameter *k* is worth
# reading directly: a more negative *k* is a heavier tail, so a shape that
# becomes more negative from the historical to the scenario window is itself
# evidence of the long-return-period end changing fastest.

# %%
fits, return_levels, index_floods = {}, {}, {}
rows = []
for window in windows:
    for duration in durations:
        am = ds["annual_max"].sel(window=window, duration=duration).values
        (xi, alpha, k), index_flood = extremes.pooled_growth_curve(am)
        growth = extremes.return_level(rps, xi, alpha, k)
        fits[(window, duration)] = (xi, alpha, k)
        index_floods[(window, duration)] = index_flood
        return_levels[(window, duration)] = growth[:, None] * index_flood[None, :]
        rows.append(
            {
                "window": window,
                "duration_h": duration,
                "gev_location": xi,
                "gev_scale": alpha,
                "gev_shape_k": k,
                "n_cells_used": int(np.sum(np.isfinite(index_flood))),
                "median_index_flood_mm": float(np.nanmedian(index_flood)),
                **{f"growth_rp{int(r)}": float(g) for r, g in zip(rps, growth)},
            }
        )

fits_df = pd.DataFrame(rows)
print(fits_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

# %% [markdown]
# ## The change matrix
#
# For every (duration, return period) cell of the matrix, the fractional change
# in return level between the two windows. Taken as the **median over cells of
# the per-cell ratio**, not the ratio of medians: the per-cell pairing keeps
# each cell's own climatology out of the comparison.

# %%
hist_window, future_window = windows[0], windows[1]
pct = np.full((len(durations), len(rps)), np.nan)
pct_lo = np.full_like(pct, np.nan)
pct_hi = np.full_like(pct, np.nan)

for i, duration in enumerate(durations):
    rl_h = return_levels[(hist_window, duration)]
    rl_f = return_levels[(future_window, duration)]
    ratio = rl_f / rl_h
    pct[i] = 100.0 * (np.nanmedian(ratio, axis=1) - 1.0)
    # Uncertainty from resampling cells: the pooled sample's effective
    # independence is limited by spatial correlation, so cells are the
    # resampling unit rather than years.
    boot_h = extremes.bootstrap_pooled_growth(
        ds["annual_max"].sel(window=hist_window, duration=duration).values,
        rps, N_BOOTSTRAP, BOOTSTRAP_SEED + duration,
    )
    boot_f = extremes.bootstrap_pooled_growth(
        ds["annual_max"].sel(window=future_window, duration=duration).values,
        rps, N_BOOTSTRAP, BOOTSTRAP_SEED + 1000 + duration,
    )
    median_if_h = np.nanmedian(index_floods[(hist_window, duration)])
    median_if_f = np.nanmedian(index_floods[(future_window, duration)])
    boot_pct = 100.0 * ((boot_f * median_if_f) / (boot_h * median_if_h) - 1.0)
    pct_lo[i], pct_hi[i] = np.nanpercentile(boot_pct, [2.5, 97.5], axis=0)

matrix = pd.DataFrame(pct, index=pd.Index(durations, name="duration_h"),
                      columns=[f"RP{int(r)}y" for r in rps])
print("Change in return level, scenario vs historical (%):")
print(matrix.to_string(float_format=lambda v: f"{v:+.2f}"))

# %% [markdown]
# ## Testing the ordering
#
# Three separate readings of the same claim, reported together because they can
# disagree and a single number would hide that:
#
# 1. **Duration effect** — Kendall's tau of the change against duration, at each
#    return period. The claim predicts a **negative** tau: shorter durations
#    change more.
# 2. **Return-period effect** — Kendall's tau of the change against return
#    period, at each duration. The claim predicts a **positive** tau.
# 3. **The corner test** — the claim's own words, taken literally: the shortest
#    duration at the longest return period against the longest duration at the
#    shortest return period.

# %%
duration_tau = {
    f"RP{int(r)}y": stats.kendalltau(durations, pct[:, j])
    for j, r in enumerate(rps)
}
rp_tau = {
    f"{d}h": stats.kendalltau(rps, pct[i, :])
    for i, d in enumerate(durations)
}

print("Kendall tau of change vs DURATION (claim predicts negative):")
for key, res in duration_tau.items():
    print(f"  {key:>7s}  tau = {res.statistic:+.3f}   p = {res.pvalue:.4f}")
print("\nKendall tau of change vs RETURN PERIOD (claim predicts positive):")
for key, res in rp_tau.items():
    print(f"  {key:>7s}  tau = {res.statistic:+.3f}   p = {res.pvalue:.4f}")

corner = {
    "short_duration_long_rp": {
        "duration_h": durations[0],
        "rp_y": float(rps[-1]),
        "change_pct": float(pct[0, -1]),
        "ci95_pct": [float(pct_lo[0, -1]), float(pct_hi[0, -1])],
    },
    "long_duration_short_rp": {
        "duration_h": durations[-1],
        "rp_y": float(rps[0]),
        "change_pct": float(pct[-1, 0]),
        "ci95_pct": [float(pct_lo[-1, 0]), float(pct_hi[-1, 0])],
    },
}
corner["difference_pct_points"] = (
    corner["short_duration_long_rp"]["change_pct"]
    - corner["long_duration_short_rp"]["change_pct"]
)
print(
    f"\nCorner test: {durations[0]} h / {int(rps[-1])} y changes by "
    f"{corner['short_duration_long_rp']['change_pct']:+.2f} %, "
    f"{durations[-1]} h / {int(rps[0])} y by "
    f"{corner['long_duration_short_rp']['change_pct']:+.2f} % — a difference of "
    f"{corner['difference_pct_points']:+.2f} percentage points."
)

# %% [markdown]
# ## Verdict
#
# The claim is supported only if **both** directions hold: the change decreases
# with duration and increases with return period. Either one alone is a weaker,
# different statement, and saying so is the point — `DOMAIN.md` § Honest
# negative results.

# %%
duration_taus = np.array([r.statistic for r in duration_tau.values()])
rp_taus = np.array([r.statistic for r in rp_tau.values()])
duration_holds = bool(np.all(duration_taus < 0))
rp_holds = bool(np.all(rp_taus > 0))
corner_holds = bool(corner["difference_pct_points"] > 0)

if duration_holds and rp_holds:
    verdict = "supported"
elif duration_holds or rp_holds:
    verdict = "partially supported"
else:
    verdict = "contradicted"

print(f"duration ordering holds at every return period : {duration_holds}")
print(f"return-period ordering holds at every duration  : {rp_holds}")
print(f"corner test holds                              : {corner_holds}")
print(f"\nVERDICT: {verdict}")

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
    attrs={"provenance": PROVENANCE, "units": "mm", "created_by": "notebooks/03_analysis.py"},
)
rl_ds.to_netcdf(RESULTS_DIR / "return_levels.nc")

claim_test = {
    "data_provenance": PROVENANCE,
    "claim": (
        "Under global warming, extreme precipitation events of short duration and long "
        "return period intensify proportionally more than events of long duration and "
        "short return period."
    ),
    "verdict": verdict,
    "duration_ordering_holds": duration_holds,
    "return_period_ordering_holds": rp_holds,
    "corner_test_holds": corner_holds,
    "kendall_tau_vs_duration": {
        k: {"tau": float(v.statistic), "p": float(v.pvalue)} for k, v in duration_tau.items()
    },
    "kendall_tau_vs_return_period": {
        k: {"tau": float(v.statistic), "p": float(v.pvalue)} for k, v in rp_tau.items()
    },
    "corner_test": corner,
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

print(f"wrote {RESULTS_DIR / 'summary.csv'}")
print(f"wrote {RESULTS_DIR / 'gev_fits.csv'}")
print(f"wrote {RESULTS_DIR / 'return_levels.nc'}")
print(f"wrote {RESULTS_DIR / 'claim_test.json'}")
