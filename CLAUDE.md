# CLAUDE.md — operating manual

@DOMAIN.md
@USER_PREFERENCES.md

This file is the universal operating manual for replication studies built from `forrt-replication-template`. It is **never edited per project**. Domain-specific conventions live in `DOMAIN.md`; per-user style lives in `USER_PREFERENCES.md`. Both are imported above.

## Purpose of this repository

This repository is a self-contained replication study. By the time it is finished, it produces:

1. A reproducible computational pipeline (notebooks + Snakefile + Docker).
2. A Zenodo-archived release with a citable concept DOI.
3. A FORRT-tagged nanopublication chain on the Science Live platform that records the claim being tested, the replication design, the outcome, and the citation relationship to the original paper.

Your job, as Claude, is to help the user move from "freshly cloned template + a paper PDF" through all four phases without needing context outside this directory.

## Standards alignment — FAIR4RS

This template is designed to satisfy the **FAIR Principles for Research Software (FAIR4RS)** (Chue Hong et al. 2022, [RDA00068](https://doi.org/10.15497/RDA00068)). FAIR4RS adapts FAIR (Findable, Accessible, Interoperable, Reusable) to software's specific lifecycle: identifiers, metadata, qualified references, license, provenance, and community standards.

Every artefact in this repo has a FAIR4RS purpose. The mapping is in `docs/fair4rs-checklist.md` — read it before declaring a phase "done", because FAIR4RS conformance is part of what makes a replication credible, not an optional polish step. When in doubt about a release, check the checklist.

Key FAIR4RS handles in this template:

- **F (Findable)** — Zenodo concept DOI minted at first release; `CITATION.cff` + `codemeta.json` populated; GitHub topics suggested in `README.md`.
- **A (Accessible)** — public GitHub repo, MIT license, GHCR image, Zenodo archive of the source tarball and (optionally) the Docker image, so the software remains accessible even if GitHub or GHCR disappears.
- **I (Interoperable)** — `pixi.toml` + `pixi.lock` are the single declarative source of truth (the lockfile pins every package per platform); standard formats (jupytext `.py` notebooks, parquet/CSV/NetCDF data, OCI Docker image); cross-references to upstream paper DOI, dataset DOIs, and FORRT nanopub URIs use qualified relations.
- **R (Reusable)** — explicit MIT license, detailed provenance via the FORRT chain (every claim traceable to data + method + author ORCID), `CITATION.cff` lists upstream paper as a `references` entry, `codemeta.json` lists `softwareRequirements` and `referencePublication`.

The FORRT nanopublication chain itself is what makes **R1.2 (provenance)** machine-actionable: it does what `CITATION.cff` cannot, by separating *claims about the world* from *facts about the software*, with cryptographically signed nanopubs at each step.

## First-run guard — DO NOT SKIP

Before doing any other work in this repository, run this check:

```bash
test -f .template-uninitialised && echo "UNINITIALISED"
```

The presence of the `.template-uninitialised` sentinel file is the single
signal that the template has not been bootstrapped — the same signal CI, Docker,
and the Jupyter Book workflow use (via `.github/actions/check-ready`). Do **not**
grep the repo for `{{...}}` tokens to decide this: the template legitimately
ships literal token examples in `docs/` and `.claude/` (they document the token
system), and grepping for them is exactly what used to cause false-positive
skips and silent-green CI. `/init-template` deletes the sentinel as its final
step.

If the sentinel file is present, the template has not been initialised. **Stop**, tell the user:

> "This repository still has unsubstituted placeholder tokens from the template. Run `/init-template` to bootstrap it (you'll be asked for author identity, paper DOI, etc.), then we can proceed."

…and offer to invoke the `init-template` skill (`.claude/skills/init-template/SKILL.md`).

## Workflow phases

A complete replication moves through six phases. Each phase has artefacts and exit criteria; do not promote a phase as "done" without the artefacts.

### Phase 0 — Bootstrap

- `init-template` skill has been run; no `{{...}}` tokens remain.
- `paper/` contains the source paper PDF.
- `USER_PREFERENCES.md` reflects this user's identity and style.
- A `git remote` exists pointing at the GitHub repo created from the template.

Exit: `git status` is clean and the first commit is on `main`.

### Phase 1 — Paper analysis (or nanopub chain import)

This phase has two valid entry points; choose based on whether the upstream paper already has FORRT chains on the network (see `docs/nanopub-chain-discovery.md`).

**Entry point A — Paper-rooted (default)**

- The paper has been read end-to-end (use `Read` on the PDF, page by page if large).
- The **headline claim sentence** has been quoted verbatim from the paper into `nanopubs/drafts/01_quote.md`. This is the sentence the replication will test or extend. Verbatim means character-for-character; paraphrase is forbidden (`docs/verify-before-drafting.md`).
- A short **methodology summary** has been written into `nanopubs/drafts/00_paper_summary.md`: data sources, statistical model, sample sizes, headline numerical result.
- The replication's **design choice** has been recorded: are we doing a Reproduction Study (same data, same methods), a Replication Study (different data and/or different methods), or both?
- **(Optional, if the paper is spatial)** the original paper's **geographic study area** has been captured into `nanopubs/drafts/09_geo_coverage.md` — the area name plus a verbatim supporting quote — so it can be published as a Geographical coverage nanopub (GeoSPARQL-searchable, map-renderable). This is grounded Record-side extraction, not AI content; skip it cleanly for non-spatial papers. See `docs/geo-coverage.md`.

Hand the user the `paper-analyst` agent (`.claude/agents/paper-analyst.md`) when starting this phase.

**Entry point B — Nanopub-rooted**

When at least one FORRT chain on the upstream paper already exists on the Science Live / nanopub network and the new replication should extend, qualify, or build on it:

- The user provides a published nanopub URI (typically a CiTO Citation or a Research Synthesis at the apex of an existing chain).
- The `/import-from-nanopub` skill (`.claude/skills/import-from-nanopub/SKILL.md`) walks the citation + provenance graph from that URI, fetches every reachable nanopub, and writes `nanopubs/imported/CHAIN_SUMMARY.md` — the prior-work analogue of `00_paper_summary.md`.
- The user reads `CHAIN_SUMMARY.md` to see what's already been tested by whom, with what scope/method, with what Outcome and CiTO relation.
- The new chain's CiTO relation is then chosen relative to the prior constellation (typically `extends` or `qualifies`).

This entry point can be combined with Entry point A: run the import first to see the prior-work landscape, then read the paper PDF to verify the verbatim Quote sentence. The two outputs (`nanopubs/imported/CHAIN_SUMMARY.md` + `nanopubs/drafts/01_quote.md`) compose cleanly.

Exit (either entry point): a complete `nanopubs/drafts/01_quote.md` with verified verbatim quote and DOI, plus — if Entry point B was used — `nanopubs/imported/CHAIN_SUMMARY.md` summarising the prior constellation.

### Phase 2 — Code & data port

- `pixi.toml` lists every dependency the notebooks import, and `pixi.lock` is regenerated and committed alongside it (`docs/cicd-conventions.md` § pixi.toml is the single source of truth).
- `notebooks/01_data_download.py` fetches all input data — no manual steps.
- `notebooks/02_data_clean.py` produces a tidy intermediate dataset.
- `notebooks/03_analysis.py` reproduces the paper's headline statistic.
- `notebooks/04_figures.py` produces the figures used in the Jupyter Book.

Anti-patterns to avoid in this phase:

- **Don't claim notebook code "works" without running it** (`docs/verify-before-drafting.md` § Test before claiming ready). If a notebook has not been executed, say so explicitly.
- **Don't extrapolate framework choices** for the Replication Study draft — read the actual code that ran the analysis (`docs/verify-before-drafting.md` § Verify code before drafting).
- **Don't embed `matplotlib.use('Agg')`** in jupytext notebooks. It blocks inline plot display, which breaks the Jupyter Book build. Use `plt.show()` after `fig.savefig()`.

Exit: `snakemake --cores 1` runs end-to-end on a fresh checkout.

### Phase 3 — Local results & figures

- The headline number from the original paper has been compared against the replication's number.
- One main figure (`figures/main_result.png`) shows the comparison.
- The result has been honestly characterised: validated, partially supported, or contradicted (`docs/claim-type-vocabulary.md`). Negative results are publishable; overclaiming is not (`DOMAIN.md` § Scientific validity standard).

Exit: `nanopubs/drafts/05_outcome.md` is written with the conclusion sentence, the supporting numerical evidence, and the limitations.

### Phase 4 — Release & archive

- `CITATION.cff` and `codemeta.json` have correct version + date.
- A GitHub release is cut with a Zenodo-facing description (no internal ops detail, no bot signatures — `docs/cicd-conventions.md` § Release notes are Zenodo descriptions).
- Zenodo mints a concept DOI; the value is written into `CITATION.cff` and `codemeta.json`.
- The Docker image is pushed to GHCR via `.github/workflows/docker.yml` and (optionally) archived on Zenodo.
- On release, two further archival workflows fire automatically (best-effort, never block the release): `swh-save.yml` requests **Software Heritage** Save Code Now so the released revision gets a permanent, forge-agnostic **SWHID**, and `wayback.yml` snapshots the deployed Jupyter Book site plus any URLs in `wayback-urls.txt` (Mode-B / paperless claim sources) in the **Internet Archive Wayback Machine**. See `docs/cicd-conventions.md` § Preservation.

Exit: the release page is live, the Zenodo record exists, and `nanopubs/PUBLISHED.md` lists the source + image DOIs. (Software Heritage + Wayback archival are best-effort and may complete asynchronously.)

### Phase 5 — FORRT nanopublication chain

A FORRT chain has six steps in order. Each step is published as a separate nanopublication on `https://platform.sciencelive4all.org`. The chain shape depends on whether there is an upstream paper (`docs/chain-decision-tree.md`):

- **Paper-rooted** (almost always for a replication): Quote-with-comment → AIDA → FORRT Claim → Replication Study → Replication Outcome → CiTO Citation.
- **Question-rooted** (no upstream paper): PCC or PICO question → AIDA → FORRT Claim → Replication Study → Replication Outcome → CiTO Citation.

Phase 5 splits cleanly in two, and the split is deliberate: **Claude authors the content; deterministic code does every mechanical step.** Researchers have limited AI credits, so nothing that a script can do is done by an agent.

**5a — Draft the content (Claude).** For each step, draft field-by-field into `nanopubs/drafts/0X_<step>.md` using the exact form structure documented in `docs/forrt-form-fields.md`, via the `nanopub-drafter` agent. **Never invent field names**. **Never ship a draft that contains only the headline content without the full field enumeration.** The pre-flight checklist in `docs/forrt-form-fields.md` is non-negotiable; run it before every draft.

Every value in a draft must be **retrieved from its authoritative source, never recalled** — the quote from the PDF, the numbers from `results/`, the methodology from the notebook, a Wikidata topic from the Wikidata API (and type-checked where the template declares a type), a controlled term copied from the template's own enumeration, a DOI confirmed to resolve. The full source-and-command table is the governing rule in `.claude/agents/nanopub-drafter.md`. This matters more than it used to: publishing is now automated, so a value invented at drafting time is signed and published with no human dropdown in between to catch it.

**5b — Publish the chain (deterministic).** Claude runs these commands, but does
not do the work: the values come from the script, never from the model. **Never
hand-write `chain-draft.json`** — if it looks wrong, fix the draft or the script
and re-run. Read what the script prints and tell the user: it reports a missing
headline figure and any Wikidata term it could not resolve, and those fields will
be silently empty in the published chain otherwise.

```bash
pixi run build-chain-draft        # drafts + CITATION.cff + templates -> nanopubs/chain-draft.json
git add nanopubs/chain-draft.json && git commit -m "Add chain draft" && git push
```

Then open the Science Live chain wizard with that file's URL:

```
https://platform.sciencelive4all.org/np/create/chain?draft=<raw URL of nanopubs/chain-draft.json>
```

The wizard walks the chain in order with every step pre-filled from the draft, you review and publish each one, and **it carries each published URI into the next step's back-reference automatically** — no copy-paste, no manual ordering. See `docs/chain-draft-contract.md` for the file format and what pre-fills what.

*Fallback:* if the platform can't reach your `chain-draft.json` (a private repo, or working offline), publish each drafted step by hand in the Science Live UI in chain order, pasting each returned URI into the next step and into `nanopubs/PUBLISHED.md`.

Exit: all six URIs are listed in `nanopubs/PUBLISHED.md`, the Jupyter Book embeds at least one of them, and the chain is browsable from `index.md`. Once the chain is published and the ledger is filled, **point the book's TOC in `myst.yml` at `nanopubs/PUBLISHED.md`** (replacing the generic `nanopubs/README.md`) so the published book surfaces the live chain instead of the drafts explainer. **Then run `/verify-chain`** — it must come back green before the chain is announced.

Optionally, generate the **reader-facing story page** — a self-contained HTML article built deterministically from the published chain (`pixi run build-story`, see `docs/story-page.md`) — and publish it alongside the Jupyter Book (e.g. GitHub Pages). It works for a single chain or a research synthesis, and like `build-chain-draft` it runs off Claude's tokens.

## Universal anti-patterns (apply across all phases)

These rules apply regardless of domain. Domain-specific anti-patterns live in `DOMAIN.md`.

### Verify quotes verbatim before drafting

The Quote-with-comment template requires **verbatim** text from the source. Generating an "approximate" quote from training-data memory is forbidden, even when the paraphrase is faithful. Always read the PDF in `paper/` first and copy the sentence character-for-character. See `docs/verify-before-drafting.md`.

### Verify code before drafting Study/Outcome

Before drafting the Methodology or Deviations fields of a FORRT Replication Study or Outcome, read the actual reproduction script in `notebooks/`. Don't infer the framework, library, or hyperparameters from prior memory or from what feels "natural" given the paper. See `docs/verify-before-drafting.md`.

### Test before claiming ready

Don't describe untested code as "works" or "ready". Run it first, or label it explicitly: "written, untested" or "written, runs in the Docker container per the API docs, not yet executed." See `docs/verify-before-drafting.md`.

### Atomic AIDA — one empirical finding per AIDA sentence

AIDA = Atomic, Independent, Declarative, Absolute. One AIDA sentence states one empirical finding. If your draft AIDA contains "and" linking two distinct findings, split it into two AIDA nanopubs anchored on two separate Claims. See `docs/forrt-form-fields.md`.

### Don't conflate PICO with method

PICO is the **question**. The Replication Study form's "what is reproduced" is the **scope**. The Replication Study form's "how is reproduced" is the **method**. Results live only in the Outcome. Stuffing methodology into PICO, or numerical results into the Study, makes the chain non-composable. See `docs/pico-study-outcome-levels.md`.

### Don't poll long-running experiments

If an analysis takes more than ~5 minutes, launch it as a background process (`nohup … &`) and tell the user the estimated completion time. Don't burn conversation context polling a results file every few seconds.

### Layered architecture: FORRT vs Research Software

The FORRT chain (Quote → AIDA → Claim → Study → Outcome → CiTO) makes claims about the world. A Research Software nanopub describes a reusable software artefact (a `pip install`-able tool, not a one-off demo repo) and cites the FORRT Claim one-way. Don't pull tooling URIs into the FORRT chain; publish a separate Research Software nanopub if the repo *produces* a reusable tool. See `docs/forrt-form-fields.md` § Research Software.

### Atomic publishing order

Publish nanopubs in the order they cite each other: Quote → AIDA → Claim → Study → Outcome → CiTO. Each step needs the URI of the previous step as input. Don't try to publish out of order.

## Document map

The documents under `docs/` are the load-bearing reference material; reach for them when drafting:

| When you are about to… | Read this |
|---|---|
| Draft any nanopub field | `docs/forrt-form-fields.md` |
| Publish the chain (draft → wizard) | `docs/chain-draft-contract.md` + `pixi run build-chain-draft` |
| Build the reader-facing story page (blog) from the published chain | `docs/story-page.md` + `pixi run build-story` |
| Decide which template starts the chain | `docs/chain-decision-tree.md` |
| Choose the FORRT Claim type | `docs/claim-type-vocabulary.md` |
| Write the Quote, Study, or Outcome | `docs/verify-before-drafting.md` |
| Write a PICO or PCC question | `docs/pico-study-outcome-levels.md` |
| Touch CI / pixi.toml / Dockerfile / myst.yml | `docs/cicd-conventions.md` |
| Cut a release / claim a phase done | `docs/fair4rs-checklist.md` |
| Update RO-Crate metadata after adding artefacts | `docs/ro-crate.md` |
| Need to retract / supersede / batch-publish a nanopub | `docs/programmatic-nanopubs.md` |
| Draft the launch announcement post | `docs/announcement-template.md` |
| Use this template with Cursor / Aider / Continue / non-Claude AI | `docs/ai-portability.md` |
| Archive HEALPix EO data as GRID4EARTH / EOPF Zarr | `docs/eopf-zarr-conversion.md` |
| Verify a published FORRT chain's internal + external consistency | `/verify-chain` skill (`.claude/skills/verify-chain/SKILL.md`) |
| Deposit the work as a Rohub Research Object | `docs/rohub-deposit.md` + `scripts/build-rohub-manifest.py` |
| Seed Phase 1 from a published nanopub URI (instead of a paper PDF) | `/import-from-nanopub` skill (`.claude/skills/import-from-nanopub/SKILL.md`) + `docs/nanopub-chain-discovery.md` |
| Record the paper's geographic study area (optional, spatial papers) | `docs/geo-coverage.md` + `nanopubs/drafts/09_geo_coverage.md` |

## When in doubt

Stop and ask. The platform's value is research integrity — the cost of pausing is small; the cost of an overclaimed result or a hallucinated quote is high.
