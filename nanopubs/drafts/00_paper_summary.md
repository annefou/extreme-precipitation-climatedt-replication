# Paper summary

> Working scratchpad for the paper-analysis phase. Feeds the Quote / AIDA / Claim
> drafts and the Study's Deviations field. Not itself a nanopub.
>
> Every fact below is read from `paper/hundhausen-2024.pdf`, with the page it came
> from, so the Study's deviations can be checked rather than trusted.

**Reference paper:** Climate change signals of extreme precipitation return levels
for Germany in a transient convection-permitting simulation ensemble

**DOI:** 10.1002/joc.8393

**Authors:** Marie Hundhausen, Hendrik Feldmann, Regina Kohlhepp, Joaquim G. Pinto
(Institute of Meteorology and Climate Research–Troposphere Research (IMK-TRO),
Karlsruhe Institute of Technology)

**Year:** 2024 · *International Journal of Climatology* · CC BY-NC

## Headline claim

From the Abstract (p. 1), and restated in the Conclusions:

> "A maximum climate change signal of 6–8.5% increase per degree of GW is
> projected within the CP ensemble, with the largest changes expected for short
> durations and long RPs."

The **transferable** half of that sentence — where the largest changes sit — is
what this replication tests. The 6–8.5 %/K magnitude is a property of one
ensemble over one domain and can only be re-measured elsewhere, not tested; it
belongs in the Outcome as evidence. See `01_quote.md` and `02_aida.md`.

## Methodology summary

- **Data (p. 3, § 2.1).** The KIT-KLIWA ensemble: four CMIP5 GCMs (MPI-ESM-LR,
  EC-EARTH, CNRM-CM5, HadGEM2-ES, all r1i1p1) under **RCP 8.5**, downscaled with
  the regional model COSMO-CLM (CCLM 5.0-CLM9) through three nests —
  0.44° Europe → 0.0625° Germany → **0.025° (~2.8 km) convection-permitting**.
  Deep convection is explicitly resolved only in the innermost nest.
- **Domain (p. 3).** The CP nest is centred over **Southern Germany**: 226 × 232
  grid points, approximately **411,000 km²**. The evaluation area is the German
  part of that domain, not the whole country.
- **Period (p. 3).** Transient **1971–2100** (1971–2005 historical, 2006–2100
  projection). Reference period 1971–2005; projections evaluated over consecutive
  **30-year running windows** from 2006–2035 to 2071–2100.
- **Extreme value method (p. 5, § 3.1).** A **partial series / peak-over-threshold**
  selection — the e = 2.72 × (number of years) highest peaks, rain events separated
  by a rain-free period of 24 h — followed by an **exponential fit in logarithmic
  form**, `RL(RP) = u_p + w_p · ln RP`, by least-squares. This follows the German
  DWA-A 531 guideline underlying the KOSTRA-DWD-2010R product. **Not** a GEV fit
  to block maxima.
- **Durations (p. 5).** 1, 6, 12, 24 and 72 h (with 2, 4, 9 and 48 h additionally
  in the reference period). Return periods up to **100 a**.
- **Sub-hourly correction (p. 5).** Because hourly sampling underestimates
  intensity for short durations, DWA-A 531/KOSTRA correction factors of 1.14,
  1.07, 1.04 and 1.03 are applied for 1, 2, 3 and 4 measurement points per event
  duration (i.e. for ED ≤ 4 h).
- **Climate change signal (p. 5, § 3.2).** Expressed against **global warming**
  rather than time, as a change factor `CF(RP,ED) = 1 + Δpr/pr_hist`, where Δpr is
  the slope of a linear regression of intensity on GW (mm per K). GW is referenced
  to 1971–2000 (0.46 K above pre-industrial); GWL2 and GWL3 are 30-year windows
  centred on 2 K and 3 K.
- **Observational references (p. 4).** DWD hourly station data (1995–2005) and the
  KOSTRA-DWD-2010R regionalised product.
- **Headline number.** 6–8.5 % increase per degree of global warming, maximum
  within the CP ensemble, largest for short durations and long RPs.

## Replication design choice

- [ ] **Reproduction Study** — same methodology, same tools.
- [x] **Replication Study** — different methodology or conditions.
- [ ] **Reproduction/Replication Study** — both.

**Different data and different method, so a Replication Study rather than a
Reproduction.** The data is the Destination Earth Climate DT (a single coupled
global ESM at ~5 km under SSP3-7.0) in place of a four-member GCM-driven
convection-permitting RCM ensemble under RCP 8.5; and the estimator is a regional
index-flood GEV fitted by L-moments to annual maxima, in place of a
peak-over-threshold partial series with an exponential fit. Neither the input nor
the statistics are shared with the original, which is what makes agreement
informative: it tests the claim rather than the pipeline.

## Notes for downstream drafts

- The Quote comes from the **Conclusions** wording ("Events with short duration
  and long RPs are expected to change the most"), which states the ordering
  without the ensemble-specific magnitude.
- **Domain mismatch is a real deviation:** the paper evaluates Southern/Central
  Germany (~411,000 km² CP nest); this replication covers all of Germany
  (8,697 HEALPix level-10 cells). Record it in the Study, not silently.
- **The magnitudes are not directly comparable.** The paper's 6–8.5 %/K is a
  *maximum across ensemble members* from a POT/exponential fit over durations
  1–72 h and RPs to 100 a. This replication reports a *median over cells* from a
  pooled GEV over 1–24 h and RPs to 20 a. Quote both with their definitions
  attached; do not present one as reproducing the other.
- The paper applies sub-hourly correction factors for ED ≤ 4 h; this replication
  does not, so its short-duration intensities are, if anything, conservative.
