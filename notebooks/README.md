# `notebooks/` — the replication pipeline

The replication is implemented as a sequence of jupytext-paired notebooks. The `.py` files are the **source of truth** (committed); the `.ipynb` files are gitignored regenerable artefacts.

## Convention

- Each notebook is a Python file with jupytext markers (`# %%` for code cells, `# %% [markdown]` for markdown cells).
- The Snakefile orchestrates them in order; you can also run them manually with `jupytext --to notebook --execute <file>.py`.
- The numbered prefix (01, 02, 03, 04) defines the pipeline order. Don't break the ordering — downstream notebooks read upstream notebooks' outputs.

## The four notebooks in this study

| File | Role |
|---|---|
| `01_data_download.py` | Retrieves hourly total precipitation over Germany from the DestinE Climate DT (generation 2, IFS-NEMO, SSP3-7.0) via Polytope's server-side polygon feature, one calendar year per file, for a historical and a scenario window. Writes to `data/raw/`. |
| `02_data_clean.py` | Forms 1/3/6/12/24-hour accumulations and reduces them to annual maxima per cell. Writes `data/clean/annual_maxima.nc`. |
| `03_analysis.py` | Fits a pooled index-flood GEV per (window, duration), computes return levels for 2/5/10/20 years, and tests the ordering the paper's claim predicts. Writes to `results/`. |
| `04_figures.py` | Draws the duration × return-period change matrix and the ordering tests. Writes to `figures/`. |

### Where the logic actually lives

The notebooks are thin: they do I/O, print what they read, and call into
`scripts/`. Everything with a right and a wrong answer is a plain module with
tests, because a rendered notebook cell is not evidence that a calculation is
correct.

| Module | What it owns | Tested by |
|---|---|---|
| `scripts/climatedt.py` | Polytope request shapes, the two analysis windows, the duration and return-period grids | `tests/test_climatedt.py` |
| `scripts/extremes.py` | Rolling accumulation, annual maxima, L-moment GEV, index-flood pooling, bootstrap | `tests/test_extremes.py` (against `scipy.stats.genextreme`) |
| `scripts/geometry.py` | Authalic latitude, point-in-polygon, the domain-mask sensitivity check | `tests/test_climatedt.py` |
| `scripts/synthetic_climatedt.py` | The offline stand-in for the retrieval | `tests/test_pipeline.py` |

### Running without DestinE credentials

`01_data_download.py` needs a Destination Earth Data Lake account. Without one
it writes a **synthetic** dataset with the same schema so that 02–04 still
execute — that is how CI runs, and how `snakemake --cores 1` completes on a
fresh clone. Every artefact produced that way is stamped `provenance=synthetic`,
`results/claim_test.json` records it, and the figures say so across their face.
A synthetic number must never reach the FORRT Outcome.

For more complex replications, add notebooks `05_…`, `06_…`, etc., and update the Snakefile and `myst.yml` TOC accordingly. Keep each notebook focused on one stage.

## Adding a new notebook

When you add a notebook:

1. Write the jupytext `.py` file in this directory.
2. Add it to `myst.yml` TOC as `notebooks/0X_….ipynb` (note: `.ipynb`, not `.py`; MyST cannot process `.py`).
3. Add a Snakefile rule that wraps it.
4. The `.github/workflows/jupyter-book.yml` "Execute notebooks" step uses a glob (`notebooks/*.ipynb`), so new notebooks are picked up automatically — no workflow edit needed.
5. Add every import in the new notebook to `pixi.toml`, then `pixi install` and commit the refreshed `pixi.lock`.

## Anti-patterns

- **Don't use `matplotlib.use('Agg')`** — blocks inline display, breaks the Jupyter Book.
- **Don't write absolute paths** — use repo-relative paths so the notebook runs in `docker run`, in CI, and locally.
- **Don't assume data exists locally** — every notebook should fetch what it needs, or fail early with a clear message pointing to `01_data_download.py`.
- **Don't claim a notebook works without running it** — see `docs/verify-before-drafting.md`.
