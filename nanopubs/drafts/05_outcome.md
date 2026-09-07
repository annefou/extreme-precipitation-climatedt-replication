# 05 — FORRT Replication Outcome

> Run the pre-flight checklist in `docs/forrt-form-fields.md` § Pre-flight checklist before drafting.
>
> **Verify the actual numerical results first** by reading `results/` and `notebooks/03_analysis.py`. Don't quote numbers from memory. See `docs/verify-before-drafting.md`.

## Field-by-field draft

<!-- field: outcome -->
### Short URI suffix for outcome ID (text input, required)

Slug. Use kebab-case.

```
climatedt-germany-duration-rp-outcome
```

<!-- field: label -->
### Plain-text label for the outcome (text input, required)

Descriptive title.

```
Climate DT confirms that short-duration, long-return-period extremes change most over Germany
```

<!-- field: study -->
### Choose study (search/select, required)

URI of the Replication Study published in step 04. Pull from `nanopubs/PUBLISHED.md`.

```

```

<!-- field: repo -->
### Repository URL (text input, required)

Use the Zenodo **version DOI** URL for the release the results came from — not a
bare branch URL, and not the concept DOI.

> **Why not the bare repo URL.** `https://github.com/ORG/REPO` names a *moving
> branch*. This Outcome asserts "this code produced this number", in a signed,
> immutable record. A branch URL means that assertion points at whatever `main`
> happens to be years from now — code that may never have produced the number
> above. A concept DOI has the same flaw: it resolves to the latest version.
> The version DOI pins the exact release. `docs/chain-decision-tree.md` § Anchor
> ranks the options: SWHID > Zenodo DOI > repo URL > Wayback.
>
> Both DOIs and the SWHID are in `CITATION.cff` under `identifiers:`, recorded
> automatically at release by `.github/workflows/release-identifiers.yml`. Take
> the one described as *"Version DOI"*.

```
https://doi.org/{{ZENODO_VERSION_DOI}}
```

<!-- field: date -->
### Choose completion date (text input, required)

```
2026-09-07
```

<!-- field: validationStatus -->
### Choose validation status (dropdown, required)


This dropdown maps to the CiTO intention in step 06: Validated → `confirms`, PartiallySupported → `qualifies`, Contradicted → `disputes`.

- [ ] contradicted
- [ ] inconclusive
- [ ] not tested
- [ ] partially supported
- [x] validated

<!-- field: confidenceLevel -->
### Choose confidence level (dropdown, required)

Live vocabulary (verified): very high / high / moderate / low / very low.

```
moderate
```

- [ ] high - Strong evidence, mostly agrees with original
- [ ] low - Limited evidence, significant disagreement
- [x] moderate - Adequate evidence, partial agreement
- [ ] very high - Extensive evidence, high agreement with original
- [ ] very low - Minimal evidence, major disagreement

<!-- field: conclusion -->
### Describe the overall conclusion about the original claim (textarea, required)

Substantive interpretation. Headline comparison: replication's number vs the paper's number, sign + significance.

```
The claim is confirmed. In the Destination Earth Climate DT, the largest increase in extreme precipitation return level over Germany between 1991-2010 and SSP3-7.0 2030-2049 falls at the shortest duration and the longest return period examined - +16.9% at 1 hour / 20 years - which is exactly the corner the original identifies. The change decreases monotonically with duration at every return period examined (Kendall tau = -1.000).

This holds in a modelling framework sharing neither its input data nor its statistics with the original: a single coupled global Earth-system model at about 5 km under SSP3-7.0, analysed with a regional index-flood GEV fitted to annual maxima, against the original's four-member convection-permitting COSMO-CLM ensemble at 2.8 km under RCP 8.5 analysed with a peak-over-threshold exponential fit. The agreement therefore tests the claim rather than the pipeline.
```

<!-- field: evidence -->
### Describe the evidence that supports your conclusion (textarea, required)

Numerical results, test statistics, model coefficients. Read directly from `results/`.

