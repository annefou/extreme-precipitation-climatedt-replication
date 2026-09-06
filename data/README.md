# `data/` — downloaded artefacts, never committed

This directory holds the raw and cleaned datasets used by the replication pipeline. **Files in this directory are never committed to git** (`.gitignore` excludes everything except this README).

## Why download-on-first-run

Every replication must be self-contained: a user clones the repo and runs `snakemake --cores 1` (or executes notebook 01 directly), and the code fetches its own input data. No "ask the author for the dataset" steps; no folder-of-CSVs that drift out of sync with the analysis.

## Where data comes from

The first notebook (`notebooks/01_data_download.py`) is responsible for fetching all inputs. Common patterns:

- **Zenodo** — `requests.get(...)` against the record's file URL.
- **GBIF** — `pygbif` to issue an occurrence download, mint a download DOI, and pin it in the notebook output.
- **Copernicus Climate Data Store** — `cdsapi`, with credentials in `~/.cdsapirc`.
- **Copernicus Marine Service** — `copernicusmarine`, with credentials at `~/.copernicusmarine/.copernicusmarine-credentials` (created from secrets in CI; `copernicusmarine login` is interactive only).
- **Destination Earth** — `polytope-client` or `earthkit-data`, with DestinE Data Lake credentials.
- **Direct URLs** — figshare, paper supplementary materials.

For each dataset, record in the notebook:
1. The exact URL or query.
2. The DOI of the dataset (or the download DOI minted at fetch time).
3. The license under which it is reused.
4. Any preprocessing applied before the cleaned artefact lands in `data/clean/`.

## Required credentials

If your replication uses a credentialled API, document the credential setup at the top of `notebooks/01_data_download.py`, including:

- Where the user gets the credential (URL).
- Where it lives on disk (or which env var Claude expects).
- The corresponding GitHub Actions secret name(s) for CI.

## CI cache

Large downloads (>100 MB) should be cached in GitHub Actions via `actions/cache@v4`. See `.github/workflows/ci.yml` for the pattern.
