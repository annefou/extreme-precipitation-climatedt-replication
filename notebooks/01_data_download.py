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
# # 01 — Data download
#
# This notebook fetches all input data needed by the replication pipeline.
# Every dataset is downloaded from a citable source (Zenodo, GBIF, Copernicus,
# etc.) and a record of the source is logged into `data/raw/sources.json`
# alongside the data files.
#
# **Self-contained data:** The repository ships without input data. This
# notebook is the only path that brings data into `data/raw/`. A user cloning
# the repo and running this notebook should get a complete reproducible run.
#
# **Credentials:** if your replication uses a credentialled API, document the
# credential setup at the top of this notebook, including:
#
# - Where the user gets the credential (URL).
# - Where it lives on disk (or which env var Claude expects).
# - The corresponding GitHub Actions secret name(s) for CI.

# %%
import json
from pathlib import Path

import requests

# %%
RAW_DIR = Path("../data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Source registry
#
# Replace the placeholder source(s) below with your actual data sources. Each
# entry should record: name, URL or DOI, license, accessed-on date, and SHA-256
# of the downloaded file (computed and added after first download).

# %%
SOURCES = [
    {
        "name": "<dataset-name>",
        "doi": "<10.x/y or null>",
        "url": "<https://...>",
        "license": "<CC-BY-4.0 / CC-BY-NC-4.0 / public-domain / ...>",
        "accessed_on": "{{RELEASE_DATE}}",
        "sha256": None,  # filled after first download
    },
    # Add more sources here as needed.
]


# %% [markdown]
# ## Download

# %%
def download_source(source: dict) -> Path:
    """Fetch a single source into data/raw/. Replace with your real implementation."""
    # Example skeleton — adapt to your data source's API:
    # response = requests.get(source["url"], stream=True, timeout=300)
    # response.raise_for_status()
    # out_path = RAW_DIR / Path(source["url"]).name
    # with open(out_path, "wb") as f:
    #     for chunk in response.iter_content(chunk_size=8192):
    #         f.write(chunk)
    # return out_path
    raise NotImplementedError(
        "Implement download for: " + source["name"] + ". "
        "See data/README.md for common patterns."
    )


# %%
# Uncomment when SOURCES is populated:
# for source in SOURCES:
#     print(f"Fetching {source['name']}...")
#     path = download_source(source)
#     print(f"  -> {path}")

# %% [markdown]
# ## Source log
#
# Persist the source registry to disk so that downstream notebooks can audit
# what data was used and when.

# %%
with open(RAW_DIR / "sources.json", "w") as f:
    json.dump({"sources": SOURCES}, f, indent=2)

print(f"Logged {len(SOURCES)} source(s) to {RAW_DIR / 'sources.json'}")
