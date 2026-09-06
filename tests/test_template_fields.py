"""Tests for scripts/template_fields.py — the template field extractor.

These lock the parser against the four committed fixture templates, which
between them exercise every branch: all seven placeholder kinds, both value
sources (inline `possibleValue` and pointer `possibleValuesFrom`), the
`possibleValuesFromApi` search, `OptionalStatement` / `RepeatableStatement`,
a placeholder in the *predicate* position (the CiTO citation type), and the
`hasRegex` length caps. The fixtures are real template nanopubs fetched from
the network; the URIs match nanopubs/templates/registry.json.

Offline by construction — no network — so this runs in the ordinary CI test
job. The networked half (comparing these specs against the *live* templates)
is scripts/check_template_drift.py, run on a schedule.

Run: pixi run -e tests test
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from template_fields import parse_template, spec_to_dict  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "templates"
REGISTRY = json.loads((ROOT / "nanopubs" / "templates" / "registry.json").read_text())
SNAPSHOT = json.loads((ROOT / "nanopubs" / "templates" / "fields.snapshot.json").read_text())


def _spec(step: str) -> dict:
    uri = REGISTRY["steps"][step]["current"]
    return spec_to_dict(parse_template((FIXTURES / f"{step}.trig").read_text(), uri))


def _field(spec: dict, fid: str) -> dict:
    return next(f for f in spec["fields"] if f["id"] == fid)


# --- fixture ⇄ snapshot agreement ----------------------------------------

@pytest.mark.parametrize("step", ["01_quote", "02_aida", "03_claim", "06_citation"])
def test_fixture_parse_matches_committed_snapshot(step):
    """The committed snapshot must be reproducible from the fixture by the parser.
    If this fails, either the parser changed behaviour or the snapshot was
    hand-edited — both are drift the check exists to prevent."""
    assert _spec(step) == SNAPSHOT["steps"][step]


# --- 01_quote: long literals, char caps, optionality, uri prefix ---------

def test_quote_fields_and_order():
    spec = _spec("01_quote")
    assert [f["id"] for f in spec["fields"]] == ["paper", "quotation", "quotation-end", "comment"]


def test_quote_paper_is_uri_with_doi_prefix():
    paper = _field(_spec("01_quote"), "paper")
    assert paper["kind"] == "uri" and paper["required"] is True
    assert paper["prefix"] == "https://doi.org/"


def test_quote_char_caps_come_from_regex():
    spec = _spec("01_quote")
    # The 500-vs-800 drift the audit flagged: quotation caps at 500, comment at 800.
    assert _field(spec, "quotation")["regex"] == r"[\s\S]{5,500}"
    assert _field(spec, "comment")["regex"] == r"[\s\S]{5,800}"
    assert _field(spec, "comment")["kind"] == "long_literal"


def test_quote_end_is_optional():
    assert _field(_spec("01_quote"), "quotation-end")["required"] is False


# --- 03_claim: inline restricted choice, guided choice, external uri ------

def test_claim_forrt_type_enumerates_seven_choices():
    forrt = _field(_spec("03_claim"), "forrtType")
    assert forrt["kind"] == "restricted_choice"
    assert forrt["required"] is True
    assert len(forrt["possible_values"]) == 7
    # Values are sorted by URI for a stable snapshot, and carry their labels.
    uris = [c["uri"] for c in forrt["possible_values"]]
    assert uris == sorted(uris)
    assert all(c["label"] for c in forrt["possible_values"])


def test_claim_aida_is_guided_choice_with_api():
    aida = _field(_spec("03_claim"), "aida")
    assert aida["kind"] == "guided_choice"
    assert aida["values_from_api"] and all(u.startswith("http") for u in aida["values_from_api"])


def test_claim_source_is_optional_external_uri():
    src = _field(_spec("03_claim"), "source")
    assert src["kind"] == "external_uri" and src["required"] is False


# --- 06_citation: placeholder in predicate position, values_from, repeat ---

def test_citation_relation_is_predicate_position_restricted_choice():
    spec = _spec("06_citation")
    # `cites` is the citation-type choice and lives in the STATEMENT PREDICATE,
    # not subject/object — the case that made the naive extractor miss it.
    cites = _field(spec, "cites")
    assert cites["kind"] == "restricted_choice"
    # Its allowed values come from a value-list nanopub, not inline (so the
    # snapshot carries `values_from`, not an inline `possible_values` list).
    assert cites["values_from"] and cites["values_from"][0].startswith("http")
    assert cites.get("possible_values", []) == []


def test_citation_cited_is_repeatable():
    assert _field(_spec("06_citation"), "cited")["repeatable"] is True


# --- 02_aida: auto-escape uri, repeatable guided choice -------------------

def test_aida_sentence_uri_is_auto_escape():
    assert _field(_spec("02_aida"), "aida")["kind"] == "auto_escape_uri"


def test_aida_topic_is_repeatable_guided_choice():
    topic = _field(_spec("02_aida"), "topic")
    assert topic["kind"] == "guided_choice"
    assert topic["repeatable"] is True
    assert topic["required"] is False


# --- structural checks over the whole snapshot ---------------------------

def test_snapshot_covers_every_registry_step():
    assert set(SNAPSHOT["steps"]) == set(REGISTRY["steps"])


def test_snapshot_every_step_has_fields_and_a_matching_uri():
    for step, spec in SNAPSHOT["steps"].items():
        assert spec["fields"], f"{step} has no fields"
        assert spec["template_uri"] == REGISTRY["steps"][step]["current"]


def test_bad_trig_without_assertion_template_raises():
    with pytest.raises(ValueError):
        parse_template("@prefix ex: <http://x/> . ex:g { ex:a ex:b ex:c . }", "http://x/np")


def test_aida_topic_lists_both_apis_deterministically():
    """`topic` declares two possibleValuesFromApi (nanopub-query + Wikidata).
    Both must appear, sorted — a single un-sorted pick was PYTHONHASHSEED-
    dependent and made the snapshot flap between processes."""
    topic = _field(_spec("02_aida"), "topic")
    assert len(topic["values_from_api"]) == 2
    assert topic["values_from_api"] == sorted(topic["values_from_api"])


@pytest.mark.parametrize("step", ["01_quote", "02_aida", "03_claim", "06_citation"])
def test_parse_is_deterministic(step):
    """Re-parsing the same fixture yields byte-identical JSON. Guards against
    any future use of an unsorted store-iteration order."""
    outs = {json.dumps(_spec(step), sort_keys=True) for _ in range(5)}
    assert len(outs) == 1
