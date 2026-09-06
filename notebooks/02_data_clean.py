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
# # 02 — Data clean
#
# This notebook tidies the raw data from `data/raw/` into an analysis-ready
# format in `data/clean/`. Document every transformation: filters, renames,
# joins, deduplications, projections, etc. The cleaned data is what the
# analysis notebook consumes.

# %%
from pathlib import Path

import pandas as pd

# %%
RAW_DIR = Path("../data/raw")
CLEAN_DIR = Path("../data/clean")
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Load raw data

# %%
# Replace with your actual file(s):
# raw = pd.read_csv(RAW_DIR / "dataset.csv")
# Or for NetCDF: ds = xr.open_dataset(RAW_DIR / "dataset.nc")
raw = None

# %% [markdown]
# ## Apply cleaning steps
#
# Document each step. Common patterns:
#
# - Filter by date range, region, or quality flag.
# - Rename columns to a stable schema.
# - Coerce dtypes.
# - Drop or impute missing values, with a recorded count.
# - Join external lookup tables (e.g. species → genus).

# %%
# Example skeleton:
# clean = (
#     raw
#     .pipe(lambda df: df[df["year"].between(2000, 2020)])
#     .rename(columns={"raw_col": "clean_col"})
#     .dropna(subset=["clean_col"])
# )

# %% [markdown]
# ## Persist clean data

# %%
# Example: clean.to_parquet(CLEAN_DIR / "dataset.parquet")
# print(f"Wrote {len(clean):,} rows to {CLEAN_DIR / 'dataset.parquet'}")
