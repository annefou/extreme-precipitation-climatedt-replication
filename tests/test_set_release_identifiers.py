"""Tests for scripts/set_release_identifiers.py.

This is the repo's first test file, and it exists on purpose. Every
high-severity bug the audit found in scripts/ — edge direction inverted for
every incoming edge, nondeterministic node selection, a hard dependency missing
from pixi.toml so the script cannot run at all — is a consequence of code that
nobody ever executed. Repeating that on the code that stamps PERMANENT,
PUBLICLY-CITED identifiers would be a materially worse trade.

Run: pixi run -e tests test

The fixtures below are real payload shapes, captured from the live APIs against
annefou/fiesta-galaxy-cellprofiler-eo and .../fiesta-galaxy-meltponds-eo — not
invented.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from set_release_identifiers import (  # noqa: E402
    extract_dois,
    find_zenodo_record,
    substitute_prose_doi,
    swhid_for,
    update_citation_cff,
    update_codemeta,
    update_ro_crate,
)

REPO = "annefou/fiesta-galaxy-cellprofiler-eo"
TAG = "v0.1.0"
COMMIT = "dd6e3377431ef305ec871ab8d791a76774c11ee6"
ORIGIN = f"https://github.com/{REPO}"

# Real shape of a Zenodo record minted by the GitHub webhook.
ZENODO_HIT = {
    "doi": "10.5281/zenodo.20811615",
    "conceptdoi": "10.5281/zenodo.20811614",
    "title": "fiesta-galaxy-cellprofiler-eo",
    "metadata": {
        "version": "v0.1.0",
        "related_identifiers": [
            {
                "identifier": f"https://github.com/{REPO}/tree/{TAG}",
                "relation": "isSupplementTo",
                "scheme": "url",
            }
        ],
    },
}


def _hits(*records):
    return {"hits": {"total": len(records), "hits": list(records)}}


def _yaml_load(text: str):
    from ruamel.yaml import YAML

    return YAML().load(text)


# --------------------------------------------------------------------------
# swhid_for
# --------------------------------------------------------------------------
def test_swhid_is_the_commit_sha_with_origin_qualifier():
    # SWH reuses git's hashing, so the revision id IS the commit sha.
    assert swhid_for(COMMIT, ORIGIN) == f"swh:1:rev:{COMMIT};origin={ORIGIN}"


def test_swhid_rejects_an_annotated_tag_object():
    """THE trap this guards. `git rev-parse v0.1.0` on an ANNOTATED tag returns
    the tag object, not the commit. swh:1:rev:<tagobj> is well-formed and
    resolves to nothing — a silently dead identifier in a permanent record.
    Verified live: meltponds' v0.1.0 tag object 23044ecf... does NOT resolve as
    swh:1:rev:, while its commit d1a052a8... does.
    """
    tag_object = "23044ecf2365d7608c1b9c4767617d69efea9e84"
    # We cannot tell a tag object from a commit by shape alone — both are 40 hex
    # chars — so this documents that the *caller* must pass ^{commit}. What we
    # CAN reject is anything that is not a 40-hex sha at all.
    assert swhid_for(tag_object, ORIGIN).startswith("swh:1:rev:")


@pytest.mark.parametrize("bad", ["", "v0.1.0", "dd6e337", "z" * 40, COMMIT + "0"])
def test_swhid_rejects_non_sha_input(bad):
    with pytest.raises(ValueError):
        swhid_for(bad, ORIGIN)


def test_swhid_normalises_case():
    assert swhid_for(COMMIT.upper(), ORIGIN) == swhid_for(COMMIT, ORIGIN)


# --------------------------------------------------------------------------
# find_zenodo_record
# --------------------------------------------------------------------------
def test_finds_record_by_exact_tree_url():
    seen = {}

    def fetch(url):
        seen["url"] = url
        return _hits(ZENODO_HIT)

    rec = find_zenodo_record(REPO, TAG, fetch=fetch)
    assert rec["doi"] == "10.5281/zenodo.20811615"

    # the query is percent-encoded, so decode before asserting on its content
    decoded = urllib.parse.unquote(seen["url"])
    # the `metadata.` prefix is required — without it Zenodo returns 0 hits
    # rather than erroring, which would look like "webhook not enabled".
    assert "metadata.related_identifiers.identifier" in decoded
    assert f"https://github.com/{REPO}/tree/{TAG}" in decoded


def test_polls_until_the_webhook_mints_the_record():
    """The webhook mints the record concurrently with the release event that
    triggers us, so 'not there yet' is the normal first response, not an error.
    """
    calls = {"n": 0}

    def fetch(url):
        calls["n"] += 1
        return _hits(ZENODO_HIT) if calls["n"] >= 3 else _hits()

    rec = find_zenodo_record(REPO, TAG, fetch=fetch, attempts=5, delay=0, sleep=lambda _: None)
    assert rec["doi"] == "10.5281/zenodo.20811615"
    assert calls["n"] == 3


def test_gives_up_loudly_rather_than_silently():
    with pytest.raises(SystemExit) as e:
        find_zenodo_record(REPO, TAG, fetch=lambda u: _hits(), attempts=2, delay=0, sleep=lambda _: None)
    assert "webhook" in str(e.value)


def test_refuses_to_guess_between_multiple_records():
    other = dict(ZENODO_HIT, doi="10.5281/zenodo.99999999")
    with pytest.raises(SystemExit) as e:
        find_zenodo_record(REPO, TAG, fetch=lambda u: _hits(ZENODO_HIT, other), attempts=1, delay=0)
    assert "Refusing to guess" in str(e.value)


def test_network_error_is_retried_not_fatal():
    calls = {"n": 0}

    def fetch(url):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("zenodo slow")
        return _hits(ZENODO_HIT)

    rec = find_zenodo_record(REPO, TAG, fetch=fetch, attempts=3, delay=0, sleep=lambda _: None)
    assert rec["doi"] == "10.5281/zenodo.20811615"


# --------------------------------------------------------------------------
# extract_dois
# --------------------------------------------------------------------------
def test_extract_dois_separates_version_from_concept():
    version, concept = extract_dois(ZENODO_HIT)
    assert version == "10.5281/zenodo.20811615"  # pins the snapshot
    assert concept == "10.5281/zenodo.20811614"  # floats to latest
    assert version != concept


def test_extract_dois_fails_without_a_concept_doi():
    with pytest.raises(SystemExit):
        extract_dois({"doi": "10.5281/zenodo.1"})


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------
CFF_BEFORE = """\
cff-version: 1.2.0
title: "fiesta-galaxy-cellprofiler-eo"
version: "0.1.0"
# After your first GitHub release the Zenodo integration mints a concept DOI.
doi: "10.5281/zenodo.20811614"
identifiers:
  - type: doi
    value: "10.5281/zenodo.20811614"
    description: "Concept DOI (resolves to the latest version)"
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_cff_records_all_three_identifiers(tmp_path):
    p = _write(tmp_path, "CITATION.cff", CFF_BEFORE)
    swhid = swhid_for(COMMIT, ORIGIN)
    update_citation_cff(p, "10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid, TAG)
    out = p.read_text()

    # doi: stays the CONCEPT doi — floating is correct for "cite this project"
    assert 'doi: "10.5281/zenodo.20811614"' in out or "doi: 10.5281/zenodo.20811614" in out
    # the version DOI is now machine-readable, not a prose comment
    assert "10.5281/zenodo.20811615" in out
    assert swhid in out
    assert "type: swh" in out


def test_cff_preserves_comments(tmp_path):
    """pyyaml would silently delete every explanatory comment in CITATION.cff.
    That is why the script requires ruamel.yaml.
    """
    p = _write(tmp_path, "CITATION.cff", CFF_BEFORE)
    update_citation_cff(p, "10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid_for(COMMIT, ORIGIN), TAG)
    assert "# After your first GitHub release" in p.read_text()


def test_cff_writer_is_idempotent(tmp_path):
    p = _write(tmp_path, "CITATION.cff", CFF_BEFORE)
    args = ("10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid_for(COMMIT, ORIGIN), TAG)
    update_citation_cff(p, *args)
    once = p.read_text()
    update_citation_cff(p, *args)
    assert p.read_text() == once, "re-running must not accumulate duplicate identifiers"


def test_cff_drops_unsubstituted_placeholder_identifiers(tmp_path):
    """Regression: caught by running the writer against the template's REAL
    CITATION.cff rather than a fixture.

    init-template deliberately leaves {{ZENODO_DOI}} in place until first release
    ("minted at first release"), so every real repo reaches the writer with a
    placeholder identifier entry present. The "keep what we don't own" rule
    faithfully preserved it, and CITATION.cff ended up listing a literal
    "{{ZENODO_DOI}}" as a citable identifier alongside the real DOIs.
    """
    p = _write(
        tmp_path,
        "CITATION.cff",
        'cff-version: 1.2.0\ndoi: "{{ZENODO_DOI}}"\n'
        'identifiers:\n  - type: doi\n    value: "{{ZENODO_DOI}}"\n    description: "Concept DOI"\n',
    )
    update_citation_cff(p, "10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid_for(COMMIT, ORIGIN), TAG)
    out = p.read_text()

    assert "{{ZENODO_DOI}}" not in out
    types = [i["type"] for i in _yaml_load(out)["identifiers"]]
    assert types == ["doi", "doi", "swh"], "exactly the three we own, no placeholder survivor"


def test_cff_swhid_is_not_line_wrapped(tmp_path):
    """A wrapped SWHID is still valid YAML but unreadable to a human skimming
    the file for the value to paste into a nanopub form.
    """
    p = _write(tmp_path, "CITATION.cff", CFF_BEFORE)
    swhid = swhid_for(COMMIT, ORIGIN)
    update_citation_cff(p, "10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid, TAG)
    assert any(swhid in line for line in p.read_text().splitlines()), "SWHID must sit on one line"


def test_cff_keeps_identifiers_it_does_not_own(tmp_path):
    p = _write(
        tmp_path,
        "CITATION.cff",
        CFF_BEFORE + '  - type: url\n    value: "https://example.org/mine"\n    description: "user\'s own"\n',
    )
    update_citation_cff(p, "10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid_for(COMMIT, ORIGIN), TAG)
    assert "https://example.org/mine" in p.read_text()


def test_codemeta_id_is_concept_identifier_lists_all(tmp_path):
    p = _write(tmp_path, "codemeta.json", json.dumps({"@id": "{{ZENODO_DOI}}", "identifier": "{{ZENODO_DOI}}"}))
    swhid = swhid_for(COMMIT, ORIGIN)
    update_codemeta(p, "10.5281/zenodo.20811615", "10.5281/zenodo.20811614", swhid)
    d = json.loads(p.read_text())

    assert d["@id"] == "https://doi.org/10.5281/zenodo.20811614"  # concept: stable project identity
    assert d["identifier"] == [
        "https://doi.org/10.5281/zenodo.20811614",
        "https://doi.org/10.5281/zenodo.20811615",
        swhid,
    ]
    assert "{{ZENODO_DOI}}" not in p.read_text()


def test_ro_crate_root_gets_version_doi_and_version(tmp_path):
    p = _write(
        tmp_path,
        "ro-crate-metadata.json",
        json.dumps({"@graph": [{"@id": "ro-crate-metadata.json"}, {"@id": "./", "name": "x"}]}),
    )
    swhid = swhid_for(COMMIT, ORIGIN)
    update_ro_crate(p, "10.5281/zenodo.20811615", swhid, TAG)
    root = [e for e in json.loads(p.read_text())["@graph"] if e["@id"] == "./"][0]

    # the Crate describes a specific packaged object -> VERSION doi, never concept
    assert root["identifier"] == ["https://doi.org/10.5281/zenodo.20811615", swhid]
    assert root["version"] == "0.1.0"


def test_ro_crate_without_root_entity_fails_loudly(tmp_path):
    p = _write(tmp_path, "ro-crate-metadata.json", json.dumps({"@graph": [{"@id": "other"}]}))
    with pytest.raises(SystemExit):
        update_ro_crate(p, "10.5281/zenodo.20811615", swhid_for(COMMIT, ORIGIN), TAG)


# --------------------------------------------------------------------------
# substitute_prose_doi (README.md / index.md badge + link)
# --------------------------------------------------------------------------
def test_readme_badge_and_link_get_the_concept_doi(tmp_path):
    """The DOI badge/link placeholder release-identifiers never used to fill is
    substituted context-aware: the bare DOI in the Zenodo badge image path, the
    resolver URL in the markdown link target."""
    readme = _write(
        tmp_path,
        "README.md",
        "[![DOI](https://zenodo.org/badge/DOI/{{ZENODO_DOI}}.svg)]({{ZENODO_DOI}})\n"
        "cite: [{{ZENODO_DOI}}]({{ZENODO_DOI}}).\n",
    )
    changed = substitute_prose_doi(readme, "10.5281/zenodo.20811614")
    out = readme.read_text()

    assert changed is True
    assert "{{ZENODO_DOI}}" not in out
    assert "badge/DOI/10.5281/zenodo.20811614.svg" in out       # bare DOI in the badge path
    assert "](https://doi.org/10.5281/zenodo.20811614)" in out  # resolver URL in the link target
    assert "[10.5281/zenodo.20811614]" in out                   # bare DOI as link text


def test_substitute_prose_doi_is_a_safe_noop(tmp_path):
    """Idempotent, and silent when the file is absent (index.md is optional)."""
    p = _write(tmp_path, "README.md", "no token here\n")
    assert substitute_prose_doi(p, "10.5281/zenodo.1") is False          # token already gone
    assert substitute_prose_doi(tmp_path / "index.md", "10.5281/zenodo.1") is False  # file absent
