# `docs/rohub-deposit.md` — Depositing as a Rohub Research Object

[Rohub](https://reliance.rohub.org) (from the RELIANCE EU project) hosts citable Research Objects with DOI minting via Zenodo integration. A Rohub deposit is *not* a duplicate of the source code; it is a **navigation index** — a single citable manifest that aggregates pointers to the GitHub repo, the Zenodo source DOI, the rendered Jupyter Book, every published FORRT nanopub, every notebook, and the cited upstream paper. Each resource keeps its own canonical URL/DOI; Rohub adds discoverability and a DOI for the bundle.

## Why Rohub on top of GitHub + Zenodo + Science Live

| Artefact | What it gives | What it lacks alone |
|---|---|---|
| GitHub repo | Source code, history, collaboration | Not citable as a fixed version |
| Zenodo concept DOI | Citable snapshot of the source | One DOI per repo; no cross-repo navigation |
| Jupyter Book | Human-friendly narrative | Not machine-actionable beyond HTML |
| Published FORRT nanopubs | Atomic, signed, queryable claims | Distributed across nanopub network; no per-replication index |
| **Rohub RO** | **Navigable cross-artefact index, citable DOI, type-tagged resources** | (the missing layer) |

A Rohub RO becomes the "one URL" you can hand to a reviewer to see the full constellation: every nanopub, every notebook, the code, the data DOI, the rendered narrative.

## The one-command path

This template ships `scripts/build-rohub-manifest.py`, which reads:

- `CITATION.cff` — title, description, author + ORCID, license, Zenodo concept DOI
- `nanopubs/PUBLISHED.md` — every published nanopub URI
- `notebooks/*.py` — every numbered jupytext notebook (skips `_*.py` helpers)
- `git remote get-url origin` — GitHub repo URL

…and writes:

- `rohub-manifest.json` — the manifest for review
- `rohub-manifest.zip` — the zipped manifest ready to upload to Rohub

Run from the repo root:

```bash
python3 scripts/build-rohub-manifest.py
```

Then in Rohub: *New Research Object → Import ZIP Research Object → select `rohub-manifest.zip`*.

## What gets included as resources

For each artefact found, an entry is added to the RO's `hasPart` with the correct Rohub-recognised `@type` IRI:

| Resource | Rohub `@type` (third slot) |
|---|---|
| Published nanopubs (all 6 chain steps + RS + Synthesis if any) | `http://www.nanopub.org/nschema#Nanopublication` |
| Each `notebooks/<NN>_*.py` | `https://w3id.org/ro/terms/earth-science#JupyterNotebook` |
| GitHub repo URL | `http://purl.org/wf4ever/wf4ever#WebService` |
| Jupyter Book site (`<user>.github.io/<repo>/`) | `http://purl.org/wf4ever/wf4ever#WebService` |
| Zenodo concept DOI URL | `http://purl.org/wf4ever/wf4ever#Dataset` |
| Cited paper DOI (if added to `citation`) | `dct:BibliographicResource` |

All resources are typed as `["File", "wf4ever#Resource", <semantic-IRI>]` and carry a `contentUrl` pointing at the external URL — the pattern Rohub's import path requires.

## Datetime format

Rohub expects `YYYY-MM-DD HH:MM:SS.SSSSSS+00:00` (space between date and time, microsecond precision, explicit timezone). The script generates this format automatically.

**Critical**: only the **root entity** carries `datePublished` / `dateCreated` / `dateModified`. If any child entry (a cited paper, for instance) has a bare year like `"2020"`, Rohub's import buggily picks it up and uses it as the RO's *created* date — your RO shows "Created 12 May 2020" instead of today. The script strips `datePublished` from all non-root entries to avoid this.

## What the script does NOT do

- **Doesn't auto-deposit** — generates the zip; you upload through Rohub's UI.
- **Doesn't read the paper PDF** — the cited paper DOI must be in `CITATION.cff` `references` or the script's optional `paper-doi` argument (TODO).
- **Doesn't follow nanopub chain semantics** — every URI in `PUBLISHED.md` is added equally; the chain structure (which step references which) lives in the nanopub network, not in the Rohub manifest.
- **Doesn't pin notebook URLs to a tag** — uses `refs/heads/main` (branch-tracking). For a Zenodo-archived stable snapshot, edit the URLs in the generated JSON to a tag before zipping.

## Cross-references

- `docs/ro-crate.md`: the per-repo `ro-crate-metadata.json` (the *bundle* RO-Crate at the repo root — different from this Rohub *manifest* RO-Crate)
- `nanopubs/PUBLISHED.md`: the source-of-truth nanopub URI registry that the script reads
- The diagnosis flow when a Rohub import doesn't render correctly is documented inline in the script's docstring.