```
Change in return level, SSP3-7.0 2030-2049 against historical 1991-2010, median over 8,697 cells, by duration (rows) and return period in years (columns):

           2 y      5 y     10 y     20 y
   1 h   +9.22%  +12.75%  +14.89%  +16.88%
   3 h   +8.47%  +11.22%  +12.88%  +14.41%
   6 h   +6.72%   +8.77%   +9.92%  +10.93%
  12 h   +4.73%   +4.96%   +5.03%   +5.06%
  24 h   +2.39%   +1.80%   +1.20%   +0.53%

The maximum of the matrix, +16.88%, is at 1 hour / 20 years - the short-duration, long-return-period corner. The corner comparison the claim states is +16.88% against +2.39% at 24 hours / 2 years, a difference of 14.5 percentage points. The change falls monotonically with duration at every return period (Kendall tau = -1.000, p = 0.017).

Global-mean warming between the two windows is 0.9295 K, computed from the Climate DT's own monthly-mean 2 m temperature. Expressed per degree, the change runs from +9.9% per degree at 1 hour / 2 years to +18.2% per degree at 1 hour / 20 years, and from +2.6% down to +0.6% per degree at 24 hours.

The original reports 6-8.5% per degree of global warming. THE TWO FIGURES ARE NOT DIRECTLY COMPARABLE and neither reproduces the other: the original's is a maximum across ensemble members from a peak-over-threshold exponential fit over durations of 1-72 hours and return periods to 100 years; this study's is a median over grid cells from a pooled GEV over 1-24 hours and return periods to 20 years. With that caveat attached, the short durations here sit at or above the original's band and the long durations well below it, consistent with a steeper dependence on duration in the Climate DT than in the convection-permitting ensemble.

Uncertainty is from bootstrap resampling of grid cells (n = 400); the 95% intervals do not change the ordering.

Repeating the entire analysis on HEALPix converted to the WGS84 ellipsoid with a conservative, mass-preserving operator gives the same verdict, with a maximum disagreement of 0.000 percentage points in any cell of the matrix.
```

<!-- field: limitations -->
### Describe what limits the conclusions of the study (textarea, optional)

Honest caveats. If the result is partial or contradicted, say so plainly. Don't overclaim.

```
1. AT 24 HOURS THE RETURN-PERIOD ORDERING REVERSES. The change decreases with return period there, from +2.39% at 2 years to +0.53% at 20 years (Kendall tau = -1.000): rarer daily totals change least. This does not contradict the claim, which is about where the maximum sits, but it bounds it - the intensification found here is concentrated in short-duration extremes and is largely absent for rare 24-hour totals.

2. ONE MODEL REALIZATION. A single member cannot separate the forced response from internal variability over 20-year windows, and cannot address the original's finding about ensemble spread. The original stresses that transient, multi-member data are needed for confidence in these signals; this study has neither multiple members nor a transient trajectory.

3. ONE WARMING INTERVAL of 0.93 K, well short of the original's 2 K and 3 K warming levels. The linearity of the response with warming is untested here, and per-degree figures derived from a sub-degree interval are correspondingly uncertain.

4. RESOLUTION. About 5 km is the grey zone, not convection-permitting: deep convection is parametrized. The original's added value came precisely from resolving it. Short convective extremes are therefore represented less faithfully here - in the very duration range where this study finds the largest changes.

5. HOURLY FLOOR. The archive resolves one hour. The original additionally corrects for sub-hourly behaviour with DWA-A 531 factors, which are not applied here.

6. RETURN PERIODS to 20 years only, from 20-year windows. The original's 50- and 100-year levels are out of reach.

7. DOMAIN MISMATCH. This study covers all of Germany; the original's convection-permitting nest covers Southern and Central Germany (about 411,000 km2).

8. NO OBSERVATIONAL EVALUATION. The original compares against DWD station data and KOSTRA-DWD-2010R. This study compares model windows to each other only, so it says nothing about whether the Climate DT's absolute return levels are realistic - only about how they change.
```

## Publication note

After publishing, paste the resulting URI into `nanopubs/PUBLISHED.md` step 05.
