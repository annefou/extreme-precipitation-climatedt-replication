"""Tests for scripts/init_template.py — the placeholder-token substituter.

The load-bearing test in this module is
test_exclusion_holds_however_the_root_is_spelled. Initialisation's job is to
rewrite every file in the repo *except* three trees whose {{TOKEN}} strings are
test fixtures rather than placeholders, and the bash implementation this script
replaced got that wrong in a way nothing detected: it excluded by matching a
rendered path string against a `^\\./` anchor, and grep does not always emit
that prefix. The exclusion silently became a no-op.

What made it dangerous was the shape of what it broke. Substituting a fixture
whose tokens feed `assert "{{" not in v` does not fail the assertion — it makes
it vacuous. The guard against publishing a raw placeholder into a signed,
immutable nanopub stops guarding, quietly.

So these tests assert the predicate directly, over roots spelled every way a
caller might spell them.

Run: pixi run -e tests test
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import init_template as it  # noqa: E402


VALUES = {
    "REPO_NAME": "pangeo-fish-replication",
    "REPO_ORG": "annefou",
    "AUTHOR_NAME": "Anne Fouilloux",
    "RELEASE_DATE": "2026-08-08",
}

# Built by concatenation so that a stray substitution over this file cannot
# rewrite the expectations in step with the fixtures they check — the same
# trick, and the same reason, as the canary in test_build_chain_draft.py.
TOK = lambda name: "{{" + name + "}}"  # noqa: E731


def _repo(tmp_path: Path) -> Path:
    """A miniature template repo: real files, plus all three protected trees."""
    (tmp_path / it.SENTINEL).write_text("")

    (tmp_path / "README.md").write_text(f"# {TOK('REPO_NAME')} by {TOK('AUTHOR_NAME')}\n")
    (tmp_path / "CITATION.cff").write_text(
        f'title: "{TOK("REPO_NAME")}"\n'
        f'repository-code: "https://github.com/{TOK("REPO_ORG")}/{TOK("REPO_NAME")}"\n'
        f'doi: "{TOK("ZENODO_DOI")}"\n'
    )
    (tmp_path / "Dockerfile").write_text(f"LABEL org={TOK('REPO_ORG')}\n")
    (tmp_path / "notes.txt").write_text(TOK("REPO_NAME"))  # ineligible suffix

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(f"Never emit a {TOK('TOKEN')} into a nanopub.\n")

    for tree in ("tests", "scripts", ".claude"):
        d = tmp_path / tree
        d.mkdir(parents=True)
        (d / "fixture.py").write_text(
            f'url = "https://github.com/{TOK("REPO_ORG")}/{TOK("REPO_NAME")}"\n'
            f'date = "{TOK("RELEASE_DATE")}"\n'
        )

    nested = tmp_path / "src" / "tests"
    nested.mkdir(parents=True)
    (nested / "deep.py").write_text(TOK("REPO_NAME"))

    return tmp_path


# --- the regression ------------------------------------------------------

@pytest.mark.parametrize("spell", ["absolute", "relative", "dot"])
def test_exclusion_holds_however_the_root_is_spelled(tmp_path, monkeypatch, spell):
    """Protected trees stay excluded for every spelling of the root.

    The bash predecessor passed `.` and filtered on a `^\\./` prefix that grep
    did not always emit, so the exclusion matched nothing at all.
    """
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    root = {"absolute": repo, "relative": Path(repo.name), "dot": Path(".")}[spell]
    if spell == "relative":
        monkeypatch.chdir(repo.parent)

    found = {p.resolve() for p in it.iter_target_files(root)}
    assert found, "walk yielded nothing — the test would pass vacuously"
    assert not [p for p in found if any(
        part in it.PROTECTED_DIRS for part in p.relative_to(repo.resolve()).parts)]


def test_protected_trees_are_never_written(tmp_path):
    repo = _repo(tmp_path)
    before = {t: (repo / t / "fixture.py").read_text() for t in ("tests", "scripts", ".claude")}
    before["nested"] = (repo / "src" / "tests" / "deep.py").read_text()

    it.initialise(repo, VALUES)

    for tree in ("tests", "scripts", ".claude"):
        assert (repo / tree / "fixture.py").read_text() == before[tree]
        assert TOK("REPO_ORG") in (repo / tree / "fixture.py").read_text()
    assert (repo / "src" / "tests" / "deep.py").read_text() == before["nested"]


def test_is_protected_matches_components_not_substrings(tmp_path):
    """A directory merely *containing* a protected name is not protected."""
    repo = tmp_path
    decoy = repo / "testsuite" / "scriptsy"
    decoy.mkdir(parents=True)
    target = decoy / "a.md"
    target.write_text("x")
    assert not it.is_protected(target, repo)


# --- substitution --------------------------------------------------------

def test_known_tokens_replaced_unknown_left_alone(tmp_path):
    repo = _repo(tmp_path)
    it.initialise(repo, VALUES)

    readme = (repo / "README.md").read_text()
    assert readme == "# pangeo-fish-replication by Anne Fouilloux\n"

    cff = (repo / "CITATION.cff").read_text()
    assert "annefou/pangeo-fish-replication" in cff
    assert TOK("ZENODO_DOI") in cff, "deferred token must survive for release automation"


def test_ineligible_files_untouched(tmp_path):
    repo = _repo(tmp_path)
    it.initialise(repo, VALUES)
    assert (repo / "notes.txt").read_text() == TOK("REPO_NAME")


def test_initialise_is_idempotent(tmp_path):
    repo = _repo(tmp_path)
    it.initialise(repo, VALUES)
    snapshot = {p: p.read_text() for p in it.iter_target_files(repo)}
    assert it.initialise(repo, VALUES) == []
    assert {p: p.read_text() for p in it.iter_target_files(repo)} == snapshot


def test_dry_run_writes_nothing(tmp_path):
    repo = _repo(tmp_path)
    before = (repo / "README.md").read_text()
    changed = it.initialise(repo, VALUES, dry_run=True)
    assert changed and (repo / "README.md").read_text() == before


# --- audit ---------------------------------------------------------------

def test_audit_allows_deferred_and_doc_example_tokens(tmp_path):
    repo = _repo(tmp_path)
    it.initialise(repo, VALUES)
    assert it.audit(repo) == {}, "ZENODO_DOI and TOKEN are expected survivors"


def test_audit_reports_a_genuine_miss(tmp_path):
    repo = _repo(tmp_path)
    it.initialise(repo, VALUES)
    (repo / "index.md").write_text(TOK("PAPER_DOI"))

    misses = it.audit(repo)
    assert misses and {p.name for p in misses} == {"index.md"}
    assert it.audit(repo, ["PAPER_DOI"]) == {}, "--allow-deferred must silence it"


# --- CITATION.cff prior-chain entry --------------------------------------

CFF_WITH_PRIOR = f"""\
references:
  - type: article
    doi: "10.1234/x"
  # Prior FORRT chain this replication extends or qualifies. The URI below
  # is the canonical persistent pointer to the prior constellation.
  - type: generic
    title: "{TOK('PRIOR_CHAIN_DESCRIPTION')}"
    url: "{TOK('PRIOR_CHAIN_URI')}"
    notes: "Apex CiTO Citation of the prior chain."
