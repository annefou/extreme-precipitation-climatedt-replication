# Snakefile — orchestrates the replication pipeline end-to-end.
#
# One rule per notebook; each rule runs the notebook via jupytext so the
# notebook stays the source of truth and this file only sequences them.
#
# Usage:
#   snakemake --cores 1                  # run everything
#   snakemake --cores 1 -n               # dry run
#
# The first rule is the only one that needs Destination Earth credentials. With
# none present it writes the synthetic stand-in instead (see
# notebooks/01_data_download.py), so `snakemake --cores 1` completes on a fresh
# clone and in CI — as a smoke test, with every artefact stamped
# provenance=synthetic. `data/raw/sources.json` is the rule's declared output
# either way, because the number of yearly files depends on which path ran.

NOTEBOOKS = "notebooks"
DATA = "data"
RESULTS = "results"
FIGURES = "figures"


rule all:
    input:
        f"{FIGURES}/main_result.png",
        f"{FIGURES}/ordering_tests.png",
        f"{RESULTS}/summary.csv",
        f"{RESULTS}/claim_test.json",


# ---------- 01: Retrieve the Climate DT hourly precipitation ----------
rule data_download:
    output:
        f"{DATA}/raw/sources.json",
    log:
        f"{RESULTS}/logs/01_data_download.log",
    shell:
        "mkdir -p {RESULTS}/logs && cd {NOTEBOOKS} && "
        "jupytext --to notebook --execute 01_data_download.py 2>&1 | tee ../{log}"


# ---------- 02: Hourly -> annual maxima per duration ----------
rule data_clean:
    input:
        f"{DATA}/raw/sources.json",
    output:
        f"{DATA}/clean/annual_maxima.nc",
    log:
        f"{RESULTS}/logs/02_data_clean.log",
    shell:
        "mkdir -p {RESULTS}/logs && cd {NOTEBOOKS} && "
        "jupytext --to notebook --execute 02_data_clean.py 2>&1 | tee ../{log}"


# ---------- 03: Pooled GEV, return levels, the ordering test ----------
rule analysis:
    input:
        f"{DATA}/clean/annual_maxima.nc",
    output:
        f"{RESULTS}/summary.csv",
        f"{RESULTS}/gev_fits.csv",
        f"{RESULTS}/return_levels.nc",
        f"{RESULTS}/claim_test.json",
    log:
        f"{RESULTS}/logs/03_analysis.log",
    shell:
        "mkdir -p {RESULTS}/logs && cd {NOTEBOOKS} && "
        "jupytext --to notebook --execute 03_analysis.py 2>&1 | tee ../{log}"


# ---------- 04: Figures ----------
rule figures:
    input:
        f"{RESULTS}/summary.csv",
        f"{RESULTS}/claim_test.json",
    output:
        f"{FIGURES}/main_result.png",
        f"{FIGURES}/main_result.pdf",
        f"{FIGURES}/ordering_tests.png",
    log:
        f"{RESULTS}/logs/04_figures.log",
    shell:
        "mkdir -p {RESULTS}/logs && cd {NOTEBOOKS} && "
        "jupytext --to notebook --execute 04_figures.py 2>&1 | tee ../{log}"
