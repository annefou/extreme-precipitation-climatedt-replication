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
# # 02 — From hourly precipitation to annual maxima
#
# Reduces the hourly retrieval to the only quantity the extreme-value analysis
# needs: the **annual maximum accumulation** for each duration, cell and year.
#
# This is a large reduction — 175,200 hourly values per cell per window become
# 20 annual maxima per duration — and it is where the duration axis is created.
# For each duration *D* the series of backward-looking *D*-hour totals is formed,
# then the largest value in each calendar year is kept. Durations are
# 1, 3, 6, 12 and 24 hours.
#
# **Deviation from the original.** The paper resolved 15-minute and 30-minute
# durations from a convection-permitting model. The Climate DT archive is
# hourly, so one hour is the shortest duration available here. The claim under
# test is about the *ordering* of change across durations, and that ordering can
# be tested on 1–24 h; but the very shortest, most convectively driven
# durations the paper emphasises are out of reach. This belongs in the
# Replication Study's Deviations field.

# %%
import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path("../scripts").resolve()))

import climatedt  # noqa: E402
import ellipsoid  # noqa: E402
import extremes  # noqa: E402
import geometry  # noqa: E402

try:
    import healpix_geo  # noqa: E402
except ImportError:  # the ellipsoid grid is then simply not produced
    healpix_geo = None

RAW_DIR = Path("../data/raw")
CLEAN_DIR = Path("../data/clean")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Inputs

# %%
# RECOMPUTE or LOAD. With no raw input but a committed analysis-ready artefact
# that is real Destination Earth output, this notebook loads it instead of
# rebuilding it. That is the CI case: the runner has no DestinE account, and
# recomputing there would rebuild the artefact from the synthetic stand-in — so
# the published Jupyter Book would show invented numbers under a SYNTHETIC
# watermark instead of the study's result. Which is exactly what it did before
# this branch existed.
OUT_PATH = CLEAN_DIR / "annual_maxima.nc"
RECOMPUTE = any(RAW_DIR.glob("precip_*.nc")) or not climatedt.existing_real_artefact(OUT_PATH)
print(f"raw input present: {any(RAW_DIR.glob('precip_*.nc'))}")
print(f"committed artefact is real: {climatedt.existing_real_artefact(OUT_PATH)}")
print(f"-> {'recomputing from raw' if RECOMPUTE else 'loading the committed real artefact'}")

available = {}
for window in climatedt.WINDOWS if RECOMPUTE else []:
    files = sorted(RAW_DIR.glob(f"precip_{window}_*.nc"))
    if not files:
        raise FileNotFoundError(
            f"no raw files for window {window!r} in {RAW_DIR}. Run 01_data_download.py first."
        )
    available[window] = files
    print(f"{window:8s} {len(files)} yearly file(s): {files[0].name} .. {files[-1].name}")

provenances: dict[str, list[str]] = {}
for files in available.values():
    for f in files:
        with xr.open_dataset(f) as ds:
            provenances.setdefault(ds.attrs.get("provenance", "unknown"), []).append(f.name)

# MIXED PROVENANCE IS FATAL, not a warning. Synthetic and real files live in the
# same directory and both match the same glob, so a leftover smoke-test file
# from a run without credentials will silently join the real retrieval and
# contribute its invented extremes to the GEV fit. That happened during
# development, and a warning would have scrolled past. The result of this
# pipeline is a signed, permanent nanopublication; there is no version of
# "partly synthetic" that is publishable.
if len(provenances) > 1:
    listing = "\n".join(
        f"  {prov}: {len(names)} file(s), e.g. {names[0]}"
        for prov, names in sorted(provenances.items())
    )
    raise ValueError(
        f"data/raw holds files from more than one provenance:\n{listing}\n"
        "Delete whichever set is not wanted before continuing. Synthetic files "
        "are written only when no DestinE credential is present."
    )

if RECOMPUTE:
    PROVENANCE = next(iter(provenances))
else:
    with xr.open_dataset(OUT_PATH) as _real:
        PROVENANCE = _real.attrs["provenance"]
print(f"\nprovenance: {PROVENANCE}")
if PROVENANCE != "destine-climate-dt":
    print(
        "WARNING — this is not Destination Earth output. Everything downstream\n"
        "is a smoke test and must not be reported as a replication result."
    )

