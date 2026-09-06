"""Tests for scripts/inherit_sibling_repos.py.

This script is the infrastructure-layer half of `/import-from-nanopub`: it
reads the cached `/np/constellation` response, resolves each Outcome's
`repository` to a GitHub URL, clones the siblings, and stages starter files.
The claim-layer walk that used to live alongside it was removed — the Science
Live platform's constellation endpoint is the single source of truth for that,
so keeping a divergent second copy in the template was the exact "two repos
from the same template drifted" failure the audit called out.

What remains is worth testing because it still parses external payloads
(constellation JSON, Zenodo API) and shells out to git. The reader and the
Zenodo resolver are pure enough to test directly; cloning is covered against a
local `file://` origin so no network is touched.

Run: pixi run -e tests test
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from inherit_sibling_repos import (  # noqa: E402
    read_outcome_repos,
    resolve_repo_url,
    run_inheritance,
    zenodo_doi_to_github,
)


def _write(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "constellation.json"
    p.write_text(json.dumps(doc))
    return p


# --- read_outcome_repos --------------------------------------------------

def test_reader_extracts_outcome_repositories_in_order(tmp_path):
    doc = {
        "chains": [
            {"steps": [
                {"step": "Claim", "uri": "c1"},
                {"step": "Outcome", "uri": "o1", "repository": "https://github.com/a/one"},
            ]},
            {"steps": [
                {"step": "Outcome", "uri": "o2", "repository": "https://github.com/a/two"},
            ]},
        ]
    }
    assert read_outcome_repos(_write(tmp_path, doc)) == [
        ("o1", "https://github.com/a/one"),
        ("o2", "https://github.com/a/two"),
    ]


def test_reader_ignores_non_outcome_steps_and_empty_repositories(tmp_path):
    doc = {"chains": [{"steps": [
        {"step": "Claim", "uri": "c1", "repository": "https://github.com/a/nope"},
        {"step": "Outcome", "uri": "o1"},                       # no repository
        {"step": "Outcome", "uri": "o2", "repository": "   "},  # whitespace only
    ]}]}
    assert read_outcome_repos(_write(tmp_path, doc)) == []


@pytest.mark.parametrize("doc", [
    {},                             # no chains key
    {"chains": None},               # null chains
    {"chains": [{"steps": None}]},  # null steps
    {"chains": [{}]},               # chain without steps
])
def test_reader_tolerates_missing_or_null_structure(tmp_path, doc):
    assert read_outcome_repos(_write(tmp_path, doc)) == []


def test_reader_missing_file_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        read_outcome_repos(tmp_path / "does-not-exist.json")
    assert exc.value.code == 2


def test_reader_malformed_json_exits_2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    with pytest.raises(SystemExit) as exc:
        read_outcome_repos(p)
    assert exc.value.code == 2


# --- resolve_repo_url ----------------------------------------------------

def test_resolve_passes_through_github_url_and_strips_trailing_slash():
    assert resolve_repo_url("https://github.com/owner/repo/") == "https://github.com/owner/repo"


def test_resolve_returns_none_for_unrecognised_reference():
    assert resolve_repo_url("https://example.org/not-a-repo") is None


def test_resolve_delegates_zenodo_doi(monkeypatch):
    seen = {}

    def fake(doi, *, timeout=20):
        seen["doi"] = doi
        return "https://github.com/owner/from-zenodo"

    monkeypatch.setattr("inherit_sibling_repos.zenodo_doi_to_github", fake)
    got = resolve_repo_url("https://doi.org/10.5281/zenodo.12345")
    assert got == "https://github.com/owner/from-zenodo"
    assert seen["doi"] == "https://doi.org/10.5281/zenodo.12345"


# --- zenodo_doi_to_github (network mocked) -------------------------------

def _mock_zenodo(monkeypatch, payload):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr("inherit_sibling_repos.urllib.request.urlopen",
                        lambda *a, **k: FakeResp())


def test_zenodo_prefers_is_supplement_to_relation(monkeypatch):
    _mock_zenodo(monkeypatch, {"metadata": {"related_identifiers": [
        {"relation": "isDerivedFrom", "identifier": "https://github.com/x/derived"},
        {"relation": "isSupplementTo", "identifier": "https://github.com/x/supplement/tree/v1"},
    ]}})
    # isSupplementTo wins over isDerivedFrom, and the /tree/... suffix is stripped.
    assert zenodo_doi_to_github("https://doi.org/10.5281/zenodo.9") == "https://github.com/x/supplement"


def test_zenodo_returns_none_when_no_github_identifier(monkeypatch):
    _mock_zenodo(monkeypatch, {"metadata": {"related_identifiers": [
        {"relation": "isSupplementTo", "identifier": "https://example.org/nope"},
    ]}})
    assert zenodo_doi_to_github("https://doi.org/10.5281/zenodo.9") is None


# --- run_inheritance: dedup + real clone against a file:// origin ---------

def _make_git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "pixi.toml").write_text("[workspace]\n")
    (path / "Snakefile").write_text("rule all:\n    input: []\n")
    (path / "notebooks").mkdir()
    (path / "notebooks" / "01_data_download.py").write_text("# download\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "init"], check=True)


def test_run_inheritance_dedups_and_clones_then_stages(tmp_path, monkeypatch):
    origin = tmp_path / "origin" / "sibling-alpha"
    _make_git_repo(origin)
    origin_url = origin.as_uri()  # file:// — no network

    # resolve_repo_url only recognises github.com / Zenodo, so redirect the
    # two (identical) references to our local file:// origin for the clone.
    monkeypatch.setattr("inherit_sibling_repos.resolve_repo_url",
                        lambda raw, **k: origin_url)

    siblings = tmp_path / "siblings"
    staging = tmp_path / "staging"
    outcome_repos = [
        ("o1", "https://github.com/owner/sibling-alpha"),
        ("o2", "https://github.com/owner/sibling-alpha"),  # duplicate → collapses
    ]
    results = run_inheritance(outcome_repos, siblings, staging, enable_clone=True)

    # Duplicate repository reference collapses to a single resolved entry.
    assert len(results) == 1
    r = results[0]
    assert r["clone_path"] == str(siblings / "sibling-alpha")
    assert (siblings / "sibling-alpha" / "pixi.toml").is_file()

    # Curated files were staged, each with a provenance header prepended.
    assert set(r["copied_files"]) == {"pixi.toml", "Snakefile", "notebooks/01_data_download.py"}
    staged = (staging / "pixi.toml").read_text()
    assert staged.startswith("# Inherited from prior FORRT chain sibling: sibling-alpha")
    assert "[workspace]" in staged


def test_run_inheritance_no_repos_returns_empty(tmp_path):
    assert run_inheritance([], tmp_path / "s", tmp_path / "st", enable_clone=True) == []
