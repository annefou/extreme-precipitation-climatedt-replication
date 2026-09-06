"""Tests for scripts/climatedt.py and scripts/geometry.py.

The request builders are checked against the keys in the official DestinE
examples (`destination-earth-digital-twins/polytope-examples`, climate-dt
feature-extraction notebooks), because a wrong key here does not fail loudly —
it silently retrieves a different simulation. Generation 1 and generation 2 in
particular use different `activity` values for the same scenario.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import climatedt  # noqa: E402
import geometry  # noqa: E402


# --- request builders -----------------------------------------------------

def test_clte_request_targets_generation_2():
    req = climatedt.clte_polygon_request("ssp370", 2035, 7)
    assert req["generation"] == "2"
    assert req["dataset"] == "climate-dt"
    assert req["class"] == "d1"
    assert req["expver"] == "0001"


def test_clte_request_uses_the_generation_2_activity_names():
    # Generation 1 used activity="ScenarioMIP"; generation 2 uses
    # "projections" for the scenario and "baseline"/"hist" for the historical
    # period. Getting this wrong retrieves a different simulation silently.
    assert climatedt.clte_polygon_request("ssp370", 2035, 7)["activity"] == "projections"
    assert climatedt.clte_polygon_request("ssp370", 2035, 7)["experiment"] == "SSP3-7.0"
    assert climatedt.clte_polygon_request("hist", 1995, 7)["activity"] == "baseline"
    assert climatedt.clte_polygon_request("hist", 1995, 7)["experiment"] == "hist"


def test_clte_request_asks_for_every_hour_as_an_explicit_list():
    # THE regression test of this module. Feature extraction accepts the
    # /to/../by/.. range syntax for `date` but NOT for `time`: given a range it
    # returns the FIRST HOUR ONLY and reports no error whatsoever. Verified
    # live -- 1 datetime with the range, 24 with this list. A 24x under-fetch
    # that looks completely healthy is the worst kind of bug in a pipeline
    # whose output is a signed, permanent nanopublication.
    req = climatedt.clte_polygon_request("hist", 2000, 7)
    hours = req["time"].split("/")
    assert len(hours) == 24
    assert hours[0] == "0000" and hours[-1] == "2300"
    assert "to" not in hours and "by" not in hours
    assert req["stream"] == "clte"
    assert req["levtype"] == "sfc"


def test_clte_request_asks_for_avg_tprate_not_tp():
    # Verified live: param=tp and param=228 are both refused with HTTP 400.
    # The clte stream carries precipitation among the 20 "sfc (hourly mean)"
    # flux variables, which keep the avg_ prefix -- and it is a RATE, not an
    # accumulation.
    assert climatedt.clte_polygon_request("hist", 2000, 7)["param"] == "avg_tprate"
    assert climatedt.PRECIP_UNITS == "kg m**-2 s**-1"


def test_rate_converts_to_millimetres_per_hour():
    # 1 kg m-2 of water is 1 mm depth; an hour is 3600 s. A metres-to-mm factor
    # of 1000 would be wrong by 3.6x and still look plausible.
    assert climatedt.RATE_TO_MM_PER_HOUR == 3600.0


def test_clte_request_covers_one_whole_calendar_month():
    assert climatedt.clte_polygon_request("hist", 2003, 7)["date"] == "20030701/to/20030731"
    # February, and February in a leap year.
    assert climatedt.clte_polygon_request("hist", 2003, 2)["date"] == "20030201/to/20030228"
    assert climatedt.clte_polygon_request("hist", 2004, 2)["date"] == "20040201/to/20040229"


def test_clte_request_rejects_an_impossible_month():
    for bad in (0, 13, -1):
        with pytest.raises(ValueError):
            climatedt.clte_polygon_request("hist", 2000, bad)


def test_clte_request_asks_for_the_native_resolution():
    # 'high' is the native HEALPix delivery (level 10, ~6.3 km); 'standard' is
    # coarser and would make the shortest durations meaningless.
    assert climatedt.clte_polygon_request("hist", 2000, 7)["resolution"] == "high"


def test_clte_request_carries_the_germany_polygon_server_side():
    feature = climatedt.clte_polygon_request("hist", 2000, 7)["feature"]
    assert feature["type"] == "polygon"
    assert len(feature["shape"]) > 50
    # MARS cannot crop HEALPix with a lat/lon box, so there must be no `area`.
    assert "area" not in climatedt.clte_polygon_request("hist", 2000, 7)


def test_clte_request_rejects_a_year_outside_its_window():
    with pytest.raises(ValueError):
        climatedt.clte_polygon_request("hist", 2035, 7)
    with pytest.raises(ValueError):
        climatedt.clte_polygon_request("ssp370", 1995, 7)


def test_request_rejects_an_unknown_window():
    with pytest.raises(KeyError):
        climatedt.clte_polygon_request("rcp85", 2035, 7)


def test_clmn_request_is_global_and_monthly():
    req = climatedt.clmn_global_request("hist", 2000)
    assert "feature" not in req  # a global mean needs the whole field
    assert req["stream"] == "clmn"
    assert req["param"] == "avg_2t"
    assert req["year"] == "2000"
    assert req["month"] == "1/2/3/4/5/6/7/8/9/10/11/12"
    assert "date" not in req and "time" not in req  # clmn uses year/month
    assert req["resolution"] == "standard"


# --- study design constants ----------------------------------------------

def test_the_two_windows_are_the_same_length():
    lengths = {
        w: spec["years"][1] - spec["years"][0] + 1
        for w, spec in climatedt.WINDOWS.items()
    }
    assert len(set(lengths.values())) == 1, lengths


def test_windows_lie_inside_the_generation_2_period():
    # Generation 2 covers 1990-2049.
    for spec in climatedt.WINDOWS.values():
        assert 1990 <= spec["years"][0] <= spec["years"][1] <= 2049


def test_longest_return_period_does_not_exceed_the_record_length():
    n_years = min(
        spec["years"][1] - spec["years"][0] + 1 for spec in climatedt.WINDOWS.values()
    )
    assert max(climatedt.RETURN_PERIODS_Y) <= n_years


def test_durations_are_whole_hours_and_ascending():
    assert list(climatedt.DURATIONS_H) == sorted(climatedt.DURATIONS_H)
    assert all(isinstance(d, int) and d >= 1 for d in climatedt.DURATIONS_H)


# --- the committed polygon ------------------------------------------------

def test_germany_polygon_is_a_closed_ring_in_the_right_box():
    ring = np.asarray(climatedt.germany_polygon())
    assert ring.shape[1] == 2
    assert np.allclose(ring[0], ring[-1]), "ring must be closed"
    lat, lon = ring[:, 0], ring[:, 1]
    assert 47.0 < lat.min() and lat.max() < 55.5
    assert 5.5 < lon.min() and lon.max() < 15.5


def test_germany_polygon_records_its_provenance():
    prov = climatedt.polygon_provenance()
    assert "NUTS" in prov["source"]["dataset"]
    assert prov["source"]["obtained_from"].startswith("https://")
    assert "ring" not in prov


# --- credential discovery -------------------------------------------------
#
# These mirror polytope-client's own lookup order (Auth.py::fetch_key,
# Config.py). Getting it wrong is expensive in a specific way: the notebook
# would silently write SYNTHETIC data on a machine that does have a key.

@pytest.fixture
def no_credentials(monkeypatch, tmp_path):
    """A machine with no polytope credential anywhere."""
    for var in ("POLYTOPE_USER_KEY", "POLYTOPE_KEY_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(climatedt.Path, "home", staticmethod(lambda: tmp_path))
    return tmp_path


def test_no_credential_anywhere_is_detected(no_credentials):
    assert climatedt.credential_source() is None
    assert climatedt.have_credentials() is False


def test_environment_key_is_found_first(no_credentials, monkeypatch):
    (no_credentials / ".polytopeapirc").write_text('{"user_key": "from-file"}')
    monkeypatch.setenv("POLYTOPE_USER_KEY", "from-env")
    # polytope-client applies env-var config over file config, so must this.
    assert climatedt.credential_source() == "env:POLYTOPE_USER_KEY"


def test_polytopeapirc_is_found(no_credentials):
    (no_credentials / ".polytopeapirc").write_text('{"user_key": "abc"}')
    assert climatedt.credential_source().endswith(".polytopeapirc")
    assert climatedt.have_credentials() is True


def test_ecmwfapirc_is_the_fallback(no_credentials):
    (no_credentials / ".ecmwfapirc").write_text('{"key": "abc", "email": "a@b.c"}')
    assert climatedt.credential_source().endswith(".ecmwfapirc")


def test_polytopeapirc_wins_over_ecmwfapirc(no_credentials):
    (no_credentials / ".polytopeapirc").write_text('{"user_key": "abc"}')
    (no_credentials / ".ecmwfapirc").write_text('{"key": "def", "email": "a@b.c"}')
    assert climatedt.credential_source().endswith(".polytopeapirc")


def test_key_path_override_is_honoured(no_credentials, monkeypatch, tmp_path):
    elsewhere = tmp_path / "keys" / "mine.json"
    elsewhere.parent.mkdir()
    elsewhere.write_text('{"user_key": "abc"}')
    monkeypatch.setenv("POLYTOPE_KEY_PATH", str(elsewhere))
    assert climatedt.credential_source() == f"file:{elsewhere}"


# --- CoverageJSON reshaping -----------------------------------------------
#
# Built from a dataset shaped exactly like the one a live polygon request
# returned on 2026-09-06: datetimes x number x steps x points, with
# latitude/longitude/levelist along points and the datetimes as STRINGS.

def _coverage_like(n_times: int = 3, n_points: int = 5):
    import xarray as xr

    times = [f"2030-06-0{i + 1} 00:00:00Z" for i in range(n_times)]
    values = np.arange(n_times * n_points, dtype="float32").reshape(n_times, 1, 1, n_points)
    return xr.Dataset(
        {climatedt.PARAM_PRECIP: (("datetimes", "number", "steps", "points"), values)},
        coords={
            "datetimes": times,
            "number": [0],
            "steps": [0],
            "points": np.arange(n_points),
            "latitude": ("points", np.linspace(48.0, 54.0, n_points)),
            "longitude": ("points", np.linspace(7.0, 14.0, n_points)),
            "levelist": ("points", np.zeros(n_points)),
        },
    )


def test_to_study_schema_renames_dims_and_parses_times():
    out = climatedt.to_study_schema(_coverage_like())
    assert out[climatedt.PARAM_PRECIP].dims == ("time", "cell")
    assert str(out["time"].dtype).startswith("datetime64")
    assert out.sizes == {"time": 3, "cell": 5}


def test_to_study_schema_keeps_cell_geometry_and_drops_the_rest():
    out = climatedt.to_study_schema(_coverage_like())
    assert {"latitude", "longitude"} <= set(out.coords)
    assert not {"number", "steps", "levelist", "datetimes", "points"} & set(out.coords)


def test_to_study_schema_preserves_values_in_order():
    src = _coverage_like()
    out = climatedt.to_study_schema(src)
    expected = src[climatedt.PARAM_PRECIP].values[:, 0, 0, :]
    assert np.array_equal(out[climatedt.PARAM_PRECIP].values, expected)


def test_to_study_schema_refuses_to_collapse_real_ensemble_members():
    # A multi-member request must fail loudly rather than silently keep member 0.
    import xarray as xr

    src = xr.concat([_coverage_like(), _coverage_like()], dim="number")
    src = src.assign_coords(number=[0, 1])
    with pytest.raises(ValueError, match="number"):
        climatedt.to_study_schema(src)


# --- geometry -------------------------------------------------------------

def test_authalic_latitude_is_zero_at_the_equator_and_poles():
    assert geometry.authalic_latitude(0.0) == pytest.approx(0.0, abs=1e-12)
    assert geometry.authalic_latitude(90.0) == pytest.approx(90.0, abs=1e-6)
    assert geometry.authalic_latitude(-90.0) == pytest.approx(-90.0, abs=1e-6)


def test_authalic_latitude_shift_peaks_near_45_degrees():
    lat = np.linspace(0.0, 90.0, 901)
    shift = np.abs(geometry.authalic_latitude(lat) - lat)
    assert 40.0 < lat[np.argmax(shift)] < 50.0
    # Published maximum for WGS84 is about 0.128 degrees.
    assert shift.max() == pytest.approx(0.128, abs=0.005)


def test_authalic_latitude_is_odd():
    lat = np.array([10.0, 33.3, 61.7])
    assert np.allclose(geometry.authalic_latitude(-lat), -geometry.authalic_latitude(lat))


def test_point_in_ring_on_a_square():
    square = np.array([[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0], [0.0, 0.0]])
    lat = np.array([1.0, 1.0, -1.0, 3.0])
    lon = np.array([1.0, 3.0, 1.0, 1.0])
    assert list(geometry.point_in_ring(lat, lon, square)) == [True, False, False, False]


def test_point_in_ring_puts_berlin_inside_germany_and_paris_outside():
    ring = np.asarray(climatedt.germany_polygon())
    lat = np.array([52.52, 48.14, 48.86, 41.90])   # Berlin, Munich, Paris, Rome
    lon = np.array([13.40, 11.58, 2.35, 12.50])
    assert list(geometry.point_in_ring(lat, lon, ring)) == [True, True, False, False]


def test_mask_sensitivity_reports_the_shift_and_the_movers():
    rng = np.random.default_rng(0)
    lat = rng.uniform(47.3, 54.9, 500)
    lon = rng.uniform(5.9, 15.0, 500)
    out = geometry.mask_sensitivity(lat, lon, np.asarray(climatedt.germany_polygon()))
    assert out["n_cells"] == 500
    assert 0.0 <= out["fraction"] <= 1.0
    assert out["cells_changing_membership"] == int(out["fraction"] * 500)
    assert 0.10 < out["max_latitude_shift_deg"] < 0.13
