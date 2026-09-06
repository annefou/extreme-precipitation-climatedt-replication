# `docs/cicd-conventions.md` — CI/CD, environment, and Jupyter Book conventions

Hard-won rules for replication repos using `pixi` + `prefix-dev/setup-pixi` + `MyST` + GitHub Actions. Each rule has an associated failure mode that has cost real debugging time in past projects.

---

## `pixi.toml` is the single source of truth

All CI workflows MUST use `prefix-dev/setup-pixi@v0.9.6` with the repo's `pixi.toml` + `pixi.lock`. Never duplicate dependency lists in manual `pip install` lines in workflow YAML.

Pattern:

```yaml
- uses: prefix-dev/setup-pixi@v0.9.6
  with:
    pixi-version: v0.68.1
    locked: true
    cache: true

- name: Run notebook
  run: pixi run jupyter execute --inplace notebooks/03_analysis.ipynb
```

The `pixi.toml` must include **every** dependency the notebooks import: `nbclient`, `ipykernel`, `pytorch-cpu`, `jupytext`, etc. Local "kitchen-sink" envs (e.g. `pangeo`) hide missing deps because they have everything pre-installed; CI builds strictly from `pixi.lock` and silently produces empty notebook cells if anything is missing.

`pixi.lock` is committed alongside `pixi.toml`. When you edit `pixi.toml`, run `pixi install` locally to refresh the lockfile and commit both files in the same commit. CI runs with `locked: true` so a stale `pixi.lock` fails fast instead of silently re-solving.

### Failure mode

A previous repo's notebooks 04 and 06 imported `sklearn` but `scikit-learn` wasn't in the dep manifest. Local execution worked (pangeo has it). CI's Jupyter Book build silently produced empty cells where the sklearn imports failed. The deployed Jupyter Book showed empty figure cells with no error indication. Fix: add `scikit-learn` to `pixi.toml`, `pixi install`, commit both files.

### How to audit

Cross-check before pushing:

```bash
grep -h "^import\|^from" notebooks/*.py | sort -u
```

…and verify every external module appears in `pixi.toml` (top-level `[dependencies]` or under a `[feature.*.dependencies]` table).

---

## Channels: conda-forge first, bioconda for snakemake

`pixi.toml` declares channels with `conda-forge` first and `bioconda` second. Conda-forge handles the scientific stack; `bioconda` hosts `snakemake` (and the wider rule-engine ecosystem) — it is not in conda-forge. Pixi handles multi-channel solves cleanly; no per-package pinning to channel is needed.

