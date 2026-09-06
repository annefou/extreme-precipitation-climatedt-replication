# `docs/eopf-zarr-conversion.md` — EOPF Zarr / GRID4EARTH for HEALPix EO archives

The EOPF (Earth Observation Processing Framework) Zarr profile, also known as the **GRID4EARTH** DGGS Zarr convention, is the standardised way to archive HEALPix-indexed earth-observation data so it interoperates cleanly with the EOPF tooling stack (`xdggs`, `healpix-geo`, `healpix-plot`, `healpix-resample`, and others) and with the broader DGGS community.

This domain (biodiversity + earth observation) defaults to EOPF Zarr for HEALPix archival per `DOMAIN.md` § Data formats. This doc is the minimal practitioner guide: structure, writing, and reading.

## Why GRID4EARTH

Traditional EO archives are stored on projected grids (UTM tiles, sinusoidal, lat-lon equirectangular) that require reprojection to combine, distort area at high latitudes, and cannot be hierarchically refined. HEALPix-NESTED with GRID4EARTH metadata fixes all three:

- **Equal-area cells** at every refinement level — spatial statistics are unbiased without area-weighting.
- **Hierarchical** — coarsening by NESTED parent-child operations is lossless and O(1).
- **Single global grid** — scenes from different orbits / tiles / sources land in the same cell IDs.
- **Cloud-optimized** — Zarr's chunked storage + HEALPix-aligned chunking gives efficient spatial queries with minimal data transfer.

The convention is what makes a HEALPix Zarr archive *interoperable* (FAIR4RS I1) — without standardised metadata, every downstream consumer has to guess what the cell-id encoding means.

## Structure of a GRID4EARTH Zarr

A GRID4EARTH dataset is a **Zarr v3** dataset organised as a tree of groups, with HEALPix-specific metadata on spatial groups.

Example for a multiscale terrestrial dataset (e.g. climate / biodiversity / EO):

```
my_dataset.zarr/
├── zarr.json                                   ← root group metadata
└── measurements/
    └── temperature/                            ← multiscale parent group
        ├── 12/                                 ← refinement level 12 (~5 km cells)
        │   ├── zarr.json                       ← spatial group metadata (HEALPix)
        │   ├── cell_ids/                       ← HEALPix cell IDs along `cells` dim
        │   ├── time/                           ← temporal coordinate (if applicable)
        │   ├── tasmin/                         ← data variable
        │   └── tasmax/
        ├── 11/                                 ← refinement level 11 (~10 km cells)
        │   └── ...
        └── 10/                                 ← refinement level 10 (~20 km)
            └── ...
```

Each **spatial group** (e.g. `temperature/12/`) contains:

- A `cells` **dimension** of length equal to the number of HEALPix cells in the spatial extent at that refinement level.
- A `cell_ids` **coordinate** (int64) along `cells` holding HEALPix-NESTED cell identifiers.
- Data variables indexed by `cells` (and any other dims like `time`, `species`, etc.).

Each spatial group's metadata includes `zarr_conventions` and `multiscales` attributes:

```json
{
  "zarr_conventions": [
    {"name": "multiscales", "uuid": "d35379db-88df-4056-af3a-620245f8e347"},
    {"name": "dggs",        "uuid": "7b255807-140c-42ca-97f6-7a1cfecdbc38"}
  ],
  "multiscales": {
    "layout": [
      {
        "asset": "12",
        "dggs": {
          "name": "healpix",
          "refinement_level": 12,
          "indexing_scheme": "nested",
          "ellipsoid": {
            "name": "wgs84",
            "semimajor_axis": 6378137.0,
            "inverse_flattening": 298.257
          }
        }
      }
    ]
  }
}
```

The root group can carry `stac_discovery` metadata (STAC Item-level: bbox, geometry, properties, assets) if the dataset corresponds to a discoverable STAC asset.

## Writing a GRID4EARTH Zarr

Minimal pattern using `xarray` + `zarr` v3, no extra packages required for a single-level dataset:

