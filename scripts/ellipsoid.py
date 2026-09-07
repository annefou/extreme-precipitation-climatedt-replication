"""Sphere to WGS84-ellipsoid HEALPix conversion.

The Climate DT is delivered on a HEALPix grid defined on a mathematical
**sphere**. Every geographic use of it -- masking a country, comparing against
station data, publishing an interoperable archive -- is on the **WGS84
ellipsoid**, where the same cell index lands somewhere else. This module does
that conversion with `healpix-resample`:

    https://pypi.org/project/healpix-resample/
    https://github.com/GRID4EARTH/healpix-resample

**Resampler: `ConservativeResampler`.** Precipitation is a flux, so the
conservative operator is the standard choice -- direct area-weighted binning,
exactly mass-preserving, and unable to produce a value the input did not have.

The alternative reconstruction-based resamplers are wrong for this variable, and
measurably so. `PSFResampler` (Gaussian kernel, damped least squares) suits a
smooth signed field such as temperature; on one month of this precipitation data
it returns 39.8% negative rainfall and inflates the field maximum by 77%, since
an unregularised fit rings on a sparse non-negative field. Conservative binning
gives a mean ratio of 1.0000 and a max ratio of 1.0000 on the same input, and
costs about half a second per year rather than two minutes.

Polytope's polygon feature returns an unstructured point cloud with **no cell
ids at all** -- just a latitude and longitude per cell -- so the resampler is
built from those coordinates, which is exactly the input it is designed for. A
useful side effect is that the conversion is what finally gives these cells real
HEALPix NESTED indices.

**Why this matters more at level 10 than it would at coarser resolution.** The
sphere-to-ellipsoid latitude offset reaches 0.128 degrees, about 14 km. At
level 7 (~50 km cells) that is a third of a cell and is often neglected; at the
level 10 (~6 km) used here it is more than two cells. Measured on this domain,
350 of 8,697 cells (4.0%) change Germany-membership between the two
conventions.

**Still compared, not assumed harmless.** Conservative binning moves values
between cells, so a cell's maximum can change even though the domain total does
not. `02_data_clean.py` therefore builds BOTH grids and `03_analysis.py` runs
the ordering test on each, so the effect of the correction on the conclusion is
a reported number rather than an assertion. The comparison belongs in the
Replication Study's deviations either way.
"""

from __future__ import annotations

import numpy as np

# Native HEALPix level of the Climate DT `resolution: high` delivery:
# nside = 1024, ~6.3 km cells.
NATIVE_LEVEL = 10

# Conservative binning takes no kernel or damping parameters -- that is the
# point of it. Nothing to tune means nothing to tune wrongly.


def build_resampler(lon_deg: np.ndarray, lat_deg: np.ndarray, level: int = NATIVE_LEVEL):
    """ConservativeResampler from the delivered (spherical) cell centres to WGS84.

    Built once and reused: the sparse operator depends only on the geometry, not
    on the values, so every timestep of every year shares it.
    """
    import healpix_resample

    return healpix_resample.ConservativeResampler(
        lon_deg=np.asarray(lon_deg, dtype=float),
        lat_deg=np.asarray(lat_deg, dtype=float),
        level=level,
        ellipsoid="WGS84",
    )


# Rows per call to `resample`, to bound peak memory. Conservative binning is a
# single sparse mat-vec with no iterative solve, so unlike the PSF path the cost
# here really is linear in the batch -- this is about memory, not conditioning.
BATCH_ROWS = 744


def to_ellipsoid(
    resampler, values: np.ndarray, batch_rows: int = BATCH_ROWS
) -> tuple[np.ndarray, np.ndarray]:
    """Resample (B, N) or (N,) sample values onto ellipsoidal HEALPix cells.

    Returns `(cell_ids, cell_data)` where `cell_ids` are real HEALPix NESTED
    indices at the resampler's level -- the identity the delivered point cloud
    never carried -- and `cell_data` matches the input's leading batch shape.
    """
    values = np.asarray(values, dtype=np.float64)
    if values.ndim == 1:
        result = resampler.resample(values)
        return np.asarray(result.cell_ids), np.asarray(result.cell_data)

    cell_ids = None
    pieces = []
    for start in range(0, values.shape[0], batch_rows):
        result = resampler.resample(values[start:start + batch_rows])
        if cell_ids is None:
            cell_ids = np.asarray(result.cell_ids)
        elif not np.array_equal(cell_ids, np.asarray(result.cell_ids)):
            # The operator is fixed by geometry alone, so every batch must land
            # on the same cells. If that ever stops holding, concatenating the
            # pieces would silently interleave different grids.
            raise RuntimeError("resampler returned different cell_ids between batches")
        pieces.append(np.asarray(result.cell_data))
    return cell_ids, np.concatenate(pieces, axis=0)
