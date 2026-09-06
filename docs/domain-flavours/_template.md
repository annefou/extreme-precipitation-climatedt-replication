# DOMAIN.md — <YOUR DOMAIN NAME>

This file encodes domain-specific conventions for replications in **<YOUR DOMAIN>**. It is loaded by `CLAUDE.md` and applied automatically.

## Domain: <your domain>

A 2-4 sentence description of the field this flavour covers, with examples of typical replications. Mention the kinds of papers, claim types, and data sources that are in scope.

## Default tooling stack

When the user asks Claude to set up a typical analysis, the default tools to suggest are:

| Concern | Default tool | Notes |
|---|---|---|
| <e.g. tabular data> | <e.g. `pandas`> | <one-line note> |
| ... | ... | ... |

Pin every dependency in `pixi.toml` and commit the regenerated `pixi.lock`.

## Domain conventions

### <Convention 1 — short imperative title>

A 1-2 paragraph description of the convention. Then concrete: a code snippet, a configuration value, a checklist. Then a 1-sentence rationale: *"if this is violated, X breaks because Y"*.

### <Convention 2 — short imperative title>

…

### Self-contained data downloads

Every notebook MUST include code to download its input data — never assume data exists locally. Use this domain's standard archives (e.g. `<DOMAIN_REPO>`) and mint a citable DOI per query if applicable.

## Style conventions

### <Convention 1 — write-up rule>

What to do, what not to do, with one example each.

### Honest negative results

A replication that contradicts the original paper's headline is publishable. Don't overclaim.

### Vision-piece framing for advocacy posts

When drafting public-facing posts about a replication in this domain, the angle is `<the broader story this replication illustrates>`. Don't lead with "we replicated X". Treat the replication as the worked example, not the lead.

## Adapting further

If your subfield has additional conventions, fork this flavour into a sub-flavour (e.g. `biodiversity-earth-observation.md` → `marine-biodiversity.md`) and replace `DOMAIN.md` accordingly.
