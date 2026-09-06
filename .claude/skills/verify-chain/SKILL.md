---
name: verify-chain
description: Read-only verification of a published FORRT nanopublication chain. Calls Science Live's /np/constellation endpoint once to fetch the structured chain, then cross-checks every URI in nanopubs/PUBLISHED.md, the Outcome's repository URL against the local git remote, and the CiTO's cited DOIs against HTTP resolvers. Returns a per-row pass/fail report. Run as the final pre-comms check after Phase 5.
---

# /verify-chain

You're verifying that the FORRT chain published from this repository is **internally consistent** (the steps cross-reference each other as the chain shape requires) and **externally consistent** (the Outcome's repository URL matches this repo, and the CiTO's cited DOIs resolve).

This is read-only work. **Do not** edit any nanopub, do not retract, do not supersede. The output is a verification report; any fixes are downstream actions the user takes if the report finds problems.

## When to run

- **After Phase 5 is fully published.** All 6 chain steps must have URIs in `nanopubs/PUBLISHED.md` (URIs replace the `_not yet published_` placeholders).
- **Before announcing the chain publicly.** A LinkedIn post, blog announcement, or paper citation should follow a green `/verify-chain` run, not precede it.
- **After any supersede or retract operation.** Re-verify because the citation graph may have shifted.

## Prerequisite — Science Live API key

This skill uses Science Live's `/np/constellation` endpoint. That endpoint requires a key.

```bash
export SCIENCELIVE_API_KEY="sl_..."
# Optional: override the API base if you self-host
export SCIENCELIVE_API_BASE="${SCIENCELIVE_API_BASE:-https://api.sciencelive4all.org}"
```

Get a key from the platform: `platform.sciencelive4all.org → Settings → API Keys`. Keys begin with `sl_`. If the user has been using the Zotero plugin to publish, they already have one — it's stored in Zotero's plugin preferences.

If `SCIENCELIVE_API_KEY` is unset when this skill runs, stop immediately and tell the user:

> *"This skill needs `SCIENCELIVE_API_KEY` set in the environment. Generate one at platform.sciencelive4all.org → Settings → API Keys, then `export SCIENCELIVE_API_KEY=sl_…` and re-run."*

## Procedure

### Step 1 — Read the local registry

Read `nanopubs/PUBLISHED.md`. Extract the published URI for each step:

| Step | Template | Required |
|---|---|---|
| 1 | Quote-with-comment, PICO, or PCC | yes |
| 2 | AIDA Sentence | yes |
| 3 | FORRT Claim | yes |
| 4 | FORRT Replication Study | yes |
| 5 | FORRT Replication Outcome | yes |
| 6 | CiTO Citation | yes |
| 7 | Research Software | optional |
| 8 | Research Synthesis | optional |

If any **required** row still reads `_not yet published_`, stop and tell the user: *"Step N has no URI in PUBLISHED.md — the chain isn't complete. Run `/verify-chain` once all six required steps are published."*

Optional steps (07, 08) flagged as `_not applicable / not yet published_` are skipped, not failed.

### Step 2 — Call the constellation API once

Pick the "deepest" URI to use as the entry point — preference order: Synthesis (step 8) → CiTO (step 6) → Outcome (step 5). The endpoint walks bidirectionally, so any of these surfaces the same constellation.

```bash
entry_uri="<deepest-published-URI>"
encoded=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$entry_uri")
api_base="${SCIENCELIVE_API_BASE:-https://api.sciencelive4all.org}"

constellation=$(curl -sL --max-time 60 \
  -H "x-api-key: $SCIENCELIVE_API_KEY" \
  -H "Accept: application/json" \
  -w "\nHTTP_STATUS:%{http_code}" \
  "$api_base/np/constellation?uri=$encoded")

http_status=$(printf '%s' "$constellation" | sed -n 's/^HTTP_STATUS://p' | tail -1)
body=$(printf '%s' "$constellation" | sed '/^HTTP_STATUS:/d')
```

