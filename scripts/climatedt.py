"""Destination Earth Climate DT retrieval: request builders and provenance.

Split out of notebooks/01_data_download.py so the request shapes can be tested
offline (tests/test_climatedt.py). Nothing here touches the network unless
`retrieve()` is called.

Every key below is copied from the official examples in
https://github.com/destination-earth-digital-twins/polytope-examples
(`climate-dt/feature-extraction/`, read 2026-09-06), not recalled:

  * generation "2" is the 1990-2049 multi-decadal set at ~5 km hourly,
    harmonised on HEALPix -- the one this study needs. Generation 1 is the
    older 2020-2050 set and uses `activity: ScenarioMIP`.
  * The historical period and the scenario period are two different
    (activity, experiment) pairs: `baseline`/`hist` and `projections`/`SSP3-7.0`.
  * The Polytope endpoint moved to MareNostrum5; the LUMI address in older
    notebooks is generation 1.
  * MARS cannot crop a HEALPix field with a lat/lon box, so a domain study
    either downloads the globe or uses Polytope's server-side feature
    extraction. This module uses the `polygon` feature, which is what makes
    20 years of hourly data over Germany tractable at all.
"""

from __future__ import annotations

import calendar
import json
import os
from pathlib import Path
from typing import Any

POLYTOPE_COLLECTION = "destination-earth"
POLYTOPE_ADDRESS = "polytope.mn5.apps.dte.destination-earth.eu"

# One coupled model, one realization. The original paper used a multi-member
# RCM ensemble; using a single Climate DT member is a deviation to record in
# the Replication Study, not something to paper over.
MODEL = "IFS-NEMO"
REALIZATION = "1"
GENERATION = "2"
EXPVER = "0001"

# 'high' is the native HEALPix delivery closest to the model grid: level 10
# (nside=1024, ~6.3 km). 'standard' is coarser. The paper's COSMO-CLM ensemble
# ran at 2.8 km, so 'high' is the closest the Climate DT gets.
RESOLUTION_HIGH = "high"
RESOLUTION_STANDARD = "standard"

# Precipitation in the hourly (clte) surface stream is `avg_tprate`, NOT `tp`.
# Verified live: `param=tp` and `param=228` are both refused with HTTP 400, and
# the Climate DT README's CLTE table puts precipitation in the 20 "sfc (hourly
# mean)" flux variables, which keep the `avg_` prefix. So what the archive
# offers is an hourly-mean RATE, not an accumulation -- units kg m-2 s-1,
# confirmed from the returned field's own metadata. Multiply by 3600 to get the
# millimetres that fell in that hour (see RATE_TO_MM_PER_HOUR).
PARAM_PRECIP = "avg_tprate"
PRECIP_UNITS = "kg m**-2 s**-1"
# An hourly-mean rate in kg m-2 s-1 is mm/s; one hour is 3600 s, and 1 kg m-2
# of water is 1 mm depth.
RATE_TO_MM_PER_HOUR = 3600.0

# Monthly-mean 2 m temperature in the monthly (clmn) stream, used only to
# express the change per degree of warming.
PARAM_AVG_2T = "avg_2t"

# EVERY HOUR, ENUMERATED. Do not "simplify" this to "0000/to/2300/by/0100".
# Feature-extraction requests accept the /to/../by/.. range syntax for `date`
# but NOT for `time`: with a range, the service returns the FIRST hour only and
# reports no error at all. Verified live -- an identical request returned 1
# datetime with the range and 24 with this list. That silent 24x under-fetch
# would have produced annual maxima computed from one hour per day, and a
# pipeline that looked entirely healthy while doing it.
ALL_HOURS = "/".join(f"{hour:02d}00" for hour in range(24))
ALL_MONTHS = "1/2/3/4/5/6/7/8/9/10/11/12"

# The two analysis windows. Both are 20 years so the two GEV fits rest on the
# same number of annual maxima -- an unequal split would confound the
# comparison with sampling uncertainty.
WINDOWS: dict[str, dict[str, Any]] = {
    "hist": {
        "activity": "baseline",
        "experiment": "hist",
        "years": (1991, 2010),
        "label": "historical 1991-2010",
    },
    "ssp370": {
        "activity": "projections",
        "experiment": "SSP3-7.0",
        "years": (2030, 2049),
        "label": "SSP3-7.0 2030-2049",
    },
}

# Accumulation windows in hours. The paper resolved 15 and 30 minutes from a
# convection-permitting model; the Climate DT archive is hourly, so 1 hour is
# the shortest duration available and that gap is a stated deviation.
DURATIONS_H = (1, 3, 6, 12, 24)

