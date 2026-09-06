#!/usr/bin/env python3
"""Substitute this template's {{PLACEHOLDER}} tokens with a repo's real values.

Run once, by /init-template, on a freshly-instantiated template. Given a JSON
file of token -> value, this rewrites every eligible file in the repo, leaves
the deferred tokens alone, and refuses to touch the three trees whose {{TOKEN}}
strings are load-bearing fixtures rather than placeholders.

WHY THIS EXISTS
---------------
Initialisation used to be a bash loop pasted into .claude/skills/init-template/
SKILL.md. It excluded tests/, scripts/ and .claude/ with a post-filter:

    grep -rln '{{[A-Z_]\\+}}' . | grep -vE '^\\./(\\.git|\\.claude|tests|scripts)/'

That assumes `grep -rln` prefixes its output with `./`. It does not always. On
a build that emits `tests/foo.py`, the anchored pattern matches nothing, the
exclusion silently becomes a no-op, and sed rewrites the very fixtures the
exclusion existed to protect.

The damage is not "two tests go red" — that is merely how it was caught. The
fixture in test_placeholder_tokens_in_draft_fences_are_never_emitted feeds an
assertion of the form `assert "{{" not in v`. Substitute the fixture and that
assertion passes *vacuously*: the guard against emitting a raw placeholder into
a signed, immutable nanopub stops guarding, and nothing fails. Silent-green CI
is the exact failure mode CLAUDE.md warns about for the first-run guard.

Hardening the bash (PR #28) removes that instance. It does not remove the
class. Prose shell in a skill file cannot be unit-tested, so the next silent
no-op — a quoting slip, a glob that does not match, a `set -e` that is not
there — survives just as long. Every other mechanical step in this template is
a tested Python script; initialisation is the one that runs first and mutates
every file in the repo, and it was the one with no tests at all.

So the exclusion is now a pure function with a test that a path-prefix
difference cannot defeat, and "which tokens may survive" is asserted rather
than described in a table.

WHAT IS PROTECTED, AND WHY
--------------------------
  tests/    Placeholder tokens here are *inputs* to tests that assert they are
            rejected. Substituting them destroys the test, sometimes loudly
            (a failing assert) and sometimes silently (a vacuous one).
  scripts/  Prose and fixtures about the placeholder contract, including this
            file. A script that rewrites itself mid-run is its own bug report.
  .claude/  Documents the token system; the tokens are the subject matter.

WHICH TOKENS MAY SURVIVE
------------------------
  deferred      ZENODO_DOI, ZENODO_VERSION_DOI, SWHID — minted at release and
                recorded by .github/workflows/release-identifiers.yml.
  doc examples  TOKEN, PLACEHOLDER — literal illustrations in docs/ prose.
  opt-in        anything passed via --allow-deferred, for a value that does not
                exist yet (e.g. PAPER_DOI when the paper is unsubmitted).

Everything else surviving a run is a genuine miss and `--check` exits nonzero.
Leaving a token in place is safe by construction: build_chain_draft.py's
_clean() rejects any value containing "{{", so a deferred token cannot reach a
signed nanopub.

Idempotent: re-running with the same values rewrites the same bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator

# Directory names that are skipped wherever they appear in the tree. Matched
# against path *components*, never against a rendered path string — that is the
# whole point of this module.
PROTECTED_DIRS = frozenset({".git", ".claude", "tests", "scripts"})

INCLUDE_SUFFIXES = frozenset({".md", ".yml", ".yaml", ".json", ".cff", ".toml", ".py"})
INCLUDE_NAMES = frozenset({"Dockerfile", "LICENSE"})

# Recorded automatically on release by release-identifiers.yml.
DEFERRED_TOKENS = frozenset({"ZENODO_DOI", "ZENODO_VERSION_DOI", "SWHID"})

# Literal illustrations of the token system in docs/ prose, not placeholders.
DOC_EXAMPLE_TOKENS = frozenset({"TOKEN", "PLACEHOLDER"})

TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

SENTINEL = ".template-uninitialised"


# --- selection -----------------------------------------------------------

def is_protected(path: Path, root: Path) -> bool:
    """True if `path` lies under a protected directory.

    Operates on path components of the *relative* path, so it behaves
    identically whether the caller passed an absolute root, a relative one, or
    ".". The bash predecessor compared a rendered string against a `^\\./`
    anchor and silently matched nothing when grep omitted the prefix.
    """
    rel = path.resolve().relative_to(root.resolve())
    return any(part in PROTECTED_DIRS for part in rel.parts)


def is_eligible_name(path: Path) -> bool:
    return path.suffix in INCLUDE_SUFFIXES or path.name in INCLUDE_NAMES


def iter_target_files(root: Path) -> Iterator[Path]:
    """Yield every file eligible for substitution, in stable order."""
    root = Path(root)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if is_protected(path, root) or not is_eligible_name(path):
            continue
        yield path


# --- substitution --------------------------------------------------------

def find_tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text))


def substitute_text(text: str, values: dict[str, str]) -> str:
    """Replace {{NAME}} with values[NAME]; leave unknown tokens untouched."""
    return TOKEN_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def allowed_surviving(extra: Iterable[str] = ()) -> frozenset[str]:
    return DEFERRED_TOKENS | DOC_EXAMPLE_TOKENS | frozenset(extra)


def audit(
    root: Path,
    extra_allowed: Iterable[str] = (),
    projected: dict[Path, str] | None = None,
) -> dict[Path, set[str]]:
    """Map file -> genuinely-missed tokens. Empty dict means clean.

    `projected` supplies in-memory content to audit instead of what is on disk.
    That is what makes --dry-run truthful: audited against disk, a dry run would
    report every token as a miss, since by definition it wrote nothing. An
    operator reading that would conclude the run had failed.
    """
    allowed = allowed_surviving(extra_allowed)
    projected = projected or {}
    misses: dict[Path, set[str]] = {}
    for path in iter_target_files(root):
        text = projected.get(path, projected.get(path.resolve()))
        found = find_tokens(_read(path) if text is None else text) - allowed
        if found:
            misses[path] = found
    return misses


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="surrogateescape")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", errors="surrogateescape")


# --- CITATION.cff prior-chain entry --------------------------------------

_PRIOR_COMMENT = re.compile(r"^\s*#\s*Prior FORRT chain\b")
_PRIOR_ENTRY = re.compile(r"^\s*-\s*type:\s*generic\b")


def remove_prior_chain_entry(text: str) -> str:
    """Drop the `- type: generic` prior-chain reference and its comment block.

    Done as a text edit, not a ruamel round-trip: the explanatory comment lines
    are part of the block being removed, and a YAML load/dump would have to
    reattach them to a neighbour to keep them. Returns the input unchanged when
    the block is absent, so a second run is a no-op.
    """
    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if _PRIOR_COMMENT.match(ln)), None)
    entry = next((i for i, ln in enumerate(lines) if _PRIOR_ENTRY.match(ln)), None)
    if entry is None:
        return text
    if start is None or start > entry:
        start = entry

    end = entry + 1
    while end < len(lines) and re.match(r"^\s{4,}\S", lines[end]):
        end += 1
    return "".join(lines[:start] + lines[end:])


# --- git remote ----------------------------------------------------------

_REMOTE_RE = re.compile(
    r"^(?:git@[^:]+:|(?:https?|ssh)://(?:[^@/]+@)?[^/]+/)(?P<org>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$"
)


def parse_git_remote(url: str) -> tuple[str, str] | None:
    """('org', 'repo') from an SSH or HTTPS GitHub remote, else None."""
    m = _REMOTE_RE.match(url.strip())
    return (m.group("org"), m.group("name")) if m else None


# --- driver --------------------------------------------------------------

def plan(
    root: Path,
    values: dict[str, str],
    *,
    drop_prior_chain: bool = False,
) -> dict[Path, str]:
    """Map every target file to its post-substitution content. Writes nothing."""
    root = Path(root)
    projected: dict[Path, str] = {}
    for path in iter_target_files(root):
        updated = substitute_text(_read(path), values)
        if drop_prior_chain and path.name == "CITATION.cff":
            updated = remove_prior_chain_entry(updated)
        projected[path] = updated
    return projected


def initialise(
    root: Path,
    values: dict[str, str],
    *,
    drop_prior_chain: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Substitute across the repo. Returns the files whose bytes changed."""
    root = Path(root)
    projected = plan(root, values, drop_prior_chain=drop_prior_chain)

    changed = [p for p, text in projected.items() if text != _read(p)]

    # Belt and braces. iter_target_files already excludes these, but this is
    # the invariant that actually matters, so state it where a future edit to
    # the walk cannot quietly drop it.
    if leaked := [p for p in changed if is_protected(p, root)]:
        raise RuntimeError(f"protected tree written: {leaked}")

    if not dry_run:
        for path in changed:
            _write(path, projected[path])

    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--values", type=Path, help="JSON file of {TOKEN: value}")
    ap.add_argument("--allow-deferred", action="append", default=[],
                    metavar="TOKEN", help="token permitted to survive (repeatable)")
    ap.add_argument("--drop-prior-chain", action="store_true",
                    help="remove the prior-chain entry from CITATION.cff")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="audit only; exit 1 if any genuine token survives")
    ap.add_argument("--force", action="store_true",
                    help="run even without the .template-uninitialised sentinel")
    args = ap.parse_args(argv)

    root: Path = args.root

    if args.check:
        misses = audit(root, args.allow_deferred)
        for path, tokens in sorted(misses.items()):
            print(f"MISS {path}: {', '.join(sorted(tokens))}", file=sys.stderr)
        print("clean" if not misses else f"{len(misses)} file(s) with missed tokens")
        return 1 if misses else 0

    if not (root / SENTINEL).exists() and not args.force:
        print(f"{SENTINEL} absent — already initialised. Use --force to override.",
              file=sys.stderr)
        return 1

    if not args.values:
        ap.error("--values is required unless --check")
    values = json.loads(args.values.read_text(encoding="utf-8"))

    if bad := sorted(k for k in values if not TOKEN_RE.fullmatch("{{" + k + "}}")):
        ap.error(f"token names must be A-Z and underscores: {bad}")
    if leftover := sorted(k for k, v in values.items() if "{{" in str(v)):
        ap.error(f"values must not themselves contain placeholders: {leftover}")

    changed = initialise(root, values,
                         drop_prior_chain=args.drop_prior_chain,
                         dry_run=args.dry_run)

    verb = "would change" if args.dry_run else "changed"
    print(f"{verb} {len(changed)} file(s)")
    for path in changed:
        print(f"  {path}")

    # On a dry run nothing was written, so audit the projected content — auditing
    # disk would report every token as a miss and read as a failed run.
    projected = plan(root, values, drop_prior_chain=args.drop_prior_chain) if args.dry_run else None
    misses = audit(root, args.allow_deferred, projected=projected)
    if misses:
        print("\nGenuine misses — report these, do not ignore:", file=sys.stderr)
        for path, tokens in sorted(misses.items()):
            print(f"  MISS {path}: {', '.join(sorted(tokens))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
