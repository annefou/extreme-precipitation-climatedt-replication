# DOMAIN.md — domain flavour

This file encodes domain-specific conventions for replications in **biodiversity + earth observation**. It is loaded by `CLAUDE.md` and applied automatically.

To swap to a different domain (e.g. genomics, social science, materials), copy the matching file from `docs/domain-flavours/` over this file, or write a new flavour using `docs/domain-flavours/_template.md` as a scaffold and ask Claude to help you fill it in.

## Domain: biodiversity + earth observation

This template was originally built for replications at the intersection of biological diversity and remote-sensing / climate data — typical examples: pollinator extirpation under climate change, marine heatwave biodiversity exposure, satellite-derived vegetation indices, sphere-aware machine learning on earth-observation data.

If your replication is in a different domain, replace this section by following the "Adapting to a new domain" guide at the bottom of this file.

## Default tooling stack

When the user asks Claude to set up a typical analysis, the default tools to suggest are:

| Concern | Default tool | Notes |
|---|---|---|
| Multi-dimensional arrays | `xarray` | NetCDF/Zarr-aware, lazy via `dask` |
| Climate reanalysis | `cdsapi` (Copernicus C3S) | ERA5, CRU TS, CMIP6 |
| Marine reanalysis | `copernicusmarine` | credentials at `~/.copernicusmarine/.copernicusmarine-credentials` |
| Climate Digital Twin (~5 km, daily) | `polytope-client` or `earthkit-data` | Destination Earth Climate DT — needs DestinE Data Lake account |
| Biodiversity occurrences | `pygbif` | always mint a download DOI per query |
| Spherical pixelisation | `healpy` (HEALPix) | **always pass `nest=True`** — see below |
| HEALPix + cartopy | `healpix-plot` (EOPF-DGGS) | replaces ad-hoc ang2pix + pcolormesh bridges |
| Discrete Global Grid Systems | `xdggs`, `dggrid4py`, `h3`, `rhealpixdggs` | DGGRID v8.41 only (v8.42+ breaks under modern GCC) |
| Map projections | `pyproj`, `cartopy` | |
| Raster / vector I/O | `rasterio`, `geopandas` | |
| Scattering on the sphere | `foscat>=2026.4.1` | upstream PyPI; CPU auto-detection |

Pin every dependency in `pixi.toml` and commit the regenerated `pixi.lock` — pangeo dev environments hide missing deps locally and CI then silently fails with empty notebook cells.

## Domain conventions

### HEALPix is always NESTED, never RING

Every `healpy` call in this domain MUST use `nest=True`. NESTED is the only ordering that supports hierarchical bit-shift refinement (parent = `pix >> 2`, children = `pix << 2 | k`) and is the optimal ordering for zoom-in / zoom-out operations across spatial scales.

```python
hp.ang2pix(nside, theta, phi, nest=True)
hp.pix2ang(nside, pix, nest=True)
hp.boundaries(nside, pix, step=N, nest=True)
```

Mixing RING and NESTED in the same workflow makes cell indices incompatible and breaks tile-based / hierarchical operations. Treat NESTED as a project-wide convention, not a per-notebook choice.

If a notebook needs RING (e.g. for spherical-harmonic transforms via `hp.map2alm`), do the SHT work in a clearly-scoped block, but keep the on-disk pixelisation NESTED.

### Biodiversity is high-precision climate-impact science

Don't dismiss small systematic biases in biodiversity work as "sub-noise" or "second-order". Biodiversity replications in this template are typically climate-impact attribution, restoration monitoring, Habitats Directive / Natura 2000 reporting, and species-distribution work — domains where a 0.3 % systematic bias compounds across millions of cells and decades of data into real attribution errors.

When choosing pixelisations, projections, or aggregation methods, default to the option with smaller systematic bias even if it costs implementation effort. The "good enough for biodiversity" framing is wrong here.

### GBIF download DOIs are mandatory

Every GBIF query that feeds a replication must mint a download DOI (not just a URL). Issue an occurrence download via the GBIF API rather than the search UI, record the resulting DOI (`10.15468/dl.…`), and cite it in `CITATION.cff` and the Replication Study's "Methodology" field. Without a download DOI, the dataset is not citable and the replication is not reusable.

### Copernicus credentials in CI

`copernicusmarine login` prompts interactively and fails in CI. Create the credentials file directly from secrets:

```yaml
- name: Set up Copernicus Marine credentials
  run: |
    mkdir -p ~/.copernicusmarine
    echo "${{ secrets.COPERNICUS_CREDENTIALS_BASE64 }}" | base64 -d \
      > ~/.copernicusmarine/.copernicusmarine-credentials
```

The secret is a base64-encoded INI file containing `[credentials]\nusername=…\npassword=…`.

### Self-contained data downloads

Every notebook MUST include code to download its input data — never assume data exists locally. The repo should be cloneable + runnable without manual data preparation. Use Zenodo, GBIF API, Copernicus API, or direct URLs. Files >100 MB go behind `actions/cache@v4` in CI.

## Style conventions

### Spell out "percentage points"

When writing scientific narrative in nanopub fields (Outcome conclusion, evidence, limitations; Quote-with-comment personal comments), spell out **"percentage points"** rather than abbreviating as **"pp"**. The abbreviation reads as cryptic and is confusable with page numbers in citations.

- ✅ "8.4 percentage points"
- ❌ "8.4 pp"

The abbreviation is acceptable in dense tables when the column header makes it unambiguous (e.g., `Δ (pp)`). In prose / textarea fields, spell it out.

### Honest negative results

A replication that contradicts the original paper's headline is publishable. A replication that overclaims to make the result look stronger is not. If your numerical replication gives a weaker effect than the paper, write it that way; if it contradicts the paper, label the FORRT Outcome as `Contradicted` and let the CiTO citation type be `disputes`. The platform's value is research integrity — overclaiming undermines the platform.

### Vision-piece framing for advocacy posts

When drafting LinkedIn / blog posts about a replication, lead with a **vision** about what's changing in research practice (Open Science, FAIR4RS, atomic claims), and treat the worked replication as the proof-of-concept payoff. Don't lead with "we replicated X". Don't write marketing-fluff openings ("excited to announce"). Don't tag the original paper authors directly — they'll find it via citation pipelines if it's notable.

## Adapting to a new domain

To use this template for a domain other than biodiversity + earth observation:

1. Pick the closest existing flavour from `docs/domain-flavours/`.
2. Copy it over `DOMAIN.md` (in the repo root) — the file Claude reads.
3. Update three things at minimum:
   - **Default tooling stack** — list the libraries your domain reaches for first.
   - **Domain conventions** — the analogue of "HEALPix always NESTED" for your field. What's a non-obvious convention that, if violated, breaks downstream interop?
   - **Style conventions** — write-up rules specific to your domain.
4. If no flavour matches, start from `docs/domain-flavours/_template.md` and ask Claude to help you fill it in based on a few example papers from your field.

A domain flavour is a contract: by including it, you're telling Claude *"in this field, do X by default, and flag if the user violates Y"*. Keep it short and load-bearing — under ~300 lines is a healthy ceiling. Domain rules are not personal style (those go in `USER_PREFERENCES.md`).
