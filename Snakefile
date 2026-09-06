# Snakefile — orchestrates the replication pipeline end-to-end.
#
# Replace the placeholder rules with your actual replication steps. The
# canonical pattern is one rule per pipeline stage, and each rule wraps a
# notebook executed via jupytext (so the notebook stays the source of truth
# and the Snakefile just sequences them).
#
# Usage:
#   snakemake --cores 1                  # run everything
#   snakemake --cores 1 -n               # dry run

NOTEBOOKS = "notebooks"
DATA = "data"
RESULTS = "results"
FIGURES = "figures"


rule all:
    input:
        # Replace with your actual final artefacts:
        f"{FIGURES}/main_result.png",
        f"{RESULTS}/summary.csv",


# ---------- 01: Data download ----------
# Every replication MUST be self-contained: data is downloaded by the notebook,
# never assumed to exist locally. See CLAUDE.md § Self-contained data.
rule data_download:
    output:
        f"{DATA}/raw/dataset.zip",
    log:
        f"{RESULTS}/logs/01_data_download.log",
    shell:
        f"cd {{NOTEBOOKS}} && jupytext --to notebook --execute 01_data_download.py 2>&1 | tee ../{{log}}"


# ---------- 02: Data clean ----------
rule data_clean:
    input:
        f"{DATA}/raw/dataset.zip",
    output:
        f"{DATA}/clean/dataset.parquet",
    shell:
        f"cd {{NOTEBOOKS}} && jupytext --to notebook --execute 02_data_clean.py"


# ---------- 03: Analysis ----------
rule analysis:
    input:
        f"{DATA}/clean/dataset.parquet",
    output:
        f"{RESULTS}/summary.csv",
    shell:
        f"cd {{NOTEBOOKS}} && jupytext --to notebook --execute 03_analysis.py"


# ---------- 04: Figures ----------
rule figures:
    input:
        f"{RESULTS}/summary.csv",
    output:
        f"{FIGURES}/main_result.png",
    shell:
        f"cd {{NOTEBOOKS}} && jupytext --to notebook --execute 04_figures.py"