# %% [markdown]
# ## Annual maxima per duration
#
# `scripts/extremes.py` does the accumulation and the block maxima; it is unit
# tested in `tests/test_extremes.py`, including that a rolling window containing
# a missing hour stays missing rather than being summed as zero.
#
# Units: the hourly Climate DT stream carries precipitation as `avg_tprate`, an
# hourly-mean **rate** in kg m⁻² s⁻¹ — *not* an accumulation in metres. One
# kg m⁻² of water is 1 mm depth and an hour is 3600 s, so the millimetres that
# fell during an hour are `rate × 3600`. That conversion happens once, here, and
# every downstream number is in mm.
#
# This is worth stating because the obvious guess is wrong in two ways at once:
# the archive has no `tp` in this stream at all (`param=tp` and `param=228` are
# both refused), and the field it does have is a rate, so a metres-to-millimetres
# factor of 1000 would be wrong by 3.6× while still producing entirely
# plausible-looking numbers.

# %%
RATE_TO_MM = climatedt.RATE_TO_MM_PER_HOUR


def year_of(path: Path) -> int:
    """1991 from `precip_hist_199103.nc`."""
    return int(path.stem.rsplit("_", 1)[-1][:4])


def read_year(files: list[Path]) -> tuple[np.ndarray, xr.Dataset]:
    """One calendar year of hourly precipitation in mm, as (time, cell)."""
    ds = xr.open_mfdataset(sorted(files), combine="by_coords")
    values = ds[climatedt.PARAM_PRECIP].transpose("time", "cell").values * RATE_TO_MM
    return values, ds


def annual_maxima_for_window(files: list[Path], resampler=None) -> xr.Dataset:
    """(n_durations, n_years, n_cells) annual maxima in mm, with cell geometry.

    Reads a **year at a time**, computing every duration in that one pass. A
    whole 20-year window is 8,697 cells x 175,200 hours = 12 GB as float64, and
    the rolling accumulation needs about four such arrays at once — roughly
    49 GB per duration against 57 GB of usable memory. Per year that is 0.6 GB.
    `extremes.annual_maxima_multi` carries the tail of each year into the next
    so a 24-hour total ending on 1 January still sees 31 December; the test
    suite asserts the result is identical to the unbroken series.

    With `resampler` given, each year is converted from the delivered
    **spherical** HEALPix cells onto **WGS84-ellipsoidal** HEALPix cells before
    the maxima are taken — see `scripts/ellipsoid.py`. The conversion happens
    inside this single pass on purpose: done per duration it would resample the
    whole hourly series five times over.
    """
    by_year: dict[int, list[Path]] = {}
    for f in files:
        by_year.setdefault(year_of(f), []).append(f)

    cell_geometry: dict | None = None

    def chunks():
        nonlocal cell_geometry
        for year in sorted(by_year):
            values, ds = read_year(by_year[year])
            if resampler is None:
                if cell_geometry is None:
                    cell_geometry = {
                        "cell": ds["cell"].values,
                        "latitude": ds["latitude"].values,
                        "longitude": ds["longitude"].values,
                    }
            else:
                # Batch the whole year through the sparse operator at once;
                # measured at ~14 ms per hourly field for this domain.
                cell_ids, values = ellipsoid.to_ellipsoid(resampler, values)
                if cell_geometry is None:
                    lon_e, lat_e = healpix_geo.nested.healpix_to_lonlat(
                        cell_ids, ellipsoid.NATIVE_LEVEL, ellipsoid="WGS84"
                    )
                    cell_geometry = {
                        "cell": np.asarray(cell_ids),
                        "latitude": np.asarray(lat_e),
                        "longitude": np.asarray(lon_e),
                    }
            ds.close()
            print(f"    {year} ...", end="", flush=True)
            yield year, values

    blocks, per_duration = extremes.annual_maxima_multi(chunks(), climatedt.DURATIONS_H)
    print()
    stack = []
    for duration in climatedt.DURATIONS_H:
        am = per_duration[duration]
        stack.append(am)
        print(
            f"    {duration:>3d} h: {am.shape[0]} years x {am.shape[1]} cells, "
            f"median annual maximum {np.nanmedian(am):.2f} mm",
            flush=True,
        )

    return xr.Dataset(
        {"annual_max": (("duration", "year", "cell"), np.stack(stack).astype("float32"))},
        coords={
            "duration": list(climatedt.DURATIONS_H),
            "year": blocks,
            "cell": cell_geometry["cell"],
            "latitude": ("cell", cell_geometry["latitude"]),
            "longitude": ("cell", cell_geometry["longitude"]),
        },
    )


