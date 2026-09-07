# 04 — FORRT Replication Study

> Run the pre-flight checklist in `docs/forrt-form-fields.md` § Pre-flight checklist before drafting.
>
> **Verify code first:** read the actual reproduction script in `notebooks/03_analysis.py` before writing the methodology field. See `docs/verify-before-drafting.md`.

## Field-by-field draft

<!-- field: study -->
### Short URI suffix for study ID (text input, required)

Slug. Use kebab-case.

```
climatedt-germany-duration-rp-return-levels
```

<!-- field: label -->
### Label/name of replication study (text input, required)

Human-readable title.

```
Duration x return-period scaling of precipitation extremes over Germany in the Destination Earth Climate DT
```

<!-- field: type -->
### Choose the study type (dropdown, required)

- [x] Replication Study - replication with different methodology or conditions
- [ ] Reproduction/Replication Study - study that is both, reproduction and replication
- [ ] Reproduction Study - direct reproduction: same methodology, same tools

<!-- field: claim -->
### Choose FORRT claim (search/select, required)

URI of the Claim published in step 03. Pull from `nanopubs/PUBLISHED.md`.

```

```

<!-- field: scope -->
### Describe what part of the claim is reproduced/replicated. (textarea, required)

The **scope** of the claim being tested. Which aspect, what's in/out of scope. NOT methodology. NOT results. See `docs/pico-study-outcome-levels.md`.

```
Tested: the ORDERING the claim asserts — that extreme precipitation events of
short duration and long return period intensify proportionally more than events of long
duration and short return period. Operationally, whether the largest change in return
level across a duration x return-period matrix falls at the short-duration,
long-return-period corner, and whether that corner exceeds the long-duration,
short-return-period corner.

Not tested: the original's reported magnitude of 6-8.5% per degree of global warming.
That figure is a maximum across the members of one convection-permitting ensemble over
one domain; elsewhere it can only be re-measured, not tested. It is recorded in the
Outcome as evidence alongside this study's own per-degree figures, with both definitions
attached.

Also not tested: the original's comparison against observations (DWD stations,
KOSTRA-DWD-2010R), its 72-hour duration, its return periods beyond 20 years, and its
GWL2/GWL3 warming levels.
```

<!-- field: methodology -->
### Describe how the claim is reproduced/replicated. (textarea, required)

The **method** in plain prose. Read `notebooks/03_analysis.py` and any config files first. NOT exact numerical results.

```
Data: Destination Earth Climate DT, generation 2 — model IFS-NEMO,
realization 1, hourly `clte` stream, variable `avg_tprate` (hourly-mean precipitation
rate, kg m-2 s-1), `levtype=sfc`, `resolution=high`, i.e. the native HEALPix level 10
grid (nside 1024, about 6.3 km). Two 20-year windows of equal length: 1991-2010
(activity `baseline`, experiment `hist`) and 2030-2049 (activity `projections`,
experiment SSP3-7.0).

Retrieval: ECMWF Polytope server-side polygon feature extraction over Germany, one
request per calendar month (480 in total, about 23 GB). MARS cannot crop a HEALPix field
with a lat/lon box, so server-side extraction is what makes 20 years of hourly level-10
data tractable. The domain polygon is committed with the code (Eurostat NUTS 2021
level 0, simplified to 128 vertices) so the study area is fixed. 8,697 cells fall inside
it.

Reduction: rates converted to millimetres per hour (x3600); backward rolling
accumulations over 1, 3, 6, 12 and 24 hours; the annual maximum of each accumulation per
cell per calendar year, with each year carrying the tail of the previous one so a
24-hour total ending on 1 January still sees 31 December.

Estimation: a regional index-flood analysis per (window, duration). Each cell's
annual-maxima series is divided by its own at-site mean, the standardised series are
pooled across all cells, and a single generalised extreme value distribution is fitted to
the pool by L-moments (Hosking). Return levels for 2, 5, 10 and 20 years are the pooled
growth factor times each cell's index flood. Pooling is what allows a 20-year return
level from a 20-year window, and is the same device the original uses. Uncertainty comes
from resampling CELLS with replacement (n=400), because spatial correlation, not record
length, limits the effective independence of the pooled sample.

Comparison: the change per matrix cell is the median over grid cells of the per-cell
ratio of return levels between windows, so each cell's own climatology cancels.

Coordinate systems: the Climate DT is delivered on HEALPix defined on a sphere. The whole
analysis is repeated on HEALPix on the WGS84 ellipsoid, converted with healpix-resample's
conservative (mass-preserving) operator, and both grids are reported.

Data attribution (Destination Earth Terms and Conditions v2.0, Art. 3.4): this
data is created based on data of the European Union, using the Destination Earth
Platform, but has been modified by Anne Fouilloux. The results are a derived
product - aggregation and transformation of Climate DT output - and are not
original DestinE Data. The underlying hourly data is not redistributed.

Software: Python; numpy, scipy, xarray, earthkit-data, polytope-client, healpix-geo,
healpix-resample. The extreme-value estimator, the coordinate conversion and the verdict
logic are unit tested — the GEV against scipy.stats.genextreme, and the verdict against
matrices whose answer is known by construction.
```