> **Why `http_status`, not `status`**: `status` is a read-only variable in zsh. Assigning to it aborts the shell with `read-only variable: status`. Use any other name.

Handle the common failures:

| Status | Meaning | What to do |
|---|---|---|
| 200 | constellation returned | proceed to Step 3 |
| 401 | API key invalid | abort: tell user to refresh / re-export key |
| 404 | URI not on Science Live | abort: the entry URI isn't published, or PUBLISHED.md points at a wrong namespace |
| 5xx / timeout | API or upstream KP unavailable | abort: tell user to retry later, mention the live status indicator at `platform.sciencelive4all.org` |

The 200 response is JSON. Top-level keys you'll use:

- `entry` — the URI you sent
- `paperDoi` — the DOI of the upstream paper this chain replicates / qualifies
- `apexCito` — the topmost CiTO Citation URI (null if none)
- `researchSynthesis` — `{uri, label, synthesis, conditions, limitations, recommendations}` (null if no Synthesis)
- `chains[]` — array of `{id, outcomeUri, outcomeVerdict, outcomeConfidence, citoRelations[], steps[]}`
- `chains[].steps[]` — array of `{step, uri, …}` where `step` is one of `"AIDA"`, `"Claim"`, `"Study"`, `"Outcome"`, `"CiTO"` and the extra fields depend on the step type

### Step 3 — Internal consistency from the structured response

Build a set of all URIs returned by the API (across `researchSynthesis.uri`, `apexCito`, every `chains[].steps[].uri`, every `chains[].outcomeUri`). Then for each URI in `PUBLISHED.md`:

| Test | Pass criterion |
|---|---|
| Step 2 (AIDA) URI | present as `step: "AIDA"` in at least one chain |
| Step 3 (Claim) URI | present as `step: "Claim"` in at least one chain |
| Step 4 (Study) URI | present as `step: "Study"` in at least one chain |
| Step 5 (Outcome) URI | present as `step: "Outcome"` in at least one chain |
| Step 6 (CiTO) URI | present as `step: "CiTO"` in at least one chain, OR equal to `apexCito.uri` (see note below) |
| Step 8 (Synthesis) URI, if published | equals `researchSynthesis.uri` |
| Step 7 (Research Software) URI, if published | not part of the FORRT chain proper — verify reachability only via direct HEAD (see fallback below) |

**Note on the apex CiTO.** When this repo's CiTO sits at the apex of the whole constellation (e.g. it's the deepest URI a downstream Research Synthesis cites), the API hoists it to top-level `apexCito.uri` and **removes it from `chains[].steps[]`** — the chain that owns it will show step types like `[AIDA, Claim, Study, Outcome, ResearchSoftware]` with no `CiTO` entry. The skill must accept either form: a per-chain `step:"CiTO"` match OR `apexCito.uri == published_cito_uri`. Verified live 2026-05-30 on the Bombus projection chain (its CiTO was apexCito-only).

If a URI in `PUBLISHED.md` is missing from the constellation, that's a chain-integrity failure: the URI exists but isn't reachable from the entry point via FORRT chain links. Record it.

The constellation API does NOT enumerate Quote-with-comment / PICO / PCC URIs as a separate `step` (they sit upstream of AIDA). In some chain shapes it also omits the **AIDA** (step 2): the Claim→AIDA link is a shared AIDA-statement IRI (`asAidaStatement → http://purl.org/aida/<sentence>`), not a nanopub reference, so the walk can terminate at the Claim. Treat a missing step 1 — and a missing step-2 AIDA — as **upstream-not-enumerated**, not a chain-integrity failure; still verify those URIs in `PUBLISHED.md` resolve.

Verify each upstream URI with a direct TriG fetch. **Do not test the `…/sciencelive/np/…` form** — it redirects to the HTML viewer and returns HTTP 200 on the SPA shell, so a status-only check passes even when no nanopub is served. Use the **bare resolver form** `https://w3id.org/np/RA…` (swap the prefix) and assert the body is TriG, not HTML:

