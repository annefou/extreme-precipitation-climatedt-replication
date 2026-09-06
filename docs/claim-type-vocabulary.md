# `docs/claim-type-vocabulary.md` — FORRT Claim "Type of FORRT claim" controlled vocabulary

The Science Live FORRT Claim template's **"Type of FORRT claim"** field is a single-select dropdown that classifies the **scientific genre** of the claim being asserted. It is **not** the type of replication being performed — that distinction (Reproduction / Replication / both) lives on the Replication Study template's "Study type" field.

## The seven options

1. **computational performance** — *Computational & Performance.* Runtime, throughput, latency claims (e.g. "method X runs in O(n log n)").
2. **scalability** — *Computational & Performance.* How a method behaves as data size or compute grows.
3. **data quality** — *preprocessing, validation, normalization.* Claims about preserving fidelity through preprocessing/transformations (e.g. "EarthCARE → DGGS conversion preserves geospatial information").
4. **data governance** — *access control, licensing, FAIR compliance.* Claims about access, licensing, FAIR conformance (e.g. "this dataset complies with FAIR4RS").
5. **descriptive pattern** — *observed trend, distribution, correlation.* Claims about an observed empirical relationship between variables (e.g. Soroye 2020: thermal exposure correlates with bumble bee extirpation).
6. **model performance** — *accuracy, F1 score, evaluation metrics.* Claims about an ML/statistical model's accuracy, F1, RMSE, etc.
7. **statistical significance** — *p-value, confidence interval.* Claims that a statistical test is significant. Use when the claim *is* about the test result itself, not the underlying pattern.

## How to choose

Pick the genre that best describes what the claim asserts about the world. Common confusions:

- **descriptive pattern vs. statistical significance.** Soroye 2020's headline ("thermal exposure correlates with bumble bee extirpation") is `descriptive pattern` — significance is the *evidence*, but the pattern is the claim. Pick `statistical significance` only when the claim is literally "the test was significant", with no underlying empirical relationship being asserted.

- **model performance vs. computational performance.** A CNN's top-1 accuracy is `model performance`. A CNN's training time is `computational performance`. If the claim is about both, pick the one the paper headlines.

- **data quality vs. data governance.** A claim about preserving information through a transformation is `data quality`. A claim about FAIR/license/access conditions is `data governance`. The two only overlap when a transformation explicitly cites a FAIR principle as its quality criterion.

- **descriptive pattern vs. model performance.** Empirical relationships discovered by fitting a model are `descriptive pattern` (the model is the instrument; the pattern is the claim). Performance of a model on a held-out test set is `model performance` (the model itself is the claim).

## Example mappings

| Replication | Claim type |
|---|---|
| `weatherxbiodiversity` (Soroye 2020 — bumble bee thermal-exposure correlation) | `descriptive pattern` |
| `fiesta-decrop-reproduction` (CNN top-1 accuracy reproduces) | `model performance` |
| `earthcare-dggs` (EarthCARE → HEALPix DGGS preserves info) | `data quality` |
| `dggs-biodiversity-bias` (DGGS gives more accurate biodiversity metrics than lat-lon grids) | `model performance` (or `descriptive pattern` if framed as the underlying truth being recovered) |
| `spherical-ml-biodiversity` chain A (sphere-aware filter beats flat at high latitude) | `model performance` |
| `spherical-ml-biodiversity` chain B (94 percent of GBIF occurrences fell on MHW cells during Ningaloo Niño 2011) | `descriptive pattern` |

## Cross-references

- **Replication-type taxonomy** (Reproducibility / Robustness / Replicability / Generalizability) is on the Replication Study template's "Study type" field, not here. See `docs/forrt-form-fields.md` § FORRT Replication Study.
- **Validation status** (Validated / PartiallySupported / Contradicted) is on the Outcome template, mapping to CiTO intention in the Citation step. See `docs/forrt-form-fields.md` § FORRT Replication Outcome and § Citation with CiTO.
