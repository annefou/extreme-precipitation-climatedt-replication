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
# # 01 — Destination Earth Climate DT retrieval
#
# Fetches hourly total precipitation over Germany from the **Climate Change
# Adaptation Digital Twin (Climate DT), generation 2**, for two 20-year
# windows, plus the global monthly mean temperature needed to express the
# result per degree of warming.
#
# | | |
# |---|---|
# | Dataset | DestinE Climate DT, generation 2 (1990–2049, ~5 km atmosphere, hourly, harmonised on HEALPix) |
# | Model | IFS-NEMO, realization 1 |
# | Scenario | SSP3-7.0 |
# | Historical window | `activity=baseline`, `experiment=hist`, 1991–2010 |
# | Scenario window | `activity=projections`, `experiment=SSP3-7.0`, 2030–2049 |
# | Variable | `tp` — total precipitation, hourly accumulation, `levtype=sfc`, `stream=clte` |
# | Resolution | `high` — the native HEALPix delivery, level 10 (nside=1024, ~6.3 km) |
# | Domain | Germany, as a server-side polygon clip |
#
# ## Why a polygon feature and not a bounding box
#
# The Climate DT is archived on HEALPix, and MARS cannot crop a HEALPix field
# with a lat/lon box — it raises
# `Representation::croppedRepresentation() not implemented for HEALPixNested`.
# A domain study therefore has two options: download the globe and subset
# locally, or use Polytope's **server-side feature extraction**. Twenty years of
# hourly level-10 global fields is far beyond what is reasonable to move, so
# this notebook uses `feature: {"type": "polygon"}` and lets Polytope do the
# clip. That is what makes the study feasible at all.
#
# The polygon itself is committed at `data/germany_polygon.json` (Eurostat NUTS
# 2021 level 0, simplified to 128 vertices) rather than downloaded at runtime,
# so the domain is fixed and reproducible.
#
# ## Credentials
#
# Polytope authenticates with a single **key**. `polytope-client` looks for it
# in this order (`polytope/api/Auth.py::fetch_key`, `Config.py`):
#
# 1. `POLYTOPE_USER_KEY` in the environment — every config key is settable as
#    `POLYTOPE_<NAME>`, and the environment wins over any file.
# 2. `~/.polytopeapirc` (move it with `POLYTOPE_KEY_PATH`):
#    `{"user_key": "<key>"}`, optionally with `"user_email"`.
# 3. `~/.ecmwfapirc` as a fallback — note the *different* key names,
#    `{"key": "...", "email": "..."}`.
#
# A key on its own is sent as `Bearer <key>`; a key paired with an email is sent
# as `EmailKey <email>:<key>`. Both are valid.
#
# ### Two different things are called "a DestinE API key"
#
# This is the trap, and it costs a confusing 401:
#
# | | **DESP offline token** | **DEDL API key** |
# |---|---|---|
# | Where from | `desp-authentication.py -u <user> -p <pass>` | "My DataLake Services" |
# | Shape | one long string, usually a JWT | a **pair**: client id + short opaque secret |
# | Issuer | `auth.destine.eu`, realm `desp`, client `polytope-api-public` | `identity.data.destination-earth.eu`, realm `dedl`, audience `hda-public` |
# | Authenticates | **Polytope** | **HDA** (Harmonised Data Access) |
# | Used directly? | yes — it *is* the bearer token | no — exchange it first via `destinelab.DEDLServiceAccountAuth(...).get_token()` |
#
# So a DEDL API key pasted into `~/.polytopeapirc` as `user_key` returns
# **401 authentication failed**: it is scoped to a different service, and a raw
# client secret is not a bearer token until it has been exchanged. `destinelab`
# has no DESP service-account path at all — `DESPAuth` is username/password only
# — so there is no route from a DEDL API key to Polytope.
#
# To get the credential this notebook needs:
#
# ```bash
# pip install --upgrade polytope-client lxml conflator
# curl -sO https://raw.githubusercontent.com/destination-earth-digital-twins/polytope-examples/main/desp-authentication.py
# python desp-authentication.py          # prompts for DESP username + password
# ```
#
# It writes `{"user_key": "<offline token>"}` to `~/.polytopeapirc`. Then
# `pixi run check-destine` proves the whole path with one tiny request.
#
# - **Where to get an account:** <https://platform.destine.eu/>.
# - **Authentication is not authorisation.** The account also needs the
#   Destination Earth Data Lake entitlement for the `destination-earth`
#   collection. A key that authenticates can still be refused the data, so a
#   found credential means "worth attempting", not "will succeed" — the cell
#   below reports which credential was found, and the first request is what
#   proves entitlement.
# - **Quotas:** 50 requests/second, and at most **5 concurrent downloads**. This
#   notebook fetches one year at a time, serially, so it stays inside both.
# - **In CI:** there is no secret for this. CI runs the pipeline on the
#   synthetic stand-in described below, which is a smoke test, not a result.
#
# ## Without credentials
#
# If no token is found, this notebook writes a **synthetic** dataset with the
# same schema (`scripts/synthetic_climatedt.py`) so that notebooks 02–04 still
# execute. Every file it writes carries `provenance = "synthetic"`, and that
# stamp is propagated all the way to `results/claim_test.json` and printed
# across the figure. A synthetic number must never reach the FORRT Outcome.