<!-- field: deviation -->
### Describe any deviations from original methodology. (textarea, optional)

What's different from the original method. Verify against the actual code, don't guess.

```
Different data and different statistics from the original; both are
deliberate, and together they are what make agreement informative rather than circular.

1. Model: a single coupled global Earth-system model (IFS-NEMO, one realization) in place
   of a four-member ensemble of CMIP5 GCMs downscaled with COSMO-CLM.
2. Resolution: about 5 km (HEALPix level 10, ~6.3 km) in place of 2.8 km. Deep convection
   is therefore NOT explicitly resolved here, whereas the original's added value came
   precisely from resolving it.
3. Domain: all of Germany (8,697 cells) in place of the original's convection-permitting
   nest over Southern and Central Germany (~411,000 km2).
4. Scenario: SSP3-7.0 in place of RCP 8.5.
5. Periods: two 20-year windows (1991-2010, 2030-2049) in place of a transient 1971-2100
   simulation with a 1971-2005 reference and 30-year running windows.
6. Warming: one interval of 0.93 K of global-mean warming between the windows, in place of
   the original's GWL2 and GWL3 (2 K and 3 K). This study therefore cannot test the
   linearity of the response with warming, only the ordering at one interval.
7. Durations: 1, 3, 6, 12, 24 hours in place of 1, 6, 12, 24, 72 hours. There is no 72-hour
   duration here and no 3-hour duration there; the shortest, most convectively driven
   durations the original emphasises are below the archive's hourly resolution.
8. Estimator: a regional index-flood GEV fitted by L-moments to annual maxima, in place of
   a partial-series peak-over-threshold selection with an exponential fit in logarithmic
   space following the German DWA-A 531 guideline.
9. Return periods: up to 20 years in place of up to 100 years. Twenty years of data cannot
   support a 100-year return level even with pooling.
10. No sub-hourly correction: the original applies DWA-A 531 factors (1.14, 1.07, 1.04,
    1.03) for event durations up to 4 hours to compensate for hourly sampling. This study
    applies none, so its short-duration intensities are, if anything, conservative — which
    matters because the short durations are where it finds the largest changes.
11. No observational comparison: the original evaluates against DWD station data and
    KOSTRA-DWD-2010R. This study compares model windows to each other only.
```

<!-- field: keyword -->
### Search keywords (Wikidata) (search/select, optional)

Labels **with their QIDs** — `build_chain_draft.py` honours an explicit QID and
only falls back to a label search without one. A label search can land on a
different item than the one you checked.

This field imposes no `owl:Class` type, so items without `P279` are acceptable
here (unlike `02_aida.topic`).

```
extreme rainfall (Q111089542)
return period (Q2627230)
generalized extreme value distribution (Q1617240)
climate model (Q620920)
```

<!-- field: discipline -->
### Search discipline (Wikidata) (search/select, optional)

Provide labels.

- _Discipline label: ___

## Publication note

After publishing, paste the resulting URI into `nanopubs/PUBLISHED.md` step 04.