If a notebook needs a pip-only package (e.g. `polytope-client`, `pygbif`'s pre-release), add a `[pypi-dependencies]` block. Pixi resolves PyPI deps against the conda env's Python — no parallel virtualenv.

---

## MyST `BASE_URL` is set in the workflow, NOT in `myst.yml`

For Jupyter Book to deploy correctly to GitHub Pages, the `BASE_URL` env var must be set on the `myst build` step, derived from the GitHub repo name:

```yaml
- name: Build MyST site
  env:
    BASE_URL: /${{ github.event.repository.name }}
  run: pixi run -e docs myst build --html
```

**Do NOT set `base_url` in `myst.yml`** — MyST silently ignores the key (with a warning if you look at the build log carefully). Without `BASE_URL`, the deployed site shows a "Site not loading correctly? This may be due to an incorrect BASE_URL configuration" error.

MyST itself is installed as a conda-forge package in the `docs` pixi feature (`mystmd`), so the workflow doesn't need a separate `setup-node` + `npm install -g mystmd` step — `pixi run -e docs myst …` picks up the env-installed binary.

---

## `myst.yml` TOC references `.ipynb`, not `.py`

MyST cannot process `.py` files. The TOC must reference `.ipynb` files:

```yaml
toc:
  - file: index.md
  - file: notebooks/01_data_download.ipynb
  - file: notebooks/02_data_clean.ipynb
```

The CI workflow converts `.py` to `.ipynb` with `jupytext` before MyST builds:

```yaml
- name: Convert .py notebooks to .ipynb
  run: |
    for nb in notebooks/*.py; do
      pixi run jupytext --to notebook "$nb"
    done
```

---

## Always use `jupyter execute --inplace`

Without `--inplace`, the executed notebook outputs are not written back to the `.ipynb` file. MyST then builds from a notebook with no cell outputs, producing a Jupyter Book with empty figure cells.

```yaml
- name: Execute notebooks
  run: |
    for nb in notebooks/*.ipynb; do
      echo "::group::Executing $nb"
      pixi run jupyter execute --inplace "$nb"
      echo "::endgroup::"
    done
```

**Use a glob, not a hard-coded list.** A hard-coded list of notebooks silently misses any new notebook that's added without updating the workflow — the new notebook gets converted (empty) and rendered (empty). Globs prevent this.

---

## `matplotlib.use('Agg')` is forbidden in jupytext notebooks

Don't put `matplotlib.use('Agg')` in jupytext notebooks. It prevents inline plot display, which means MyST builds an empty notebook even when execution succeeded.

Always pair `fig.savefig(...)` with `plt.show()` so plots appear both in the saved file AND inline in the notebook output.

```python
fig, ax = plt.subplots()
# ... plot ...
fig.savefig("../figures/main_result.png", dpi=150, bbox_inches="tight")
plt.show()  # required for MyST inline display
```

---

## MyST iframe responsive wrapper — long embeds need `<details>`

MyST automatically wraps every `<iframe>` in a responsive container with `padding-bottom:60%; width:min(max(100%, 500px), 100%)` and forces `width="100%" height="100%"` on the iframe. Explicit pixel heights on raw `<iframe>` tags are ignored — the iframe's height is locked to 60 percent of the page width.

For long embedded content (e.g. FORRT Replication Studies with multi-paragraph methodology), this produces a small embed with internal scrolling — bad UX.

**Workaround:** wrap long embeds in `<details>` collapsibles (closed by default), and put one short embed (e.g. an AIDA sentence or CiTO citation, both about half a page tall) inline as a default-visible example:

```html
<details>
<summary>Show the [name] nanopub inline</summary>

<iframe src="https://platform.sciencelive4all.org/np/?uri=..." width="100%" height="900"></iframe>

</details>

[View the nanopub on Science Live →](...)
```

Wrapping in a `<div style="height:700px">` does NOT defeat the MyST wrapper — MyST nests its own padded inner div inside the outer one.

---

## Release notes are Zenodo descriptions

GitHub release notes become the Zenodo record's Description field verbatim via the GitHub ↔ Zenodo integration. A reader discovering the archive on Zenodo sees only that text — they have no GitHub context.

Write release bodies using this structure:

1. One-sentence abstract: what the software does, which paper / claim it reproduces or extends, and the headline scientific result if any.
2. Reference paper with DOI link.
3. Bulleted list of what's in the release (notebooks, Dockerfile, CI workflows, nanopub chain).
4. For patch / metadata-only releases: state in plain language, e.g. "Metadata-only release — source identical to v0.X.0, triggered to archive the Docker image."
5. Citation note linking back to `CITATION.cff`.

**Strict rules:**

- No internal ops detail (no token state, no CI failures, no workflow reasons for patch releases).
- No bot signatures (`🤖 Generated with Claude Code` etc.). Co-authoring trailers belong in git commits, not scholarly archives.
- Keep to ≤200 words; details belong in the repo `README.md`.
- Link to the paper and any prior Zenodo records so the deposit is navigable standalone.

If a bad description is already on Zenodo: edit in place via `zenodo.org/records/<id>` → Edit → Save → Publish. This issues a metadata-only version with the same DOI; no new files needed.

---

## Preservation: Zenodo (release), Software Heritage (code), Wayback (web sources)

Three release-time archival paths, each with a distinct job. They are complementary, not redundant — capture all three where applicable.

| Workflow | Archives | Identifier | Coverage |
|---|---|---|---|
| `docker.yml` (Zenodo) | the release source tarball + (optionally) the Docker image | Zenodo concept DOI | GitHub-only auto-archival |
| `swh-save.yml` (Software Heritage) | the source tree at the released revision | **SWHID** (ISO/IEC standard) | forge-agnostic — GitHub, GitLab.com, self-hosted GitLab, any git |
| `wayback.yml` (Internet Archive) | the deployed Jupyter Book site + the URLs in `wayback-urls.txt` | timestamped `web.archive.org` snapshot | web pages (prose), not code |

Conventions:

- **Code → Software Heritage (SWHID).** SWH is the universal, forge-agnostic anchor: it covers GitLab / self-hosted forks that Zenodo's GitHub-only integration misses. `swh-save.yml` requests Save Code Now on each release. Zenodo gives the *citable release + metadata DOI*; SWH gives the *immutable code identity*. Capture both.
- **Prose / web sources → Wayback.** Blogs, design notes, README pages that state a claim are not code, so Software Heritage cannot archive them. List them in `wayback-urls.txt`; `wayback.yml` snapshots them (plus the deployed book site) on release. Pair with a Zenodo deposit if a citable DOI is also wanted.
- **Never anchor on a conda package.** Software Heritage's conda loader is not in production; built conda-forge / bioconda *artifacts* are not archived. The recipes (feedstock GitHub repos) and upstream source repos *are* archived (as git). So anchor reproducibility on **pinned `pixi.toml` / `pixi.lock` + the source repo's SWHID + the container image on Zenodo** — not the conda artifact.

All three workflows trigger only on `release` (plus manual `workflow_dispatch`), so they never run on an uninitialised template or on routine pushes.

---

## Long-running experiments — don't poll

If an analysis takes more than ~5 minutes:

1. Launch as a `nohup` background process with output to a log file.
2. Tell the user the estimated completion time.
3. Move on to other work.
4. Check results when the user asks or in the next conversation.

```bash
nohup pixi run python notebooks/03_analysis.py > results/logs/analysis.log 2>&1 &
echo "Started; tail -f results/logs/analysis.log"
```

Polling a results file every few seconds wastes conversation context and produces an unhelpful interaction shape ("checking… still running… still running…"). The runtime is what it is; let it run.

---

## Credentials in CI

For services that require credentials, never use the interactive login command in CI (it prompts for input and hangs the workflow). Construct the credentials file directly from secrets.

Example for Copernicus Marine:

```yaml
- name: Set up Copernicus Marine credentials
  run: |
    mkdir -p ~/.copernicusmarine
    echo "${{ secrets.COPERNICUS_CREDENTIALS_BASE64 }}" | base64 -d \
      > ~/.copernicusmarine/.copernicusmarine-credentials
```

The secret is a base64-encoded INI file. Generate it locally with `base64 < ~/.copernicusmarine/.copernicusmarine-credentials | tr -d '\n'` and paste into a GitHub Actions secret.

---

## Audit before push

Before pushing a release-relevant change, audit:

```bash
# Every notebook import is in pixi.toml
grep -h "^import\|^from" notebooks/*.py | sort -u

# pixi.lock is fresh (no diff after a clean install)
pixi install --locked && git diff --exit-code pixi.lock

# myst.yml TOC references .ipynb (not .py)
grep "\.py" myst.yml

# Workflow uses BASE_URL env var
grep "BASE_URL" .github/workflows/jupyter-book.yml

# Workflow executes all notebooks via glob
grep "notebooks/\*.ipynb" .github/workflows/jupyter-book.yml
```

The cost of a bad CI configuration is debugging an empty Jupyter Book at 11 PM the day before a release. The cost of the audit is 30 seconds.
