---
name: init-template
description: Initialise a freshly-cloned forrt-replication-template repository — derive the repo name and org from the git remote, prompt the user for author identity and paper details, substitute all {{...}} placeholder tokens, and commit the result. Run this once on first clone. After successful run, this skill removes itself.
---

# /init-template

You're invoked the first time a user opens Claude in a repository that was created from `forrt-replication-template`. Your job is to convert the placeholder tokens (`{{REPO_NAME}}`, `{{AUTHOR_NAME}}`, etc.) into real values, then commit the change.

## Step 1 — Detect

Verify this is a freshly-instantiated template:

```bash
test -f .template-uninitialised && echo "UNINITIALISED"
```

The sentinel is the authoritative signal (same one CI, Docker, and the Jupyter
Book workflow use — see `CLAUDE.md` § First-run guard). If it is absent, tell the
user the repo is already initialised and exit.

To see *which* files carry tokens, use the scoped list below — but note it is a
survey, not the detection test. Some tokens are load-bearing fixtures that must
survive initialisation (Step 4).

```bash
grep -rln '{{[A-Z_]\+}}' . \
  --exclude-dir=.git --exclude-dir=.claude \
  --exclude-dir=tests --exclude-dir=scripts \
  --include='*.md' --include='*.yml' --include='*.yaml' \
  --include='*.json' --include='*.cff' --include='*.toml' \
  --include='Dockerfile' --include='LICENSE' \
  2>/dev/null | head
```

> **Exclude with `--exclude-dir`, never with a `grep -v '^\./…'` post-filter.**
> Whether `grep -rln` prefixes its output with `./` is not guaranteed — some
> builds and locales emit `tests/foo.py`, not `./tests/foo.py`. An anchored
> `^\./(tests|scripts)/` pattern then matches nothing, the exclusion silently
> becomes a no-op, and Step 4 substitutes the very fixtures Step 4 exists to
> protect. `--exclude-dir` is matched by grep against the directory name itself,
> so it cannot be defeated by a path-prefix difference.

## Step 2 — Derive what you can without asking

Run:

```bash
git remote get-url origin 2>/dev/null
```

If the result is a GitHub URL like `https://github.com/<org>/<name>.git` or `git@github.com:<org>/<name>.git`, parse `<org>` → `{{REPO_ORG}}` and `<name>` → `{{REPO_NAME}}`.

Also derive:

- `{{YEAR}}` → current year (use `date +%Y`).
- `{{RELEASE_DATE}}` → today (use `date +%Y-%m-%d`).

If `git remote` is missing, ask the user for the GitHub org/name they intend to use.

## Step 3 — Ask the user for the rest

Ask for the following (one prompt; offer them as a structured list):

| Token | What to ask |
|---|---|
| `{{AUTHOR_NAME}}` | Full name as you'd like it to appear in citations |
| `{{AUTHOR_GIVEN}}` | Given name(s) — e.g. "Anne" |
| `{{AUTHOR_FAMILY}}` | Family name — e.g. "Fouilloux" |
| `{{AUTHOR_EMAIL}}` | Email for git commits (must be GitHub-verified for commits to credit the right user) |
| `{{AUTHOR_ORCID}}` | ORCID URL — `https://orcid.org/0000-0000-0000-0000` |
| `{{AUTHOR_AFFILIATION}}` | Your institution |
| `{{GITHUB_USERNAME}}` | Your GitHub handle |
| `{{PAPER_TITLE}}` | Title of the paper being replicated |
| `{{PAPER_DOI}}` | DOI of the paper, bare form (`10.x/y`) |
| `{{PAPER_AUTHOR_GIVEN}}` | First author's given name |
| `{{PAPER_AUTHOR_FAMILY}}` | First author's family name |
| `{{PAPER_YEAR}}` | Paper publication year |
| `{{REPO_DESCRIPTION}}` | One-sentence description of this repo |
| `{{PRIOR_CHAIN_URI}}` | *(Optional)* Apex CiTO URI of a prior FORRT chain this replication extends — e.g. `https://w3id.org/sciencelive/np/RA1q6c0fG2bMbiozF8Az2UpIfzAzqp8hoVEl6QIzfUpH8`. Leave blank if this is a fresh replication with no prior chain on the Science Live / nanopub network. |
| `{{PRIOR_CHAIN_DESCRIPTION}}` | *(Optional, only if URI above is filled)* One-line description of the prior chain — e.g. `"Iberian Bombus FORRT constellation — Synthesis-level CiTO"`. |