# Return periods in years. Twenty annual maxima per cell, pooled over the
# domain, support 20 years comfortably. The paper went to 100; extrapolating
# that far from 20 years is not defensible here even with pooling.
RETURN_PERIODS_Y = (2.0, 5.0, 10.0, 20.0)

POLYGON_PATH = Path(__file__).resolve().parents[1] / "data" / "germany_polygon.json"


def germany_polygon() -> list[list[float]]:
    """Closed [latitude, longitude] ring for Germany, from the committed file."""
    with open(POLYGON_PATH) as f:
        return json.load(f)["ring"]


def polygon_provenance() -> dict:
    """Everything but the coordinates: source, licence, processing."""
    with open(POLYGON_PATH) as f:
        doc = json.load(f)
    return {k: v for k, v in doc.items() if k != "ring"}


def clte_polygon_request(
    window: str, year: int, month: int, param: str = PARAM_PRECIP
) -> dict:
    """Every hour of one calendar month, clipped to Germany server-side.

    A month is the retrieval chunk. Timed live at `high` resolution over
    Germany (8,697 cells): one day takes ~12 s on its own, a week ~4.4 s/day, a
    month ~2.9 s/day -- so fewer, larger requests win, and a month is where the
    curve flattens. That puts a 20-year window at roughly six hours, and keeps
    each response near 300 MB rather than the ~3.6 GB a whole year would be.
    """
    if window not in WINDOWS:
        raise KeyError(f"unknown window {window!r}; expected one of {sorted(WINDOWS)}")
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")
    spec = WINDOWS[window]
    first, last = spec["years"]
    if not first <= year <= last:
        raise ValueError(f"{year} is outside window {window} ({first}-{last})")
    last_day = calendar.monthrange(year, month)[1]
    return {
        "activity": spec["activity"],
        "class": "d1",
        "dataset": "climate-dt",
        "experiment": spec["experiment"],
        "generation": GENERATION,
        "expver": EXPVER,
        "model": MODEL,
        "realization": REALIZATION,
        "resolution": RESOLUTION_HIGH,
        "stream": "clte",
        "type": "fc",
        "levtype": "sfc",
        "param": param,
        "date": f"{year}{month:02d}01/to/{year}{month:02d}{last_day:02d}",
        "time": ALL_HOURS,
        "feature": {"type": "polygon", "shape": germany_polygon()},
    }


def clmn_global_request(window: str, year: int, param: str = PARAM_AVG_2T) -> dict:
    """Global monthly means for one year -- the warming-level normalisation.

    No `feature`, so this is a full field: the change per degree of warming is
    defined against GLOBAL mean temperature, not the domain's own. Requested at
    'standard' resolution because a global mean does not need 6 km cells.
    """
    if window not in WINDOWS:
        raise KeyError(f"unknown window {window!r}; expected one of {sorted(WINDOWS)}")
    spec = WINDOWS[window]
    first, last = spec["years"]
    if not first <= year <= last:
        raise ValueError(f"{year} is outside window {window} ({first}-{last})")
    return {
        "activity": spec["activity"],
        "class": "d1",
        "dataset": "climate-dt",
        "experiment": spec["experiment"],
        "generation": GENERATION,
        "expver": EXPVER,
        "model": MODEL,
        "realization": REALIZATION,
        "resolution": RESOLUTION_STANDARD,
        "stream": "clmn",
        "type": "fc",
        "levtype": "sfc",
        "param": param,
        "year": str(year),
        "month": ALL_MONTHS,
    }


REAL_PROVENANCE = "destine-climate-dt"


def existing_real_artefact(path: Path) -> bool:
    """True if `path` is a NetCDF this pipeline produced from real Climate DT data.

    Used to stop a credential-less run from overwriting committed real results
    with the synthetic stand-in. CI has no DestinE account, so without this the
    published Jupyter Book would rebuild every figure from invented numbers --
    which is exactly what happened before this check existed.
    """
    if not path.exists():
        return False
    try:
        import xarray as xr

        with xr.open_dataset(path) as ds:
            return ds.attrs.get("provenance") == REAL_PROVENANCE
    except Exception:  # noqa: BLE001 - an unreadable file is not a real artefact
        return False


