"""Tests for scripts/analysis.py — the claim test itself.

The verdict logic is the part of this pipeline that turns numbers into a
published statement, so it is tested against constructed matrices where the
right answer is known by construction, not against its own output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import analysis  # noqa: E402
import extremes  # noqa: E402

DURATIONS = [1, 3, 6, 12, 24]
RPS = np.array([2.0, 5.0, 10.0, 20.0])


def _matrix(rows):
    return np.asarray(rows, dtype=float)


def test_verdict_supported_when_the_maximum_sits_at_the_claimed_corner():
    # The claim is about where the largest change is, not about monotonicity.
    pct = _matrix([[9, 10, 11, 12], [7, 8, 9, 10], [5, 6, 7, 8], [3, 4, 5, 6], [1, 2, 3, 4]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "supported"
    assert out["corner_test_holds"] and out["maximum_at_corner"]
    assert out["maximum"] == {"duration_h": 1, "rp_y": 20.0, "change_pct": 12.0}


def test_a_reversal_between_the_corners_does_not_deny_the_claim():
    # THE regression test for a real mistake. This matrix is the shape the
    # Climate DT actually produced: the maximum is at 1 h / RP20 and the corner
    # comparison holds, but the 24 h row DECREASES with return period. An
    # earlier version required full monotonicity everywhere and returned
    # "partially supported", scoring the paper against a stronger statement
    # than it made.
    pct = _matrix([
        [9.22, 12.75, 14.89, 16.88],
        [8.47, 11.22, 12.88, 14.41],
        [6.72,  8.77,  9.92, 10.93],
        [4.73,  4.96,  5.03,  5.06],
        [2.39,  1.80,  1.20,  0.53],   # reverses
    ])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "supported"
    assert out["maximum_at_corner"]
    # ...and the reversal is still reported, just not decisive.
    assert not out["return_period_ordering_holds"]
    assert out["kendall_tau_vs_return_period"]["24h"]["tau"] < 0


def test_verdict_contradicted_when_the_change_is_largest_at_the_opposite_corner():
    # Long duration / short RP changes most: the claim reversed.
    pct = _matrix([[4, 3, 2, 1], [6, 5, 4, 3], [8, 7, 6, 5], [10, 9, 8, 7], [12, 11, 10, 9]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "contradicted"
    assert not out["corner_test_holds"] and not out["maximum_at_corner"]


def test_verdict_partial_when_the_corner_holds_but_the_peak_is_elsewhere():
    # Short/long beats long/short, but the biggest change is at 3 h, not 1 h.
    pct = _matrix([[9, 10, 11, 12], [9, 11, 13, 15], [5, 6, 7, 8], [3, 4, 5, 6], [1, 2, 3, 4]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "partially supported"
    assert out["corner_test_holds"] and not out["maximum_at_corner"]
    assert out["maximum"]["duration_h"] == 3


def test_a_flat_matrix_is_not_supported():
    # Nothing changes anywhere, so nothing "changes the most".
    out = analysis.ordering_tests(np.zeros((5, 4)), DURATIONS, RPS)
    assert out["verdict"] != "supported"
    assert not out["corner_test_holds"]


def test_corner_test_reads_the_claim_literally():
    pct = _matrix([[0, 0, 0, 20], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [5, 0, 0, 0]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    corner = out["corner_test"]
    assert corner["short_duration_long_rp"] == {"duration_h": 1, "rp_y": 20.0, "change_pct": 20.0}
    assert corner["long_duration_short_rp"] == {"duration_h": 24, "rp_y": 2.0, "change_pct": 5.0}
    assert corner["difference_pct_points"] == pytest.approx(15.0)


def test_monotonicity_flags_still_use_all_not_any():
    # These no longer set the verdict, but they are reported, so they must stay
    # honest: one favourable column among unfavourable ones is not "holds".
    pct = _matrix([[9, 1, 1, 1], [7, 2, 2, 2], [5, 3, 3, 3], [3, 4, 4, 4], [1, 5, 5, 5]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert not out["duration_ordering_holds"]


# --- end to end on a dataset with a known planted ordering -----------------

def _dataset_with_planted_ordering(seed=3):
    """Annual maxima whose scenario window intensifies more at short durations."""
    rng = np.random.default_rng(seed)
    n_years, n_cells = 20, 300
    scale = rng.uniform(5, 40, n_cells)
    boost = {1: 1.12, 3: 1.09, 6: 1.07, 12: 1.05, 24: 1.02}
    data = np.empty((2, len(DURATIONS), n_years, n_cells))
    for wi, window in enumerate(["hist", "ssp370"]):
        for di, duration in enumerate(DURATIONS):
            base = rng.gamma(6.0, 1.0, size=(n_years, n_cells)) * scale * (duration ** 0.4)
            data[wi, di] = base * (boost[duration] if window == "ssp370" else 1.0)
    return xr.Dataset(
        {"annual_max": (("window", "duration", "block", "cell"), data)},
        coords={
            "window": ["hist", "ssp370"],
            "duration": DURATIONS,
            "block": np.arange(n_years),
            "cell": np.arange(n_cells),
        },
    )


def test_analyse_recovers_a_planted_duration_ordering():
    ds = _dataset_with_planted_ordering()
    out = analysis.analyse(ds, ["hist", "ssp370"], DURATIONS, RPS, bootstrap=False)
    assert out["duration_ordering_holds"], out["kendall_tau_vs_duration"]
    assert out["pct"][0].mean() > out["pct"][-1].mean()
    assert out["corner_test_holds"]


def test_analyse_returns_a_matrix_of_the_right_shape():
    ds = _dataset_with_planted_ordering()
    out = analysis.analyse(ds, ["hist", "ssp370"], DURATIONS, RPS, bootstrap=False)
    assert out["pct"].shape == (len(DURATIONS), len(RPS))
    assert set(out["fits"]) == {(w, d) for w in ("hist", "ssp370") for d in DURATIONS}
