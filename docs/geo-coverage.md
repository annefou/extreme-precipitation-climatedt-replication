# Geographical coverage (optional, Record-side)

Many replications in this template are **spatial** — an earth-observation scene, a
species range, an estuary, a transect. When the original paper's findings have a
specific geographic scope, record it as a **Geographical coverage** nanopub so the
work becomes:

- **discoverable by place** — the geometry is stored as a GeoSPARQL `wktLiteral`, so
  the platform's spatial search can find the replication by area, and
- **map-renderable** — the reader-facing story page can draw the study area from the
  published geometry instead of a flat image.

It is **optional and conditional**: draft it only when the paper actually has a study
area. A non-spatial paper has no geographic coverage — skip it. Never invent a
location to fill the form.

## It is Record, not AI

Geographical coverage is **grounded extraction**, published as a signed nanopub — it
is *not* AI-generated content. So it is the `paper-analyst`'s job (Phase 1, alongside
the headline quote), not the `audience-writer`'s:

- The **place name** and a **verbatim supporting quotation** come from the PDF —
  character-for-character, same discipline as the headline Quote
  (`docs/verify-before-drafting.md`).
- The **geometry (WKT)** is resolved by the Science Live form — typing the area name
  into the location search geocodes it (PlaceAutocomplete), or you draw it on the map
  (`MapGeometrySelector`). **Never hand-write coordinates**; a hallucinated bounding
  box is a fabricated datum. The only exception is coordinates the paper states
  verbatim, copied exactly.

## More than one location

A paper often covers several areas. Two shapes, both supported:

- **Distinct study sites** (separately meaningful) → **one coverage nanopub per site**,
  each with its own name, own verbatim quote, and own geometry, so each is individually
  searchable and citable. This is the atomic default — duplicate the per-location block
  in `09_geo_coverage.md` once per site.
- **One pooled coverage** (regions the study combines into a single extent, e.g. "North
  America, the EU and Australia") → **one** nanopub. In the form's location search, add
  each place in turn; it merges them into a single GeoSPARQL `GEOMETRYCOLLECTION` under
  one combined label.

When unsure, prefer separate nanopubs.

## Where it sits

`nanopubs/drafts/09_geo_coverage.md` holds the draft (07 = Research Software, 08 =
Research Synthesis are already taken, so geo is 09). The subject is the **original
paper's DOI** — the same DOI as the Quote (01) and CiTO (06) steps — so it documents
the *paper's* coverage.

## How to publish it

It is a **standalone** nanopub, not one of the six FORRT chain steps, and it is not
yet wired into `build-chain-draft` / the chain wizard. Publish it directly:

1. On Science Live, **Create → "Document geographical coverage"**.
2. Fill the fields from `nanopubs/drafts/09_geo_coverage.md` (the location search will
   geocode the area name and fill the geometry).
3. Review and publish.
4. Paste the resulting URI into `nanopubs/PUBLISHED.md` under a *Geographical coverage*
   row.

> **Original-paper coverage vs the replication's own study area.** The existing
> "Document geographical coverage" template anchors coverage to a **paper (DOI) + a
> verbatim quotation**, which fits documenting the *original paper's* area (works
> today). A replication whose own study area differs from the original's (e.g. testing
> a Sado-Estuary method on the Westerschelde) has no paper-quote for *its* area — that
> needs a generalized geo template (subject = the Replication Study nanopub) which is a
> separate, platform-side change. For now, document the original paper's coverage.
