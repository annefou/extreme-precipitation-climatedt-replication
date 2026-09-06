# `chain-draft.json` — the pre-filled FORRT-chain hand-off contract

This document defines `chain-draft.json`: the interface between **this template
repo** (which produces it) and the **Science Live platform's FORRT-chain wizard**
(which consumes it). It exists so a user can publish a whole FORRT chain by
reviewing pre-filled fields step by step, instead of hand-copying values from the
`nanopubs/drafts/` files into the Science Live form and pasting URIs back into
`PUBLISHED.md`.

## The workflow it enables

Today: the drafts are authored during the replication; the user then reads each
one, **manually** fills the fields in `platform.sciencelive4all.org`, publishes,
copies the returned URI back into `nanopubs/PUBLISHED.md`, and repeats — six
times, in order. At the end `PUBLISHED.md` becomes the Jupyter Book landing page.

With this contract: the template repo emits one `chain-draft.json` carrying every
step's values. The platform wizard imports it and walks the user through the
chain — each step pre-filled, the user reviews and publishes, and **the wizard
carries each published URI into the next step's back-reference automatically**
(no copy-paste). The URI ledger falls out of the wizard rather than being
hand-maintained.

Two things pre-fill each step:

1. **Repo-derived values** — carried in this file (`prefill`). Only the repo
   knows these: the paper DOI, the Zenodo version DOI, the SWHID, the release
   date, and the drafted content (quotation, methodology, conclusion, …).
2. **Chain linkage** — *not* in this file. Step N's published URI fills step
   N+1's back-reference field; the wizard owns this because only it knows the URI
   at publish time. This file only declares the topology (`carry_forward`).

## Producer and consumer

- **Producer:** `scripts/build_chain_draft.py` in this repo (reads `CITATION.cff`,
  `nanopubs/PUBLISHED.md`, `nanopubs/drafts/`, and `nanopubs/templates/` — see
  "Value sources"). Output: `nanopubs/chain-draft.json`, **committed to the repo**
  (not git-ignored) so the wizard can load it by URL — its values are all
  non-secret repo-derived content. Regenerate and commit when the drafts change.
- **Consumer:** the platform wizard (`science-live-platform`), which already has
  every FORRT template form component and a dormant `prefilledData` prop on each.
  The wizard spreads each step's `prefill` object straight onto that prop — no
  mapping layer, because the keys already are the component field names (below).

## How the wizard loads the file — by URL, not upload

The wizard takes the draft as a **URL**, not a file upload — simpler for the user
and less code (`fetch(url).then(r => r.json())` instead of a file picker + reader).
Because `chain-draft.json` is committed, every repo has a stable raw URL for it.

The intended entry is a **deep link**, so a repo's Jupyter Book (or README) can
carry a *"Publish this chain on Science Live"* button that opens the wizard
already pointed at the draft — zero steps for the researcher:

```
https://platform.sciencelive4all.org/np/create/chain?draft=<url-encoded raw chain-draft.json URL>
```

**CORS caveat for the wizard implementer.** A browser `fetch` of
`raw.githubusercontent.com` can be blocked by cross-origin policy. Prefer a
CORS-clean source: the GitHub Contents API
(`https://api.github.com/repos/OWNER/REPO/contents/nanopubs/chain-draft.json`,
which returns base64 content with permissive CORS) or a CDN mirror
(`https://cdn.jsdelivr.net/gh/OWNER/REPO/nanopubs/chain-draft.json`). The producer
side is unaffected — it just writes the committed file.

## Field-name keys are the platform's, not ours

The keys inside `prefill` are the **exact field `name`s of the platform's template
components** (what its `prefilledData` prop expects) — verified against
`science-live-platform/frontend/src/pages/np/create/components/templates/`. They
happen to equal the placeholder local names in `nanopubs/templates/fields.snapshot.json`,
but the platform component is the authority. If a template component renames a
field, this contract's keys follow it (and `build_chain_draft.py` must be updated).

