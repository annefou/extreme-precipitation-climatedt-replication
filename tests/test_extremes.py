"""Tests for scripts/extremes.py.

The GEV fit is checked against scipy's independent implementation (recovery of
known parameters from large samples, and agreement of the quantile function
with `scipy.stats.genextreme.ppf`), not against numbers this module produced
itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import extremes  # noqa: E402


# --- rolling accumulation -------------------------------------------------

def test_rolling_sum_window_one_is_identity():
    v = np.array([[1.0], [2.0], [3.0]])
    assert np.allclose(extremes.rolling_sum(v, 1), v)


def test_rolling_sum_is_backward_looking_and_leading_nan():
    v = np.arange(6, dtype=float).reshape(6, 1)
    got = extremes.rolling_sum(v, 3)
    assert np.isnan(got[0, 0]) and np.isnan(got[1, 0])
    assert got[2, 0] == 0 + 1 + 2
    assert got[5, 0] == 3 + 4 + 5


def test_rolling_sum_does_not_treat_nan_as_zero():
    v = np.array([[1.0], [np.nan], [3.0], [4.0]])
    got = extremes.rolling_sum(v, 2)
    assert np.isnan(got[1, 0])  # window contains the NaN
    assert np.isnan(got[2, 0])  # still contains it
    assert got[3, 0] == 7.0     # clear of it


def test_annual_maxima_blocks_by_calendar_year():
    hours = 24
    v = np.zeros((2 * hours, 1))
    v[5, 0] = 10.0     # year 1
    v[hours + 5, 0] = 4.0  # year 2
    years = np.repeat([2001, 2002], hours)
    uniq, am = extremes.annual_maxima(v, years, window=1)
    assert list(uniq) == [2001, 2002]
    assert am[0, 0] == 10.0 and am[1, 0] == 4.0


def test_annual_maxima_of_longer_duration_is_at_least_the_shorter_one():
    rng = np.random.default_rng(0)
    v = rng.gamma(0.5, 1.0, size=(8760, 4))
    years = np.zeros(8760, dtype=int)
    _, am1 = extremes.annual_maxima(v, years, 1)
    _, am6 = extremes.annual_maxima(v, years, 6)
    assert np.all(am6 >= am1 - 1e-9)


# --- L-moments and the GEV ------------------------------------------------

def test_sample_lmoments_of_uniform_sample():
    # For a large U(0,1) sample: l1 -> 0.5, l2 -> 1/6, l3 -> 0.
    x = (np.arange(20000) + 0.5) / 20000
    l1, l2, l3 = extremes.sample_lmoments(x)
    assert l1 == pytest.approx(0.5, abs=1e-3)
    assert l2 == pytest.approx(1 / 6, abs=1e-3)
    assert l3 == pytest.approx(0.0, abs=1e-3)


def test_sample_lmoments_needs_three_values():
    with pytest.raises(ValueError):
        extremes.sample_lmoments(np.array([1.0, 2.0]))


@pytest.mark.parametrize("k", [-0.2, -0.05, 0.0, 0.15, 0.3])
def test_gev_quantile_matches_scipy_genextreme(k):
    xi, alpha = 12.0, 3.0
    f = np.array([0.5, 0.8, 0.9, 0.95, 0.99])
    ours = extremes.gev_quantile(f, xi, alpha, k)
    theirs = stats.genextreme.ppf(f, c=k, loc=xi, scale=alpha)
    assert np.allclose(ours, theirs, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("k", [-0.15, 0.0, 0.2])
def test_gev_fit_recovers_known_parameters(k):
    xi, alpha = 20.0, 5.0
    sample = stats.genextreme.rvs(
        c=k, loc=xi, scale=alpha, size=40000, random_state=np.random.default_rng(7)
    )
    xi_hat, alpha_hat, k_hat = extremes.gev_fit_lmoments(sample)
    assert k_hat == pytest.approx(k, abs=0.02)
    assert alpha_hat == pytest.approx(alpha, rel=0.03)
    assert xi_hat == pytest.approx(xi, rel=0.03)


def test_return_level_uses_the_annual_maxima_convention():
    xi, alpha, k = 10.0, 2.0, -0.1
    # RP = 1 / (1 - F), so RP 20 is the 0.95 quantile.
    assert extremes.return_level(20.0, xi, alpha, k) == pytest.approx(
        extremes.gev_quantile(0.95, xi, alpha, k)
    )


def test_return_level_increases_with_return_period():
    xi, alpha, k = 10.0, 2.0, -0.1
    rl = extremes.return_level(np.array([2.0, 5.0, 10.0, 20.0]), xi, alpha, k)
    assert np.all(np.diff(rl) > 0)


def test_gev_fit_rejects_a_constant_sample():
    with pytest.raises(ValueError):
        extremes.gev_fit_lmoments(np.full(20, 3.0))


# --- index-flood pooling --------------------------------------------------

def _synthetic_am(n_years: int, n_cells: int, k: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Annual maxima whose cells share one growth curve but differ in magnitude."""
    rng = np.random.default_rng(seed)
    scale_per_cell = rng.uniform(5.0, 50.0, n_cells)
    std = stats.genextreme.rvs(
        c=k, loc=1.0, scale=0.2, size=(n_years, n_cells), random_state=rng
    )
    return std * scale_per_cell, scale_per_cell


