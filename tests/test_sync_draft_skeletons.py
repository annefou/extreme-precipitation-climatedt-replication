"""Tests for scripts/sync_draft_skeletons.py — the draft-skeleton generator.

The skeletons restate the templates' field list, and that restatement is the one
part of a draft that can disagree with the schema. It did, silently, and a filled
01_quote.md then yielded no quotation at all. This generator regenerates the
headings from the templates so they cannot disagree; these tests pin the two
properties that make it safe to run: it never loses what a human wrote, and it
reaches a fixed point.

Run: pixi run -e tests test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_chain_draft as bcd  # noqa: E402
import sync_draft_skeletons as sync  # noqa: E402

TEMPLATES = ROOT / "nanopubs" / "templates"
DRAFTS = ROOT / "nanopubs" / "drafts"
SNAPSHOT = json.loads((TEMPLATES / "fields.snapshot.json").read_text())


def test_shipped_skeletons_are_in_sync_with_the_templates():
    """`pixi run sync-drafts` must be a no-op on a committed tree — otherwise the
    skeletons and the schema have diverged again."""
    drifted = []
    for step_id, body in SNAPSHOT["steps"].items():
        path = DRAFTS / f"{step_id}.md"
        if not path.exists():
            continue
        current = path.read_text()
        new, _orphans, _added = sync.render(step_id, body, current)
        if new != current:
            drifted.append(step_id)
    assert not drifted, (
        f"these skeletons are out of date with the templates: {drifted}. "
        "Run `pixi run sync-drafts`."
    )


def test_regeneration_is_idempotent():
    """A second pass must change nothing — a generator that grows the file every
    run (trailing blank lines, duplicated sections) can never be wired into CI."""
    for step_id, body in SNAPSHOT["steps"].items():
        path = DRAFTS / f"{step_id}.md"
        if not path.exists():
            continue
        once, _, _ = sync.render(step_id, body, path.read_text())
        twice, _, _ = sync.render(step_id, body, once)
        assert twice == once, f"{step_id} is not a fixed point"


def test_guidance_and_drafted_values_survive_regeneration():
    """The prose and any value already drafted must come through untouched — this
    is the property that makes running the generator safe on a real replication."""
    body = SNAPSHOT["steps"]["03_claim"]
    drafted = (
        "# 03 — FORRT Claim\n\n## Field-by-field draft\n\n"
        "<!-- field: label -->\n"
        "### Label of the claim, to find it later (text input, required)\n\n"
        "KEEP THIS GUIDANCE — it explains how to choose a label.\n\n"
        "```\nThermal exposure predicts extirpation\n```\n"
    )
    out, _, _ = sync.render("03_claim", body, drafted)
    assert "KEEP THIS GUIDANCE" in out
    assert "Thermal exposure predicts extirpation" in out


def test_ticked_restricted_choice_survives_regeneration():
    """A drafter's `[x]` selection is a human choice that build_chain_draft reads
    to pre-fill the wizard; render must carry it over, not reset the list to
    blank. Regression for the bug where every option came back unticked."""
    body = SNAPSHOT["steps"]["03_claim"]
    drafted = (
        "# 03 — FORRT Claim\n\n## Field-by-field draft\n\n"
        "<!-- field: forrtType -->\n"
        "### Type of FORRT claim (dropdown, required)\n\n"
        "- [x] model performance (accuracy, F1 score, evaluation metrics)\n"
    )
    out, _, _ = sync.render("03_claim", body, drafted)
    assert "- [x] model performance (accuracy, F1 score, evaluation metrics)" in out
    assert out.count("- [x] ") == 1          # exactly the chosen option, nothing else
    twice, _, _ = sync.render("03_claim", body, out)
    assert twice == out                      # ...and it stays a fixed point


def test_a_section_it_cannot_place_is_kept_not_dropped():
    """Losing a researcher's writing to a parsing miss would be worse than the
    drift this fixes, so an unrecognised section is preserved and reported."""
    body = SNAPSHOT["steps"]["03_claim"]
    drafted = (
        "# 03\n\n## Field-by-field draft\n\n"
        "### Some heading that is not a template field (note)\n\n"
        "IRREPLACEABLE PROSE\n"
    )
    out, orphans, _ = sync.render("03_claim", body, drafted)
    assert "IRREPLACEABLE PROSE" in out
    assert any("not a template field" in o for o in orphans)


def test_generated_headings_are_what_build_chain_draft_looks_for():
    """The point of the generator: every heading it writes is one the extractor
    finds. Ties the two scripts together so they cannot drift apart again."""
    for step_id, body in SNAPSHOT["steps"].items():
        for field in body.get("fields", []):
            if (step_id, field["id"]) in sync.GROUPED_FIELDS:
                continue
            heading = sync.heading_for(step_id, field).lstrip("# ")
            key = bcd._norm(sync.draft_label(step_id, field))
            got = bcd._norm(heading)
            assert got and (got in key or key in got), (
                f"{step_id}.{field['id']}: generated heading {heading!r} "
                f"does not match {key!r}"
            )