# %% [markdown]
# ### Two grids, deliberately
#
# The Climate DT is delivered on HEALPix defined on a mathematical **sphere**.
# Every geographic use of it — masking a country, comparing with station data,
# publishing an interoperable archive — is on the **WGS84 ellipsoid**, where the
# same cell index lands somewhere else. `scripts/ellipsoid.py` does that
# conversion with `healpix-resample`'s `PSFResampler`.
#
# At coarse resolution the difference is routinely neglected: the latitude
# offset reaches 0.128° (~14 km), a third of a level-7 cell. At the level 10
# (~6 km) used here it is more than two cells, and the mask check below measures
# **350 of 8,697 cells (4.0%)** changing Germany-membership between the two
# conventions.
#
# But PSF resampling is a Gaussian-kernel reconstruction: it **smooths**, and
# this study measures maxima. So neither grid is assumed harmless — both are
# built, and `03_analysis.py` runs the ordering test on each. Whether the
# correction changes the conclusion is then a reported number, not an assertion.

# %%
GRIDS: dict[str, object] = {"native": None}
by_grid: dict[str, dict[str, xr.Dataset]] = {}

if RECOMPUTE:
    if healpix_geo is not None:
        probe_file = next(iter(available.values()))[0]
        with xr.open_dataset(probe_file) as probe:
            GRIDS["ellipsoid"] = ellipsoid.build_resampler(
                probe["longitude"].values, probe["latitude"].values
            )
        print("ellipsoid resampler built (sphere -> WGS84, conservative)")
    else:
        print("healpix-resample unavailable — building the native grid only")

    for grid, resampler in GRIDS.items():
        print(f"\n=== {grid} grid ===", flush=True)
        by_grid[grid] = {}
        for window, files in available.items():
            print(f"{window} ({climatedt.WINDOWS[window]['label']}):", flush=True)
            by_grid[grid][window] = annual_maxima_for_window(files, resampler)

# %% [markdown]
# ## Combine into one artefact
#
# The two windows cover different calendar years, so they are stacked along a
# `block` index (0, 1, 2, …) with the actual calendar year kept as a
# `(window, block)` variable. Both windows must have the same number of blocks:
# an unequal split would confound the comparison with sampling uncertainty,
# because the GEV's tail estimate depends on the record length.

# %%
def combine(per_window: dict[str, xr.Dataset], grid: str) -> xr.Dataset:
    """Stack the two windows into the artefact 03 reads."""
    n_blocks = {w: ds.sizes["year"] for w, ds in per_window.items()}
    if len(set(n_blocks.values())) != 1:
        raise ValueError(
            f"windows have different numbers of years {n_blocks}; the two GEV fits "
            "would rest on different sample sizes and the comparison would be confounded"
        )
    windows = list(per_window)
    out = xr.Dataset(
        {
            "annual_max": (
                ("window", "duration", "block", "cell"),
                np.stack([per_window[w]["annual_max"].values for w in windows]),
            ),
            "year": (
                ("window", "block"),
                np.stack([per_window[w]["year"].values for w in windows]),
            ),
        },
        coords={
            "window": windows,
            "duration": list(climatedt.DURATIONS_H),
            "block": np.arange(next(iter(n_blocks.values())), dtype="int32"),
            "cell": per_window[windows[0]]["cell"].values,
            "latitude": ("cell", per_window[windows[0]]["latitude"].values),
            "longitude": ("cell", per_window[windows[0]]["longitude"].values),
        },
        attrs={
            "provenance": PROVENANCE,
            "grid": grid,
            "grid_description": (
                "HEALPix level 10 NESTED on the WGS84 ellipsoid, converted from the "
                "delivered spherical grid with healpix-resample's PSFResampler"
                if grid == "ellipsoid"
                else "HEALPix level 10 NESTED as delivered, on the sphere"
            ),
            "title": "Annual maximum precipitation accumulation by duration, Germany",
            "source": "Destination Earth Climate DT generation 2, IFS-NEMO, SSP3-7.0",
            "window_labels": json.dumps({w: climatedt.WINDOWS[w]["label"] for w in windows}),
            "created_by": "notebooks/02_data_clean.py",
            **climatedt.attribution_attrs(),
        },
    )
    out["annual_max"].attrs.update(units="mm", long_name="Annual maximum accumulation")
    out["duration"].attrs.update(units="h", long_name="Accumulation duration")
    return out


if RECOMPUTE:
    combined_by_grid = {grid: combine(pw, grid) for grid, pw in by_grid.items()}
