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
# # 03 — Analysis
#
# This notebook computes the headline statistic that the replication tests.
# Write the analysis as a faithful port of the original paper's method, with
# any deviations flagged explicitly in the markdown.
#
# **Verify before drafting nanopubs:** the Replication Study's Methodology
# field and the Outcome's Evidence field will be drafted *from this code* —
# don't extrapolate framework or hyperparameters from memory. See
# `docs/verify-before-drafting.md`.

# %%
from pathlib import Path

import pandas as pd

# %%
CLEAN_DIR = Path("../data/clean")
RESULTS_DIR = Path("../results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Load clean data

# %%
# clean = pd.read_parquet(CLEAN_DIR / "dataset.parquet")

# %% [markdown]
# ## Method (port of paper §X)
#
# Briefly state the method and any deviations from the original paper.
#
# - **Same as paper:** ...
# - **Deviations:** ...

# %%
# Implement the analysis here. Examples:
# - Statistical model fit (statsmodels, bambi, scikit-learn)
# - ML training/evaluation (PyTorch, TensorFlow, scikit-learn)
# - Spatial aggregation + zonal statistics

# %% [markdown]
# ## Persist results

# %%
# Persist a tidy summary that downstream notebooks (and the Outcome
# nanopub draft) can read. Include numerical headlines + uncertainty.
#
# Example:
# summary = pd.DataFrame({
#     "metric": ["coefficient", "p_value", "n"],
#     "value":  [0.4792, 1e-5, 528],
# })
# summary.to_csv(RESULTS_DIR / "summary.csv", index=False)
# print(summary)