```bash
upstream_uri="<step-1 or, if absent, step-2 AIDA URI>"
resolver_uri=$(printf '%s' "$upstream_uri" | sed 's#/sciencelive/np/#/np/#')
body=$(curl -sL --max-time 30 -H "Accept: application/trig" "$resolver_uri")
case "$(printf '%s' "$body" | head -c 16 | tr 'A-Z' 'a-z')" in
  '@prefix'*)            echo "PASS — TriG served" ;;
  '<!doctype'*|'<html'*) echo "FAIL — HTML viewer, not a nanopub" ;;
  *)                     echo "FAIL — unexpected response" ;;
esac
```

### Step 4 — External consistency

**Outcome's Repository URL matches this repo's GitHub remote.**

The constellation's Outcome step exposes the repository inline. Find the Outcome whose URI matches step 5 in PUBLISHED.md and read its `.repository` field via `jq`:

```bash
outcome_repo=$(printf '%s' "$body" | jq -r \
  --arg uri "$step5_uri" \
  '.chains[].steps[] | select(.step == "Outcome" and .uri == $uri) | .repository' \
  | head -1)
```

Compare against the local repo's GitHub URL:

```bash
expected_repo=$(git remote get-url origin | sed 's|.*github.com[:/]||;s|\.git$||')
# Example: "annefou/weatherxbiodiversity-projection"
```

The Outcome's `repository` may be a Zenodo concept DOI, a Zenodo version DOI, or a github URL. All three are acceptable. Pass criterion (first match wins):

1. **GitHub URL match.** `github.com/${expected_repo}` appears as a substring of the Outcome's `repository`.

2. **Same-record Zenodo redirect.** Both the Outcome's `repository` (if a Zenodo DOI) and the `CITATION.cff` `doi:` value resolve to the same `zenodo.org/records/<N>` URL. This is the common version-drift case: each GitHub release mints a new version DOI on the same concept; the Outcome may have been published against an earlier version DOI than the one now in `CITATION.cff`, but both redirects converge on the same record. Detect via the final URL after redirects:

   ```bash
   resolve_zenodo_record() {
     # Returns "zenodo.org/records/<N>" or empty string
     curl -sI -L --max-time 20 -o /dev/null -w '%{url_effective}' "$1" \
       | sed -nE 's|.*(zenodo\.org/records?/[0-9]+).*|\1|p'
   }
   outcome_record=$(resolve_zenodo_record "$outcome_repo")
   cff_record=$(resolve_zenodo_record "https://doi.org/$cff_doi")
   [ -n "$outcome_record" ] && [ "$outcome_record" = "$cff_record" ] && echo "PASS"
   ```

3. **Exact-string DOI match.** The Zenodo DOI in `CITATION.cff` appears verbatim in the Outcome's `repository`. (This is the trivial case where the same DOI is used in both places — rare in practice once multiple releases exist.)

If none of the three pass, that's a RED failure: the Outcome points at a repository the local repo no longer claims as its own.

**CiTO's cited DOIs resolve.**

For each chain's CiTO step, read its `.targets[]` (DOIs) from the response. If this repo's CiTO is the apex (no chain step), use `.apexCito.citedTargets[]` instead.

Publisher landing pages (Wiley, Springer, Science, Elsevier) routinely return `403`/`406` to `curl` or HEAD requests via anti-bot middleware, even with a browser User-Agent. A `404` could mean "not registered"; a `403` from `science.org` does **not**. Verify DOI registration via the doi.org Content Negotiation endpoint, which is the canonical machine-readable resolution path and is not behind a publisher paywall or bot wall:

```bash
curl -sL --max-time 20 \
  -H "Accept: application/vnd.citationstyles.csl+json" \
  "$doi_url" \
  | jq -e '.DOI' >/dev/null 2>&1
```

Pass: `jq` exit `0` (response is JSON with a `.DOI` field). Fail: exit non-zero (DOI not registered, or the registrar returned an error).

If you want extra diagnostics on failure, the CSL JSON also contains `.title`, `.container-title`, and `.issued.date-parts[0][0]` (year) — useful for printing what the DOI actually resolved to in the report.

