# `data/`

:::{attention} Destination Earth data attribution
This data is created based on data of the European Union, using the Destination Earth Platform, but has been modified by Anne Fouilloux.
:::

## What is shared, what is not, and why

The Destination Earth Terms and Conditions v2.0 (8 July 2025) draw a sharp line,
and this repository is built to sit on the right side of it.

| | Shared here? | Governing article |
|---|---|---|
| Hourly Climate DT retrieval (`raw/`, ~23 GB) | **No** — gitignored, never committed | Art. 2.5 forbids forwarding DestinE Data to third parties without written consent of the European Commission |
| Annual maxima (`clean/annual_maxima*.nc`, 14 MB) | Yes | Art. 3.3: IPR in data the User creates from DestinE Data is owned by the User |
| Return levels, GEV fits, change matrices (`../results/`) | Yes | as above |
| Figures (`../figures/`) | Yes | as above |

### Why the shared files satisfy Article 2.3

> "The User may only create and distribute services/applications/tools/data from
> which the original DestinE Data cannot be retrieved or reverse engineered."

The shared files are an aggregation and transformation of the hourly input, and
the original cannot be recovered from them:

- **Reduction of about 1,750:1.** Each 20-year window is 175,200 hourly fields
  over 8,697 cells — roughly 1.5 billion values. What is shared is 5 durations ×
  20 years × 8,697 cells = 870,000 annual maxima.
- **The time index is gone.** An annual maximum records *how much* fell, never
  *when*. There is no way to place a value back into the hourly series, and no
  way to recover the 8,759 hours of each year that were not the maximum.
- **Only the 1-hour maxima are original values at all.** The 3, 6, 12 and 24-hour
  figures are sums of consecutive hours — transformed, not reproduced. The 1-hour
  maxima do reproduce individual original values exactly, but they are about
  **0.011 %** of the hourly data and only its annual extremes.
- **Return levels are further removed still.** They are parameters of a GEV
  fitted to pooled, index-flood-standardised maxima; no input value survives.

### Why share these at all

Because a replication that cannot be checked is not a replication. With these
files a reader can rerun notebooks 03 and 04 and reproduce every number in the
study — the return-level matrix, the ordering tests, the verdict — **without a
DestinE account**, and can verify or challenge the conclusion independently. The
Jupyter Book is built from them, so the published result is the real one rather
than a smoke test. The hourly input remains behind DestinE's access control,
where the terms require it; reproducing the retrieval itself needs your own DESP
account (see the repository README).

This is the ordinary FAIR position for licensed source data: share the derived,
citable artefact and the code that made it; point at the source for the rest.

### Attribution

Required by Art. 3.4, which specifies both the wording and that it be displayed
prominently and co-located with the data. It appears in `index.md`, in
`CITATION.cff`, on the headline figure, in `results/claim_test.json`, and as
`attribution` / `licence_note` attributes inside **every** NetCDF file this
pipeline writes — so it survives a file being downloaded on its own. Art. 3.4
also requires that derived data never be presented as original DestinE Data;
`licence_note` states that explicitly in each file.

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