```python
import numpy as np
import xarray as xr
import zarr  # v3+

# Compute your HEALPix cell IDs (NESTED ordering — see DOMAIN.md):
import healpix_geo as hg

nside = 2**12               # refinement level 12 -> nside = 4096 (~5 km cells)
level = int(np.log2(nside)) # GRID4EARTH calls this `refinement_level`

# Example: the cells covering Iberia at level 12, populated with tasmin/tasmax:
cell_ids = ...               # int64 array of HEALPix-NESTED cell indices
n_cells = cell_ids.size
n_time = 240                 # 20 years × 12 months
time = np.arange("2041-01", "2061-01", dtype="datetime64[M]")

ds = xr.Dataset(
    data_vars={
        "tasmin": (("time", "cells"), np.random.randn(n_time, n_cells).astype("float32")),
        "tasmax": (("time", "cells"), np.random.randn(n_time, n_cells).astype("float32")),
    },
    coords={
        "cell_ids": (("cells",), cell_ids.astype("int64")),
        "time":     (("time",),  time),
    },
    attrs={
        "zarr_conventions": [
            {"name": "multiscales", "uuid": "d35379db-88df-4056-af3a-620245f8e347"},
            {"name": "dggs",        "uuid": "7b255807-140c-42ca-97f6-7a1cfecdbc38"},
        ],
        "multiscales": {
            "layout": [
                {
                    "asset": str(level),
                    "dggs": {
                        "name": "healpix",
                        "refinement_level": level,
                        "indexing_scheme": "nested",
                        "ellipsoid": {
                            "name": "wgs84",
                            "semimajor_axis": 6378137.0,
                            "inverse_flattening": 298.257,
                        },
                    },
                }
            ]
        },
    },
)

# Write at a single refinement level — store the dataset under a numeric group name
# matching the refinement level (GRID4EARTH convention):
ds.to_zarr(
    f"my_dataset.zarr/measurements/temperature/{level}",
    mode="w",
    zarr_format=3,
)
```

**Multi-level (multiscale) datasets** add coarsening: write level 12 as the native, then NESTED-coarsen by `pix >> 2` to derive level 11, level 10, etc. (`healpix-geo` and `healpix-resample` provide helpers; see `DOMAIN.md` § Default tooling stack).

## Reading a GRID4EARTH Zarr

```python
import xarray as xr
import xdggs  # registers the .dggs accessor on Datasets

dt = xr.open_datatree("my_dataset.zarr", engine="zarr", chunks="auto")

# Access a specific level's spatial group:
ds = dt["measurements/temperature/12"].ds

# Decode the DGGS metadata onto the dataset:
ds = ds.dggs.decode()
print(ds.dggs.grid_info)
# -> Healpix(level=12, indexing_scheme='nested', ellipsoid='wgs84')

# Convert cell IDs to lon/lat for plotting / further analysis:
import healpix_geo.nested as hgn
lon, lat = hgn.healpix_to_lonlat(ds.cell_ids.values, level=12, ellipsoid="wgs84")
```

## What changes vs plain Zarr

| Concern | Plain Zarr | GRID4EARTH Zarr |
|---|---|---|
| Cell indexing | Arbitrary array dim names | `cells` dim with `cell_ids` coordinate |
| Grid metadata | Ad-hoc / missing | `multiscales` attribute with HEALPix params + ellipsoid |
| Resolution levels | Separate stores | Single store with numeric group names = refinement levels |
| Interop | Per-tool conventions | Standardised across xdggs, healpix-geo, EOPF stack |

The metadata cost is modest (two attributes + a coordinate); the interop benefit is large.

## Full conversion examples (Sentinel-2, Sentinel-3)

For complete worked examples of converting legacy projected EO products (Sentinel-2 UTM tiles, Sentinel-3 swaths) to GRID4EARTH HEALPix Zarr — including resampling method choice, multi-stage parallel processing, and STAC metadata propagation — see [`EOPF-DGGS/legacy-converters`](https://github.com/EOPF-DGGS/legacy-converters).

> **Currently private; will be public soon.** Until then, ask the project maintainer for collaborator access if you need worked S2/S3 conversion examples. This doc covers the convention itself; `legacy-converters` covers product-specific conversion pipelines.

## When to use this format

| Scenario | Use? |
|---|---|
| HEALPix-indexed EO data archived as a Zarr | **Yes** — primary use case |
| HEALPix-indexed climate data subset (e.g. DestinE-derived per-cell TEI) | **Yes** — gets you xdggs accessor + cross-tool interop |
| Tabular results (rank lists, summary tables) | No — use CSV / Parquet (see DOMAIN.md) |
| Posterior samples (e.g. bambi `idata`) | No — use NetCDF (`idata.nc`) |
| Single-resolution, non-HEALPix gridded data | No — use plain NetCDF or plain Zarr without GRID4EARTH metadata |

## References

- [HEALPix](https://healpix.sourceforge.io/) — original DGGS specification (NASA, astrophysics).
- [healpix-geo](https://healpix-geo.readthedocs.io/) — Earth-aware HEALPix Python library (WGS84 ellipsoidal).
- [xdggs](https://xdggs.readthedocs.io/) — xarray accessor for DGGS, including HEALPix.
- [Zarr v3 specification](https://zarr-specs.readthedocs.io/) — underlying storage format.
- [GRID4EARTH](https://github.com/EOPF-DGGS) — the EU's EOPF DGGS effort hosting this convention.
- `EOPF-DGGS/legacy-converters` (private; soon public) — production-quality S2/S3 → GRID4EARTH converter.