keywords:
  - replication
"""


def test_remove_prior_chain_entry_takes_comment_block_with_it():
    out = it.remove_prior_chain_entry(CFF_WITH_PRIOR)
    assert "type: generic" not in out
    assert "Prior FORRT chain" not in out
    assert "PRIOR_CHAIN_URI" not in out
    # Neighbours on both sides survive.
    assert 'doi: "10.1234/x"' in out
    assert "keywords:" in out and "- replication" in out


def test_remove_prior_chain_entry_is_idempotent():
    once = it.remove_prior_chain_entry(CFF_WITH_PRIOR)
    assert it.remove_prior_chain_entry(once) == once


def test_remove_prior_chain_entry_absent_is_noop():
    text = 'references:\n  - type: article\n    doi: "10.1/x"\n'
    assert it.remove_prior_chain_entry(text) == text


def test_drop_prior_chain_only_touches_citation_cff(tmp_path):
    repo = _repo(tmp_path)
    (repo / "CITATION.cff").write_text(CFF_WITH_PRIOR)
    (repo / "other.md").write_text(CFF_WITH_PRIOR)

    it.initialise(repo, VALUES, drop_prior_chain=True)

    assert "type: generic" not in (repo / "CITATION.cff").read_text()
    assert "type: generic" in (repo / "other.md").read_text()


# --- git remote ----------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("git@github.com:annefou/pangeo-fish-replication.git", ("annefou", "pangeo-fish-replication")),
    ("https://github.com/annefou/pangeo-fish-replication.git", ("annefou", "pangeo-fish-replication")),
    ("https://github.com/annefou/pangeo-fish-replication", ("annefou", "pangeo-fish-replication")),
    ("ssh://git@github.com/ScienceLiveHub/forrt-replication-template.git",
     ("ScienceLiveHub", "forrt-replication-template")),
    ("  git@github.com:annefou/repo.git\n", ("annefou", "repo")),
    ("not-a-remote", None),
])
def test_parse_git_remote(url, expected):
    assert it.parse_git_remote(url) == expected


# --- CLI -----------------------------------------------------------------

def _values_file(tmp_path: Path, values: dict) -> Path:
    p = tmp_path / "values.json"
    p.write_text(json.dumps(values))
    return p


def test_cli_refuses_values_that_contain_placeholders(tmp_path, capsys):
    repo = _repo(tmp_path)
    vf = _values_file(tmp_path, {"REPO_NAME": TOK("REPO_NAME")})
    with pytest.raises(SystemExit) as e:
        it.main(["--root", str(repo), "--values", str(vf)])
    assert e.value.code != 0
    assert "must not themselves contain placeholders" in capsys.readouterr().err


def test_cli_refuses_without_sentinel(tmp_path, capsys):
    repo = _repo(tmp_path)
    (repo / it.SENTINEL).unlink()
    vf = _values_file(tmp_path, VALUES)
    assert it.main(["--root", str(repo), "--values", str(vf)]) == 1
    assert "already initialised" in capsys.readouterr().err


def test_dry_run_audits_projected_content_not_disk(tmp_path, capsys):
    """A complete dry run must report clean.

    Audited against disk it would flag every token as missed — a dry run writes
    nothing by definition — and an operator reading that would conclude the run
    had failed and go looking for a bug that is not there.
    """
    repo = _repo(tmp_path)
    vf = _values_file(tmp_path, VALUES)
    assert it.main(["--root", str(repo), "--values", str(vf), "--dry-run"]) == 0
    assert "MISS" not in capsys.readouterr().err
    assert TOK("REPO_NAME") in (repo / "README.md").read_text(), "dry run wrote to disk"


def test_dry_run_still_reports_a_genuine_miss(tmp_path, capsys):
    repo = _repo(tmp_path)
    (repo / "index.md").write_text(TOK("PAPER_DOI"))
    vf = _values_file(tmp_path, VALUES)
    assert it.main(["--root", str(repo), "--values", str(vf), "--dry-run"]) == 1
    assert "PAPER_DOI" in capsys.readouterr().err


def test_plan_writes_nothing(tmp_path):
    repo = _repo(tmp_path)
    before = {p: p.read_text() for p in it.iter_target_files(repo)}
    projected = it.plan(repo, VALUES)
    assert projected, "plan produced nothing"
    assert {p: p.read_text() for p in it.iter_target_files(repo)} == before


def test_cli_check_exits_nonzero_on_miss(tmp_path):
    repo = _repo(tmp_path)
    assert it.main(["--root", str(repo), "--check"]) == 1
    it.initialise(repo, VALUES)
    assert it.main(["--root", str(repo), "--check"]) == 0