else:
    # Load what the real run committed, rather than rebuilding it.
    combined_by_grid = {}
    for grid, fname in (("native", "annual_maxima.nc"),
                        ("ellipsoid", "annual_maxima_ellipsoid.nc")):
        path = CLEAN_DIR / fname
        if climatedt.existing_real_artefact(path):
            combined_by_grid[grid] = xr.load_dataset(path)
    print(f"loaded committed real artefacts: {list(combined_by_grid)}")

combined = combined_by_grid["native"]
windows = [str(w) for w in combined["window"].values]
print(f"blocks per window: {dict((w, combined.sizes['block']) for w in windows)}")
for grid, ds_grid in combined_by_grid.items():
    print(f"  {grid:9s} {ds_grid.sizes['cell']} cells")


# %% [markdown]
# ## Cell geometry: equal area, and the sphere-versus-ellipsoid question
#
# HEALPix cells are **equal-area by construction**, and the authalic definition
# preserves that on the WGS84 ellipsoid too. A domain mean is therefore an
# unweighted mean over cells — no cosine-latitude weights, no area weights.
# Nothing in this pipeline resamples the precipitation field, which matters: a
# smoothing resampler (a PSF kernel, say) would damp exactly the extremes being
# measured.
#
# The one place the ellipsoid does bite is the **domain mask**. Polytope's
# polygon clip is applied on the sphere, and the authalic and geodetic latitudes
# of the same point differ by up to 0.128° (~14 km, peaking near 45°). Cells near
# the German border can therefore fall on the other side of the boundary under
# the two conventions. `scripts/geometry.py` measures how many; it is a
# sensitivity number to report in the Study's Deviations, not a correction to
# apply.
#
# No HEALPix library appears anywhere in this pipeline, and that is the point:
# the Climate DT is *delivered* on HEALPix and nothing here regrids it, so there
# is no resampling step whose kernel choice could bias the extremes. The only
# ellipsoid-aware calculation needed is the latitude mapping in
# `scripts/geometry.py`, which is a dozen lines and is unit tested against
# published authalic-latitude values.

# %%
sensitivity = geometry.mask_sensitivity(
    combined["latitude"].values,
    combined["longitude"].values,
    np.asarray(climatedt.germany_polygon()),
)
print(json.dumps(sensitivity, indent=2))
combined.attrs["ellipsoid_mask_sensitivity"] = json.dumps(sensitivity)

# %% [markdown]
# ## Warming level
#
# Used only to express the magnitude of the change per degree, for comparison
# with the paper's reported figure. The claim under test is about ordering and
# does not depend on it.

# %%
wl_path = RAW_DIR / "warming_levels.json"
if wl_path.exists():
    with open(wl_path) as f:
        wl = json.load(f)
    gmst = wl["gmst_k"]
    delta_t = gmst[windows[1]] - gmst[windows[0]]
    print(f"global mean 2t per window: {gmst}")
    print(f"warming between windows: {delta_t:.3f} K  (provenance: {wl['provenance']})")
    combined.attrs["warming_levels"] = json.dumps(wl)
    combined.attrs["delta_t_k"] = delta_t
else:
    print(
        "No warming_levels.json — the per-degree normalisation will be skipped in 03.\n"
        "The ordering test does not need it."
    )

# %%
# The mask sensitivity and warming level are properties of the study, not of a
# grid, so carry them onto both artefacts.
for grid, ds_grid in combined_by_grid.items():
    for key in ("ellipsoid_mask_sensitivity", "warming_levels", "delta_t_k"):
        if key in combined.attrs:
            ds_grid.attrs[key] = combined.attrs[key]
    name = "annual_maxima.nc" if grid == "native" else f"annual_maxima_{grid}.nc"
    out_path = CLEAN_DIR / name
    ds_grid.to_netcdf(out_path)
    print(f"wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB, {grid} grid)")

# %% [markdown]
# ### What the conversion did to the maxima
#
# The number that decides whether the correction is harmless: PSF resampling
# smooths, so if it damps the maxima materially, that has to be said out loud in
# the Replication Study rather than left implicit.

# %%
if "ellipsoid" in combined_by_grid:
    print(f"{'dur':>5} {'native':>10} {'ellipsoid':>10} {'change':>9}")
    for d in climatedt.DURATIONS_H:
        a = float(np.nanmedian(combined["annual_max"].sel(duration=d)))
        b = float(np.nanmedian(combined_by_grid["ellipsoid"]["annual_max"].sel(duration=d)))
        print(f"{d:>4}h {a:>10.2f} {b:>10.2f} {100 * (b / a - 1):>+8.2f}%")

combined
