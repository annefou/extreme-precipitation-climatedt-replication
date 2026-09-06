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
# # 04 — Figures
#
# This notebook produces the figures used in the Jupyter Book. Each figure is
# saved to `figures/` as a high-DPI PNG **and** displayed inline (so MyST
# renders the figure inside the Jupyter Book — see
# `docs/cicd-conventions.md`).
#
# **Inline display rule:** always pair `fig.savefig(...)` with `plt.show()`.
# Without `plt.show()`, MyST builds an empty cell. Don't use
# `matplotlib.use('Agg')` — it blocks inline display.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# %%
RESULTS_DIR = Path("../results")
FIGURES_DIR = Path("../figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Main result figure

# %%
# summary = pd.read_csv(RESULTS_DIR / "summary.csv")

# fig, ax = plt.subplots(figsize=(8, 5))
# ax.bar(summary["metric"], summary["value"])
# ax.set_title("Replication headline result")
# ax.set_ylabel("Value")
# fig.tight_layout()
#
# fig.savefig(FIGURES_DIR / "main_result.png", dpi=150, bbox_inches="tight")
# plt.show()  # required for MyST inline display
