# 07 — Research Software (optional)

> Run the pre-flight checklist in `docs/forrt-form-fields.md` § Pre-flight checklist before drafting.
>
> **Scope check:** Research Software nanopubs describe **reusable software artefacts** — tools people would `pip install` or `git clone` to use in their own work. They do NOT describe one-off demo / reproduction repos. If your repo is a reproduction of someone else's paper, the reusable artefact is the *upstream library* it uses (e.g. `foscat`, `planktonclas`), not your reproduction repo. Author the Research Software nanopub for the upstream tool, not the demo. See `CLAUDE.md` § Layered architecture: FORRT vs Research Software.

**Form heading:** *"Research Software — Describe research software with metadata including repository, supporting publications, and related resources."*

## Field-by-field draft

<!-- field: software -->
### URI of published software (text input, required)

Use the Zenodo **version DOI** URL — `https://doi.org/10.5281/zenodo.<N>` for the
specific release, NOT the concept DOI. Full URL form. Fall back to a GitHub URL
only if there is no Zenodo deposit at all.

> **Why the version DOI, not the concept DOI.** A concept DOI resolves to
> whatever version is *latest*. This nanopub is signed and immutable — once
> published it can only be retracted or superseded, never edited. If it names a
> concept DOI, then the moment a v0.2.0 is released this permanent record
> silently starts describing different code, with no signature breakage and
> nothing to alert a reader. The version DOI pins the snapshot that actually
> exists behind this assertion.
>
> Both DOIs are in `CITATION.cff` under `identifiers:`, recorded automatically at
> release by `.github/workflows/release-identifiers.yml`. Take the one described
> as *"Version DOI"*. The concept DOI is correct in `CITATION.cff`'s top-level
> `doi:` field — "cite this project" — and wrong here.

```
https://doi.org/{{ZENODO_VERSION_DOI}}
```

### Software Heritage ID (optional but recommended)

The SWHID from `CITATION.cff` `identifiers:` (`type: swh`). It identifies the
exact source tree in a preservation archive, so it still resolves if the repo is
deleted, renamed, or force-pushed — which a DOI pointing at a GitHub URL does
not. `docs/chain-decision-tree.md` ranks it above the Zenodo DOI for exactly
this reason.

```
{{SWHID}}
```

<!-- field: title -->
### Software Title (text input, required)

The full name or title of the software.

```

```

<!-- field: repository -->
### Repository URL (text input, required)

```
https://github.com/{{REPO_ORG}}/{{REPO_NAME}}
```

<!-- field: project -->
### URI of nanopublication for research project that produced software (search/select, required)

URI of the FORRT Claim or PCC question this software is associated with — pull from `nanopubs/PUBLISHED.md`. This is the back-link to the FORRT chain.

```

```

<!-- field: license -->
### URI of license of published software (text input, optional)

```
https://spdx.org/licenses/MIT.html
```

<!-- field: dataset -->
### Related Datasets (text input, optional)

Input data DOIs (Zenodo data records, dataset DOIs, ESA product DOIs).

- _Dataset URL 1: ___
- _Dataset URL 2: ___

<!-- field: researchoutput -->
### Related Publications (text input, optional)

One-way back-links to the FORRT Outcome URI(s) the software implements, plus any cited methods papers.

- _Publication URL 1 (FORRT Outcome from step 05): ___
- _Publication URL 2 (methods paper, optional): ___

## Publication note

After publishing, paste the resulting URI into `nanopubs/PUBLISHED.md` step 07.
