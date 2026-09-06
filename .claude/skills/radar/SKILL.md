---
name: radar
description: Pre-Phase-0 discovery — find a replication target before you have a paper PDF. Uses the replication-radar MCP server (OpenAIRE Graph + Software Heritage + Science Live verdicts) to surface impact-ranked papers worth replicating in a field, find INDEPENDENT reusable tooling (author-disjoint from the original = replication, not reproduction), and check whether a claim has already been replicated and how it held. Run this when the user knows the field but not yet the paper, or wants to confirm a candidate is worth the effort.
---

# /radar

You're helping the user **choose what to replicate**, before Phase 0. This is the step *upstream* of `CLAUDE.md`'s six phases: discovery of a worthwhile, feasible, not-already-done target. Once a target is chosen, hand off to Phase 0 (`/init-template`) and Phase 1.

This skill is read-only discovery. It does not init the template, write nanopubs, or run analysis.

## When to use

- The user knows a **field** ("species distribution models", "marine heatwave biodiversity") but hasn't picked a paper.
- The user has a **candidate paper** and wants to know: is it high-impact enough to be worth replicating? Has someone already done it? Is there independent tooling so this is a *replication* and not a from-scratch reproduction?
- The user wants to avoid duplicating an existing Science Live replication (or wants to deliberately *extend* one — in which case route to `/import-from-nanopub` next).

If the upstream paper is already known to have FORRT chains on the network, prefer `/import-from-nanopub` (Phase 1 entry B) — this skill is for the step *before* that.

## Prerequisite — the replication-radar MCP server

This skill calls the **`replication-radar`** MCP server. Install it **once, user-scoped**, so it is available in every session and folder (and there is no per-repo scope clash):

```
pipx install replication-radar
claude mcp add replication-radar -s user -- replication-radar
```

`pipx` needs no extra runtime; see the [MCP setup guide](https://github.com/ScienceLiveHub/replication-radar/blob/main/docs/mcp-setup.md) for other agents and an optional `GITHUB_TOKEN`. The server hits the public OpenAIRE Graph API anonymously (no key). This repo intentionally does **not** bundle the server in a `.mcp.json`: per-repo `uvx` autoload needs `uv` installed and conflicts with a user-scoped install. If the tools below are not available, tell the user to install replication-radar user-scoped as above.

It exposes three tools:

| Tool | Use it to… |
|---|---|
| `radar(topic, limit)` | List impact-ranked replication targets in a field — each **OPEN** (opportunity) or **VERIFIED** (a Science Live replication already exists, with the verdict) + independent tooling + field funder context |
| `find_independent_software(doi, topic)` | For a chosen paper, list reusable engines **not authored by the original team**, ranked by reuse signal (code repo + Software Heritage + usage) |
| `replication_status(doi)` | Has this exact DOI been replicated, and did it hold? Returns the verdict(s) + CiTO nanopub links, or `open` |

## How to run

1. **Clarify the field or candidate.** If the user gives a field, use `radar(topic=…)`. Keep the topic **short (2–3 words)** — OpenAIRE free-text terms are AND-ed, so long queries return nothing. If the user names a specific paper/DOI, start with `replication_status(doi)` then `find_independent_software(doi)`.

2. **Read the ranking honestly.** Present OPEN targets (the opportunities) ranked by citation impact, and call out any VERIFIED entries (already done — either skip, or `/import-from-nanopub` to extend them). Citation impact is the OpenAIRE signal for *where verification matters most* — it is NOT a measure of whether the claim is true. Say so if it comes up.

3. **Check feasibility = independent tooling exists.** A target is *replicable* (vs only reproducible) when there's reusable method software **not authored by the original team**. Surface those candidates; the `independent` flag is the reproduction-vs-replication line. You are surfacing + ranking — the **user judges** whether a given tool can actually test the claim. Do not assert relevance the data doesn't support.

4. **Hand off.** Once the user picks a target:
   - New paper-rooted replication → Phase 0 `/init-template`, then Phase 1 entry A (read the PDF, verbatim Quote).
   - Extending an existing Science Live chain → `/import-from-nanopub` with the VERIFIED entry's nanopub URI.

## Honesty rules (inherit `docs/verify-before-drafting.md`)

- **OPEN-target recall is keyword-bound.** The radar surfaces what the OpenAIRE free-text search returns for your short topic; it is not an exhaustive census of a field. Say "candidates found for this query", not "the most replicable papers in the field".
- **The VERIFIED overlay is authoritative but small.** It reflects the Science Live verdict index bundled with the server (a known set of chains), not every replication that exists anywhere. "Not VERIFIED here" means "not in this index", not "never replicated".
- **Don't overstate tooling relevance.** `find_independent_software` matches by topic + author-independence, not by a proven ability to test the specific claim. Present them as candidates for the user to assess.
- **Funder context is field-level, not per-paper.** The funder panel aggregates projects in the field; it does not attribute funding to a specific paper (the Graph relation isn't exposed). Reported budgets are often 0 in records.
