# `nanopubs/templates/` — the FORRT chain templates as the schema of record

Every step of a FORRT chain is published by filling in a **Science Live nanopub
template**. Each template is itself a signed nanopublication whose typed
placeholders (`nt:LiteralPlaceholder`, `nt:RestrictedChoicePlaceholder` with its
enumerated `nt:possibleValue`s, `nt:OptionalStatement` for requiredness,
`nt:hasRegex` for character caps, …) define the fields of that step. **That
template is the schema** — not `docs/forrt-form-fields.md`, which is a
human-readable transcription of it.

The audit that drives the template-hardening work found that the transcription
had silently drifted from the templates (validation status documented as 3
options when the template had 5; the Quote comment documented as a 500-char cap
when the template allows 800) because nothing pinned the two together and
nothing checked them. **The repository recorded zero template URIs.** These
files close that gap.

## The three files

| File | What it is | Maintained by |
|---|---|---|
| `registry.json` | The template URI per chain step (`current`) plus the curated prior versions still in use (`superseded`). The pin that was missing. | Hand-vendored from science-live-platform; see below. |
| `fields.snapshot.json` | The field spec extracted from every `current` template — labels, kinds, requiredness, restricted-choice vocabularies, `possibleValuesFromApi`, regex caps. | **Generated** — `scripts/check_template_drift.py --update`. Do not hand-edit. |

There is no vendored TriG copy of the templates: the committed snapshot and the
live nanopub network are the two representations, and the drift check reconciles
them. Extraction lives in `scripts/template_fields.py` (pure, offline, `rdflib`);
`tests/test_template_fields.py` locks it against fixtures in
`tests/fixtures/templates/`.

## `registry.json` — current vs superseded

`current` URIs are vendored from ScienceLiveHub/science-live-platform,
`frontend/src/pages/np/create/components/templates/registry-metadata.ts`
(`TEMPLATE_URI`). `superseded` URIs are vendored from that file's
`LEGACY_TEMPLATE_URIS`.

The `superseded` list is **not** the full `npx:supersedes` chain. Templates are
edited iteratively, and most of the chain is throwaway test versions that were
never published from — the AIDA template's chain is eleven deep, but only a
handful of those versions have any published nanopubs. The criterion for
inclusion is empirical: **a prior version with at least one published nanopub on
the network.** (Checked with a `wasCreatedFromTemplate` count; the unlisted
predecessors of Quote / Study / Outcome / Research Software all return zero.)

## Drift check

`scripts/check_template_drift.py` fetches the live `current` templates and diffs
their extracted specs against `fields.snapshot.json`:

```bash
pixi run -e tests check-templates            # exit 1 on drift, with a readable diff
pixi run -e tests python scripts/check_template_drift.py --update   # re-vendor the snapshot
```

It is **networked**, so it is not part of the per-PR CI gate (which is
deliberately network-free). It runs monthly and on demand via
`.github/workflows/template-drift.yml`. The offline extractor tests run in the
ordinary `test` job.

### When the drift check fails

A failure means a template was superseded upstream. It is a normal, expected
event — the point is that it is now **loud and reviewable** instead of a slow
divergence nobody notices. To resolve:

1. `pixi run -e tests python scripts/check_template_drift.py --update`
2. Read the JSON diff in `fields.snapshot.json`. That diff is the exact set of
   field / vocabulary / cap changes.
3. Reconcile `docs/forrt-form-fields.md` (and any affected `nanopubs/drafts/`
   skeleton) with those changes.
4. If the old template URI is now a prior version people have published from,
   move it into `registry.json` `superseded`; update `current` to the new URI.
5. Commit the regenerated snapshot and the reconciled docs together.

## What this does not do

It pins the **field structure** of the standard FORRT chain templates. It does
not resolve `possibleValuesFrom` value-list nanopubs (e.g. the CiTO relation
vocabulary — it records the pointer, not the expanded list), and it does not
generate the draft skeletons in `nanopubs/drafts/` from the templates. Both are
natural follow-ups now that the extractor exists.
