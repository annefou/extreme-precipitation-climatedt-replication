"""End-to-end check that the analysis recovers a signal it was not told about.

`scripts/synthetic_climatedt.py` generates hourly precipitation whose scenario
window intensifies more at short durations than at long ones. The analysis
chain — accumulate, take annual maxima, pool by index flood, fit a GEV, compare
return levels — never sees that generator. If it reports the ordering the
generator planted, the chain is doing what the notebooks claim it does.

This is the test that would catch a sign error, a mis-shaped array, or a
duration axis built the wrong way round — none of which the unit tests in
test_extremes.py can see, because each of them checks one function in isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import climatedt  # noqa: E402
import extremes  # noqa: E402
import synthetic_climatedt  # noqa: E402


@pytest.fixture(scope="module")
def annual_maxima(tmp_path_factory) -> dict:
    """Run the 01 -> 02 reduction on synthetic input, once for the module."""
    raw = tmp_path_factory.mktemp("raw")
    synthetic_climatedt.write_all(raw)
    out = {}
    for window in climatedt.WINDOWS:
        files = sorted(raw.glob(f"precip_{window}_*.nc"))
        ds = xr.open_mfdataset(files, combine="by_coords")
        tp_mm = ds[climatedt.PARAM_PRECIP].transpose("time", "cell").values * climatedt.RATE_TO_MM_PER_HOUR
        years = ds["time"].dt.year.values
        out[window] = {
            d: extremes.annual_maxima(tp_mm, years, d)[1] for d in climatedt.DURATIONS_H
        }
        ds.close()
    return out


def test_synthetic_writer_produces_the_schema_02_expects(tmp_path):
    paths = synthetic_climatedt.write_all(tmp_path)
    assert any(p.name == "warming_levels.json" for p in paths)
    nc = sorted(tmp_path.glob("precip_hist_*.nc"))
    assert len(nc) == synthetic_climatedt.N_YEARS
    with xr.open_dataset(nc[0]) as ds:
        assert set(ds.dims) == {"time", "cell"}
        assert climatedt.PARAM_PRECIP in ds.data_vars
        assert {"latitude", "longitude"} <= set(ds.coords)
        assert ds[climatedt.PARAM_PRECIP].attrs["units"] == climatedt.PRECIP_UNITS
        assert ds.attrs["provenance"] == "synthetic"
        assert ds.sizes["time"] in (8760, 8784)  # one calendar year, hourly


def test_synthetic_data_is_stamped_so_it_cannot_be_mistaken_for_a_result(tmp_path):
    synthetic_climatedt.write_all(tmp_path)
    with xr.open_dataset(sorted(tmp_path.glob("precip_*.nc"))[0]) as ds:
        assert ds.attrs["provenance"] == "synthetic"
        assert "SYNTHETIC" in ds.attrs["warning"]


def test_synthetic_filenames_cannot_be_confused_with_real_months(tmp_path):
    # Real files are precip_<window>_<YYYYMM>.nc with a valid month; synthetic
    # ones use month 00, which does not exist. Both match 02's glob, so this is
    # a readability guard, not the safety mechanism -- the provenance check in
    # 02_data_clean.py is that. During development a set of synthetic yearly
    # files sat unnoticed beside the real monthly ones.
    synthetic_climatedt.write_all(tmp_path)
    for path in tmp_path.glob("precip_*.nc"):
        stamp = path.stem.rsplit("_", 1)[-1]
        assert len(stamp) == 6 and stamp.endswith("00"), path.name
    # And they still match the glob 02 uses, so the provenance check sees them.
    assert list(tmp_path.glob("precip_hist_*.nc"))


def test_annual_maxima_grow_with_duration(annual_maxima):
    for window, per_duration in annual_maxima.items():
        medians = [np.nanmedian(per_duration[d]) for d in climatedt.DURATIONS_H]
        assert medians == sorted(medians), f"{window}: {medians}"


def test_every_duration_yields_a_usable_pooled_fit(annual_maxima):
    for window, per_duration in annual_maxima.items():
        for duration, am in per_duration.items():
            (xi, alpha, k), index_flood = extremes.pooled_growth_curve(am)
            assert alpha > 0, f"{window} {duration}h: non-positive GEV scale"
            assert -1.0 < k < 1.0, f"{window} {duration}h: implausible shape {k}"
            assert np.isfinite(index_flood).sum() > 0.9 * index_flood.size


def _change_matrix(annual_maxima) -> np.ndarray:
    """(n_durations, n_rps) percentage change, exactly as 03_analysis.py computes it."""
    rps = np.array(climatedt.RETURN_PERIODS_Y)
    windows = list(climatedt.WINDOWS)
    pct = np.full((len(climatedt.DURATIONS_H), len(rps)), np.nan)
    for i, duration in enumerate(climatedt.DURATIONS_H):
        rl = {
            w: extremes.regional_return_levels(annual_maxima[w][duration], rps)
            for w in windows
        }
        pct[i] = 100.0 * (np.nanmedian(rl[windows[1]] / rl[windows[0]], axis=1) - 1.0)
    return pct


def test_analysis_recovers_the_planted_duration_ordering(annual_maxima):
    # The generator adds a single-hour burst term, so 1 h maxima must rise more
    # than 24 h maxima. The analysis is never told this.
    pct = _change_matrix(annual_maxima)
    for j in range(pct.shape[1]):
        tau = stats.kendalltau(list(climatedt.DURATIONS_H), pct[:, j]).statistic
        assert tau < 0, f"return-period column {j}: tau={tau:+.3f}"
    assert pct[0].mean() > pct[-1].mean() + 5.0


def test_change_is_positive_everywhere_for_an_intensified_scenario(annual_maxima):
    pct = _change_matrix(annual_maxima)
    assert np.all(pct > 0)


def test_no_intensification_gives_no_ordering(annual_maxima, tmp_path):
    # Control: two windows drawn from the same generator must not produce a
    # systematic duration ordering. Without this, the test above could be
    # passing on an artefact of the pipeline rather than on the planted signal.
    synthetic_climatedt.write_window(tmp_path, "hist", seed=101)
    baseline_a = {}
    for name, seed in (("a", 101), ("b", 202)):
        target = tmp_path / name
        synthetic_climatedt.write_window(target, "hist", seed=seed)
        ds = xr.open_mfdataset(sorted(target.glob("precip_hist_*.nc")), combine="by_coords")
        tp_mm = ds[climatedt.PARAM_PRECIP].transpose("time", "cell").values * climatedt.RATE_TO_MM_PER_HOUR
        years = ds["time"].dt.year.values
        baseline_a[name] = {
            d: extremes.annual_maxima(tp_mm, years, d)[1] for d in climatedt.DURATIONS_H
        }
        ds.close()

    rps = np.array(climatedt.RETURN_PERIODS_Y)
    pct = np.full((len(climatedt.DURATIONS_H), len(rps)), np.nan)
    for i, duration in enumerate(climatedt.DURATIONS_H):
        rl_a = extremes.regional_return_levels(baseline_a["a"][duration], rps)
        rl_b = extremes.regional_return_levels(baseline_a["b"][duration], rps)
        pct[i] = 100.0 * (np.nanmedian(rl_b / rl_a, axis=1) - 1.0)

    taus = [
        stats.kendalltau(list(climatedt.DURATIONS_H), pct[:, j]).statistic
        for j in range(pct.shape[1])
    ]
    assert not all(t < 0 for t in taus), (
        f"two draws from the same distribution produced a consistent duration "
        f"ordering (taus={taus}) — the ordering test is detecting the pipeline, "
        f"not the signal"
    )