def credential_source() -> str | None:
    """Where polytope-client will find a credential, or None if it will find none.

    Mirrors `polytope/api/Auth.py::fetch_key` and `Config.py`, in their order of
    precedence, so this reports what the client will actually do rather than a
    guess:

      1. `POLYTOPE_USER_KEY` in the environment (every config key is settable as
         `POLYTOPE_<NAME>`), which takes priority over any file.
      2. `~/.polytopeapirc` — `{"user_key": ...}` and optionally `"user_email"`.
         `POLYTOPE_KEY_PATH` moves it.
      3. `~/.ecmwfapirc` — the fallback, with the differently named keys
         `{"key": ..., "email": ...}`.

    A key WITHOUT an email is sent as `Bearer <key>`; a key WITH one is sent as
    `EmailKey <email>:<key>`. Both are valid — `desp-authentication.py` writes
    the first kind — so the presence of an email is not something to warn about.
    """
    if os.environ.get("POLYTOPE_USER_KEY"):
        return "env:POLYTOPE_USER_KEY"
    key_path = Path(os.environ.get("POLYTOPE_KEY_PATH") or Path.home() / ".polytopeapirc")
    if key_path.exists():
        return f"file:{key_path}"
    ecmwf = Path.home() / ".ecmwfapirc"
    if ecmwf.exists():
        return f"file:{ecmwf}"
    return None


def have_credentials() -> bool:
    """True if polytope-client will find a credential to authenticate with.

    Authentication is not authorisation: a DESP account also needs the
    Destination Earth Data Lake entitlement for the `destination-earth`
    collection. A key that authenticates fine can still be refused the data, so
    treat a True here as "worth attempting", not "will succeed".
    """
    return credential_source() is not None


def to_study_schema(ds, param: str = PARAM_PRECIP):
    """Reshape a CoverageJSON-derived dataset into the (time, cell) form 02 reads.

    Polytope's feature extraction hands back `datetimes` x `number` x `steps` x
    `points`, with `latitude`/`longitude`/`levelist` along `points` and the
    datetimes as STRINGS ("2030-01-02 00:00:00Z"). The rest of the pipeline
    wants plain (time, cell) with a real datetime index, so the rename happens
    once, here, rather than in every notebook that touches the data.

    `number` (ensemble member), `steps` and `levelist` are all length 1 for a
    single-realization surface field; they are dropped rather than squeezed
    blindly, so a future multi-member request fails loudly instead of silently
    collapsing members together.
    """
    import numpy as np
    import pandas as pd

    for name, size in (("number", 1), ("steps", 1)):
        if ds.sizes.get(name, 1) != size:
            raise ValueError(
                f"expected {name} to have length 1, got {ds.sizes[name]}; this "
                "reshaping would silently collapse it"
            )
    out = ds[[param]]
    for name in ("number", "steps"):
        if name in out.dims:
            out = out.isel({name: 0}, drop=True)
    for name in ("levelist", "number", "steps"):
        if name in out.coords:
            out = out.drop_vars(name)

    times = pd.to_datetime([str(t) for t in np.ravel(ds["datetimes"].values)], utc=True)
    out = out.rename({"datetimes": "time", "points": "cell"})
    out = out.assign_coords(
        time=times.tz_localize(None),
        cell=np.arange(out.sizes["cell"], dtype="int32"),
    )
    return out.transpose("time", "cell")


def configure_cache(cache_dir: Path, max_size: str = "6G") -> dict:
    """Bound earthkit's download cache, and put it on the data disk.

    This is not a tuning knob, it is a correctness fix. earthkit-data ships with
    `cache-policy = "off"`, which does NOT mean "do not cache": it means cache
    into a temporary directory that is cleaned up only when the process exits.
    Over a long retrieval the CoverageJSON responses therefore accumulate with
    no eviction at all -- roughly 300 MB per month here. A real run filled the
    root filesystem after 50 months (16 GB in /tmp) and every subsequent request
    died with ENOSPC.

    Switching to the `user` policy is what turns eviction on, and gives a
    directory we choose, so the cache can live on the same large disk as the
    data instead of on `/`.

    Returns the resulting settings so a caller can print what it applied.
    """
    from earthkit.data import config

    cache_dir.mkdir(parents=True, exist_ok=True)
    config.set(
        {
            "cache-policy": "user",
            "user-cache-directory": str(cache_dir),
            "maximum-cache-size": max_size,
        }
    )
    return {
        "cache-policy": config.get("cache-policy"),
        "user-cache-directory": config.get("user-cache-directory"),
        "maximum-cache-size": config.get("maximum-cache-size"),
    }


def retrieve(request: dict):
    """Run one Polytope request and return the earthkit source.

    Imported lazily: earthkit/polytope are only needed on the machine that has
    DestinE credentials, and the rest of the pipeline must import this module
    without them.

    Returns the source rather than writing a file. The obvious
    `data.to_target("file", path)` — which the official examples use for GRIB —
    raises `TypeError: a bytes-like object is required, not 'str'` on the
    CoverageJSON a feature-extraction request returns. Callers convert with
    `.to_xarray()` and write NetCDF, which is the archival format this study
    wants anyway (DOMAIN.md § Data formats).
    """
    import earthkit.data

    return earthkit.data.from_source(
        "polytope",
        POLYTOPE_COLLECTION,
        request,
        address=POLYTOPE_ADDRESS,
        stream=False,
    )
