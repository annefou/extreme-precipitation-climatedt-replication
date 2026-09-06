# `docs/nanopub-chain-discovery.md` — nanopub-rooted Phase 1 entry point

A new replication can start from one of two entry points:

| Entry point | When | What it produces |
|---|---|---|
| **Paper PDF** (default — Phase 1, `paper-analyst` agent) | The upstream paper has no FORRT chains on the network yet, or you don't know whether it does. | `nanopubs/drafts/00_paper_summary.md` + `01_quote.md` (verbatim quote from the PDF) |
| **Nanopub URI** (this doc, `/import-from-nanopub` skill) | At least one FORRT chain on the upstream paper already exists on the Science Live / nanopub network and you want to extend, qualify, or build on it. | `nanopubs/imported/CHAIN_SUMMARY.md` + `constellation.json` + cached TriG |

Both are valid Phase 1 outputs. The two can also be combined: run `/import-from-nanopub` first to see the prior-work landscape, then read the paper PDF to verify the verbatim Quote sentence.

## Why this entry point matters

FORRT chains on the Science Live network *are themselves data*. Every step (Quote, AIDA, Claim, Study, Outcome, CiTO, Research Synthesis) carries:

- The verbatim text being cited
- The author ORCID + ROR
- The CiTO relation (`confirms` / `qualifies` / `disputes` / `extends`)
- The scope and method declared in the Replication Study
- The verdict declared in the Replication Outcome
- Cross-references to sibling chains (substrate-sensitivity diagnostics, multi-resolution refits, etc.)

A new replication that ignores this prior signed record is doing twice the work: re-reading the paper to find the headline claim, re-deriving the methodology, possibly re-discovering the same Outcome the prior chain already published. **Reading the prior chain first** is the cheapest way to find the open scientific space the new replication should target.

## When to use the nanopub entry point

1. **Extending an existing chain.** A prior chain replicated the upstream paper on dataset X with verdict `Validated`. You want to test the same mechanism on dataset Y. The prior chain's CiTO is the natural anchor for your new CiTO via `cito:extends`.

2. **Qualifying a confirmed chain.** A prior chain published `confirms` for the upstream paper's headline. You're going to test the same headline under a different grid resolution / time horizon / spatial scale / taxon and may find a methodological caveat. Your CiTO will `qualifies` (or, less commonly, `disputes`) — built on top of the prior `confirms`.

3. **Probing a contradicted finding.** A prior chain `disputes` the upstream paper. You want to re-test under different assumptions and either confirm the dispute or restore confidence in the original claim. Your CiTO relation depends on what the data show.

4. **Building on a Research Synthesis.** A prior Research Synthesis aggregated several chains into a constellation-level finding. Your replication extends or qualifies that *synthesis*, not the individual chains. The Synthesis URI is the cleanest entry point.

5. **Multi-method or multi-substrate diagnostic.** You're running the methodological diagnostic chain (e.g. substrate-sensitivity, multi-resolution refit) that complements an existing science chain. The existing chain's CiTO is your entry URI.

## When NOT to use it

- The upstream paper has no FORRT chains on the network at all. Use paper-rooted Phase 1.
- You're starting a question-rooted chain (no upstream paper) — there's nothing to import.
- The entry URI is from outside the Science Live / nanopub network — the constellation endpoint is network-specific. To *search* the full nanopub network for chains that are about the same paper but don't reference your entry URI, see `feedback_nanopub_uri_verification.md` (the verification side); the constellation walk only follows references reachable from the entry URI.

## How to run

The entry point is the `/import-from-nanopub` skill, which calls Science Live's `/np/constellation` endpoint for the entry URI and caches the response at `nanopubs/imported/constellation.json`. That JSON is the claim-layer import — every reachable chain step with its prose inline. The skill then writes the human-/AI-readable `nanopubs/imported/CHAIN_SUMMARY.md` from it. See `.claude/skills/import-from-nanopub/SKILL.md` for the full procedure (API key, request, failure modes).

The infrastructure layer — cloning the sibling repos of the prior chain and staging their reusable files — is a separate step the skill runs after caching the constellation:

```bash
pixi run python scripts/inherit_sibling_repos.py \
    --constellation-json nanopubs/imported/constellation.json
```

## What an "ideal" import looks like

For a well-published constellation (Bombus example, apex CiTO `RA1q6c0f…`), the constellation response carries:

- 3 chains, each with its Claim → Study → Outcome → CiTO steps inline
- 1 Research Synthesis + 1 apex CiTO Citation
- `paperDoi` set to the upstream paper's DOI
- an Outcome `repository` per chain, feeding the infrastructure-inheritance step

