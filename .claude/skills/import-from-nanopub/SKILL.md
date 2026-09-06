---
name: import-from-nanopub
description: Seed Phase 1 of a fresh replication from a published nanopub URI instead of (or alongside) a paper PDF. Calls Science Live's /np/constellation endpoint to fetch every reachable nanopub in the chain — CiTO Citation, Research Synthesis, all chain steps, all sibling chains — and produces `nanopubs/imported/CHAIN_SUMMARY.md` summarising what's already been tested by whom, with what scope/method, and with what Outcome. Use when the new replication extends, qualifies, or builds on existing FORRT chains on the network.
---

# /import-from-nanopub

You're seeding Phase 1 of this replication from a **published nanopub URI** instead of (or in addition to) a paper PDF. The typical entry point is a CiTO Citation or a Research Synthesis nanopub at the apex of an existing chain; from that one URI the whole constellation is reachable via Science Live's `/np/constellation` endpoint.

This skill produces a structured summary that the `paper-analyst` agent (and the human running the replication) can read as if it were `00_paper_summary.md`, except it summarises **prior signed claims about the upstream paper**, not the paper itself.

## When to use this skill

- **Extending an existing chain.** Same upstream paper, new dataset / method / region. You want to see what's already been claimed so the new chain can `extends` prior work via CiTO instead of duplicating it.
- **Replacing or qualifying a contradicted chain.** Prior work disputed the upstream paper; you want to re-test under different conditions.
- **Awareness-check before fresh replication.** Same upstream paper; you want to confirm there is no near-duplicate already on the network.
- **Constellation entry point.** Given a Research Synthesis URI, you want to expand it back into its constituent Outcome / Study / Claim / AIDA / Quote chain steps.

## When NOT to use

- Your replication has no relationship to existing FORRT chains on the network — use the paper-rooted Phase 1 (`paper-analyst` agent on a PDF) instead.
- The entry URI is from outside the Science Live / nanopub network (a Wikidata item, a Zenodo DOI). The skill is nanopub-network-specific.

## Prerequisite — Science Live API key

This skill calls `/np/constellation`, which requires authentication.

```bash
export SCIENCELIVE_API_KEY="sl_..."
# Optional: override the API base if you self-host
export SCIENCELIVE_API_BASE="${SCIENCELIVE_API_BASE:-https://api.sciencelive4all.org}"
```

Get a key from the platform at `platform.sciencelive4all.org → Settings → API Keys`. Keys begin with `sl_`. If the user has the Zotero plugin set up to publish nanopubs, they already have one stored in Zotero preferences.

If `SCIENCELIVE_API_KEY` is unset, stop and tell the user: *"This skill needs `SCIENCELIVE_API_KEY` exported in the environment. Generate one at platform.sciencelive4all.org → Settings → API Keys, then re-run."*

## Procedure

### Step 1 — Get the entry URI

Ask the user for the entry URI. Acceptable forms:

- `https://w3id.org/sciencelive/np/RA...` (Science Live native)
- `https://w3id.org/np/RA...` (nanopub network)

Reject URIs that don't match this pattern — this skill is nanopub-network-specific.

### Step 2 — Call the constellation API

```bash
entry_uri="<the user's URI>"
encoded=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$entry_uri")
api_base="${SCIENCELIVE_API_BASE:-https://api.sciencelive4all.org}"

response=$(curl -sL --max-time 90 \
  -H "x-api-key: $SCIENCELIVE_API_KEY" \
  -H "Accept: application/json" \
  -w "\nHTTP_STATUS:%{http_code}" \
  "$api_base/np/constellation?uri=$encoded")

status=$(printf '%s' "$response" | sed -n 's/^HTTP_STATUS://p' | tail -1)
body=$(printf '%s' "$response" | sed '/^HTTP_STATUS:/d')
```

Handle the failure modes:

| Status | Meaning | Action |
|---|---|---|
| 200 | constellation returned | proceed |
| 401 | API key invalid | abort, ask user to refresh / re-export key |
| 404 | entry URI not on Science Live | abort, ask user to verify the URI by opening `https://w3id.org/sciencelive/np/<RA-id>` in a browser first |
| 5xx / timeout | API or upstream KP unavailable | abort, suggest retry later |

The 200 JSON response is the constellation. Top-level keys:

- `entry` — the URI you sent
- `paperDoi` — the DOI of the upstream paper this chain replicates / qualifies (may be null)
- `apexCito` — the topmost CiTO Citation URI (null if none)
- `researchSynthesis` — `{uri, label, synthesis, conditions, limitations, recommendations}` or null
- `chains[]` — array of `{id, outcomeUri, outcomeVerdict, outcomeConfidence, citoRelations[], steps[]}`
- `chains[].steps[]` — array of `{step, uri, …}` where `step` is `"AIDA"`, `"Claim"`, `"Study"`, `"Outcome"`, or `"CiTO"` and each step type carries its substantive prose fields inline (Study has `scope`, `method`, `deviations`; Outcome has `label`, `verdict`, `confidence`, `conclusion`, `evidence`, `limitations`, `repository`; CiTO has `relations[]`, `targets[]`)