| Step (`step`) | `template_key` | Field keys (component `name`s) |
|---|---|---|
| `01_quote` | `ANNOTATE_QUOTATION` | `paper`, `quotation`, `quotation-end`, `comment` |
| `02_aida` | `AIDA_SENTENCE` | `aida`, `topic`, `project`, `dataset`, `publication` |
| `03_claim` | `FORRT_CLAIM` | `claim`, `label`, `aida`, `forrtType`, `source` |
| `04_study` | `FORRT_REPLICATION` | `study`, `label`, `type`, `claim`, `scope`, `methodology`, `deviation` |
| `05_outcome` | `FORRT_REPLICATION_OUTCOME` | `outcome`, `label`, `study`, `repo`, `date`, `validationStatus`, `confidenceLevel`, `conclusion`, `evidence`, `limitations` |
| `06_citation` | `CITATION_CITO` | `work`, `cites`, `cited` |

Question-rooted chains replace `01_quote` with `01_pico` (`PICO_RESEARCH_QUESTION`)
or `01_pcc` (`PCC_RESEARCH_QUESTION`); the optional `07_research_software`
(`RESEARCH_SOFTWARE`) and `08_synthesis` (`RESEARCH_SYNTHESIS`) steps append when
applicable.

## Repeatable and complex fields — array-shaped, form-field names

A few template fields are **repeatable groups** (an "add another" list) or custom
widgets, and for these the component's form-field name is **not** the template
placeholder name and the value is **not** a flat string. `prefill` must use the
form-field name and the exact shape below (verified against the platform's
`create/components/templates/*.tsx`). The producer hard-codes these; the wizard
stays a pass-through.

| Step | Form field (prefill key) | Shape | Notes |
|---|---|---|---|
| `06_citation` | `st02` | `[{ cites, cited }]` | **required ≥1.** `cites` = a CiTO relation URI, `cited` = the cited work. This replaces flat `cites`/`cited`. |
| `08_synthesis` | `sources` | `[{ source }]` | required ≥1 |
| `08_synthesis` | `topicSelection` | `[{ uri, label }]` | required ≥1 |
| `02_aida` | `st3` / `st4` | `[{ dataset }]` / `[{ publication }]` | optional |
| `02_aida` | `topic` | `[{ uri, label }]` | optional |
| `04_study` | `keywordSelection` | `[{ uri, label }]` | optional |
| `04_study` | `disciplineSelection` | `{ uri, label }` | optional — a single object, **not** an array |
| `07_research_software` | `datasets` / `researchOutputs` | `["url", …]` | optional — plain-string arrays |

Two runtime notes for the wizard: **date** fields (`05_outcome.date`,
`08_synthesis.date`) want a JS `Date` — the wizard converts a `YYYY-MM-DD` prefill
string to a `Date` before passing it on; and the `minItems: 1` groups above must
always carry at least one entry or the form won't submit.

## Judgment fields are pre-filled, not left blank

The `restricted_choice` dropdowns (claim type, study type, validation status,
confidence, CiTO relation) are **decisions the agent already made during the
replication**, recorded in the drafts — not things to leave to a form default
(which can be wrong). The producer reads the agent's ticked option from the draft
and puts it in `prefill` as an editable suggestion, **and** keeps the field in
`manual` so the wizard flags it "confirm" rather than "you choose". The CiTO
relation is derived from the validation status (Validated→`confirms`,
PartiallySupported→`qualifies`, Contradicted→`disputes`, …).

The **URI-suffix id** of each step (`claim`, `study`, `outcome`, …), if the draft
gives none, is suggested as `<org>-<repo>-<step>` (from `CITATION.cff`'s
`repository-code`), editable.

**Wikidata concept fields** (`04_study.keywordSelection`/`disciplineSelection`,
`02_aida.topic`, `08_synthesis.topicSelection`) need a `{uri, label}` — but the
draft records only plain labels. The producer resolves each label to a Wikidata
QID at build time (one `wbsearchentities` call per label; this is the producer's
only network use, and it degrades to leaving the field empty if Wikidata is
unreachable). `disciplineSelection` is a single object; the rest are arrays.

