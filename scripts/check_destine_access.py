"""Does this machine's DestinE key actually reach the Climate DT data?

    pixi run check-destine

Answers the two separate questions that a credential raises, in order, because
they fail differently and the fix is different:

  1. **Authentication** -- will `polytope-client` find a key, and will the
     service accept it? A key alone is sent as `Bearer <key>`; a key with an
     email as `EmailKey <email>:<key>`. Both are valid.
  2. **Authorisation** -- is this account entitled to the `destination-earth`
     collection and to generation-2 Climate DT? An account can authenticate
     perfectly and still be refused the data.

The probe is deliberately the cheapest request the archive can answer: one
variable, one hour, one day, one point, at `standard` resolution. It proves the
path end to end without pulling anything. If it succeeds, the real retrieval in
notebooks/01_data_download.py differs only in scale.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import climatedt  # noqa: E402

# Somewhere in the study domain, so a success also confirms the domain is
# covered by the archive.
PROBE_POINT = (51.05, 13.74)  # Dresden


def probe_request() -> dict:
    """One hour, one day, one point -- the smallest thing worth asking for."""
    first_year = climatedt.WINDOWS["ssp370"]["years"][0]
    return {
        "activity": "projections",
        "class": "d1",
        "dataset": "climate-dt",
        "experiment": "SSP3-7.0",
        "generation": climatedt.GENERATION,
        "expver": climatedt.EXPVER,
        "model": climatedt.MODEL,
        "realization": climatedt.REALIZATION,
        "resolution": climatedt.RESOLUTION_STANDARD,
        "stream": "clte",
        "type": "fc",
        "levtype": "sfc",
        "param": climatedt.PARAM_TP,
        "date": f"{first_year}0102",
        "time": "0000",
        "feature": {
            "type": "timeseries",
            "points": [[PROBE_POINT[0], PROBE_POINT[1]]],
            "time_axis": "date",
        },
    }


def describe_key() -> str:
    """Guess which KIND of credential is present, without printing it.

    DestinE issues two things people both call "an API key", and they are for
    different services:

      * a **DESP offline token** -- minted from a DESP username/password by
        `desp-authentication.py` against auth.destine.eu (realm `desp`, client
        `polytope-api-public`). Long, usually a JWT. This is what Polytope
        wants, and it goes into ~/.polytopeapirc alone.
      * a **DEDL API key** -- an OAuth2 *client-credentials pair* (client id +
        secret) generated in "My DataLake Services". The secret is short and
        opaque. It is issued for the DEDL realm with audience `hda-public`, so
        it authenticates the **HDA** API, not Polytope -- and it must be
        EXCHANGED for an access token first
        (`destinelab.DEDLServiceAccountAuth(...).get_token()`). A raw client
        secret can never work as a bearer token, which is exactly the 401 you
        get for pasting one in here.

    Length is only a hint, so this reports a suspicion, never a verdict -- the
    live request below is the verdict.
    """
    key_path = Path(os.environ.get("POLYTOPE_KEY_PATH") or Path.home() / ".polytopeapirc")
    if os.environ.get("POLYTOPE_USER_KEY"):
        key, email = os.environ["POLYTOPE_USER_KEY"], os.environ.get("POLYTOPE_USER_EMAIL")
    elif key_path.exists():
        info = json.loads(key_path.read_text())
        key, email = info.get("user_key", ""), info.get("user_email")
    else:
        ecmwf = json.loads((Path.home() / ".ecmwfapirc").read_text())
        key, email = ecmwf.get("key", ""), ecmwf.get("email")

    how = f"EmailKey {email}:<key>" if key and email else "Bearer <key>"
    note = f"  {len(key)} characters, sent as `{how}`"
    if email:
        return note + "\n  paired with an email, so this is the ECMWF-API-key style."
    if key.count(".") == 2 or len(key) > 200:
        return note + "\n  long/JWT-shaped: consistent with a DESP offline token. Good."
    return (
        note
        + "\n  SHORT and opaque. That is the shape of a DEDL API key's client SECRET,"
        "\n  which belongs to the HDA API, not Polytope -- and which has to be"
        "\n  exchanged for an access token before it is a bearer credential at all."
        "\n  Polytope wants the DESP offline token from `desp-authentication.py`."
        "\n  If the live request below returns 401, that is almost certainly why."
    )


def main() -> int:
    print("--- 1. credential discovery ---")
    source = climatedt.credential_source()
    if source is None:
        print("  NO CREDENTIAL FOUND.")
        print("  polytope-client looks, in order, at:")
        print("    POLYTOPE_USER_KEY in the environment")
        print("    ~/.polytopeapirc      {\"user_key\": \"<key>\"[, \"user_email\": ...]}")
        print("    ~/.ecmwfapirc         {\"key\": \"<key>\", \"email\": \"<email>\"}")
        print("  A DESP key goes in the second file, alone -- it is a bearer token.")
        return 1
    print(f"  found: {source}")
    print(describe_key())

    print("\n--- 2. client import ---")
    try:
        import earthkit.data  # noqa: F401
    except ImportError as exc:
        print(f"  earthkit-data is not importable: {exc}")
        print("  run `pixi install` (it is declared in pixi.toml).")
        return 1
    print("  earthkit-data importable")

    print("\n--- 3. one tiny live request ---")
    request = probe_request()
    print(f"  endpoint: {climatedt.POLYTOPE_ADDRESS}")
    print(f"  {ffmt(request)}")
    out = Path("data/raw/_access_probe.covjson")
    try:
        data = climatedt.retrieve(request, out)
        ds = data.to_xarray()
    except Exception as exc:
        # polytope-client logs the server's own message to stderr before
        # raising, so print ours to stderr too — otherwise the two halves of the
        # same failure land in different streams and read out of order.
        print("\n  REQUEST FAILED:", file=sys.stderr)
        print(f"  {type(exc).__name__}: {exc}\n", file=sys.stderr)
        traceback.print_exc()
        print(
            "\n  What the response code means here — the wording above is the\n"
            "  authority, these are the usual cases:\n"
            "    401 'authentication failed'  -> the KEY. Polytope never got past\n"
            "        the front door. A DESP offline token can be revoked or\n"
            "        expired; mint a fresh one. Check too that the key is in the\n"
            "        right file under the right name: a DESP token is a BEARER\n"
            "        token and must sit alone as {\"user_key\": ...}, while an\n"
            "        ECMWF key needs its \"user_email\" alongside it.\n"
            "    403 / 'not authorised for'   -> the ENTITLEMENT. The key is\n"
            "        fine and this account is not cleared for the collection.\n"
            "        Request access at platform.destine.eu; a new key will not\n"
            "        help.\n"
            "    'no data found' / MARS error -> the key and entitlement are\n"
            "        fine and a REQUEST KEY is wrong. Check generation, activity\n"
            "        and experiment against the polytope-examples notebooks\n"
            "        before touching anything else.",
            file=sys.stderr,
        )
        return 1

    print("\n  SUCCESS. Returned:")
    print(f"    variables: {list(ds.data_vars)}")
    print(f"    dims     : {dict(ds.sizes)}")
    print(
        "\n  Authentication AND authorisation are both fine. "
        "notebooks/01_data_download.py will retrieve for real."
    )
    out.unlink(missing_ok=True)
    return 0


def ffmt(request: dict) -> str:
    """The request on one line, with the feature summarised."""
    parts = [f"{k}={v}" for k, v in request.items() if k != "feature"]
    return " ".join(parts) + f" feature={request['feature']['type']}"


if __name__ == "__main__":
    raise SystemExit(main())
