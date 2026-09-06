# `docs/fair4rs-checklist.md` — FAIR4RS conformance checklist

The **FAIR Principles for Research Software (FAIR4RS)** (Chue Hong et al. 2022, [doi:10.15497/RDA00068](https://doi.org/10.15497/RDA00068)) adapt FAIR — Findable, Accessible, Interoperable, Reusable — to research software's specific lifecycle. There are 17 sub-principles. This checklist maps each principle to where in this template it is addressed and what artefact provides the evidence.

Run through this checklist before each release. A "✓" requires both: (a) the artefact exists, and (b) it has the right content (not just a placeholder).

---

## Findable

### F1.1 — Software has a globally unique and persistent identifier

| Where | Evidence |
|---|---|
| `CITATION.cff` field `doi` | Zenodo concept DOI from first GitHub release. Format: `10.5281/zenodo.<N>`. |
| `codemeta.json` field `identifier` and `@id` | Same concept DOI in URL form: `https://doi.org/10.5281/zenodo.<N>`. |

**Mint procedure:** create the first GitHub release; the GitHub ↔ Zenodo integration mints a concept DOI automatically (one DOI that resolves to the latest version, plus per-version DOIs). Update `CITATION.cff` and `codemeta.json` after the first release.

### F1.2 — Components representing levels of granularity are assigned distinct identifiers

| Where | Evidence |
|---|---|
| Per-version Zenodo DOIs | Each GitHub release mints its own version DOI. |
| Docker image Zenodo DOI | `.github/workflows/docker.yml` archives the GHCR image to Zenodo on each release with a separate DOI. |
| FORRT chain nanopub URIs | Each step in the chain (Quote, AIDA, Claim, Study, Outcome, Citation) is its own nanopub with a distinct URI. Listed in `nanopubs/PUBLISHED.md`. |

### F2 — Software is described with rich metadata

| Where | Evidence |
|---|---|
| `CITATION.cff` | author, ORCID, affiliation, version, release date, license, keywords, references. |
| `codemeta.json` | structured CodeMeta-2.0 metadata: `name`, `description`, `version`, `license`, `programmingLanguage`, `softwareRequirements`, `author`, `referencePublication`. |
| `README.md` | human-readable overview, quick start, citation. |
| FORRT Replication Outcome | scientific provenance: claim being tested, methodology, deviations, validation status, evidence, limitations. |

### F3 — Metadata clearly include the identifier of the software they describe

| Where | Evidence |
|---|---|
| `CITATION.cff` | `doi` and `identifiers` fields name the Zenodo DOI. |
| `codemeta.json` | `identifier` and `@id` fields. |
| FORRT Outcome's `Repository URL` field | Points to `https://github.com/{{REPO_ORG}}/{{REPO_NAME}}`. |

### F4 — Metadata are FAIR, searchable, and indexable

| Where | Evidence |
|---|---|
| Zenodo record | indexed by Google Scholar, OpenAIRE, OpenCitations. |
| GitHub repo with topics | suggested topics in `README.md` make the repo discoverable via GitHub search. |
| FORRT chain on Science Live | nanopubs are published to the global nanopub network, queryable via SPARQL. |

---

## Accessible

### A1 — Software is retrievable by its identifier using a standardised protocol

| Where | Evidence |
|---|---|
| Zenodo DOI resolves via HTTPS | DOI proxy (`https://doi.org/...`) is universally implemented. |
| GitHub HTTPS / SSH | clone via standard protocols. |
| GHCR Docker pull | `docker pull ghcr.io/{{REPO_ORG}}/{{REPO_NAME}}:latest` over HTTPS. |

### A1.1 — Protocol is open, free, and universally implementable

HTTPS, git, OCI Docker registry — all open standards, free, and widely implemented. ✓

### A1.2 — Protocol allows authentication where necessary

Public release artefacts are anonymous-accessible. Private upstream data sources (Copernicus Marine, DestinE Data Lake) authenticate per their own protocols, documented in `data/README.md`.

### A2 — Metadata are accessible even when software is no longer available

| Where | Evidence |
|---|---|
| Zenodo archives the source tarball | Source remains accessible even if GitHub or the GitHub repo is deleted. |
| Zenodo archives the Docker image | Image remains accessible even if GHCR purges it (containers on GHCR can disappear). |
| `CITATION.cff` and `codemeta.json` are inside the source tarball | Metadata travels with the archive. |

---

## Interoperable

### I1 — Software reads, writes, and exchanges data in a way that meets domain-relevant community standards

| Where | Evidence |
|---|---|
| `pixi.toml` + `pixi.lock` declarative dependency manifest | TOML manifest + per-platform lockfile pinning every package to an exact build hash; conda + PyPI sources. |
| `Dockerfile` based on `ghcr.io/prefix-dev/pixi` | OCI-compliant container; image installs from `pixi.lock` so the container env is byte-identical to local + CI. |
| Notebook outputs | NetCDF, parquet, CSV, GeoTIFF — all open, community-standard formats. |
| Jupyter Book + jupytext `.py` source-of-truth | open notebook formats; `.py` is round-trippable to `.ipynb`. |

### I2 — Software includes qualified references to other objects

| Where | Evidence |
|---|---|
| `CITATION.cff` `references` | qualified link to the original paper DOI. |
| `codemeta.json` `referencePublication` | structured reference. |
| FORRT chain CiTO Citation | typed citation (`confirms` / `qualifies` / `disputes` / `extends` / `usesMethodIn`) to the original paper. |
| FORRT Replication Study | typed reference to the FORRT Claim it tests. |
| Research Software nanopub `Related Publications` | typed back-link to the FORRT Outcome(s) the software implements. |

The FORRT chain is the strongest contribution to **I2** — the citations are not just URLs but *typed assertions about the relationship*.

---

## Reusable

### R1 — Software is described with a plurality of accurate and relevant attributes

Covered by F2 (rich metadata) plus the FORRT chain's scientific provenance (claim, scope, method, results).

### R1.1 — Software is given a clear and accessible license

| Where | Evidence |
|---|---|
| `LICENSE` | MIT license at the repo root. |
| `CITATION.cff` `license: MIT` | declarative metadata. |
| `codemeta.json` `license` field | URL form: `https://spdx.org/licenses/MIT`. |

### R1.2 — Software is associated with detailed provenance

This is where the **FORRT chain matters most.** `CITATION.cff` and `codemeta.json` describe what the software is; the FORRT chain describes what the software *did* — what scientific claim it tested, what data it used, what method, and what the result was.

| Where | Evidence |
|---|---|
| FORRT Quote-with-comment | links to the original paper sentence being tested. |
| FORRT AIDA | atomic declarative version of the claim. |
| FORRT Claim | typed claim with scientific genre. |
| FORRT Replication Study | scope + method + deviations from the original. |
| FORRT Replication Outcome | result + evidence + limitations + repo URL + completion date + author ORCID. |
| FORRT Citation (CiTO) | typed citation back to the original paper. |
| Each nanopub is cryptographically signed by the author's ORCID-linked key | tamper-evident provenance. |

A reader who finds this software via its Zenodo DOI can follow the references to the FORRT chain and see the full scientific provenance, including which claim it implements, the original paper, the validation result, and the date.

### R2 — Software includes qualified references to other software

| Where | Evidence |
|---|---|
| `pixi.toml` (+ `pixi.lock`) and `codemeta.json` `softwareRequirements` | declared upstream dependencies; the lockfile additionally pins each upstream package to an exact build hash. |
| Research Software nanopub for upstream tools (when applicable) | the upstream library (e.g. `foscat`, `planktonclas`) gets its own Research Software nanopub that the FORRT Outcome cites. |

If your replication's reusable artefact is an upstream library (not just a one-off demo), publish a separate Research Software nanopub for the upstream tool. See `CLAUDE.md` § Layered architecture: FORRT vs Research Software, and `docs/forrt-form-fields.md` § Research Software.

### R3 — Software meets domain-relevant community standards

| Where | Evidence |
|---|---|
| `DOMAIN.md` | encodes domain conventions (e.g. HEALPix NESTED for biodiversity-EO). |
| Snakefile + jupytext + Docker pattern | matches the FAIR for Reproducible Research Software (FAIR-RRS) workshop pattern from FORCE11 / RDA. |
| FORRT alignment | the work is auditable against a community-driven open-science framework, not bespoke metadata. |

---

## Pre-release checklist

Run this list before cutting any GitHub release:

- [ ] `CITATION.cff` `version` and `date-released` updated.
- [ ] `codemeta.json` `version` and `dateModified` updated.
- [ ] All `{{...}}` placeholder tokens substituted, **except `{{ZENODO_DOI}}`** which is allowed to remain until the first release mints the concept DOI (see line 167). Audit with: `grep -rln '{{[A-Z_]\+}}' . --include='*.md' --include='*.yml' --include='*.json' --include='*.cff' --include='*.toml' | while read f; do grep -oE '\{\{[A-Z_]+\}\}' "$f" | grep -qv '{{ZENODO_DOI}}' && echo "$f"; done` — should return nothing.
- [ ] `pixi.toml` lists every notebook import (`grep -h "^import\|^from" notebooks/*.py | sort -u`); `pixi.lock` is fresh (`pixi install --locked && git diff --exit-code pixi.lock`).
- [ ] `LICENSE` carries the right author and year.
- [ ] Release notes follow the Zenodo-description format (`docs/cicd-conventions.md` § Release notes are Zenodo descriptions).
- [ ] If this is the first release: `CITATION.cff` `doi` field is left as `{{ZENODO_DOI}}` (the integration mints it on release; update afterwards).
- [ ] If this is a subsequent release: `CITATION.cff` `doi` field carries the concept DOI from the first release.
- [ ] FORRT chain (if any) is published; URIs are listed in `nanopubs/PUBLISHED.md` and embedded in the Jupyter Book.
- [ ] Docker image builds and runs the snakemake target via `docker run --rm ghcr.io/{{REPO_ORG}}/{{REPO_NAME}}:latest`.

If any item is unchecked, the release is not FAIR4RS-conformant and should not ship.

---

## References

- Chue Hong, N. P., Katz, D. S., Barker, M., Lamprecht, A.-L., Martinez, C., Psomopoulos, F. E., Harrow, J., Castro, L. J., Gruenpeter, M., Martinez, P. A., Honeyman, T., Struck, A., Lee, A., Loewe, A., van Werkhoven, B., Jones, S., Garijo, D., Plomp, E., Genova, F., … RDA FAIR4RS WG (2022). *FAIR Principles for Research Software (FAIR4RS Principles)*. Research Data Alliance. [doi:10.15497/RDA00068](https://doi.org/10.15497/RDA00068).
- Lamprecht, A.-L. et al. (2020). *Towards FAIR principles for research software*. Data Science 3:37-59. [doi:10.3233/DS-190026](https://doi.org/10.3233/DS-190026).
- Force11 Software Citation Working Group. *Software Citation Principles*. [doi:10.7717/peerj-cs.86](https://doi.org/10.7717/peerj-cs.86).
- CodeMeta. *CodeMeta-2.0 schema*. [https://codemeta.github.io/](https://codemeta.github.io/).
- Citation File Format (CFF). [https://citation-file-format.github.io/](https://citation-file-format.github.io/).