# %%
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("../scripts").resolve()))

import climatedt  # noqa: E402
import synthetic_climatedt  # noqa: E402

RAW_DIR = Path("../data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## The requests
#
# Printed in full before anything is fetched. These are the exact dictionaries
# sent to Polytope; they are the retrieval's provenance and are stored next to
# the data in `data/raw/sources.json`.

# %%
one_request = climatedt.clte_polygon_request("ssp370", 2030)
print(json.dumps({k: v for k, v in one_request.items() if k != "feature"}, indent=2))
print(
    f"feature: polygon with {len(one_request['feature']['shape'])} vertices "
    f"(Germany, see data/germany_polygon.json)"
)

# %%
for window, spec in climatedt.WINDOWS.items():
    first, last = spec["years"]
    print(f"{window:8s} {spec['label']:24s} {last - first + 1} years x 8760 hours")
print(f"\ndurations to be derived in 02: {climatedt.DURATIONS_H} hours")
print(f"return periods to be estimated in 03: {climatedt.RETURN_PERIODS_Y} years")

# %% [markdown]
# ## Retrieval
#
# One request per (window, calendar year). Yearly files keep each NetCDF around
# 300 MB — comfortably under the 2 GB point where `DOMAIN.md` switches to Zarr —
# and make the retrieval restartable: an interrupted run resumes at the first
# missing year instead of starting over.

# %%
HAVE_DESTINE = climatedt.have_credentials()
print(f"credential found : {climatedt.credential_source() or 'none'}")
print(f"will attempt Polytope: {HAVE_DESTINE}")
print(f"endpoint         : {climatedt.POLYTOPE_ADDRESS}")


# %%
def fetch_year(window: str, year: int) -> Path:
    """Retrieve one calendar year of hourly tp over Germany into a NetCDF file."""
    out = RAW_DIR / f"tp_{window}_{year}.nc"
    if out.exists():
        print(f"  [cached] {out.name}")
        return out
    request = climatedt.clte_polygon_request(window, year)
    covjson = RAW_DIR / f"tp_{window}_{year}.covjson"
    print(f"  [fetch] {window} {year} ...")
    data = climatedt.retrieve(request, covjson)
    ds = data.to_xarray()
    ds.attrs.update(
        provenance="destine-climate-dt",
        window=window,
        window_label=climatedt.WINDOWS[window]["label"],
        year=year,
        polytope_address=climatedt.POLYTOPE_ADDRESS,
        request=json.dumps({k: v for k, v in request.items() if k != "feature"}),
        polygon=json.dumps(climatedt.polygon_provenance()),
    )
    ds.to_netcdf(out)
    covjson.unlink(missing_ok=True)
    print(f"    -> {out.name} ({out.stat().st_size / 1e6:.0f} MB)")
    return out


# %%
written: list[Path] = []
if HAVE_DESTINE:
    for window, spec in climatedt.WINDOWS.items():
        first, last = spec["years"]
        print(f"{window} ({spec['label']}):")
        for year in range(first, last + 1):
            written.append(fetch_year(window, year))
else:
    print(
        "No DestinE credentials — writing the SYNTHETIC stand-in instead.\n"
        "Notebooks 02-04 will run, and every artefact they produce will be\n"
        "stamped provenance=synthetic. This is a smoke test, not a result."
    )
    written = synthetic_climatedt.write_all(RAW_DIR)
    for p in written:
        print(f"  wrote {p.name}")

# %% [markdown]
# ## Global mean temperature, for the per-degree normalisation
#
# The claim under test is about the *ordering* of changes across durations and
# return periods, which needs no temperature at all. The warming level is used
# only to express the magnitude as "% per degree", so that it can be compared
# with the original paper's reported figure. Requested from the monthly (`clmn`)
# stream at `standard` resolution: a global mean does not need 6 km cells.
#
# HEALPix cells are equal-area by construction, so the global mean is the plain
# unweighted mean over cells — no cosine-latitude weighting, and no ellipsoidal
# area weights either, since the authalic HEALPix definition preserves area on
# the WGS84 ellipsoid too.

# %%
def fetch_warming_levels() -> Path:
    """Global-mean 2 m temperature per window, from the clmn monthly stream."""
    import numpy as np
    import xarray as xr

    out = RAW_DIR / "warming_levels.json"
    if out.exists():
        print(f"  [cached] {out.name}")
        return out
    gmst = {}
    for window, spec in climatedt.WINDOWS.items():
        first, last = spec["years"]
        yearly = []
        for year in range(first, last + 1):
            grib = RAW_DIR / f"avg2t_{window}_{year}.grib"
            if not grib.exists():
                climatedt.retrieve(climatedt.clmn_global_request(window, year), grib)
            ds = xr.open_dataset(grib, engine="cfgrib")
            name = [v for v in ds.data_vars][0]
            yearly.append(float(ds[name].mean().values))
            ds.close()
        gmst[window] = float(np.mean(yearly))
        print(f"  {window}: global mean 2t = {gmst[window]:.3f} K over {last - first + 1} years")
    with open(out, "w") as f:
        json.dump({"provenance": "destine-climate-dt", "gmst_k": gmst}, f, indent=2)
    return out


if HAVE_DESTINE:
    fetch_warming_levels()

# %% [markdown]
# ## Source log

# %%
SOURCES = [
    {
        "name": "Destination Earth Climate DT (generation 2), hourly total precipitation over Germany",
        "doi": None,
        "url": "https://platform.destine.eu/climate-dt/",
        "access": f"Polytope feature extraction at {climatedt.POLYTOPE_ADDRESS}",
        "licence": "Destination Earth Data Lake terms; DESP account required",
        "accessed_on": "2026-09-06",
        "model": climatedt.MODEL,
        "generation": climatedt.GENERATION,
        "resolution": climatedt.RESOLUTION_HIGH,
        "windows": {w: s["label"] for w, s in climatedt.WINDOWS.items()},
        "provenance": "destine-climate-dt" if HAVE_DESTINE else "synthetic",
    },
    {
        "name": "Germany boundary polygon",
        **climatedt.polygon_provenance()["source"],
        "processing": climatedt.polygon_provenance()["processing"],
    },
]

with open(RAW_DIR / "sources.json", "w") as f:
    json.dump({"sources": SOURCES}, f, indent=2)

print(f"Logged {len(SOURCES)} source(s) to {RAW_DIR / 'sources.json'}")
print(f"Wrote {len(written)} file(s) into {RAW_DIR}")
