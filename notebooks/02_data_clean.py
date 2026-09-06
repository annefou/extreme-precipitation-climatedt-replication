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
import extremes  # noqa: E402
import geometry  # noqa: E402

RAW_DIR = Path("../data/raw")
CLEAN_DIR = Path("../data/clean")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Inputs

# %%
available = {}
for window in climatedt.WINDOWS:
    files = sorted(RAW_DIR.glob(f"tp_{window}_*.nc"))
    if not files:
        raise FileNotFoundError(
            f"no raw files for window {window!r} in {RAW_DIR}. Run 01_data_download.py first."
        )
    available[window] = files
    print(f"{window:8s} {len(files)} yearly file(s): {files[0].name} .. {files[-1].name}")

provenances = set()
for files in available.values():
    for f in files:
        with xr.open_dataset(f) as ds:
            provenances.add(ds.attrs.get("provenance", "unknown"))
PROVENANCE = (
    "mixed:" + "+".join(sorted(provenances)) if len(provenances) > 1 else provenances.pop()
)
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
# Units: the Climate DT delivers `tp` in **metres**, so everything is converted
# to millimetres here, once, and every downstream number is in mm.

# %%
M_TO_MM = 1000.0


def annual_maxima_for_window(files: list[Path]) -> xr.Dataset:
    """(n_durations, n_years, n_cells) annual maxima in mm, with cell geometry."""
    ds = xr.open_mfdataset(files, combine="by_coords", chunks={"time": 24 * 90})
    tp_mm = ds["tp"].transpose("time", "cell").values * M_TO_MM
    years = ds["time"].dt.year.values
    blocks, stack = None, []
    for duration in climatedt.DURATIONS_H:
        blocks, am = extremes.annual_maxima(tp_mm, years, duration)
        stack.append(am)
        print(
            f"    {duration:>3d} h: {am.shape[0]} years x {am.shape[1]} cells, "
            f"median annual maximum {np.nanmedian(am):.2f} mm"
        )
    out = xr.Dataset(
        {"annual_max": (("duration", "year", "cell"), np.stack(stack).astype("float32"))},
        coords={
            "duration": list(climatedt.DURATIONS_H),
            "year": blocks,
            "cell": ds["cell"].values,
            "latitude": ("cell", ds["latitude"].values),
            "longitude": ("cell", ds["longitude"].values),
        },
    )
    ds.close()
    return out


per_window = {}
for window, files in available.items():
    print(f"{window} ({climatedt.WINDOWS[window]['label']}):")
    per_window[window] = annual_maxima_for_window(files)

# %% [markdown]
# ## Combine into one artefact
#
# The two windows cover different calendar years, so they are stacked along a
# `block` index (0, 1, 2, …) with the actual calendar year kept as a
# `(window, block)` variable. Both windows must have the same number of blocks:
# an unequal split would confound the comparison with sampling uncertainty,
# because the GEV's tail estimate depends on the record length.

# %%
n_blocks = {w: ds.sizes["year"] for w, ds in per_window.items()}
print(f"blocks per window: {n_blocks}")
if len(set(n_blocks.values())) != 1:
    raise ValueError(
        f"windows have different numbers of years {n_blocks}; the two GEV fits would "
        "rest on different sample sizes and the comparison would be confounded"
    )

windows = list(per_window)
combined = xr.Dataset(
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
        "title": "Annual maximum precipitation accumulation by duration, Germany",
        "source": "Destination Earth Climate DT generation 2, IFS-NEMO, SSP3-7.0",
        "window_labels": json.dumps({w: climatedt.WINDOWS[w]["label"] for w in windows}),
        "created_by": "notebooks/02_data_clean.py",
    },
)
combined["annual_max"].attrs.update(units="mm", long_name="Annual maximum accumulation")
combined["duration"].attrs.update(units="h", long_name="Accumulation duration")


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
# of the same point differ by up to ~0.19° (~21 km at mid-latitudes). Cells near
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
out_path = CLEAN_DIR / "annual_maxima.nc"
combined.to_netcdf(out_path)
print(f"\nwrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")
combined
