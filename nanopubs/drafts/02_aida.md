# 02 — AIDA Sentence

> Run the pre-flight checklist in `docs/forrt-form-fields.md` § Pre-flight checklist before drafting.

**Form heading:** *"AIDA Sentence — Make structured scientific claims following the AIDA model"*

## Field-by-field draft

<!-- field: aida -->
### AIDA sentence (text input, required)

Atomic, Independent, Declarative, Absolute. One empirical finding. Must end with a full stop.

> _If your draft AIDA contains "and" linking two distinct findings, split into two AIDA nanopubs._

Atomicity check: the two "and"s here join the two *arms of one comparison*
(short-duration/long-RP vs long-duration/short-RP), not two separate findings.
One empirical claim: a rank ordering of the intensification response across the
duration x return-period matrix.

Deliberately carries no region, no model and no number, so it is testable in any
domain with hourly km-scale data — a later chain can `extends` it to another
country. The magnitude (6 or 8.5% per K) belongs in the Outcome as evidence, not
here.

```
Under global warming, extreme precipitation events of short duration and long return period intensify proportionally more than events of long duration and short return period.
```

<!-- field: topic -->
### Select related topics/tags (search/select, optional)

Predefined topic vocabulary — list the labels you intend to pick from the dropdown.

Each verified with `wikidata_lookup`: this field's template declares `owl:Class`,
so every term below was confirmed to carry a `P279` (subclass of) statement.

| Label | QID | P279 | |
|---|---|---|---|
| extreme rainfall | Q111089542 | ✓ | the phenomenon the claim is about |
| global warming | Q7942 | ✓ | the forcing the response is scaled against |
| climate change adaptation | Q260607 | ✓ | why the duration/return-period structure matters |

**Not used: `return period` (Q2627230).** It is the right concept, but the
Wikidata item carries *no* `P31` or `P279` statements at all, so it fails this
field's `owl:Class` requirement. It would be acceptable in a plain keyword field,
which imposes no type.

```
extreme rainfall
global warming
climate change adaptation
```

<!-- field: project -->
### Relates to this nanopublication (search/select, required)

URI of the nanopub the AIDA derives from.

- For paper-rooted chains: the Quote-with-comment URI (from step 01).
- For question-rooted chains: the PICO or PCC URI (from step 01).

Pull the URI from `nanopubs/PUBLISHED.md`.

```

```

<!-- field: dataset -->
### Supported by datasets (text input, optional)

DOIs/URLs of datasets that ground the AIDA claim.

- _DOI 1: ___
- _DOI 2: ___

<!-- field: publication -->
### Supported by other publications (text input, optional)

DOIs/URLs of publications that support the AIDA claim — e.g. peer-reviewed methods papers, or the original paper if not already cited via the Quote.

- _DOI 1: ___
- _DOI 2: ___

> **Known platform bug (2026-04-26):** if both *Supported by datasets* AND *Supported by other publications* are populated and publishing fails, fall back to publishing this AIDA via Nanodash. The URI namespace becomes `https://w3id.org/np/...` (still valid and citable).

## Publication note

After publishing, paste the resulting URI into `nanopubs/PUBLISHED.md` step 02.
