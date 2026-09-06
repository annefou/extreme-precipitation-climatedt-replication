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
# One headline figure, `figures/main_result.png`, in two panels:
#
# * **left** — the change in return level across the duration × return-period
#   matrix. The claim under test says this surface should rise towards the
#   short-duration, long-return-period corner (top right).
# * **right** — the same numbers as lines, one per return period, with the
#   bootstrap 95 % interval, so the ordering can be read against its own
#   uncertainty rather than as a bare colour.
#
# If the input was synthetic, the figure says so across its face. A figure
# outlives the notebook that made it, and this one must never be mistaken for a
# replication result.

# %%
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path("../scripts").resolve()))

RESULTS_DIR = Path("../results")
FIGURES_DIR = Path("../figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
DPI = 150

# %%
summary = pd.read_csv(RESULTS_DIR / "summary.csv")
with open(RESULTS_DIR / "claim_test.json") as f:
    claim_test = json.load(f)

PROVENANCE = claim_test["data_provenance"]
IS_REAL = PROVENANCE == "destine-climate-dt"
durations = sorted(summary["duration_h"].unique())
rps = sorted(summary["return_period_y"].unique())

grid = summary.pivot(index="duration_h", columns="return_period_y", values="change_pct")
lo = summary.pivot(index="duration_h", columns="return_period_y", values="change_pct_ci_lo")
hi = summary.pivot(index="duration_h", columns="return_period_y", values="change_pct_ci_hi")
print(grid.to_string(float_format=lambda v: f"{v:+.2f}"))

# %% [markdown]
# ## The headline figure

# %%
fig, (ax_map, ax_lines) = plt.subplots(1, 2, figsize=(13, 5.2))

vmax = float(np.nanmax(np.abs(grid.values))) or 1.0
im = ax_map.imshow(
    grid.values, origin="lower", aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax
)
ax_map.set_xticks(range(len(rps)), [f"{int(r)}" for r in rps])
ax_map.set_yticks(range(len(durations)), [f"{int(d)}" for d in durations])
ax_map.set_xlabel("Return period (years)")
ax_map.set_ylabel("Duration (hours)")
ax_map.set_title("Change in return level, scenario vs historical")
ax_map.grid(False)
for i in range(len(durations)):
    for j in range(len(rps)):
        value = grid.values[i, j]
        ax_map.text(
            j, i, f"{value:+.1f}%", ha="center", va="center", fontsize=9,
            color="white" if abs(value) > 0.6 * vmax else "black",
        )
fig.colorbar(im, ax=ax_map, label="change (%)")
# The claim predicts the surface rises towards short duration, long RP.
ax_map.annotate(
    "claim: largest change here",
    xy=(len(rps) - 1, 0), xytext=(len(rps) - 1.9, 0.9),
    fontsize=8, color="0.25",
    arrowprops={"arrowstyle": "->", "color": "0.25", "lw": 1},
)

for j, rp in enumerate(rps):
    ax_lines.plot(durations, grid.values[:, j], marker="o", label=f"RP {int(rp)} y")
    ax_lines.fill_between(durations, lo.values[:, j], hi.values[:, j], alpha=0.12)
ax_lines.set_xscale("log")
ax_lines.set_xticks(durations, [f"{int(d)}" for d in durations])
ax_lines.set_xlabel("Duration (hours)")
ax_lines.set_ylabel("Change in return level (%)")
ax_lines.set_title("Shaded: bootstrap 95 % interval over cells")
ax_lines.axhline(0.0, color="0.4", lw=0.8)
ax_lines.legend(fontsize=8, title="return period", title_fontsize=8)

windows = claim_test.get("windows", {})
subtitle = " vs ".join(str(v) for v in windows.values()) if windows else ""
fig.suptitle(
    "Extreme precipitation over Germany, Destination Earth Climate DT\n"
    f"{subtitle} — verdict: {claim_test['verdict']}",
    fontsize=12,
)

if not IS_REAL:
    fig.text(
        0.5, 0.5, f"SYNTHETIC INPUT ({PROVENANCE})\nNOT A REPLICATION RESULT",
        fontsize=34, color="red", alpha=0.22, ha="center", va="center",
        rotation=22, weight="bold", zorder=10,
    )

fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.savefig(FIGURES_DIR / "main_result.png", dpi=DPI, bbox_inches="tight")
fig.savefig(FIGURES_DIR / "main_result.pdf", bbox_inches="tight")
# plt.show() after savefig, never matplotlib.use('Agg') — the Jupyter Book
# needs the inline display or the built page shows an empty cell.
plt.show()

# %% [markdown]
# ## What the ordering tests say

# %%
fig2, ax = plt.subplots(figsize=(7, 3.6))
tau_d = [v["tau"] for v in claim_test["kendall_tau_vs_duration"].values()]
tau_r = [v["tau"] for v in claim_test["kendall_tau_vs_return_period"].values()]
labels = (
    [f"vs duration\n@ {k}" for k in claim_test["kendall_tau_vs_duration"]]
    + [f"vs RP\n@ {k}" for k in claim_test["kendall_tau_vs_return_period"]]
)
values = tau_d + tau_r
# The claim predicts negative tau against duration and positive against RP, so
# a bar is coloured by whether it points the way the claim says.
predicted_sign = [-1] * len(tau_d) + [1] * len(tau_r)
colours = ["#2c7fb8" if np.sign(v) == s else "#d95f02" for v, s in zip(values, predicted_sign)]
ax.bar(range(len(values)), values, color=colours)
ax.set_xticks(range(len(values)), labels, fontsize=7)
ax.set_ylabel("Kendall tau")
ax.axhline(0.0, color="0.3", lw=0.8)
ax.set_ylim(-1.05, 1.05)
ax.set_title("Blue: consistent with the claim.  Orange: against it.", fontsize=10)
if not IS_REAL:
    fig2.text(
        0.5, 0.5, "SYNTHETIC", fontsize=40, color="red", alpha=0.2,
        ha="center", va="center", rotation=18, weight="bold",
    )
fig2.tight_layout()
fig2.savefig(FIGURES_DIR / "ordering_tests.png", dpi=DPI, bbox_inches="tight")
plt.show()

# %%
print(f"wrote {FIGURES_DIR / 'main_result.png'}")
print(f"wrote {FIGURES_DIR / 'main_result.pdf'}")
print(f"wrote {FIGURES_DIR / 'ordering_tests.png'}")
print(f"provenance: {PROVENANCE}  |  verdict: {claim_test['verdict']}")
