# USER_PREFERENCES.md — per-user style

This file holds personal preferences for the human collaborating with Claude on this repository. The defaults below are conservative; edit them on first clone. The `init-template` skill will offer to set the most important fields for you.

This file is loaded by `CLAUDE.md` and overrides nothing in `CLAUDE.md` or `DOMAIN.md`. It only adds personal-style rules.

## Identity

```yaml
name: "{{AUTHOR_NAME}}"
email: "{{AUTHOR_EMAIL}}"
orcid: "{{AUTHOR_ORCID}}"
github_username: "{{GITHUB_USERNAME}}"
affiliation: "{{AUTHOR_AFFILIATION}}"
```

For git commits, configure the local repo (run once after cloning):

```bash
git config user.name "{{AUTHOR_NAME}}"
git config user.email "{{AUTHOR_EMAIL}}"
```

**Important — three layers must agree** for GitHub to credit your commits to your profile:

1. Local repo `git config user.email` (set above).
2. Global `git config --global user.email` (so new repos default right).
3. The email must be a **verified email** on your GitHub account (`https://github.com/settings/emails`). Without verification, GitHub treats commits as anonymous and won't link them to your profile, even though `git log` shows the right author.

If commits are showing as anonymous on GitHub: add the email at the link above, click the verification email, then refresh the repo page — the contributor index updates retroactively.

## Co-authoring trailer

```yaml
add_co_authored_by_claude_trailer: false
```

When `false` (default), commit messages do not append `Co-Authored-By: Claude …`. This is the recommended default because GitHub's contributor widget treats the trailer as a real co-author and will list `claude` (github.com/claude) alongside you in the repo's Contributors panel — accurate but visually noisy for a one-human project.

When `true`, every commit appends the trailer. Use this if you want explicit AI-authorship attribution in the commit graph.

To enable: change to `true`. Claude will pick up the change next session.

## Output language

```yaml
language: en
date_format: ISO  # ISO (2026-05-09), US (05/09/2026), or EU (09/05/2026)
```

Set `language` to a 2-letter ISO code if you want Claude to write nanopub drafts, READMEs, and notebook narrative in a language other than English. Note: nanopub form fields on Science Live are language-agnostic (you can fill them in any language), but Wikidata search labels work best in English.

## Code style preferences

```yaml
prefer_type_hints: true        # add Python type hints to function signatures
prefer_docstrings: minimal     # full | minimal | none (one-line summary only)
prefer_inline_comments: minimal  # explain WHY, not WHAT — avoid restating code
max_function_length: 60        # split functions longer than this
```

## Notebook style

```yaml
plot_style: "seaborn-v0_8-whitegrid"  # matplotlib style sheet
plot_dpi: 150                          # for savefig() — Jupyter Book uses inline display
always_show_after_savefig: true        # always plt.show() after fig.savefig() — required for inline display
```

## What NOT to put here

This file is **personal style**. Don't put:

- Domain conventions (those go in `DOMAIN.md`).
- Methodology rules (those go in `CLAUDE.md` or `docs/`).
- Project state (that's in commit history and `nanopubs/PUBLISHED.md`).

If you find yourself writing a rule that another person in your field would also want, it belongs in `DOMAIN.md` instead.