For tokens that don't apply yet (e.g. `{{ZENODO_DOI}}` — minted at first release), leave them as-is and tell the user they'll be filled in later.

**Handling the optional prior-chain URI**: if the user provides `{{PRIOR_CHAIN_URI}}`, substitute both that and `{{PRIOR_CHAIN_DESCRIPTION}}` normally. If the user leaves it blank, **delete the entire `- type: generic` references entry block** from `CITATION.cff` (the block spanning the introductory comment lines through the `notes:` line). Otherwise the unsubstituted `{{...}}` tokens will fail the first-run guard in `CLAUDE.md`.

## Step 4 — Substitute

Substitution runs across the repo — but **not across all of it**. Three trees are
excluded, and the third is not optional. The exclusion is enforced by
`is_protected()` in `scripts/init_template.py` and tested; the rationale below is
why it exists, not a spec you re-implement by hand:

- `.git/` — obviously.
- `.claude/` — this SKILL.md documents the token system, and
  `skills/replication-study/SKILL.md` names `{{PRIOR_CHAIN_URI}}` as a concept.
- **`tests/` and `scripts/`** — these carry `{{TOKEN}}` strings as *literal
  fixtures* for the placeholder-detection logic in `scripts/build_chain_draft.py`
  (`_clean()` returns `None` for any value containing `{{`). Substituting them
  does not merely dirty the files, it destroys the tests that defend the
  guarantee:

  | File / line | Token | Effect of substituting it |
  |---|---|---|
  | `tests/test_build_chain_draft.py:341-342` | `{{REPO_ORG}}`, `{{REPO_NAME}}`, `{{RELEASE_DATE}}` | These are the *input* to `test_load_citation_ignores_placeholder_tokens`, which asserts they are rejected as `None`. Real values → the test fails loudly, in the user's fresh repo, looking like the template is broken. |
  | `tests/test_build_chain_draft.py:85,89` | `{{ZENODO_VERSION_DOI}}`, `{{RELEASE_DATE}}` | These are the draft fixture for `test_placeholder_tokens_in_draft_fences_are_never_emitted`. Substituted, the fixture holds no tokens, so its `assert "{{" not in v` **passes vacuously** — the regression guard against emitting a raw placeholder into a signed nanopub silently stops guarding. |
  | `tests/test_set_release_identifiers.py`, `scripts/*.py` | `{{ZENODO_DOI}}`, `{{TOKEN}}` | Prose and fixtures about the placeholder contract; substituting is meaningless at best. |

  The second row is the dangerous one: it is a *silent* coverage loss, in every
  repo built from this template. It is the same failure mode `CLAUDE.md` warns
  about for the first-run guard ("grepping for `{{...}}` … is exactly what used
  to cause false-positive skips and silent-green CI"), one directory over.

**Do not hand-roll this as a shell loop.** `scripts/init_template.py` does it,
and the exclusion above is a tested function there rather than a regex you have
to get right in the moment. Write the answers from Step 3 to a JSON file and run
it:

```bash
cat > /tmp/init-values.json <<'JSON'
{
  "REPO_NAME": "<actual repo name>",
  "REPO_ORG": "<actual org>",
  "AUTHOR_NAME": "<full name>",
  "AUTHOR_GIVEN": "<given>",
  "AUTHOR_FAMILY": "<family>",
  "AUTHOR_EMAIL": "<email>",
  "AUTHOR_ORCID": "https://orcid.org/0000-0000-0000-0000",
  "AUTHOR_AFFILIATION": "<institution>",
  "GITHUB_USERNAME": "<handle>",
  "PAPER_TITLE": "<title>",
  "PAPER_DOI": "10.x/y",
  "PAPER_AUTHOR_GIVEN": "<given>",
  "PAPER_AUTHOR_FAMILY": "<family>",
  "PAPER_YEAR": "<year>",
  "REPO_DESCRIPTION": "<one sentence>",
  "YEAR": "<current year>",
  "RELEASE_DATE": "<today, ISO>"
}
JSON

# Add --drop-prior-chain when the user left {{PRIOR_CHAIN_URI}} blank; it removes
# the `- type: generic` entry and its comment block from CITATION.cff.
# Add --allow-deferred TOKEN for any value that does not exist yet — e.g.
# --allow-deferred PAPER_DOI when the paper is unsubmitted.
pixi run -e tests python scripts/init_template.py --values /tmp/init-values.json

# Preview first if you want: --dry-run lists what would change and writes nothing.
```

The script refuses to run without the `.template-uninitialised` sentinel, rejects
a values file whose values themselves contain `{{`, never writes a protected
tree, and finishes by auditing for genuine misses — reporting them and exiting
nonzero. Re-running it with the same values is a no-op.

Everything it enforces is covered by `tests/test_init_template.py`, including
the exclusion holding for an absolute root, a relative root and `.` alike —
which is exactly what the bash predecessor got wrong.

## Step 5 — Configure git identity

If the user provided `{{AUTHOR_NAME}}` and `{{AUTHOR_EMAIL}}`, configure the local repo:

```bash
git config user.name "<author name>"
git config user.email "<author email>"
```

Tell the user that for GitHub to credit their commits, the email must also be verified at <https://github.com/settings/emails>.

## Step 6 — Set Co-Authored-By preference

Read `USER_PREFERENCES.md` `add_co_authored_by_claude_trailer` value. If `true`, future commits should append the trailer. If `false` (default), do not. Do not edit `USER_PREFERENCES.md` here — the user can change it later if they want.

## Step 7 — Verify

Confirm nothing unexpected survives. Four classes of token are *expected* to
remain and must not be reported as failures:

- **Release-minted** — `{{ZENODO_DOI}}`, `{{ZENODO_VERSION_DOI}}`, `{{SWHID}}`.
  Recorded automatically by `.github/workflows/release-identifiers.yml`.
- **Doc examples** — `{{TOKEN}}`, `{{PLACEHOLDER}}`, literal illustrations of the
  token system in `docs/` prose.
- **Fixtures** — everything under `tests/`, `scripts/` and `.claude/` (Step 4).
- **Explicitly allowed** — anything you passed to `--allow-deferred`, for a value
  that does not exist yet. Leaving such a token in place is safe: `_clean()` in
  `build_chain_draft.py` rejects any value containing `{{`, so it cannot reach a
  signed nanopub.

Step 4's script already audits on exit, so this is a re-check rather than the
first look. Pass the same `--allow-deferred` flags you passed in Step 4:

```bash
pixi run -e tests python scripts/init_template.py --check
# ...or, when a value legitimately does not exist yet:
pixi run -e tests python scripts/init_template.py --check --allow-deferred PAPER_DOI
```

It prints `MISS <file>: <tokens>` per genuine miss and exits nonzero. Anything it
reports is a real miss — report it and ask the user. Exit 0 means the only
survivors are the deferred, doc-example and explicitly-allowed tokens.

Then run the test suite. It must be green *after* substitution, not just before:

```bash
pixi run -e tests test
```

## Step 8 — Commit

```bash
git add -A
git commit -m "Initialise from forrt-replication-template

Substituted placeholder tokens with author and paper details.
"
```

(Honour the `add_co_authored_by_claude_trailer` setting from Step 6.)

## Step 9 — Import the prior FORRT chain (if URI was provided)

If the user provided a value for `{{PRIOR_CHAIN_URI}}` at Step 3 (i.e. this replication extends a prior chain on the Science Live / nanopub network), now chain into the `/import-from-nanopub` skill's work so the resulting repo is fully set up — claim layer summarised, infrastructure-layer sibling repos cloned, starter files staged — by the time `/init-template` finishes.

If the user left `{{PRIOR_CHAIN_URI}}` blank, skip this step entirely (you should have already deleted the `type: generic` references entry from `CITATION.cff` in Step 3 / Step 4).

Otherwise:

### Step 9a — Confirm the API key is set

The import path relies on Science Live's `/np/constellation` endpoint, which requires authentication.

```bash
test -n "$SCIENCELIVE_API_KEY" || {
  echo "Set SCIENCELIVE_API_KEY before continuing. Get a key at"
  echo "platform.sciencelive4all.org → Settings → API Keys."
  exit 1
}
```

If unset, pause `/init-template` and tell the user to set it (`export SCIENCELIVE_API_KEY=sl_…` in their shell) before re-running. Don't try to import the prior chain without it — the resulting `nanopubs/imported/` will be empty and the user will think the URI was wrong.

### Step 9b — Chain into `/import-from-nanopub`

Invoke the `/import-from-nanopub` skill with the value the user set for `{{PRIOR_CHAIN_URI}}`:

```
/import-from-nanopub <PRIOR_CHAIN_URI>
```

That skill calls `/np/constellation` once, caches the structured response to `nanopubs/imported/constellation.json`, writes `nanopubs/imported/CHAIN_SUMMARY.md` from the inline prose fields, and (if any Outcome `repository` URLs resolve) clones sibling repos into `../` and stages starter files into `_template_from_prior/` with provenance headers. See `.claude/skills/import-from-nanopub/SKILL.md` for the full procedure.

The constellation JSON contains all the substantive content inline — there's no separate per-URI TriG fetching step. Only the optional archival TriG fetch (also documented in `import-from-nanopub`) needs network bandwidth beyond the single API call.

### Step 9c — Don't commit the imports

`nanopubs/imported/` and `_template_from_prior/` are both gitignored (see `.gitignore`). The persistent contract to the prior chain is the URI in `CITATION.cff` `references:` (already substituted in Step 4); the local cache + staging area are derived artefacts that re-run whenever `/import-from-nanopub` is invoked.

Do NOT `git add` any of those paths in Step 10. If you accidentally do, `git status` will show them as new files because `.gitignore` excludes the *unrelated* path; `git add` is permissive about gitignored paths if you list them explicitly. Just don't.

## Step 10 — Self-removal and activation

This skill should not exist in the resulting repo. Remove the entire `.claude/skills/init-template/` directory, **and delete the `.template-uninitialised` sentinel** — that sentinel is what makes CI, Docker, and the Jupyter Book workflow skip their pipelines (and what makes the `CLAUDE.md` first-run guard fire). Deleting it activates them:

```bash
rm -rf .claude/skills/init-template
rm -f .template-uninitialised
```

Stage and commit both deletions as a separate commit:

```bash
git add -A
git commit -m "Remove init-template skill and activation sentinel (one-shot)"
```

> **Why the sentinel matters:** once it's gone, the workflows run for real on the
> next push. If the notebooks are still scaffolds they'll skip with a `::notice::`
> (expected) — but once you've also published a nanopub chain, a skip becomes a
> hard CI failure on purpose (`.github/actions/check-ready`), so a finished
> replication can never sit on silently-green-but-empty CI.

## Step 11 — Report

Tell the user, in this order, with the push reminder loud and unmissable:

1. **What was substituted and where** (which files were modified).
2. **🚨 Push the commits.** Both the substitution commit and the skill-removal commit live **locally only** — pushing is a separate manual step. Until they push, GitHub Actions, Docker pulls, and fresh clones will see the un-substituted template state, which looks identical to "the template didn't work". Concrete command:

   ```bash
   git push
   ```

   This is the single most common confusion after `/init-template`. State it explicitly even if it feels redundant.
3. **If a prior chain was imported in Step 9** — surface this prominently:

   > *"The prior chain `<URI>` has been imported. Claim-layer summary at `nanopubs/imported/CHAIN_SUMMARY.md` (read this alongside the paper PDF when you start Phase 1 paper analysis). Infrastructure-layer inheritance has cloned `<N>` sibling repos and staged starter files at `_template_from_prior/` — review each staged file, merge into your own repo's corresponding location, then delete the staging directory."*

4. **The next phase**: read `paper/` (drop the PDF in there if not already), then run `/agent paper-analyst` to start Phase 1.
5. **The pending placeholder `{{ZENODO_DOI}}`** — filled in after the first GitHub release.
6. **GitHub email verification reminder** at <https://github.com/settings/emails> if the user hasn't already verified the email used for git commits.

## Failure modes

- **No git remote** — ask the user; offer to skip GitHub-derived fields and let them fill in manually.
- **No paper PDF in `paper/`** — non-blocking; tell the user to drop the PDF in before running `/agent paper-analyst`.
- **Token in a file outside the substitution scope** — report and let the user decide. Do *not* "fix" it by widening the scope to `tests/` or `scripts/`: those tokens are fixtures, and rewriting them silently disables the placeholder-detection tests (Step 4).
- **`pixi run -e tests test` red after substitution** — a test whose premise was "this repo is an uninitialised template" has been invalidated by your own work. Retarget the test at the invariant it actually meant to defend; do not leave the user's fresh repo with red CI.
