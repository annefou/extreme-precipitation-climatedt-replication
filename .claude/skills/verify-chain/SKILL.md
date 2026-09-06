---
name: verify-chain
description: Read-only verification of a published FORRT nanopublication chain. Calls the forrt-research MCP's verify_chain tool, which checks every URI in nanopubs/PUBLISHED.md against the network, the Outcome's archived repository, the cited DOIs, and whether the CiTO relation agrees with the Outcome's verdict. Returns a per-row pass/fail report. Run as the final pre-comms check after Phase 5.
---

# /verify-chain

You're verifying that the FORRT chain published from this repository is **internally consistent** (the steps cross-reference each other as the chain shape requires) and **externally consistent** (the Outcome's archived repository resolves, the cited DOIs resolve, and the citation agrees with the outcome).

This is read-only work. **Do not** edit any nanopub, do not retract, do not supersede. The output is a verification report; any fixes are downstream actions the user takes if the report finds problems.

## When to run

- **After Phase 5 is fully published.** All required steps must have URIs in `nanopubs/PUBLISHED.md` (URIs replace the `_not yet published_` placeholders).
- **Before announcing the chain publicly.** A LinkedIn post, blog announcement, or paper citation should follow a green run, not precede it.
- **After any supersede or retract operation.** Re-verify because the citation graph may have shifted.

## Prerequisite — the forrt-research MCP server

This skill calls the **`forrt-research`** MCP server. Install it once, user-scoped, so it is available in every session and folder:

```
pipx install forrt-research-mcp
claude mcp add forrt-research -s user -- forrt-research-mcp
```

If the `verify_chain` tool is not available, tell the user to install it as above rather than falling back to hand-written `curl`. The verification logic is tested code with pinned regression cases; a hand-rolled reimplementation reproduces the bugs those tests exist to prevent.

```bash
# optional — the server defaults to the dev deployment and needs no key for a public read
export SCIENCELIVE_API_BASE="https://api-dev.sciencelive4all.org"
export SCIENCELIVE_API_KEY="sl_..."
```

## Procedure

### Step 1 — Run the tool

```
verify_chain(published_path="nanopubs/PUBLISHED.md", repo_url="<the repo's GitHub URL>", mode="auto")
```

`repo_url` is optional and only used when the Outcome declares a bare GitHub URL rather than an archived DOI. Get it from `git remote get-url origin` if you want that check.

`mode` is `auto` unless the user tells you otherwise. It changes only what is *required*:

| mode | Requires a CiTO (step 06) and a cited DOI |
|---|---|
| `replication` / `reproduction` | yes |
| `new_research` | no — research starting from scratch has no existing work to cite |
| `auto` (default) | infers `new_research` when no step 06 is published |

### Step 2 — Read the result

The tool returns `green` (true only when nothing failed), `mode`, `citedPaper`, `counts`, and `rows` — one row per check, failures first. Each row has a `status` of `pass`, `fail`, `warn`, `skip` or `info`.

Checks performed:

| Check | What it means |
|---|---|
| `ledger` | every required step has a URI in `PUBLISHED.md` |
| `reachable` | every URI is really published |
| `repository` | the Outcome's archived version DOI resolves |
| `cited-doi` | every DOI the chain cites resolves |
| `verdict-relation` | the CiTO relation agrees with the Outcome's verdict |

**Read `citedPaper`, not the API's `paperDoi`.** The API picks its top-level `paperDoi` by counting DOIs across the whole graph walk, so unrelated nanopubs can outvote the chain's own citation — it names the wrong paper on both of this project's real chains. The tool derives the paper from the CiTO instead and sets `disagreesWithReported` when the two differ. (Fixed upstream in science-live-platform PR #114; until that is deployed, the tool's value is the correct one.)

### Step 3 — Report

Render `rows` as a Markdown table the user can paste into a release-readiness checklist or a Jupyter Book section. Keep the tool's own wording — it is precise about the distinction between a failure and an absence.

```markdown
## /verify-chain report

Ledger: `nanopubs/PUBLISHED.md` · mode: <mode> · steps published: <list>
Cited paper: <citedPaper.doi> (source: <citedPaper.source>)

| Check | Status | Notes |
|---|---|---|
| … | ✓ / ✗ / ⚠ | <the row's message> |

**Verdict:** GREEN / RED / YELLOW
```

- **GREEN** (`green: true`, no warns) — *"The chain is internally consistent and externally resolves correctly. Safe to announce."*
- **RED** (any `fail`) — list the specific failures and suggest the next step, typically retract + supersede via `docs/programmatic-nanopubs.md`.
- **YELLOW** (`green: true` with warns) — list the warnings and judge whether they are real. A DOI that could not be confirmed because the resolver returned 5xx is transient; retry before concluding anything.

## Reading the rows correctly

Three results look like problems and are not. The tool words them carefully; do not "helpfully" re-interpret them as failures.

- **"not enumerated by the walk but its TriG resolves"** is a **pass**. The constellation walk routinely stops short of the upstream anchors — on both of this project's real chains it returned only `[Claim, Study, Outcome]` and `[Study, Outcome, CiTO]` while the Quote, AIDA and Claim nanopubs were published and merely unreachable. Missing from the walk never means unpublished.
- **"the Outcome pins an archived version DOI"** is a **pass**. The drafts deliberately record the Zenodo *version* DOI rather than a GitHub URL, because `github.com/ORG/REPO` names a moving target while a version DOI pins the archived state the outcome was computed from.
- **"cited with … which asserts no verdict"** is **info**. A chain may cite a method paper with `citesAsAuthority` or a source with `citesAsDataSource`; that asserts no verdict on the cited work, so there is nothing to cross-check.

## Anti-patterns

- **Don't edit any nanopub.** This skill is read-only. Verification surfaces problems; the user takes the fix action.
- **Don't try to publish anything.** No publish, no retract, no supersede from this skill.
- **Don't reimplement the checks in `curl` and `jq`** if the tool is unavailable. Say it is unavailable and how to install it. This skill used to be ~250 lines of hand-written HTTP, and the tool that replaced it exists because that version had bugs — it verified from the constellation alone, which fails both real chains.
- **Don't conflate failure with absence.** Steps 07 (Research Software) and 08 (Synthesis) are genuinely optional.
- **Don't cache results across runs.** Fresh call each time — the chain may have been superseded since.

## Tools

`verify_chain` from the `forrt-research` MCP server, plus `Read` for local files and `Bash` for `git remote`. No `Edit`, `Write`, or any state-changing tool.

## Cross-references

- Chain shapes and which step references which: `docs/chain-decision-tree.md`, `nanopubs/README.md` § Order matters
- Retract / supersede (the typical fix when this returns RED): `docs/programmatic-nanopubs.md`
- The published-URI registry: `nanopubs/PUBLISHED.md`
- The server: <https://github.com/ScienceLiveHub/forrt-research-mcp>
