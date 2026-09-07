# Published nanopub chain — URI registry

This file is the canonical registry of published nanopub URIs for this replication. Update it as you publish each step.

## Chain

| Step | Template | URI | Published |
|---|---|---|---|
| 01 | Quote-with-comment | https://w3id.org/sciencelive/np/RAGFxQEhyijfEXZ0fZCdsnPkfa9xhyi3EtkfeACdxU7EQ | 2026-09-07 |
| 02 | AIDA Sentence | https://w3id.org/sciencelive/np/RAT7-YqPy3iaywOuuWKpSMl_pexB8Dfe8bqriXzBnW_ek | 2026-09-07 |
| 03 | FORRT Claim | https://w3id.org/sciencelive/np/RAz-DKQA8-UhwW_w9QMtuRAcmimmE-1zxz_dGkI8_3llo | 2026-09-07 |
| 04 | FORRT Replication Study | https://w3id.org/sciencelive/np/RAazzwF05nb7FbNBMNBoNLGRygKzqD-CMFgo8fA4zbS6s | 2026-09-07 |
| 05 | FORRT Replication Outcome | https://w3id.org/sciencelive/np/RACgxEzHoCa6VWoEV7tFPLMAhqrwXMvUlzg3KuWwHl0l4 | 2026-09-07 |
| 06 | CiTO Citation | https://w3id.org/sciencelive/np/RAbhgs4f839xduTVH0aI6GifJz3kZxGmxWi4gI7WDYb1I | 2026-09-07 |

**Chain shape:** paper-rooted — Quote-with-comment → AIDA → FORRT Claim →
Replication Study → Replication Outcome → CiTO Citation. Published 2026-09-07 on the
Science Live platform, in that order, each step carrying the previous step's URI.

**Outcome:** `validated`. The CiTO relation to the original paper is `confirms`.

Full URIs, for copy-paste:

```
01 quote    https://w3id.org/sciencelive/np/RAGFxQEhyijfEXZ0fZCdsnPkfa9xhyi3EtkfeACdxU7EQ
02 aida     https://w3id.org/sciencelive/np/RAT7-YqPy3iaywOuuWKpSMl_pexB8Dfe8bqriXzBnW_ek
03 claim    https://w3id.org/sciencelive/np/RAz-DKQA8-UhwW_w9QMtuRAcmimmE-1zxz_dGkI8_3llo
04 study    https://w3id.org/sciencelive/np/RAazzwF05nb7FbNBMNBoNLGRygKzqD-CMFgo8fA4zbS6s
05 outcome  https://w3id.org/sciencelive/np/RACgxEzHoCa6VWoEV7tFPLMAhqrwXMvUlzg3KuWwHl0l4
06 citation https://w3id.org/sciencelive/np/RAbhgs4f839xduTVH0aI6GifJz3kZxGmxWi4gI7WDYb1I
```

## What the chain records

| | |
|---|---|
| Claim tested | Short-duration, long-return-period extremes intensify most under warming |
| Original paper | [10.1002/joc.8393](https://doi.org/10.1002/joc.8393) — Hundhausen et al. 2024 |
| Replication data | Destination Earth Climate DT gen 2, IFS-NEMO, SSP3-7.0 |
| Verdict | **validated** — largest change +16.88 % at 1 h / 20 y, the corner the paper names |
| Software archive | [10.5281/zenodo.22641172](https://doi.org/10.5281/zenodo.22641172) (v0.1.0 version DOI) |

## Optional layers

| Step | Template | URI | Published |
|---|---|---|---|
| 07 | Research Software (if applicable) | _not applicable / not yet published_ | |
| 08 | Research Synthesis (if applicable) | _not applicable — one chain; a synthesis is for several chains testing facets of one property_ | |

## Format

URIs from Science Live are of the form `https://w3id.org/sciencelive/np/RA…`. URIs from Nanodash (used as a fallback when the Science Live UI hits a bug) are of the form `https://w3id.org/np/RA…`. Both are valid and citable.

If a URI is not in the Science Live namespace, view it via the Science Live viewer by wrapping the URI:

```
https://platform.sciencelive4all.org/np/?uri=<full-URI>
```

## Cross-references

- Drafts: `nanopubs/drafts/`
- Form structure: `docs/forrt-form-fields.md`
- Chain shape decision: `docs/chain-decision-tree.md`

## A note on the Wikidata topics

The topics in the published AIDA were **added by hand in the publishing wizard**,
not carried from `chain-draft.json`. At the time of publication
`build_chain_draft.py` was dropping them silently — it read only bullets, while
`02_aida.md` listed its topics in a fenced block, and it reported nothing. Fixed
in template PR #36 and in this repo's copy; the drafts now write `label (Qnnn)`
so the QID that was type-checked is the one used.

Verified in the published RDF (`https://w3id.org/np/RAT7-…`, not the
`…/sciencelive/np/…` viewer URL, which serves an HTML shell):

```
<http://schema.org/about> <http://www.wikidata.org/entity/Q111089542>,
                          <http://www.wikidata.org/entity/Q125928>,
                          <http://www.wikidata.org/entity/Q7942> ;
```

`Q125928` is *climate change*; `Q7942` is *global warming*. Both are present. The
draft specifies Q7942, which is the item that was type-checked against this
field's `owl:Class` requirement.
