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


def test_verdict_supported_when_both_orderings_hold():
    # Falls with duration, rises with return period.
    pct = _matrix([[9, 10, 11, 12], [7, 8, 9, 10], [5, 6, 7, 8], [3, 4, 5, 6], [1, 2, 3, 4]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "supported"
    assert out["duration_ordering_holds"] and out["return_period_ordering_holds"]
    assert out["corner_test_holds"]


def test_verdict_contradicted_when_both_orderings_reverse():
    pct = _matrix([[1, 2, 3, 4], [3, 4, 5, 6], [5, 6, 7, 8], [7, 8, 9, 10], [9, 10, 11, 12]])
    pct = pct[:, ::-1]  # also falls with return period
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "contradicted"
    assert not out["duration_ordering_holds"] and not out["return_period_ordering_holds"]


def test_verdict_partial_when_only_the_duration_ordering_holds():
    # Falls with duration (holds), but also falls with return period (fails).
    pct = _matrix([[12, 11, 10, 9], [10, 9, 8, 7], [8, 7, 6, 5], [6, 5, 4, 3], [4, 3, 2, 1]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "partially supported"
    assert out["duration_ordering_holds"]
    assert not out["return_period_ordering_holds"]


def test_verdict_partial_when_only_the_return_period_ordering_holds():
    pct = _matrix([[1, 2, 3, 4], [3, 4, 5, 6], [5, 6, 7, 8], [7, 8, 9, 10], [9, 10, 11, 12]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert out["verdict"] == "partially supported"
    assert not out["duration_ordering_holds"]
    assert out["return_period_ordering_holds"]


def test_a_flat_matrix_is_not_supported():
    # No ordering either way must never read as support for the claim.
    out = analysis.ordering_tests(np.zeros((5, 4)), DURATIONS, RPS)
    assert out["verdict"] != "supported"


def test_corner_test_reads_the_claim_literally():
    pct = _matrix([[0, 0, 0, 20], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [5, 0, 0, 0]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    corner = out["corner_test"]
    assert corner["short_duration_long_rp"] == {"duration_h": 1, "rp_y": 20.0, "change_pct": 20.0}
    assert corner["long_duration_short_rp"] == {"duration_h": 24, "rp_y": 2.0, "change_pct": 5.0}
    assert corner["difference_pct_points"] == pytest.approx(15.0)


def test_verdict_is_not_fooled_by_a_single_column():
    # One return period ordering correctly while the others reverse must not
    # produce "supported" -- `all`, not `any`.
    pct = _matrix([[9, 1, 1, 1], [7, 2, 2, 2], [5, 3, 3, 3], [3, 4, 4, 4], [1, 5, 5, 5]])
    out = analysis.ordering_tests(pct, DURATIONS, RPS)
    assert not out["duration_ordering_holds"]
    assert out["verdict"] != "supported"


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


def test_analyse_returns_a_matrix_of_the_right_shape():
    ds = _dataset_with_planted_ordering()
    out = analysis.analyse(ds, ["hist", "ssp370"], DURATIONS, RPS, bootstrap=False)
    assert out["pct"].shape == (len(DURATIONS), len(RPS))
    assert set(out["fits"]) == {(w, d) for w in ("hist", "ssp370") for d in DURATIONS}
