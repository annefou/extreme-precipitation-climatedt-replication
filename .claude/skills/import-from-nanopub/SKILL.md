---
name: import-from-nanopub
description: Seed Phase 1 of a fresh replication from a published nanopub URI instead of (or alongside) a paper PDF. Calls the forrt-research MCP's prior_work tool to summarise what has already been tested on this paper — by whom, with what scope and method, and with what Outcome — into `nanopubs/imported/CHAIN_SUMMARY.md`. Use when the new work extends, qualifies, or builds on existing FORRT chains on the network.
---

# /import-from-nanopub

You're seeding Phase 1 from a **published nanopub URI** instead of (or in addition to) a paper PDF. The typical entry point is a CiTO Citation or a Research Synthesis at the apex of an existing chain; from that one URI the whole constellation is reachable.

This skill produces a structured summary that the `paper-analyst` agent (and the human) can read as if it were `00_paper_summary.md`, except it summarises **prior signed claims about the upstream paper**, not the paper itself.

## When to use this skill

- **Extending an existing chain.** Same upstream paper, new dataset / method / region. You want to see what's already been claimed so the new chain can `extends` prior work via CiTO instead of duplicating it.
- **Replacing or qualifying a contradicted chain.** Prior work disputed the upstream paper; you want to re-test under different conditions.
- **Awareness-check before fresh work.** Same upstream paper; confirm there is no near-duplicate already on the network.
- **Constellation entry point.** Given a Research Synthesis URI, expand it back into its constituent chain steps.

## When NOT to use

- Your work has no relationship to existing FORRT chains — use the paper-rooted Phase 1 (`paper-analyst` on a PDF) instead.
- The entry URI is from outside the nanopub network (a Wikidata item, a Zenodo DOI). This skill is nanopub-network-specific.

## Prerequisite — the forrt-research MCP server

```
pipx install forrt-research-mcp
claude mcp add forrt-research -s user -- forrt-research-mcp
```

If `prior_work` is unavailable, say so and tell the user to install it. **Do not fall back to hand-written `curl` against `/np/constellation`.** A single chain's raw response is ~330 KB, ~95 % of which is a depth-5 neighbourhood of *unrelated* chains reached through shared hubs — on one real chain, 64 of 98 nodes were other studies' AIDA statements. Pulling that into context wastes it and invites you to summarise another paper's claims as if they were this one's.

## Procedure

### Step 1 — Get the entry URI

Ask the user. Acceptable forms:

- `https://w3id.org/sciencelive/np/RA...` (Science Live native)
- `https://w3id.org/np/RA...` (nanopub network)

### Step 2 — Call `prior_work`

```
prior_work(uri="<entry URI>")
```

Returns, per already-published chain: the claim type, `scope` (what was tested), `method` (how), `deviations`, the verdict and confidence, the archived `repository`, the CiTO relations, plus `citedPaper`, `upstreamAnchors` and any `researchSynthesis`.

**Read `citedPaper`, not the API's `paperDoi`.** The API picks `paperDoi` by counting DOIs across the whole walk, so unrelated nanopubs outvote the chain's own citation — it names the wrong paper on both of this project's real chains. `prior_work` derives it from the CiTO and sets `disagreesWithReported` when the two differ.

**Read `limitations` most carefully.** It is where the previous authors stated, in signed and immutable words, what their study did *not* cover — which is very often exactly where the new work begins.

### Step 3 — Write `CHAIN_SUMMARY.md`

Write `nanopubs/imported/CHAIN_SUMMARY.md` from the tool's output. Keep it **factual and short** — copy prose verbatim where possible, do not editorialise.

```markdown
# Prior FORRT chain summary

**Entry URI**: <entry URI>
**Imported on**: <ISO date>
**Prior chains**: <replicationCount> · **Verdicts**: <verdicts joined>

## Upstream paper

DOI: <citedPaper.doi>  (source: <citedPaper.source>)
<if citedPaper.disagreesWithReported: note that the API's own paperDoi disagrees
 and names <citedPaper.reportedPaperDoi> — the CiTO-derived value is correct>

## Chain(s) already published

For each entry in `priorWork[]`:

### <verdict> (<confidence>) — CiTO: <citoRelations joined>

Claim type: <claimType>
Outcome: <outcomeUri>
Repository: <repository>

**Scope** (what was tested): <scope>
**Method**: <method>
**Deviations**: <deviations>
**Conclusion**: <conclusion>
**Limitations — what this did NOT cover**: <limitations>

## Research Synthesis (if researchSynthesis is not null)

URI: <uri> · Label: "<label>"

## Upstream anchors (if upstreamAnchors is non-empty)

| Step | URI | Text |
|---|---|---|
| Quote / Question | <uri> | "<text>" (<text_source>) |

## What this new work can do

- A prior chain `confirms` and you test a different taxon / region / horizon → new CiTO `extends` the prior CiTO.
- A prior chain `qualifies` and you may reinforce or contradict it → `confirms` (noting it in the comment) or `disputes`.
- No prior chain covers your dimension → fresh sibling chain rooted on the same paper, CiTO relation derived from your own Outcome verdict.

## Open questions for the user

- Extend the existing chain's CiTO, or open a fresh chain rooted on the paper?
- Any prior Research Software nanopubs whose toolchain to reuse (cite via `cito:usesMethodIn`)?
- Does the prior Synthesis already cover your case?
```

