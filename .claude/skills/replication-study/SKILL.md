---
name: replication-study
description: End-to-end orchestration skill for a FORRT replication study — guides the user through Phases 0-5 of CLAUDE.md, dispatches to specialist agents (paper-analyst, replication-coder, nanopub-drafter), and tracks progress. Use this when starting a new replication or resuming one mid-phase.
---

# /replication-study

You're orchestrating a complete FORRT replication study from the freshly-initialised template through publication. This skill walks the user through the six phases in `CLAUDE.md`, dispatching to specialist agents at each stage.

## Preflight — Science Live API key

Two of the skills this orchestrator dispatches to (`/import-from-nanopub`, `/verify-chain`) call Science Live's `/np/constellation` endpoint, which requires authentication. Before you start any phase that needs them — Phase 0 (if `{{PRIOR_CHAIN_URI}}` is set) and Phase 5 (final verification) — confirm the key is exported:

```bash
test -n "$SCIENCELIVE_API_KEY" || echo "SCIENCELIVE_API_KEY not set — needed for /import-from-nanopub and /verify-chain"
```

If unset, tell the user to set it before continuing:

> *"Two later phases will need a Science Live API key. Get one at platform.sciencelive4all.org → Settings → API Keys (it starts with `sl_`), then `export SCIENCELIVE_API_KEY=sl_…` in your shell. You don't need it for Phases 1-4, but Phase 5's `/verify-chain` will block without it."*

## Procedure

### Step 1 — Detect current phase

Inspect repo state to determine which phase the user is currently in:

| Indicator | Phase |
|---|---|
| `{{...}}` tokens present | Phase 0 not done — run `/init-template` first |
| `paper/` empty | Phase 0 partial — ask user to drop the PDF |
| `nanopubs/drafts/00_paper_summary.md` placeholder | Phase 1 not done |
| `notebooks/03_analysis.py` is the unmodified scaffold | Phase 2 not done |
| `results/` empty or stale | Phase 3 not done |
| No GitHub release tag exists (`gh release list`) | Phase 4 not done |
| `nanopubs/PUBLISHED.md` shows "_not yet published_" | Phase 5 not done |

Report the detected phase and ask the user to confirm before proceeding.

### Step 2 — Run the relevant phase

For each phase, dispatch to the right specialist or guide the user manually:

| Phase | What happens | Handoff |
|---|---|---|
| **0 Bootstrap** | Run `/init-template`. Drop paper PDF in `paper/`. | — |
| **1 Paper analysis** | Use the `paper-analyst` agent. Output: `nanopubs/drafts/00_paper_summary.md` + `nanopubs/drafts/01_quote.md` Quoted Text. | `Agent({subagent_type: "paper-analyst"})` |
| **2 Code & data port** | Use the `replication-coder` agent. Update `pixi.toml` (+ `pixi.lock`), notebooks, Snakefile. | `Agent({subagent_type: "replication-coder"})` |
| **3 Local results** | Run `pixi run snakemake --cores 1`. Compare headline number to paper. Write `nanopubs/drafts/05_outcome.md` placeholders. | manual |
| **4 Release** | Run `docs/fair4rs-checklist.md` pre-release checklist. Cut a `gh release` with a Zenodo-formatted body. | manual |
| **5a Draft the chain** | Use the `nanopub-drafter` agent for each step. Every value must be *retrieved* from its source, never recalled (governing rule in the agent). | `Agent({subagent_type: "nanopub-drafter"})` ×6 |
| **5b Publish the chain** | Run `pixi run build-chain-draft`, **relay its warnings** (missing figure, unresolved Wikidata terms), commit `nanopubs/chain-draft.json`, then open `/np/create/chain?draft=<raw url>` — the wizard pre-fills each step and carries published URIs forward. | `Bash` — run the script, never hand-write the JSON |

### Step 3 — Phase exit checks

Before promoting a phase as "done", verify the exit criteria from `CLAUDE.md`:

- Phase 1: `01_quote.md` has a verified verbatim quote.
- Phase 2: `snakemake --cores 1` runs end-to-end on a fresh checkout.
- Phase 3: `nanopubs/drafts/05_outcome.md` has a conclusion sentence.
- Phase 4: GitHub release page is live, Zenodo record exists, `CITATION.cff`/`codemeta.json` show the concept DOI.
- Phase 5: All six chain-step URIs are in `nanopubs/PUBLISHED.md`, embedded in the Jupyter Book, browsable from `index.md`. **Then run `/verify-chain`** — the report must come back GREEN (internal + external consistency) before declaring Phase 5 done.

If any exit criterion fails, do not promote the phase. Tell the user what's missing.

### Step 4 — Final FAIR4RS check

After Phase 5, run the checklist in `docs/fair4rs-checklist.md`. Tell the user which boxes are ticked and which need attention. The replication is "complete" when the checklist is fully ticked.

### Step 5 — Final chain verification

After the FAIR4RS checklist is green, run `/verify-chain` one more time. This is the "safe to announce" gate — a green report confirms the published nanopubs cross-reference each other correctly, the Outcome points at the right repo URL, and the cited DOI resolves. A red report names the specific step to retract+supersede before any public announcement (see `docs/programmatic-nanopubs.md`).

## Anti-patterns

- **Don't skip phases.** Each phase has artefacts the next one depends on.
- **Don't promote a phase without the exit criteria.** "Mostly done" leaves landmines for the user later.
- **Don't draft nanopubs before the code is verified to work.** The Outcome's evidence comes from `results/`, which doesn't exist until Phase 3 is done.
- **Don't publish nanopubs.** That's the user's job, on platform.sciencelive4all.org. You draft; they publish.

## Output

Phase-by-phase progress reports. Each phase ends with: "Phase N complete. Next: Phase N+1, which does X. Shall I continue?"
