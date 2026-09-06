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

# MARS short name for total precipitation in the hourly (clte) surface stream.
PARAM_TP = "tp"
# Monthly-mean 2 m temperature in the monthly (clmn) stream, used only to
# express the change per degree of warming.
PARAM_AVG_2T = "avg_2t"

ALL_HOURS = "0000/to/2300/by/0100"
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


def clte_polygon_request(window: str, year: int, param: str = PARAM_TP) -> dict:
    """Hourly surface field for one calendar year, clipped to Germany server-side."""
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
        "resolution": RESOLUTION_HIGH,
        "stream": "clte",
        "type": "fc",
        "levtype": "sfc",
        "param": param,
        "date": f"{year}0101/to/{year}1231",
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


def have_credentials() -> bool:
    """True if a DestinE Data Lake token looks available to earthkit/polytope.

    Polytope reads `~/.polytopeapirc`, and the DestinE examples export the
    token as an environment variable after running `desp-authentication.py`.
    Either is enough to attempt a retrieval; neither means we are offline.
    """
    if os.environ.get("POLYTOPE_USER_KEY") or os.environ.get("DESP_ACCESS_TOKEN"):
        return True
    return (Path.home() / ".polytopeapirc").exists()


def retrieve(request: dict, out_path: Path):
    """Run one Polytope request and return the earthkit source.

    Imported lazily: earthkit/polytope are only needed on the machine that has
    DestinE credentials, and the rest of the pipeline must import this module
    without them.
    """
    import earthkit.data

    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = earthkit.data.from_source(
        "polytope",
        POLYTOPE_COLLECTION,
        request,
        address=POLYTOPE_ADDRESS,
        stream=False,
    )
    data.to_target("file", str(out_path))
    return data