**Not every step will be present.** The constellation walk routinely stops short of the upstream anchors — on two real chains it enumerated only `[Claim, Study, Outcome]` and `[Study, Outcome, CiTO]` while the Quote, AIDA and Claim nanopubs were published and merely unreachable. `upstreamAnchors` may therefore be empty and `claimType` blank. That is not missing data; record what you have and move on.

### Step 4 — Sibling-repo inheritance (optional)

`scripts/inherit_sibling_repos.py` clones the sibling replication repos and stages their starter files. It reads a raw constellation file, so fetch one *to disk* only if the user wants this step — never into your context:

```bash
mkdir -p nanopubs/imported
uri="<entry URI>"
enc=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$uri")
base="${SCIENCELIVE_API_BASE:-https://api-dev.sciencelive4all.org}"
# An explicit User-Agent is required: Cloudflare answers urllib/curl defaults
# inconsistently, and Python-urllib/3.x specifically gets HTTP 403.
curl -sL --max-time 120 -A "forrt-replication-template" \
  ${SCIENCELIVE_API_KEY:+-H "x-api-key: $SCIENCELIVE_API_KEY"} \
  "$base/np/constellation?uri=$enc" \
  | python3 -m json.tool > nanopubs/imported/constellation.json

pixi run python scripts/inherit_sibling_repos.py \
  --constellation-json nanopubs/imported/constellation.json
```

Pass `--no-clone-siblings` to stage only from siblings already present under `../`.

### Step 5 — Hand off

> *"Imported the constellation rooted at `<entry_uri>` — <N> prior chain(s), verdicts <…>. Summary at `nanopubs/imported/CHAIN_SUMMARY.md` (local cache — **gitignored, do NOT commit**).*
>
> *The persistent pointer is the entry URI itself; add it to `CITATION.cff` `references:` as a `type: generic` entry with `url:` set to the URI. The nanopub network is the single source of truth, not a committed snapshot — anyone cloning the repo can regenerate the cache by re-running `/import-from-nanopub <URI>`.*
>
> *Answer the open questions at the bottom of `CHAIN_SUMMARY.md` before drafting any nanopubs. Then either (a) place the paper PDF at `paper/<name>.pdf` and run `paper-analyst` in Phase 1 with `CHAIN_SUMMARY.md` as prior-work context, or (b) skip to Phase 2 if this is a pure method-extension of a prior chain."*

If `SETUP_INHERITED.md` reports staged files:

> *"`<N>` starter files staged at `_template_from_prior/`. **Review each, merge into your own tree, then delete the directory.** It is a one-shot reference area, not durable repo state. Do not commit it."*

**The cache is gitignored on purpose.** Nanopubs are immutable and identified by URI; mirroring them into each repo creates divergence risk and bloats the repo with derived data.

## Failure modes

- **`ok: false` with an error** — relay the server's message verbatim. A 500 from the API is a different problem from an unresolvable URI, and paraphrasing costs the user the one clue they need.
- **Empty `priorWork[]`** — the URI resolved but no completed chain was reachable. Usually the entry is a leaf nanopub with no incoming CiTO yet; verify it is a CiTO Citation or Research Synthesis, not an isolated AIDA.
- **`citedPaper.source` is `unknown`** — no CiTO was reached, so nothing identifies the upstream paper. Check the source repo's `PUBLISHED.md`.
- **Empty prose fields** — the chain may use a superseded template version. Run `template_fields(step)` and check `driftedFromSnapshot`.
- **`Could not resolve <Zenodo DOI> to a GitHub URL`** — the record's `related_identifiers` lack a GitHub link. Ask the user, or clone manually under `../` and re-run with `--no-clone-siblings`.

## Companion docs

- `docs/nanopub-chain-discovery.md` — when this entry point makes sense vs. a paper-rooted Phase 1.
- `docs/forrt-form-fields.md` — the form structure of each chain step.
- `docs/chain-decision-tree.md` — which template starts a chain.
- `/verify-chain` — run once the new chain is published.
- The server: <https://github.com/ScienceLiveHub/forrt-research-mcp>