**Outcome's source DOI matches CITATION.cff (if present).**

If `CITATION.cff` has a `doi:` field (Zenodo concept DOI), check the Outcome's `repository` or `conclusion`/`evidence` text references it:

```bash
cff_doi=$(grep -E '^\s+value:' CITATION.cff | head -1 | sed 's/.*"\(.*\)".*/\1/')
printf '%s' "$body" | jq '.chains[].steps[] | select(.step == "Outcome")' | grep -F "$cff_doi"
```

If absent: warn (not fail) — the CITATION.cff DOI may be a newer release than the one referenced in the published Outcome (normal version-drift).

### Step 5 — Report

Output a single Markdown table the user can paste into a release-readiness checklist or a Jupyter Book section. One row per check, with pass / fail / warn status.

```markdown
## /verify-chain report

Entry point: `<deepest-published-URI>`
Constellation summary: <N chains, M total steps fetched>

| Check | Status | Notes |
|---|---|---|
| All required step URIs present in PUBLISHED.md | ✓ / ✗ | |
| Constellation API reachable | ✓ / ✗ | HTTP <status> |
| Step 1 (Quote/PICO/PCC) URI resolves | ✓ / ✗ | |
| Step 2 (AIDA) URI appears in constellation | ✓ / ✗ | |
| Step 3 (Claim) URI appears in constellation | ✓ / ✗ | |
| Step 4 (Study) URI appears in constellation | ✓ / ✗ | |
| Step 5 (Outcome) URI appears in constellation | ✓ / ✗ | |
| Step 6 (CiTO) URI appears in constellation | ✓ / ✗ | |
| Step 8 (Synthesis) URI matches apex | ✓ / ✗ / N/A | |
| Outcome Repository URL matches git remote | ✓ / ✗ | annefou/<repo> |
| CiTO cited DOIs resolve | ✓ / ✗ | <list of DOIs> |
| Outcome source DOI matches CITATION.cff | ✓ / ⚠ | warn = version drift |

**Verdict:** GREEN (all ✓) / RED (any ✗) / YELLOW (warns only).
```

If the verdict is GREEN, conclude with:
> *"The chain is internally consistent in the constellation graph and externally resolves correctly. Safe to announce."*

If RED, conclude with the list of specific failures and a suggested next step (typically: retract + supersede via `nanopub-agent-utilities` — see `docs/programmatic-nanopubs.md`).

If YELLOW, conclude with the warnings and a one-line judgement of whether they're real (CITATION.cff DOI vs Outcome DOI drift is normal during active releases; flag but don't block).

## Anti-patterns

- **Don't edit any nanopub.** This skill is read-only. Verification surfaces problems; the user takes the fix action.
- **Don't try to publish anything.** No `publish`, no `retract`, no `supersede` from this skill.
- **Don't conflate failure with absence.** Step 7 (Research Software) genuinely optional. Step 8 (Synthesis) genuinely optional. If the user didn't publish either, that's N/A, not a failure.
- **Don't fall back to per-URI TriG parsing as the primary path.** That's an explicit downgrade; if `SCIENCELIVE_API_KEY` is missing or the API is down, fail loudly, don't degrade silently.
- **Don't cache the constellation response across runs.** Fresh fetch each time — the chain may have been superseded since last run.

## Tools

This skill uses `Read` (for PUBLISHED.md, CITATION.cff, and local files) and `Bash` (for `curl`, `jq`, `git remote`). No `Edit`, `Write`, or any state-changing tool.

## Cross-references

- The chain shapes and which step references which: `docs/chain-decision-tree.md` and `nanopubs/README.md` § Order matters
- For retract / supersede (the typical fix when this skill returns RED): `docs/programmatic-nanopubs.md`
- The published-URI registry: `nanopubs/PUBLISHED.md`
- The constellation endpoint contract: `science-live-platform/docs/plans/nanopub-query-api.md` § `/api/np/{uri}/constellation`
