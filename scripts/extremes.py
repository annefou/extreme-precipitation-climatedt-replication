"""Extreme-value statistics for the duration x return-period matrix.

Kept out of the notebooks so it can be unit-tested (tests/test_extremes.py)
rather than only eyeballed in a rendered cell. The notebooks import it and do
the I/O; every number in results/ comes from a function here.

The estimator is Hosking & Wallis L-moments for the GEV, with a regional
index-flood pooling step. That combination is what makes return periods longer
than the record length defensible: the original paper states that "estimates
for long RP are only possible for pooled spatial information", and pooling the
standardised at-site series is the standard way to do it.

GEV parameterisation follows Hosking (1990), as used by `lmoments`/`lmom` and
the FEH/regional-frequency-analysis literature:

    x(F) = xi + (alpha / k) * (1 - (-ln F) ** k)      for k != 0
    x(F) = xi - alpha * ln(-ln F)                     for k == 0

so k > 0 is a bounded (Weibull) upper tail and k < 0 a heavy (Frechet) tail.
Note the sign convention is the NEGATIVE of scipy's `genextreme` shape `c`
only in name -- in fact scipy uses the same convention, `c = k`, which the
tests assert directly rather than trusting this comment.
"""

from __future__ import annotations

import warnings

import numpy as np
from scipy.special import gamma

# Below this many finite annual maxima an at-site series is dropped rather than
# fitted. Three points is the bare minimum for the third L-moment to exist at
# all; the pooled fit is what carries the estimate, so this is a floor, not a
# recommendation.
MIN_AM_YEARS = 3


def rolling_sum(values: np.ndarray, window: int) -> np.ndarray:
    """Backward-looking rolling sum along axis 0, NaN until the window is full.

    `values` is (time, cell) hourly accumulation; the result at t is the total
    over hours (t-window, t].
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if window == 1:
        return values.astype(np.float64, copy=True)
    cs = np.cumsum(np.nan_to_num(values, nan=0.0), axis=0, dtype=np.float64)
    out = np.full(values.shape, np.nan, dtype=np.float64)
    out[window - 1:] = cs[window - 1:] - np.concatenate(
        [np.zeros((1,) + values.shape[1:]), cs[:-window]], axis=0
    )
    # Any window containing a NaN input must stay NaN rather than silently
    # summing it as zero.
    bad = rolling_any_nan(values, window)
    out[bad] = np.nan
    return out


def rolling_any_nan(values: np.ndarray, window: int) -> np.ndarray:
    """Boolean mask, True where the backward window of length `window` holds a NaN."""
    isnan = np.isnan(values).astype(np.float64)
    cs = np.cumsum(isnan, axis=0)
    out = np.ones(values.shape, dtype=bool)
    counts = cs[window - 1:] - np.concatenate(
        [np.zeros((1,) + values.shape[1:]), cs[:-window]], axis=0
    )
    out[window - 1:] = counts > 0
    return out


def annual_maxima(values: np.ndarray, years: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Block maxima of the `window`-hour accumulation, one block per calendar year.

    Returns (unique_years, maxima) with maxima shaped (n_years, n_cells).
    """
    acc = rolling_sum(values, window)
    uniq = np.unique(years)
    out = np.full((len(uniq), values.shape[1]), np.nan)
    for i, y in enumerate(uniq):
        block = acc[years == y]
        if block.size and not np.all(np.isnan(block)):
            # A single all-NaN cell within an otherwise fine year is expected
            # and stays NaN; the warning about it is noise.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out[i] = np.nanmax(block, axis=0)
    return uniq, out


# --- L-moments ------------------------------------------------------------

def sample_lmoments(x: np.ndarray) -> tuple[float, float, float]:
    """First three sample L-moments (l1, l2, l3) via probability-weighted moments."""
    x = np.sort(np.asarray(x, dtype=np.float64))
    n = x.size
    if n < 3:
        raise ValueError(f"need at least 3 values, got {n}")
    j = np.arange(1, n + 1, dtype=np.float64)
    b0 = x.mean()
    b1 = np.sum((j - 1) / (n - 1) * x) / n
    b2 = np.sum((j - 1) * (j - 2) / ((n - 1) * (n - 2)) * x) / n
    return b0, 2 * b1 - b0, 6 * b2 - 6 * b1 + b0


