# `docs/forrt-form-fields.md` — verbatim Science Live nanopub form fields

This document records the **exact form structure** of each Science Live nanopublication template, so drafts map 1:1 to the form. Don't draft against an imagined structure. Don't invent field names. Don't ship a draft that contains only the headline content (the AIDA sentence, the verbatim quote, the conclusion text) without the full field enumeration.

> **This prose is a companion, not the source of truth. The templates are.**
> Each Science Live template *is itself* a nanopublication whose typed placeholders
> define the fields, their requiredness, their allowed values, and their character
> caps. Those template URIs are pinned in [`../nanopubs/templates/registry.json`](../nanopubs/templates/registry.json);
> the extracted field spec of every current template is committed at
> [`../nanopubs/templates/fields.snapshot.json`](../nanopubs/templates/fields.snapshot.json);
> and `scripts/check_template_drift.py` (scheduled, see `.github/workflows/template-drift.yml`)
> fails when the live templates diverge from that snapshot. When it fails, a template
> was superseded upstream — read the diff, fix the affected section **here** to match,
> and commit the regenerated snapshot. This is how the transcription below is kept
> honest instead of silently rotting (the "validation status is 3 options" / "comment
> caps at 500" kind of drift). See [`../nanopubs/templates/README.md`](../nanopubs/templates/README.md).

## Pre-flight checklist — RUN THIS BEFORE EVERY NANOPUB DRAFT

Before drafting *any* nanopub content for *any* template — Quote-with-comment, AIDA, FORRT Claim, FORRT Replication Study, FORRT Replication Outcome, CiTO Citation, Research Software, Research Synthesis, PCC Question, PICO Question:

1. **Open this file and find the section for the template you're about to draft.**
2. **If the section says "not yet documented" / "needs screenshot": STOP.** Do not draft. Ask the user for a screenshot of the form on `platform.sciencelive4all.org`. Add the form structure to this file first. Only then draft.
3. **Enumerate every field in your draft, in the order they appear on the form, EVERY TIME.** Required fields: provide a value. Optional fields: provide a value if you have one, otherwise explicitly write *(skip — optional)*. The full enumeration is non-negotiable.
4. **Never invent field names.** If the form documentation doesn't list a field, do not make one up.
5. **Never put parenthetical "form may have other fields I don't know about" caveats inside an otherwise complete draft.** If you're missing fields, the answer is to stop and ask, not to ship a partial draft.
6. **At the START of each draft, paste the documented field list verbatim** (with its template URI / status note) so the user can verify alignment before content review.

This checklist exists because it is unreasonably easy to ship a partial draft that looks complete on the surface — the AIDA sentence is right, the quote is verbatim — but is missing the topic tags, the dataset references, or the source-paper "Supported by" group. Drafts that lose form structure cost the user a round-trip in the UI to figure out what's missing.

---

## Quote-with-comment ("Annotate a paper quotation")

Form heading: *"Annotate a paper quotation — Annotating a paper quotation with personal interpretation"*

> ⚠️ **Both the Quoted Text and the Comment cap at 500 characters on the live platform.** The Quoted Text limit is `{5,500}`. The **Comment is enforced at 500 by the live form too**, even though the vendored snapshot regex still reads `{5,800}` — treat **500 as the ceiling** (the snapshot is stale here; re-vendor it with `check_template_drift.py --update`). Brevity is the discipline regardless — a tight *why this quote matters* beats a padded comment. If your verbatim quote is longer than 500 chars, switch the radio button to **Quote start/end** mode and use start-phrase + end-phrase to mark a longer span instead of pasting the whole text.

| Field label | Field type | Notes |
|---|---|---|
| Cited DOI | text input | Format: starts with `10.` — placeholder reads "DOI, starting with 10." So enter `10.3389/fmars.2025.1699781`, **NOT** `https://doi.org/10.3389/...` |
| Quote whole text (less than 500 characters) | radio button (default selected) | Mode for quoting a single short passage. The Quoted Text field below must be ≤ 500 chars. |
| Quote start/end | radio button (alternative) | Alternative mode — two short text inputs for start phrase + end phrase, marking a longer span. Use when the quote is too long for whole-text mode. |
| Quoted Text | textarea, **required** | The verbatim sentence(s) from the paper. ≤ 500 chars in "Quote whole text" mode. **Must be character-for-character verbatim — see `docs/verify-before-drafting.md`.** |
| Comment | textarea, **required** | Subtitle: *"Our interpretation or explanation of why this quotation is relevant."* Explain **why the quotation matters on its own terms** — a standalone interpretation that must be **true independently of any replication**. Do **not** describe the replication, its design, or what it tests: the annotation stands alone and is reused by anyone citing the quote. **Cap 500 chars** (the live form enforces 500, even though the vendored regex reads `{5,800}`); aim well under it — long comments dilute the *why this quote matters* point and read as marketing rather than interpretation. |

Use this template for **paper-rooted chains** where you are testing or extending a sentence from someone else's paper. See `docs/chain-decision-tree.md`.

---

## AIDA sentence

Form heading: *"AIDA Sentence — Make structured scientific claims following the AIDA model"*

| Field label | Field type | Notes |
|---|---|---|
| Enter your AIDA sentence here (ending with a full stop) | textarea, **required** | The atomic, independent, declarative, absolute sentence. Must end with a full stop. |
| Select related topics/tags | dropdown, **optional** | Predefined topic vocabulary — open the dropdown and pick available labels. |
| Relates to this nanopublication | text input, **required** | URI of the nanopub the AIDA derives from. For paper-rooted chains this is the Quote-with-comment URI. For question-rooted chains, this is the PCC or PICO URI. |
| Supported by datasets | repeatable group ("+ Add Item"), **optional** | DOI/URL of datasets that ground the AIDA claim. |
| Supported by other publications | repeatable group ("+ Add Item"), **optional** | DOI/URL of publications that support the AIDA claim — e.g. the original paper if not already cited via the Quote, or peer-reviewed methods papers. |

**Atomic AIDA rule:** one AIDA sentence states one empirical finding. If your draft AIDA contains "and" linking two distinct findings, split it into two AIDA nanopubs anchored on two separate Claims. The whole point of AIDA is composability — non-atomic AIDAs cannot be cited individually.

**Known platform bug (2026-04-26):** publishing on Science Live with both *Supported by datasets* AND *Supported by other publications* fields populated has previously caused the platform to fail. Workaround if it happens again: publish the AIDA via Nanodash instead (URI namespace becomes `https://w3id.org/np/...` rather than `https://w3id.org/sciencelive/np/...`). The nanopub is valid and citable; the chain just has a mixed-namespace URI.

---

## FORRT Claim

Form heading: *"FORRT Claim — Declare an original claim according to FORRT, linking it to an AIDA sentence with a specific FORRT type."*

| Field label | Field type | Notes |
|---|---|---|
| Short URI suffix as claim ID | text input, **required** | Placeholder: "e.g. my-claim-01". Slug becomes part of nanopub URI. Use kebab-case. |
| Label of the claim (to find it later) | text input, **required** | Used for searches/discovery. A descriptive title, not a sentence. |
| Search for an AIDA sentence | search/select dropdown, **required** | Search by AIDA text → pick the published AIDA URI. **Caveat**: not yet confirmed whether this search finds AIDAs published via Nanodash (`w3id.org/np/...` namespace) versus only Science Live (`w3id.org/sciencelive/np/...`). If your AIDA was published via Nanodash, paste the URI manually rather than relying on search. |
| Type of FORRT claim | dropdown, **required** | Single-select from 7 options. See `docs/claim-type-vocabulary.md`. |
| Source URI (optional) | text input, **optional** | Placeholder: `https://doi.org/...` — **expects full URL form** (`https://doi.org/10.x/y`), unlike the Quote-with-comment "Cited DOI" field which expects bare `10.x/y`. |

There are no other substantive fields below "Source URI" — only a "publish as example" toggle. Earlier versions of this documentation listed Wikidata keywords / discipline fields here, but those live on the Replication Study and Outcome templates, not on the Claim.

---

## FORRT Replication Study

| Field label | Field type | Notes |
|---|---|---|
| Short URI suffix for study ID | text input, **required** | e.g. `soroye-replication-study` — short slug, becomes part of the nanopub URI. |
| Label/name of replication study | text input, **required** | The human-readable title. |
| Study type | dropdown, **required** | Three options: (1) **Reproduction Study** — direct reproduction: same methodology, same tools; (2) **Replication Study** — replication with different methodology or conditions; (3) **Reproduction/Replication Study** — both. |
| Search for a FORRT claim | search/select, **required** | Pick the published Claim URI. |
| Describe what part of the claim is reproduced/replicated | textarea, **required** | The **scope** of the claim being tested (which aspect, what's in/out of scope). NOT methodology. NOT results. See `docs/pico-study-outcome-levels.md`. |
| Describe how the claim is reproduced/replicated | textarea, **required** | The **method** in plain prose. NOT exact numerical results. |
| Describe any deviations from original methodology | textarea, **optional** | What's different from the original method. **Verify against the actual code first** — see `docs/verify-before-drafting.md`. |
| Search keywords (Wikidata) | multi-select Wikidata search, **optional** | Topic Q-ids — provide search labels rather than QIDs. |
| Search discipline (Wikidata) | search Wikidata, **optional** | Academic discipline Q-ids. |

---

## FORRT Replication Outcome

| Field label | Field type | Notes |
|---|---|---|
| Short URI suffix for outcome ID | text input, **required** | e.g. `my-outcome-01`. |
| Plain-text label for the outcome | text input, **required** | Descriptive title. |
| Search for a FORRT replication study | search/select, **required** | Pick the published Replication Study URI. |
| Repository URL | text input, **required** | e.g. `https://github.com/{{REPO_ORG}}/{{REPO_NAME}}`. |
| Completion date | date picker, **required** | When the replication finished (ISO format). |
| Validation status | dropdown, **required** | Vocabulary (5 options, signalling the direction of agreement rather than the strength of evidence): `Validated` (validated) / `PartiallySupported` (partially supported) / `Contradicted` (contradicted) / `Inconclusive` (inconclusive) / `NotTested` (not tested). Maps to CiTO intention in the Citation step: Validated → `cito:confirms`; PartiallySupported → `cito:qualifies`; Contradicted → `cito:disputes`. `Inconclusive` and `NotTested` have no canonical CiTO mapping — use `cito:discusses` or `cito:cites` as a neutral choice when no stronger claim is warranted. |
| Confidence level | dropdown, **required** | Vocabulary (5 options, signalling how strong the evidence is rather than the direction of agreement): `VeryHighConfidence` (very high — extensive evidence, high agreement with original) / `HighConfidence` (high — strong evidence, mostly agrees with original) / `Moderate` (moderate — adequate evidence, partial agreement) / `LowConfidence` (low — limited evidence, significant disagreement) / `VeryLowConfidence` (very low — minimal evidence, major disagreement). Independent of Validation status — a `Contradicted` outcome can be `HighConfidence` when the evidence against the original is strong. |
| Describe the overall conclusion about the original claim | textarea, **required** | Substantive interpretation. This is where the headline numerical comparison goes ("v0.2.0 reproduces sc_TEI_delta = +0.479, sign and significance match Soroye 2020"). |
| Describe the evidence that supports your conclusion | textarea, **required** | Numerical results, test statistics, model coefficients. The reproducible numbers. |
| Describe what limits the conclusions of the study | textarea, **optional** | Caveats / limitations. Honest negative framings go here. |

---

## PCC Research Question

Form heading: *"PCC Research Question — Define a review question using the PCC framework (Population, Concept, Context)"*

| Field label | Field type | Notes |
|---|---|---|
| Short ID (used as URI suffix) | text input, **required** | Placeholder "e.g., my-review-question-2024". |
| Review Question Label | text input, **required** | A short label for searches/discovery. |
| Review Question Description | textarea, **required** | Describe the review question in detail; commentary on why it matters. |
| Population | textarea, **required** | The population or participants being studied. |
| Concept | textarea, **required** | The core concept or phenomenon being examined. |
| Context | textarea, **required** | The context or setting in which the review is conducted. |

Use for **descriptive/scoping question-rooted chains** with no clear comparator. See `docs/chain-decision-tree.md`.

---

## PICO Research Question

Form heading: *"PICO Research Question — Define a research question using the PICO framework (Population, Intervention, Comparator, Outcome)"*

| Field label | Field type | Notes |
|---|---|---|
| Short ID (used as URI suffix) | text input, **required** | |
| Research Question Title | text input, **required** | 10-200 characters. Length-bounded — keep tight. |
| Complete Research Question | textarea, **required** | One coherent sentence/paragraph that names P, I, C, O inline. |
| Question Type | radio button, **required** | One of: `Causation`, `Descriptive`, `Effectiveness`, `Experience`, `Prediction`. |
| Population (P) | textarea, **required** | Who/what is being studied. For non-clinical work this is whatever entities/data the question is *about*. |
| Intervention (I) | textarea, **required** | The intervention or exposure being examined. |
| Comparison (C) | textarea, **required** | The comparison or control condition. |
| Outcome (O) | textarea, **required** | What outcomes are being measured. |

Use for **comparative question-rooted chains** with a clear comparator (X versus Y). See `docs/chain-decision-tree.md`.

PICO content rule: PICO is the **question**. Don't stuff implementation specifics into PICO fields — those go in the Replication Study's "how" field. See `docs/pico-study-outcome-levels.md`.

---

## Citation with CiTO

Description: "Declare citations between papers or other works, using Citation Typing Ontology"

| Field label | Field type | Notes |
|---|---|---|
| Identifier for the citing creative work | text input, **required** | URL or DOI of the citing work — for FORRT chains this is the Outcome's nanopub URI. |
| List citations | repeatable group, **required** ≥1 | One or more citation entries, each with type + URL. |
| ↳ Citation Type | dropdown | CiTO intention from the controlled list. Available: `confirms`, `qualifies`, `disputes`, `extends`, `usesMethodIn`, `citesAsAuthority`, `obtainsBackgroundFrom`, `discusses`, `citesAsDataSource`, `containsAssertionFrom`, `includesQuotationFrom`, `reviews`, `critiques`, `credits`. **NOT available**: `replicates`. When citing a notebook/tutorial that was directly reused, use **`credits`** instead. |
| ↳ DOI or other URL of the cited work | text input | DOI URL form `https://doi.org/10.x/y` or other URL. |

**Mapping rule for FORRT Outcomes** (validation status → CiTO intention):

| Validation status | CiTO intention |
|---|---|
| Validated | `confirms` |
| PartiallySupported | `qualifies` |
| Contradicted | `disputes` |

---

## Research Software

Form heading: *"Research Software — Describe research software with metadata including repository, supporting publications, and related resources."*

| Field label | Field type | Notes |
|---|---|---|
| URI of published software | text input, **required** | The Zenodo concept DOI URL when available, or a GitHub URL. **Expects full URL form** (`https://doi.org/10.x/y`). |
| Software Title | text input, **required** | The full name or title of the software. |
| Repository URL | text input, **required** | URL where the software source code is hosted (e.g. GitHub URL). |
| Research Project | text input, **optional** | URI of the nanopub describing the research project that produced this software. **Use this field for the back-link to the FORRT Claim or PCC question URI** at the head of the chain. |
| License | text input, **optional** | URL of the software license (e.g. `https://spdx.org/licenses/MIT.html`). |
| Related Datasets | repeatable group, **optional** | Each entry is a single URL field. Use for the software's input data DOIs. |
| Related Publications | repeatable group, **optional** | Each entry is a single URL field. **Use for one-way back-links to the FORRT Outcome URI(s)** the software implements, plus any cited methods papers. |

**Scope rule:** Research Software nanopubs describe a *reusable, citable software artefact* — a tool people would `pip install` or `git clone` to use in their own work. They do NOT describe one-off demo / reproduction repos. If your repo is a reproduction of someone else's paper, the reusable artefact is the *upstream library* it uses (e.g. `foscat`, `planktonclas`), not your reproduction repo. Author the Research Software nanopub for the upstream tool, not the demo. See `CLAUDE.md` § Layered architecture: FORRT vs Research Software.

---

## Research Synthesis

Form heading: *"Science Live Research Synthesis — Synthesise findings across multiple replication outcomes with conclusions, recommendations, conditions, and limitations."*

| Field label | Field type | Notes |
|---|---|---|
| Short URI suffix for synthesis ID | text input, **required** | |
| Label of the synthesis | text input, **required** | A one-line summary. |
| Conclusion of the synthesis | textarea, **required** | The aggregate finding across the underlying outcomes. |
| Recommendations | textarea, **required** | Actionable guidance for practitioners. |
| Conditions under which the synthesis applies | textarea, **required** | Scope: data types, methods, domains. |
| Limitations of the synthesis | textarea, **required** | Caveats: what was not tested, what might not generalise. |
| Completion date | date picker, **required** | ISO format. |
| Supporting sources (nanopub or other URIs) | repeatable group, **required** ≥1 | Each entry is a URL — typically the FORRT Outcome URIs being synthesised, but any nanopub or URL works. |
| Search topics (Wikidata) | multi-select Wikidata search, **optional** | Provide labels, not QIDs. |

Use this template to **bind multiple parallel FORRT chains together** under one cross-cutting conclusion. Typical use: when three Outcomes from three independent chains test different facets of a shared underlying property, the Synthesis is the meta-publication that names the shared property and lists actionable practitioner guidance.

---

## Drafting rules — recap

1. **Always check this file first** before drafting nanopub content.
2. **Field-by-field drafts** — produce text that maps 1:1 to the form, not free-form bundles.
3. **Verify content** — verbatim quotes from the paper PDF; methodology from actual code; numbers from actual results.
4. **Wikidata fields = give search labels, not QIDs.** QIDs from memory are often wrong (mismatched item) — labels are what's actionable in the platform's UI.
5. **Atomic AIDA** — one empirical finding per AIDA sentence. Split if "and" links two findings.
6. **Layer separation** — PICO is the question, Study is the design (scope + method), Outcome is the result. Don't conflate. See `docs/pico-study-outcome-levels.md`.