## Carry-forward topology

Each step's published URI fills one field of the next step. These edges are fixed
for a FORRT chain and are declared in `carry_forward` so the wizard is generic:

| From (published) | Into | Field |
|---|---|---|
| `01_quote` | `02_aida` | `project` (labelled "Relates to this nanopublication") |
| `02_aida` | `03_claim` | `aida` |
| `03_claim` | `04_study` | `claim` |
| `04_study` | `05_outcome` | `study` |
| `05_outcome` | `06_citation` | `work` |

The wizard fills the carry-forward field from its captured URI; it does **not**
appear in the producer's `prefill` (the URI does not exist until publish time).

### Optional side-branches (07 / 08) — multiple, non-adjacent, shaped edges

The two optional layers don't continue the linear chain — they link **back** to
earlier steps, and a step can have **several** incoming edges. So a step may be
the `into` of more than one edge, the `from` may be any earlier step (not just the
immediately-preceding one), and the target field may be an array rather than a
scalar. Two optional keys on an edge describe the target shape:

| From (published) | Into | Field | `mode` / `itemKey` | Injected as |
|---|---|---|---|---|
| `03_claim` | `07_research_software` | `project` | — (scalar) | `"<uri>"` |
| `05_outcome` | `07_research_software` | `researchOutputs` | `mode: "uriList"` | `["<uri>"]` (appended) |
| `05_outcome` | `08_synthesis` | `sources` | `mode: "uriObjectList"`, `itemKey: "source"` | `[{ "source": "<uri>" }]` (appended) |

- **No `mode`** → scalar string (the linear edges above, and `07.project`).
- **`mode: "uriList"`** → append the URI to an array-of-strings field.
- **`mode: "uriObjectList"`** (+ `itemKey`) → append `{ [itemKey]: uri }` to an
  array-of-objects field.

These edges are emitted only when **both** ends are present in the chain (the
producer appends 07/08 only when their drafts have content). As with the linear
edges, the carried field is absent from the step's `prefill`.

### Known friction (for the wizard implementer)

Most back-reference fields are plain text inputs (`02_aida.project`,
`06_citation.work`) and prefill cleanly. But `04_study.claim` is a custom search
combobox (`QueryComboboxField`) with its own internal selection state — setting
the form value may not update its visible selection. The wizard should set the
widget's display state as well as the form value for combobox-backed carry-forward
fields.

## Schema

```jsonc
{
  "schema_version": "1.0",
  "kind": "forrt-chain-draft",
  "chain_shape": "paper-rooted",          // "paper-rooted" | "pico" | "pcc"
  "source": {
    "repository": "https://github.com/OWNER/REPO",
    "commit": "<sha>",                     // the repo state the values were drawn from
    "figure": "figures/main_result.png"    // optional; absent when the repo has none
  },
  "steps": [
    {
      "step": "01_quote",                  // stable step id (matches nanopubs/drafts/ + snapshot)
      "template_key": "ANNOTATE_QUOTATION",
      "template_uri": "https://w3id.org/np/RA24onqmqTMsraJ7ypYFOuckmNWpo4Zv5gsLqhXt7xYPU",
      "prefill": {                         // component field name -> value; only known values appear
        "paper": "10.5281/zenodo.123456",
        "quotation": "…verbatim…",
        "comment": "…interpretation…"
      },
      "provenance": {                      // optional: where each value came from, for the review UI
        "paper": "CITATION.cff references[article]",
        "quotation": "nanopubs/drafts/01_quote.md",
        "comment": "nanopubs/drafts/01_quote.md"
      },
      "manual": ["quoteType"],             // optional: fields the user must set/choose in the wizard
      "published_uri": null                // from PUBLISHED.md; non-null means already done (resume)
    }
  ],
  "carry_forward": [
    { "from": "01_quote",   "into": "02_aida",     "field": "project" },
    { "from": "02_aida",    "into": "03_claim",    "field": "aida"    },
    { "from": "03_claim",   "into": "04_study",    "field": "claim"   },
    { "from": "04_study",   "into": "05_outcome",  "field": "study"   },
    { "from": "05_outcome", "into": "06_citation", "field": "work"    },
    // optional side-branches — only when 07/08 are in the chain (see above):
    { "from": "03_claim",   "into": "07_research_software", "field": "project" },
    { "from": "05_outcome", "into": "07_research_software", "field": "researchOutputs", "mode": "uriList" },
    { "from": "05_outcome", "into": "08_synthesis", "field": "sources", "mode": "uriObjectList", "itemKey": "source" }
  ]
}
```