def test_pooled_growth_curve_separates_magnitude_from_shape():
    am, scale_per_cell = _synthetic_am(60, 400, k=-0.1, seed=3)
    (xi, alpha, k), index_flood = extremes.pooled_growth_curve(am)
    # The index flood must track each cell's own magnitude...
    assert np.corrcoef(index_flood, scale_per_cell)[0, 1] > 0.99
    # ...and the pooled growth curve must recover the shared shape.
    assert k == pytest.approx(-0.1, abs=0.03)


def test_pooled_growth_curve_is_invariant_to_rescaling_a_cell():
    am, _ = _synthetic_am(40, 200, k=-0.05, seed=11)
    (_, _, k_a), _ = extremes.pooled_growth_curve(am)
    am_b = am.copy()
    am_b[:, 7] *= 1000.0  # one cell in different units entirely
    (_, _, k_b), _ = extremes.pooled_growth_curve(am_b)
    assert k_b == pytest.approx(k_a, abs=1e-6)


def test_pooled_growth_curve_skips_cells_with_too_few_years():
    am, _ = _synthetic_am(30, 50, k=-0.1, seed=5)
    am[:, 3] = np.nan
    am[2:, 4] = np.nan  # 2 finite years, below MIN_AM_YEARS
    (_, _, _), index_flood = extremes.pooled_growth_curve(am)
    assert np.isnan(index_flood[3]) and np.isnan(index_flood[4])
    assert np.isfinite(index_flood[0])


def test_pooled_growth_curve_raises_when_nothing_is_usable():
    with pytest.raises(ValueError):
        extremes.pooled_growth_curve(np.full((10, 5), np.nan))


def test_regional_return_levels_shape_and_ordering():
    am, _ = _synthetic_am(40, 120, k=-0.1, seed=2)
    rps = np.array([2.0, 5.0, 10.0, 20.0])
    rl = extremes.regional_return_levels(am, rps)
    assert rl.shape == (4, 120)
    assert np.all(np.diff(rl, axis=0) > 0)


def test_bootstrap_growth_brackets_the_point_estimate():
    am, _ = _synthetic_am(40, 300, k=-0.1, seed=13)
    rps = np.array([2.0, 20.0])
    (xi, alpha, k), _ = extremes.pooled_growth_curve(am)
    point = extremes.return_level(rps, xi, alpha, k)
    boot = extremes.bootstrap_pooled_growth(am, rps, n_boot=200, seed=1)
    lo, hi = np.nanpercentile(boot, [2.5, 97.5], axis=0)
    assert np.all(lo < point) and np.all(point < hi)
