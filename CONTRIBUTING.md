# Contributing to the FORRT Replication Template

Thanks for helping improve this template! It scaffolds a complete replication
study — a reproducible pipeline, a Zenodo-archived release, and a signed **FORRT
nanopublication chain** on [Science Live](https://sciencelive4all.org) — so a
researcher can go from "a paper and a question" to a citable, independently-checked
replication, driven by an AI agent.

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Add your scientific domain.** The template is built to grow across fields — we
  started with **biodiversity + earth observation** (`DOMAIN.md`). To support a new
  domain (genomics, social science, materials science, …), copy
  [`docs/domain-flavours/_template.md`](docs/domain-flavours/_template.md), fill in
  the default tooling stack, the load-bearing conventions, and the style rules for
  your field, and open a PR adding it under `docs/domain-flavours/`. This is the
  highest-leverage way to help the template reach more researchers.
- **Use the template for a real replication** — start from *"Use this template"* and
  follow `CLAUDE.md` (the operating manual). The rough edges you hit doing real work
  are the most valuable bug reports.
- **Improve the scaffolding** — docs, scripts, CI, or the nanopub-drafting tooling.
  Open an [issue](https://github.com/ScienceLiveHub/forrt-replication-template/issues)
  or a pull request.

## What this template stands for (please preserve it)

- **FAIR4RS by default.** Every artefact has a FAIR-for-Research-Software purpose —
  see the "Standards alignment — FAIR4RS" section of `CLAUDE.md` and
  `docs/fair4rs-checklist.md`. FAIR is not optional polish.
- **Grounded, verified, never recalled.** Quotes are copied verbatim from the paper
  PDF; numbers come from `results/`; methods from the notebook that ran; controlled
  terms from the template's own enumerations (`docs/verify-before-drafting.md`).
  Publishing is automated, so a value invented from memory gets *signed* — don't.
- **Deterministic code does the mechanical work; the agent does the judgement.**
  Phase 5 splits this way on purpose (`pixi run build-chain-draft` pre-fills the
  nanopub JSON; the human/agent supplies only the claim and its interpretation).
  Keep new automation on the deterministic side.
- **Domain conventions are load-bearing**, not preferences — e.g. HEALPix is always
  NESTED, `healpix-geo` is the default for geographic work, GBIF queries mint a
  download DOI (`DOMAIN.md`). A flavour is a contract; keep it short and honest.

## AI-assisted contributions

AI agents are welcome — this template is built to be *driven* by one. Two conditions
keep it trustworthy, and they are the same the template enforces on every field:

- **A human is accountable.** Verify everything before it is committed or published,
  and a human reviews pull requests before they are merged. AI does not get
  autonomous merge rights.
- **Grounded, never hallucinated.** Retrieve every value from its authoritative
  source. If it can't be verified, it doesn't ship.

Please note substantial AI assistance in your PR description. In short: **use AI
freely, verify like a scientist.**

## Development

The repository uses [`pixi`](https://pixi.sh) for its environment and ships a test
suite under `tests/`:

```bash
pixi install                              # set up the environment
pytest                                    # run the tests (see pixi.toml [tasks] for shortcuts)
python scripts/check_template_drift.py    # check the template's own consistency
```

Keep pull requests focused, and describe **what** changed and **why**.

## License

The template is released under the **MIT License**. By contributing, you agree your
contributions are licensed under the same terms.