Rules:

- **Only known values appear in `prefill`.** A field the repo can't fill is
  simply absent — the wizard renders it empty for the user. Never emit a `{{TOKEN}}`
  or a placeholder string as a value.
- **`manual`** lists fields the user is expected to decide in the wizard — the
  judgment calls (`forrtType`, `validationStatus`, `confidenceLevel`, `type`, the
  CiTO `cites` relation). The wizard already renders these with the template's own
  vocabulary; `manual` is a review-UI hint, not data.
- **`published_uri`** lets the wizard resume a partly-published chain: skip steps
  that already have a URI and seed carry-forward from them.
- **Determinism:** the producer does not stamp a timestamp (so regenerating on an
  unchanged repo yields an identical file); `source.commit` records the state.

## The headline figure

`source.figure` is the repo-relative path to the one image that represents the
replication. It is **not** published in any nanopublication and the wizard does
not consume it — it is recorded because the producer is where a missing figure
can still be noticed and fixed.

The story page the platform generates from a published chain finds the figure by
resolving the chain's Zenodo DOI to its GitHub repo and looking in `figures/`.
So the figure reaches the blog by *being committed at that path*, not by being
declared here. The producer applies the same rule the platform does:

- only `figures/` is scanned — never `results/`, which collects run artefacts;
- among several images, a name matching `main`, `result`, `headline` or `hero`
  wins; otherwise the alphabetically first, so the pick never varies by machine;
- `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg` count as images.

When nothing is found the producer says so on stderr. The failure this catches is
a figure written to a **git-ignored** path: it exists on the machine that ran the
experiment, the author sees it locally, and the published story page has no image.

Because the choice is inferred from filenames rather than stated by the author,
it is a sensible default and not a permanent contract — a future FORRT template
field would let the author name the figure explicitly and have it signed.

## Value sources (what the producer fills from where)

| Field(s) | Source |
|---|---|
| `01_quote.paper`, `03_claim.source`, `06_citation.cited` (paper DOI) | `CITATION.cff` → `references` (`type: article`) → `doi` |
| `05_outcome.repo`, `07_research_software.software` (version DOI) | `CITATION.cff` → `identifiers` → the **Version DOI** entry |
| `07_research_software` SWHID | `CITATION.cff` → `identifiers` (`type: swh`) |
| `05_outcome.date`, `08_synthesis` date | `CITATION.cff` → `date-released` |
| `*.label` | derived from `CITATION.cff` `title` / the drafted content |
| `quotation`, `comment`, `aida`, `scope`, `methodology`, `deviation`, `conclusion`, `evidence`, `limitations`, … (drafted content) | `nanopubs/drafts/0X_*.md` (authored by the `nanopub-drafter` agent during the replication) |
| `carry_forward` fields, `published_uri` | `nanopubs/PUBLISHED.md` |
| field set, `template_uri`, dropdown vocabularies | `nanopubs/templates/registry.json` + `fields.snapshot.json` |

Identity (author ORCID/name) is **not** a chain-draft field — the platform takes
it from the signed-in user's profile.

## Versioning

`schema_version` is bumped on any breaking change to the shape. The wizard should
reject a `schema_version` it doesn't understand rather than guess. Additive,
optional fields (like `provenance`) do not bump the major version.
