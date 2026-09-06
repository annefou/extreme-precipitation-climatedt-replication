"""The Climate DT retrieval loop, as a module and as a CLI.

    pixi run retrieve                 # everything, both windows
    pixi run retrieve -- --window hist --workers 4

Lives here rather than inside `notebooks/01_data_download.py` because the real
retrieval takes hours: it has to survive a closed laptop, and a notebook kernel
held open for that long is a liability. The notebook imports `fetch_month` from
this module, so the two cannot drift apart, and because every month is cached on
disk, re-running the notebook afterwards is near-instant and still produces the
executed `.ipynb` the Jupyter Book needs.

Restartable by construction: one NetCDF per (window, year, month), and an
existing file is skipped. Kill it and start it again and it resumes.
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import climatedt  # noqa: E402

# Polytope's DestinE quota is 5 concurrent downloads. Four leaves room for the
# interactive `check-destine` probe to run alongside a long retrieval without
# either of them queueing behind the other.
DEFAULT_WORKERS = 4

# Transient failures happen over hours of requests: a dropped connection, a
# server-side hiccup. Retry a few times with a growing pause before giving up
# on a month; a permanent problem (bad key, wrong request) fails all attempts
# fast and the traceback still surfaces.
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 20


def month_path(raw_dir: Path, window: str, year: int, month: int) -> Path:
    return raw_dir / f"precip_{window}_{year}{month:02d}.nc"


def all_months(windows: list[str] | None = None) -> list[tuple[str, int, int]]:
    """Every (window, year, month) the study needs, in chronological order."""
    out = []
    for window in windows or list(climatedt.WINDOWS):
        first, last = climatedt.WINDOWS[window]["years"]
        for year in range(first, last + 1):
            out += [(window, year, month) for month in range(1, 13)]
    return out


def fetch_month(window: str, year: int, month: int, raw_dir: Path) -> Path:
    """One calendar month of hourly precipitation over Germany, as NetCDF.

    Cached: returns immediately if the file already exists.
    """
    out = month_path(raw_dir, window, year, month)
    if out.exists():
        return out

    request = climatedt.clte_polygon_request(window, year, month)
    ds = climatedt.to_study_schema(climatedt.retrieve(request).to_xarray())

    # The silent under-fetch guard. Polytope accepts a `/to/../by/..` range for
    # `time` and then returns only the FIRST hour, with no error -- verified
    # live. Counting what arrived against what the calendar says is the only
    # thing standing between that and annual maxima computed from one hour a
    # day, in a pipeline that would otherwise look entirely healthy.
    expected = calendar.monthrange(year, month)[1] * len(climatedt.ALL_HOURS.split("/"))
    got = ds.sizes.get("time", 0)
    if got != expected:
        raise RuntimeError(
            f"{window} {year}-{month:02d}: expected {expected} hourly fields, got "
            f"{got}. Check that `time` is an explicit hour list, not a range."
        )

    ds.attrs.update(
        provenance="destine-climate-dt",
        window=window,
        window_label=climatedt.WINDOWS[window]["label"],
        year=year,
        month=month,
        polytope_address=climatedt.POLYTOPE_ADDRESS,
        request=json.dumps({k: v for k, v in request.items() if k != "feature"}),
        polygon=json.dumps(climatedt.polygon_provenance()),
    )
    # Write to a temporary name and rename, so an interrupted run never leaves a
    # truncated NetCDF that the next run would happily treat as cached.
    partial = out.with_suffix(".nc.partial")
    ds.to_netcdf(partial)
    partial.rename(out)
    return out


def fetch_with_retries(window: str, year: int, month: int, raw_dir: Path) -> Path:
    last: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fetch_month(window, year, month, raw_dir)
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            last = exc
            if attempt < MAX_ATTEMPTS:
                pause = BACKOFF_SECONDS * attempt
                print(
                    f"  ! {window} {year}-{month:02d} attempt {attempt} failed "
                    f"({type(exc).__name__}: {str(exc)[:120]}); retrying in {pause}s",
                    flush=True,
                )
                time.sleep(pause)
    raise RuntimeError(f"{window} {year}-{month:02d} failed after {MAX_ATTEMPTS} attempts") from last


def retrieve_all(raw_dir: Path, windows: list[str] | None = None, workers: int = DEFAULT_WORKERS):
    """Fetch every missing month, `workers` at a time. Returns (done, failed)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    wanted = all_months(windows)
    todo = [t for t in wanted if not month_path(raw_dir, *t).exists()]
    print(
        f"{len(wanted)} months wanted, {len(wanted) - len(todo)} already on disk, "
        f"{len(todo)} to fetch with {workers} worker(s)",
        flush=True,
    )
    if not todo:
        return [month_path(raw_dir, *t) for t in wanted], []

    started = time.time()
    done: list[Path] = []
    failed: list[tuple[str, int, int, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_with_retries, w, y, m, raw_dir): (w, y, m) for w, y, m in todo
        }
        for i, future in enumerate(as_completed(futures), start=1):
            window, year, month = futures[future]
            try:
                path = future.result()
            except Exception as exc:  # noqa: BLE001 - recorded, run continues
                failed.append((window, year, month, str(exc)[:200]))
                print(f"[{i}/{len(todo)}] FAILED {window} {year}-{month:02d}", flush=True)
                continue
            done.append(path)
            elapsed = time.time() - started
            eta = elapsed / i * (len(todo) - i)
            size_mb = path.stat().st_size / 1e6
            print(
                f"[{i}/{len(todo)}] {window} {year}-{month:02d}  {size_mb:5.0f} MB  "
                f"elapsed {elapsed / 3600:.2f} h  eta {eta / 3600:.2f} h",
                flush=True,
            )
    return done, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default="data/raw", type=Path)
    parser.add_argument("--window", action="append", choices=list(climatedt.WINDOWS))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    if not climatedt.have_credentials():
        print("No DestinE credential found. Run `pixi run check-destine` for details.")
        return 1
    print(f"credential: {climatedt.credential_source()}")
    print(f"endpoint  : {climatedt.POLYTOPE_ADDRESS}")
    print(f"started   : {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    done, failed = retrieve_all(args.raw_dir, args.window, args.workers)
    print(f"\nfinished  : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{len(done)} month(s) fetched this run, {len(failed)} failed")
    for window, year, month, message in failed:
        print(f"  FAILED {window} {year}-{month:02d}: {message}")
    # Re-running picks up exactly the months that failed, so a partial run is a
    # resume point rather than a restart.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
