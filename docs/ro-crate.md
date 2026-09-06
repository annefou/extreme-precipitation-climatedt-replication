# `docs/ro-crate.md` — RO-Crate packaging

This template ships an `ro-crate-metadata.json` at the repo root, making the entire repository a **Research Object Crate** ([RO-Crate 1.2](https://www.researchobject.org/ro-crate/specification/1.2/)). RO-Crate is a community-driven JSON-LD packaging convention for research data, code, and metadata — a Crate is a directory (or zip) that contains a structured `ro-crate-metadata.json` alongside the artefacts it describes.

## Profiles

The Crate conforms to three layered profiles:

1. **[RO-Crate 1.2](https://w3id.org/ro/crate/1.2)** — the base spec. Defines the `Dataset` root, `hasPart` graph, file metadata.
2. **[Process Run Crate 0.5](https://w3id.org/ro/wfrun/process/0.5)** — describes a *single execution* of a workflow. Encodes inputs, outputs, and the workflow definition.
3. **[Workflow RO-Crate 1.0](https://w3id.org/workflowhub/workflow-ro-crate/1.0)** — describes a *workflow* itself (independent of any one execution). The `Snakefile` is the `mainEntity` and is typed as `ComputationalWorkflow`.

These three together describe the replication as both *the workflow definition* and *the artefact of running it*, in a way that downstream tools (WorkflowHub, Galaxy, FAIR-RDM) can consume.

## What's inside the Crate

The default `ro-crate-metadata.json` lists:

- **Author** — Person with ORCID and affiliation.
- **Workflow** — `Snakefile` typed as `SoftwareSourceCode` + `ComputationalWorkflow`, with declared inputs and outputs.
- **Notebooks** — each `notebooks/*.py` typed as `SoftwareSourceCode` + `Notebook`.
- **Datasets** — `paper/`, `data/`, `results/`, `figures/` typed as `Dataset` with descriptions.
- **Configuration files** — `pixi.toml`, `pixi.lock`, `Dockerfile` typed as `ConfigurationFile`.
- **Citation** — back-link to the original paper DOI as `ScholarlyArticle`.
- **Nanopub registry** — `nanopubs/PUBLISHED.md` typed as `TextObject` with description pointing to the FORRT chain.

## Maintaining the Crate

The Crate description should stay in sync with the repository content. When you add a notebook, dataset, or output:

1. Add a new entry under the root `Dataset`'s `hasPart`.
2. Add a node describing the new file/directory (with `@type`, `name`, optional `description`).
3. If the new artefact is consumed or produced by the Snakemake workflow, add it to the `Snakefile` node's `input` or `output` array.

For releases, also update:

- The root `Dataset` `datePublished` to the release date.
- The root `Dataset` `version` (add this property at release time).
- The Crate's `identifier` to the Zenodo concept DOI once it's minted (`{{ZENODO_DOI}}` placeholder is currently in `CITATION.cff` and `codemeta.json` — promote the value here too).

## Validating the Crate

Use the [ro-crate-py](https://github.com/ResearchObject/ro-crate-py) library to validate:

```bash
pip install rocrate
rocrate validate .
```

Or use the [RO-Crate Playground](https://www.researchobject.org/ro-crate/playground/) — paste the JSON in and it will lint conformance.

CI integration is straightforward: add a step to `.github/workflows/ci.yml` that runs `rocrate validate .` on every push.

## Why RO-Crate alongside `CITATION.cff` / `codemeta.json` / FORRT?

Each artefact captures a different layer of metadata:

| Artefact | Captures | Audience |
|---|---|---|
| `CITATION.cff` | how to cite the software | humans, citation tools (Zotero, Zenodo) |
| `codemeta.json` | software-specific structured metadata | Software Heritage, OpenAIRE |
| `ro-crate-metadata.json` | the *whole research object* (workflow + data + code + provenance) as a navigable graph | WorkflowHub, FAIR-RDM platforms, RO-Crate consumers |
| FORRT nanopub chain | typed scientific provenance — what claim, tested how, what result | Scholarly literature, Wikidata, nanopub network |

They are complementary, not redundant. RO-Crate ties the local repo together as one navigable entity; `CITATION.cff` makes the repo citable; `codemeta.json` makes the software discoverable; the FORRT chain makes the science auditable.

## Future: depositing the Crate

For long-term archival, zip the entire repo (including `ro-crate-metadata.json`) and deposit on Zenodo. RO-Crate is increasingly recognised by FAIR-RDM platforms — Zenodo's Crate-aware tooling is in development; for now, the Crate just lives as a top-level JSON file inside the deposit.

## References

- [RO-Crate 1.2 specification](https://www.researchobject.org/ro-crate/specification/1.2/)
- [RO-Crate profiles](https://www.researchobject.org/ro-crate/specification/1.2/profiles.html)
- [Process Run Crate](https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate)
- [Workflow RO-Crate](https://www.researchobject.org/workflow-ro-crate/)
- [WorkflowHub](https://workflowhub.eu/) — the largest aggregator of Workflow RO-Crates.
