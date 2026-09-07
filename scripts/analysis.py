"""The claim test: pooled GEV return levels, and the ordering the paper predicts.

Kept out of the notebook so it can be unit tested and so it can be run over more
than one grid without copying it. `03_analysis.py` calls `analyse()` once per
grid (the delivered spherical HEALPix, and the WGS84-ellipsoidal conversion) and
prints the comparison, so the effect of the coordinate correction on the
conclusion is a reported number rather than an assumption.

The claim under test, from the paper's Conclusions:

    "Events with short duration and long RPs are expected to change the most."

stated as an AIDA sentence in `nanopubs/drafts/02_aida.md`. It is about the
**ordering** of changes, which is what makes it transferable to another region
or model -- and which means testing it needs no warming level at all. The
warming level is used only to express the magnitude as "% per degree" for
comparison with the paper's reported 6-8.5 %/K.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extremes  # noqa: E402

N_BOOTSTRAP = 400
BOOTSTRAP_SEED = 20260906


def fit_grid(ds, windows, durations, rps):
    """Pooled index-flood GEV per (window, duration). Returns fits and levels."""
    fits, return_levels, index_floods = {}, {}, {}
    for window in windows:
        for duration in durations:
            am = ds["annual_max"].sel(window=window, duration=duration).values
            (xi, alpha, k), index_flood = extremes.pooled_growth_curve(am)
            growth = extremes.return_level(rps, xi, alpha, k)
            fits[(window, duration)] = (xi, alpha, k)
            index_floods[(window, duration)] = index_flood
            return_levels[(window, duration)] = growth[:, None] * index_flood[None, :]
    return fits, return_levels, index_floods


def change_matrix(ds, return_levels, index_floods, windows, durations, rps, bootstrap=True):
    """Percentage change in return level per (duration, return period), with CIs.

    The change is the **median over cells of the per-cell ratio**, not the ratio
    of medians: pairing by cell keeps each cell's own climatology out of it.
    """
    hist, future = windows[0], windows[1]
    shape = (len(durations), len(rps))
    pct = np.full(shape, np.nan)
    lo = np.full(shape, np.nan)
    hi = np.full(shape, np.nan)

    for i, duration in enumerate(durations):
        ratio = return_levels[(future, duration)] / return_levels[(hist, duration)]
        pct[i] = 100.0 * (np.nanmedian(ratio, axis=1) - 1.0)
        if not bootstrap:
            continue
        # Cells are the resampling unit, not years: the pooled sample's
        # effective independence is limited by spatial correlation.
        boot_h = extremes.bootstrap_pooled_growth(
            ds["annual_max"].sel(window=hist, duration=duration).values,
            rps, N_BOOTSTRAP, BOOTSTRAP_SEED + duration,
        )
        boot_f = extremes.bootstrap_pooled_growth(
            ds["annual_max"].sel(window=future, duration=duration).values,
            rps, N_BOOTSTRAP, BOOTSTRAP_SEED + 1000 + duration,
        )
        med_h = np.nanmedian(index_floods[(hist, duration)])
        med_f = np.nanmedian(index_floods[(future, duration)])
        boot_pct = 100.0 * ((boot_f * med_f) / (boot_h * med_h) - 1.0)
        lo[i], hi[i] = np.nanpercentile(boot_pct, [2.5, 97.5], axis=0)
    return pct, lo, hi


def ordering_tests(pct, durations, rps) -> dict:
    """Three readings of the same claim, reported together because they can disagree.

    1. Change against DURATION at each return period -- the claim predicts a
       NEGATIVE Kendall tau (shorter durations change more).
    2. Change against RETURN PERIOD at each duration -- predicts POSITIVE.
    3. The corner test, the claim taken literally: shortest duration at the
       longest return period against longest duration at the shortest.
    """
    by_duration = {
        f"RP{int(r)}y": stats.kendalltau(list(durations), pct[:, j])
        for j, r in enumerate(rps)
    }
    by_rp = {
        f"{d}h": stats.kendalltau(list(rps), pct[i, :])
        for i, d in enumerate(durations)
    }
    corner = {
        "short_duration_long_rp": {
            "duration_h": int(durations[0]),
            "rp_y": float(rps[-1]),
            "change_pct": float(pct[0, -1]),
        },
        "long_duration_short_rp": {
            "duration_h": int(durations[-1]),
            "rp_y": float(rps[0]),
            "change_pct": float(pct[-1, 0]),
        },
    }
    corner["difference_pct_points"] = (
        corner["short_duration_long_rp"]["change_pct"]
        - corner["long_duration_short_rp"]["change_pct"]
    )

    duration_holds = bool(np.all([r.statistic < 0 for r in by_duration.values()]))
    rp_holds = bool(np.all([r.statistic > 0 for r in by_rp.values()]))
    if duration_holds and rp_holds:
        verdict = "supported"
    elif duration_holds or rp_holds:
        verdict = "partially supported"
    else:
        verdict = "contradicted"

    return {
        "verdict": verdict,
        "duration_ordering_holds": duration_holds,
        "return_period_ordering_holds": rp_holds,
        "corner_test_holds": bool(corner["difference_pct_points"] > 0),
        "kendall_tau_vs_duration": {
            k: {"tau": float(v.statistic), "p": float(v.pvalue)} for k, v in by_duration.items()
        },
        "kendall_tau_vs_return_period": {
            k: {"tau": float(v.statistic), "p": float(v.pvalue)} for k, v in by_rp.items()
        },
        "corner_test": corner,
    }


def analyse(ds, windows, durations, rps, bootstrap=True) -> dict:
    """Everything for one grid: fits, change matrix, ordering verdict."""
    fits, return_levels, index_floods = fit_grid(ds, windows, durations, rps)
    pct, lo, hi = change_matrix(
        ds, return_levels, index_floods, windows, durations, rps, bootstrap
    )
    out = ordering_tests(pct, durations, rps)
    out.update(
        pct=pct, pct_lo=lo, pct_hi=hi,
        fits=fits, return_levels=return_levels, index_floods=index_floods,
    )
    return out