If the constellation doesn't reach a step you expected (commonly the upstream AIDA / Quote — see the "upstream terminus" note in the skill), that's a property of the walk on the platform side, not something to re-derive locally: recover those URIs from the source chain's `PUBLISHED.md` and fetch them directly.

## What this entry point does NOT do

- **No automatic chain authoring.** The summary is read-only. Drafting the new chain's nanopubs is still the user's job, using the `nanopub-drafter` agent and the field-by-field structure in `docs/forrt-form-fields.md`.
- **No signature verification.** The constellation API and the TriG resolver are trusted at the HTTP layer. For full cryptographic verification, use the `nanopub` PyPI package's `Nanopub.verify_signature()` method.
- **No claim-layer discovery in this repo.** Walking the citation graph and classifying step types lives on the platform (`science-live-platform/api/src/np/constellation.ts`), reached via the endpoint. The template deliberately does not keep a second, divergent copy of that walk.

## What gets committed to git, and what doesn't

The **persistent contract** to the prior chain is **the entry URI itself**, written to `CITATION.cff` `references:` as a `type: generic` entry with `url:` set to the apex CiTO URI. Anyone cloning the repo regenerates the local cache by re-running `/import-from-nanopub <URI>`. The nanopub network is the single source of truth.

The **local cache** (`nanopubs/imported/`) is **gitignored**. It contains:

- `constellation.json` — the graph structure of fetched nanopubs
- `trig/*.trig` — cached TriG for each fetched nanopub
- `CHAIN_SUMMARY.md` — the AI-generated human-readable summary (claim layer)
- `SETUP_INHERITED.md` — the auto-generated report of which sibling repos were cloned and which files were staged (infrastructure layer)
- `cited_papers.txt` — external DOIs referenced by the chain

All are *derived artefacts*. Mirroring them into every replication repo would:

1. Duplicate network data into git (the network is authoritative; nanopubs are immutable, identified by URI).
2. Risk silent drift — if the upstream constellation gains a new sibling chain or supersedure, our committed snapshot becomes stale without warning.
3. Bloat the repo with content that's reproducible from a single line of YAML.

Add the URI to `CITATION.cff`; let the cache live and die in `nanopubs/imported/`.

## Infrastructure-layer inheritance (`SETUP_INHERITED.md` + `_template_from_prior/`)

`/import-from-nanopub` operates on two complementary axes:

1. **Claim layer**: walk the citation graph, summarise the FORRT chain steps (Quote → AIDA → Claim → Study → Outcome → CiTO + Synthesis), output a human-/AI-readable `CHAIN_SUMMARY.md`. This is the "what was published" axis.

2. **Infrastructure layer**: discover the GitHub repositories underlying each prior chain (from each Outcome step's `repository` value in the constellation — resolves GitHub URLs and Zenodo DOIs alike), `git clone` them as siblings of your current repo (default `../`), and stage reusable starter files into `_template_from_prior/`. This is the "what was built" axis — gives you a workspace that starts where the prior replication ended, not a blank one. Run by `scripts/inherit_sibling_repos.py`.

The inherited files are deliberately staged to `_template_from_prior/` rather than the new repo's actual locations:

- `_template_from_prior/pixi.toml` + `_template_from_prior/pixi.lock` — pinned dependencies and per-platform lockfile from the canonical sibling
- `_template_from_prior/Snakefile` — workflow scaffold
- `_template_from_prior/notebooks/01_data_download.py` — data-access patterns (GBIF pre-minted-DOI, Polytope for DestinE, Figshare for CRU TS, etc.)
- `_template_from_prior/notebooks/02_data_clean.py` — cleaning patterns
- `_template_from_prior/Dockerfile` — container scaffold

Each file gets a provenance header noting where it came from. The user reviews each and merges into the corresponding location in their own repo, then deletes `_template_from_prior/`. **The staging directory is one-shot reference, not durable repo state — don't commit it.**

To stage from siblings already cloned under `../` without fetching anything, pass `--no-clone-siblings`. To skip the infrastructure layer entirely (pure claim-only import), simply don't run `scripts/inherit_sibling_repos.py` — the constellation cache and `CHAIN_SUMMARY.md` from the earlier steps stand on their own.

## Companion artefacts

- `.claude/skills/import-from-nanopub/SKILL.md` — the orchestrating skill (calls `/np/constellation`, writes `CHAIN_SUMMARY.md`).
- `scripts/inherit_sibling_repos.py` — the infrastructure-inheritance helper (reads the cached constellation, clones siblings, stages `_template_from_prior/`).
- `nanopubs/imported/` — gitignored local cache (created on first run, regenerable on demand).