def gev_fit_lmoments(x: np.ndarray) -> tuple[float, float, float]:
    """Fit a GEV by L-moments. Returns (xi, alpha, k) -- location, scale, shape.

    Hosking's rational approximation for k; exact to about 9e-4 over
    -0.5 < k < 0.5, which covers everything precipitation annual maxima do.
    """
    l1, l2, l3 = sample_lmoments(x)
    if l2 <= 0:
        raise ValueError("degenerate sample: L-scale is not positive")
    t3 = l3 / l2
    c = 2.0 / (3.0 + t3) - np.log(2.0) / np.log(3.0)
    k = 7.8590 * c + 2.9554 * c * c
    if abs(k) < 1e-8:  # Gumbel limit
        alpha = l2 / np.log(2.0)
        return l1 - alpha * np.euler_gamma, alpha, 0.0
    g = gamma(1.0 + k)
    alpha = l2 * k / ((1.0 - 2.0 ** -k) * g)
    xi = l1 - alpha * (1.0 - g) / k
    return xi, alpha, k


def gev_quantile(f: np.ndarray | float, xi: float, alpha: float, k: float) -> np.ndarray:
    """GEV quantile x(F) in Hosking's parameterisation."""
    f = np.asarray(f, dtype=np.float64)
    y = -np.log(f)
    if abs(k) < 1e-8:
        return xi - alpha * np.log(y)
    return xi + alpha / k * (1.0 - y ** k)


def return_level(rp: np.ndarray | float, xi: float, alpha: float, k: float) -> np.ndarray:
    """Return level for a return period in years (annual-maxima convention)."""
    rp = np.asarray(rp, dtype=np.float64)
    return gev_quantile(1.0 - 1.0 / rp, xi, alpha, k)


# --- regional index-flood -------------------------------------------------

def pooled_growth_curve(am: np.ndarray) -> tuple[tuple[float, float, float], np.ndarray]:
    """Index-flood pooling over cells.

    `am` is (n_years, n_cells) of annual maxima. Each cell's series is divided
    by its own at-site mean (the index flood), the standardised series are
    pooled into one sample, and a single GEV is fitted to the pool. The growth
    curve is therefore dimensionless and shared; the cell-to-cell magnitude
    lives entirely in the index flood.

    Returns ((xi, alpha, k), index_flood) with index_flood shaped (n_cells,).
    """
    am = np.asarray(am, dtype=np.float64)
    n_finite = np.sum(np.isfinite(am), axis=0)
    # An all-NaN cell is expected (a cell outside the domain, or one the
    # retrieval never filled), and `usable` drops it two lines below; the
    # "Mean of empty slice" warning it raises is noise, not a signal.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        index_flood = np.nanmean(am, axis=0)
    usable = (n_finite >= MIN_AM_YEARS) & np.isfinite(index_flood) & (index_flood > 0)
    if not usable.any():
        raise ValueError("no cell has a usable annual-maxima series")
    scaled = am[:, usable] / index_flood[usable]
    pool = scaled[np.isfinite(scaled)]
    index_flood = np.where(usable, index_flood, np.nan)
    return gev_fit_lmoments(pool), index_flood


def regional_return_levels(am: np.ndarray, rps: np.ndarray) -> np.ndarray:
    """Per-cell return levels from the pooled growth curve. Shape (n_rps, n_cells)."""
    (xi, alpha, k), index_flood = pooled_growth_curve(am)
    growth = return_level(np.asarray(rps, dtype=np.float64), xi, alpha, k)
    return growth[:, None] * index_flood[None, :]


def bootstrap_pooled_growth(
    am: np.ndarray, rps: np.ndarray, n_boot: int, seed: int
) -> np.ndarray:
    """Growth factors from `n_boot` cell-resampled pools. Shape (n_boot, n_rps).

    Cells are resampled with replacement (years are not): the pooled sample's
    effective independence is limited by spatial correlation between cells, so
    resampling cells is the conservative choice.
    """
    rng = np.random.default_rng(seed)
    am = np.asarray(am, dtype=np.float64)
    n_cells = am.shape[1]
    out = np.full((n_boot, len(rps)), np.nan)
    for b in range(n_boot):
        idx = rng.integers(0, n_cells, n_cells)
        try:
            (xi, alpha, k), _ = pooled_growth_curve(am[:, idx])
        except ValueError:
            continue
        out[b] = return_level(np.asarray(rps, dtype=np.float64), xi, alpha, k)
    return out
