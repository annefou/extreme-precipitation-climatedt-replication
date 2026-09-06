# `docs/pico-study-outcome-levels.md` — PICO is the question, Study is the design, Outcome is the result

The four FORRT-chain forms — PICO (or PCC), Replication Study, and Replication Outcome — separate cleanly into question / scope / method / results. Each form's fields are a level of abstraction; mixing levels is the most common source of non-composable nanopubs.

## The four levels

| Form | Field | Contains | Does NOT contain |
|---|---|---|---|
| PICO | all P/I/C/O fields | discipline-level concepts only | implementation details, sample counts, exact numbers |
| Replication Study | "what part of the claim is reproduced" | the **scope** of the claim being tested | methodology, library calls, results |
| Replication Study | "how the claim is reproduced" | the **method** in plain prose | exact numerical results, accuracies, F1 scores |
| Replication Outcome | "conclusion" + "evidence" + "limitations" | results, including all numerical headlines and substantive interpretation | (nothing extra to exclude — this is the only place results go) |

## Why this matters

PICO is searched / reused / cited as a *research question*. If it carries methodology, downstream readers conflate the question with the implementation, and the same question can't anchor a *different* method's chain.

The Replication Study is searched / reused / cited as a *replication design*. If it carries results, the design becomes confused with the outcome and other replicators can't see what they're replicating without also pre-committing to your specific numerical conclusion.

Keeping the layers clean makes the chain composable: a question can anchor multiple Studies (different methods); a Study can anchor multiple Outcomes (different runs, different data extensions); an Outcome carries the only result-level claim.

## Pre-flight checklist

Before drafting PICO/PCC or Replication Study fields, sanity-check these specifically:

### PICO Population
- Am I describing the *kind of data*, or am I describing my *experimental setup* (sample counts, raster resolution, exact event amplitude)? **If the latter, move to Study "how".**

### PICO Intervention
- Am I describing the *approach* (e.g., "sphere-aware ML on HEALPix"), or am I describing the *implementation* (e.g., `hp.map2alm` at lmax=64 with `fₗ = 0` for `ℓ < 5`)? **If the latter, move to Study "how".**

### PICO Comparison
- Same rule. The comparator is conceptual ("flat lat-lon CNN baseline"), not implementation-specific.

### PICO Outcome
- Am I describing what gets *measured* (e.g., "classification accuracy at the 70-80° latitude band"), or am I quoting the *measurement value* (e.g., "1.000 accuracy")? **The value goes in the Outcome's evidence field, not in PICO Outcome.**

### Study "what is reproduced"
- Am I describing the **scope** (which aspect of the claim, what's in/out of scope, what's the comparator scope), or am I sneaking method or results in? **If method, move to "how"; if results, drop entirely (they live in Outcome).**

### Study "how is reproduced"
- Am I describing the *method*, or am I quoting *numbers*? **Drop the numbers.** Specific numerical hyperparameters (batch size, lmax, nside) belong here as configuration, but result numbers don't.

## Before-and-after example

A previously-flagged version of a PICO Intervention field (BAD):

> A sphere-harmonic band-pass matched filter on HEALPix-NESTED nside=64 — aggregate the lat-lon SST to HEALPix, mean-subtract, transform via `healpy.map2alm` at lmax=64, multiply by `fₗ × bₗ` where `fₗ = 0` for `ℓ < 5` (high-pass to remove the cosine-of-latitude SST baseline) and `bₗ` is a Gaussian beam with `FWHM = 2 × 10° = 20°` (matched to the cap diameter), inverse SHT via `healpy.alm2map`, return `(max, mean, std)` of the response field, fed to a logistic-regression classifier head.

Revised (GOOD):

> Sphere-aware machine learning — feature extraction and detection that operate directly on a HEALPix-NESTED substrate, exploiting rotation equivariance on the sphere.

The implementation specifics moved from PICO Intervention into the Study form's "how the claim is reproduced" field, where they belong.

## When you're tempted to put a number in PICO

You're not writing a paper-style methods section. The PICO is a discipline-level question that someone scanning the platform's question feed might use to find your work, even if their methods would be different. If you can't write the question without a number, the number is probably in the wrong field.

## Cross-references

- Form structure: `docs/forrt-form-fields.md` § PICO / FORRT Replication Study / FORRT Replication Outcome.
- Verify-code-before-drafting rule: `docs/verify-before-drafting.md`.
- Atomic AIDA: `CLAUDE.md` § Atomic AIDA.
