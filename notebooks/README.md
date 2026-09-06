# `notebooks/` — the replication pipeline

The replication is implemented as a sequence of jupytext-paired notebooks. The `.py` files are the **source of truth** (committed); the `.ipynb` files are gitignored regenerable artefacts.

## Convention

- Each notebook is a Python file with jupytext markers (`# %%` for code cells, `# %% [markdown]` for markdown cells).
- The Snakefile orchestrates them in order; you can also run them manually with `jupytext --to notebook --execute <file>.py`.
- The numbered prefix (01, 02, 03, 04) defines the pipeline order. Don't break the ordering — downstream notebooks read upstream notebooks' outputs.

## The four standard notebooks

| File | Role |
|---|---|
| `01_data_download.py` | Fetches all input data (Zenodo, GBIF, Copernicus, etc.). Mints citable DOIs where applicable. Writes to `data/raw/`. |
| `02_data_clean.py` | Tidies the raw data into the analysis-ready format. Writes to `data/clean/`. |
| `03_analysis.py` | Computes the headline statistic. Writes to `results/`. |
| `04_figures.py` | Produces figures for the Jupyter Book. Writes to `figures/`. |

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
