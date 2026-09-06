"""Domain geometry: the Germany mask, and the sphere-versus-ellipsoid question.

Nothing here resamples the precipitation field, and that is deliberate. HEALPix
cells are equal-area by construction, and the authalic definition keeps them
equal-area on the WGS84 ellipsoid, so a domain mean is an unweighted mean over
cells — no cosine-latitude weights, no area weights, and no regridding step that
a smoothing kernel could use to damp the very extremes being measured.

The ellipsoid does matter in exactly one place: the **domain mask**. Polytope
applies its polygon clip on the sphere the Climate DT's HEALPix is defined on.
The authalic and geodetic latitudes of the same point differ by up to 0.128°
(~14 km, peaking near 45°), so cells near the German border can fall on the
other side of the boundary under the two conventions. `mask_sensitivity()`
measures how many do. That is a number to report in the Replication Study's
Deviations field, not a correction to apply.
"""

from __future__ import annotations

import numpy as np

# WGS84 first eccentricity squared.
WGS84_E2 = 6.69437999014e-3


def authalic_latitude(lat_deg: np.ndarray) -> np.ndarray:
    """Geodetic -> authalic (equal-area sphere) latitude, in degrees.

    The standard series to second order in e^2, which is well under a metre of
    error at any latitude — the same mapping `healpix-geo` applies when it
    places HEALPix cells on the WGS84 ellipsoid.
    """
    phi = np.radians(np.asarray(lat_deg, dtype=np.float64))
    beta = phi - (WGS84_E2 / 3.0 + 31.0 * WGS84_E2**2 / 180.0) * np.sin(2 * phi)
    return np.degrees(beta)


def point_in_ring(lat: np.ndarray, lon: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Ray-casting point-in-polygon over (lat, lon) pairs.

    `ring` is an (n, 2) array of [latitude, longitude] vertices, closed or not.
    """
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    ring = np.asarray(ring, dtype=np.float64)
    inside = np.zeros(lat.shape, dtype=bool)
    for i in range(len(ring)):
        y1, x1 = ring[i]
        y2, x2 = ring[(i + 1) % len(ring)]
        if y1 == y2:  # a horizontal edge is never crossed by a horizontal ray
            continue
        straddles = (y1 > lat) != (y2 > lat)
        x_at_lat = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
        inside ^= straddles & (lon < x_at_lat)
    return inside


def mask_sensitivity(lat: np.ndarray, lon: np.ndarray, ring: np.ndarray) -> dict:
    """How many cells change domain membership under the authalic latitude shift."""
    lat = np.asarray(lat, dtype=np.float64)
    shifted = authalic_latitude(lat)
    moved = int(np.sum(point_in_ring(lat, lon, ring) != point_in_ring(shifted, lon, ring)))
    return {
        "n_cells": int(lat.size),
        "cells_changing_membership": moved,
        "fraction": round(float(moved / lat.size), 5),
        "max_latitude_shift_deg": round(float(np.max(np.abs(shifted - lat))), 4),
    }