**Upstream terminus — the constellation may not reach AIDA or Quote.** The Claim→AIDA link is a shared AIDA-statement IRI (`asAidaStatement → http://purl.org/aida/<sentence>`), not a nanopub-to-nanopub reference, and the `/np/constellation` walk follows only nanopub references. For some chain shapes it therefore terminates at the **Claim**: `steps[]` has no `"AIDA"` entry, and the upstream Quote-with-comment / PICO / PCC (step 1) is absent too. This is expected, not a missing-data failure — those upstream nanopubs exist and are valid. If you need the AIDA / Quote prose, recover their URIs from the source chain's `PUBLISHED.md` (or from the Claim's `asAidaStatement` IRI) and fetch them directly via the **bare resolver form** (see Step 3's archival loop). An API-side fix to bridge the AIDA-statement IRI is tracked separately.

### Step 3 — Cache the response

Write the raw response to `nanopubs/imported/constellation.json` (this directory is gitignored by the template). This is the single source of truth for the rest of the skill.

```bash
mkdir -p nanopubs/imported
printf '%s' "$body" | python3 -m json.tool > nanopubs/imported/constellation.json
```

Optionally also fetch each step URI's TriG for archival (useful if the user wants to inspect the raw signed payload):

```bash
mkdir -p nanopubs/imported/trig
for uri in $(printf '%s' "$body" | jq -r '.chains[].steps[].uri'); do
  ra_id=$(printf '%s' "$uri" | sed 's|.*/||')
  # The …/sciencelive/np/… form redirects to the HTML viewer; only the bare
  # w3id.org/np/ resolver form serves TriG. Swap the prefix before fetching.
  resolver_uri=$(printf '%s' "$uri" | sed 's#/sciencelive/np/#/np/#')
  curl -sL -H "Accept: application/trig" -o "nanopubs/imported/trig/${ra_id}.trig" "$resolver_uri"
done
```

(TriG fetching is optional — the constellation JSON already includes the substantive prose. Only do this if the user explicitly asks, or if a downstream step needs the raw RDF.)

### Step 4 — Generate `CHAIN_SUMMARY.md`

Use the constellation JSON to write `nanopubs/imported/CHAIN_SUMMARY.md`. The constellation API gives you all the prose inline — no per-URI TriG parsing needed.

Template:

```markdown
# Prior FORRT chain summary

**Entry URI**: <entry_uri>
**Imported on**: <ISO date>
**Constellation size**: <jq '.chains | length'> chain(s), <jq '[.chains[].steps[]] | length'> steps total

## Upstream paper

DOI: <.paperDoi>
<resolve to title via doi.org if useful; otherwise leave for the user to fill in>

## Chain(s) already published

For each entry in `.chains[]`, emit a section:

### Chain <.chains[N].id> — <derive a short label from .chains[N].steps[step=="Outcome"].label>

Verdict: <.chains[N].outcomeVerdict> (<.chains[N].outcomeConfidence>)
CiTO relations to upstream paper: <.chains[N].citoRelations | join(", ")>

| Step | URI | Key content |
|---|---|---|
| AIDA | <step.uri> | "<step.text>" |
| Claim | <step.uri> | type=<step.type>, label="<step.label>" |
| Study | <step.uri> | scope: "<first 200 chars of step.scope>"; method: "<first 200 chars of step.method>" |
| Outcome | <step.uri> | "<step.label>"; conclusion: "<first 300 chars of step.conclusion>" |
| CiTO | <step.uri> | relations=<step.relations | join(",")> → targets=<step.targets | join(", ")> |

Repository (Outcome): <step.repository>

### Apex Research Synthesis (if .researchSynthesis is not null)

URI: <.researchSynthesis.uri>
Label: "<.researchSynthesis.label>"

Synthesis (full text):
"<.researchSynthesis.synthesis>"

Conditions: <.researchSynthesis.conditions>
Limitations: <.researchSynthesis.limitations>
Recommendations: <.researchSynthesis.recommendations>

### Apex CiTO (if .apexCito is not null)

URI: <.apexCito>
(see `chains[*].steps[]` for its `relations[]` and `targets[]`)

## What this new replication can do

Given the prior chains above, the new replication's natural positioning:

- If a prior chain `confirms` the upstream paper and your replication tests a different taxon / region / horizon → new chain's CiTO will `extends` one of the prior CiTO URIs.
- If a prior chain `qualifies` and your replication may reinforce or contradict the qualification → new CiTO is either `cito:confirms` (qualifies the qualification — note in the CiTO comment field) or `cito:disputes`.
- If no prior chain exists for the dimension you test → fresh sibling chain rooted on the upstream paper, CiTO relation chosen from the new Outcome verdict (`confirms` / `qualifies` / `disputes` / `extends`).

## Methodological precedents to inherit

- Scope and method from prior Study nanopubs (already in `chains[].steps[step="Study"]`) — read before drafting `nanopubs/drafts/04_study.md` to ensure comparability where intended.
- Limitations declared by prior Outcome nanopubs — these flag constraints prior authors hit; your replication may hit the same.

## Open questions for the user

- Will the new replication `extends` the canonical chain's CiTO, or open a fresh chain rooted on the upstream paper?
- Are there prior Research Software nanopubs whose toolchain to reuse (cite via `cito:usesMethodIn`)?
- Does the prior Synthesis already cover the case you're testing? If so, do you add a new chain or extend the existing Synthesis?
```

Keep the summary **factual and short** — copy prose from the constellation response verbatim where possible. Do not editorialise. The user (and the `paper-analyst` agent that runs next) will read this to position the new replication.

### Step 5 — Infrastructure-layer inheritance (sibling repos)

The constellation response gives you `chains[].steps[].repository` for each Outcome. These are typically Zenodo concept DOIs or GitHub URLs of the sibling replication repos. For each unique repository URL:

```bash
for repo in $(printf '%s' "$body" | jq -r '.chains[].steps[] | select(.step=="Outcome") | .repository' | sort -u); do
  echo "Sibling: $repo"
  # If $repo is a Zenodo DOI, resolve to its GitHub URL via the Zenodo API:
  #   curl -s "https://zenodo.org/api/records/<id>" | jq -r '.metadata.related_identifiers[] | select(.relation=="isSupplementTo" or .scheme=="url") | .identifier'
  # Otherwise it's already a GitHub URL.
  # git clone into ../ (filesystem-sibling convention)
done
```

`scripts/inherit_sibling_repos.py` does exactly this — reads the cached constellation, resolves each Outcome's `repository` (Zenodo DOIs included), clones the siblings, stages the starter files, and writes `SETUP_INHERITED.md`. Prefer it over hand-rolling the loop above:

```bash
pixi run python scripts/inherit_sibling_repos.py \
  --constellation-json nanopubs/imported/constellation.json
```

Pass `--no-clone-siblings` to skip the `git clone` step (staging then only proceeds for siblings already present under `../`).

### Step 6 — Hand off

Tell the user:

> *"Imported the constellation rooted at `<entry_uri>` — <N> chain(s), <M> steps. Summary at `nanopubs/imported/CHAIN_SUMMARY.md` (local cache — **gitignored, do NOT commit**).*
>
> *The persistent pointer to this prior chain is the entry URI itself, which should be added to `CITATION.cff` `references:` as a `type: generic` entry with `url:` set to the URI. The nanopub network is the single source of truth, not a committed snapshot — anyone cloning the repo can regenerate the local cache by re-running `/import-from-nanopub <URI>`.*
>
> *Open questions are listed at the bottom of `CHAIN_SUMMARY.md` — answer those before drafting any nanopubs. Then either: (a) place the upstream paper PDF at `paper/<name>.pdf` and run the `paper-analyst` agent in Phase 1 with `CHAIN_SUMMARY.md` as the prior-work context, or (b) skip directly to Phase 2 if the new replication is a pure method-extension of a prior chain and doesn't need fresh paper analysis."*

If `SETUP_INHERITED.md` reports files were staged to `_template_from_prior/`:

> *"The infrastructure-layer inheritance has staged `<N>` starter files at `_template_from_prior/`, copied from the canonical sibling chain. **Review each staged file, merge with your own at the corresponding path, then delete `_template_from_prior/`.** This is a one-shot reference area, NOT durable repo state. Do not commit it."*

**The cache is gitignored on purpose.** Nanopubs are immutable on the network and identified by their URI. Mirroring them into each replication repo creates inconsistency risk (the local snapshot can diverge from the live network) and bloats repos with derived data.

## Failure modes

- **Empty `chains[]`** — the entry URI resolved but the constellation walker found no chain steps reachable from it. Common cause: the entry URI is a leaf nanopub with no incoming CiTO links yet. Verify the URI is a CiTO Citation or a Research Synthesis (those are the canonical apex points), not e.g. an isolated AIDA.
- **`paperDoi` is null** — the constellation didn't surface an upstream DOI. Check the `chains[].steps[step="CiTO"].targets[]` manually; the paper DOI is usually in there.
- **All `step` values look correct but prose fields are empty** — the published nanopubs may use a non-standard template version. The constellation API extracts fields from known templates; if a chain uses a custom template, fall back to fetching the TriG manually via Step 3's optional block.
- **`Could not resolve <Zenodo DOI> to a GitHub URL`** — the Zenodo record's `related_identifiers` don't include a GitHub link. Common in older deposits; ask the user to manually add the GitHub URL, or visit the Zenodo page and clone the linked repo manually.
- **`git clone failed`** — repo is private, network down, or rate-limited. Continue without cloning; tell the user to clone the repo manually under `../`, then re-run `scripts/inherit_sibling_repos.py --no-clone-siblings` to stage from the local clone.
- **Inherited file conflicts** — `_template_from_prior/` files start fresh each import. If you re-run with different siblings, prior staging is overwritten. Don't store work-in-progress edits in `_template_from_prior/`.

## Companion docs

- `docs/nanopub-chain-discovery.md` — when this entry point makes sense vs. a paper-rooted Phase 1.
- `docs/forrt-form-fields.md` — the form structure of each FORRT chain step.
- `docs/chain-decision-tree.md` — which template starts a chain; paper-rooted vs question-rooted.
- `docs/programmatic-nanopubs.md` — for batch / retract / supersede operations.
- `/verify-chain` skill — once the new replication has its own chain published, run that skill to check internal+external consistency.
