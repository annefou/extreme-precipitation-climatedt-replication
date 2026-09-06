"""Tests for scripts/build_story.py — the reader-facing story-page generator.

The generator is deterministic: it turns a published FORRT chain (or research
synthesis) into a self-contained HTML article, every value read from the signed
nanopublications. A live build needs the network and SCIENCELIVE_API_KEY, so
these tests exercise only the offline, pure parts: the prose/label helpers, the
CSS asset loader, and the PUBLISHED.md apex selection. They also guard the one
thing that would break `pixi run -e tests test` — importing the module must not
require the API key.

Run: pixi run -e tests test
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_story as bs  # noqa: E402


def test_module_imports_without_api_key(monkeypatch):
    """Importing the module (done above) must not need the key — otherwise the
    whole test env fails to collect. The key is only read when a build runs."""
    monkeypatch.delenv("SCIENCELIVE_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        bs._api_key()


def test_first_sentence_guards_abbreviations():
    text = ("Sent et al. (2021) reported that Sentinel-2 retrieves parameters with "
            "parameter-dependent accuracy. A second sentence follows.")
    # must not split at "et al." — the first real sentence ends at the first period
    assert bs.first_sentence(text) == (
        "Sent et al. (2021) reported that Sentinel-2 retrieves parameters with "
        "parameter-dependent accuracy.")


def test_first_sentence_collapses_whitespace():
    # newlines (hard-wrapped nanopub prose) collapse to single spaces; the
    # first real sentence (>= the 40-char floor) is returned, not the whole text
    assert bs.first_sentence("A finding that wraps\n   onto the next line here. Second one.") == \
        "A finding that wraps onto the next line here."


def test_first_list_item_numbered_and_bulleted():
    numbered = "1. Do not treat it as one thing.\n2. Validate per parameter."
    assert bs.first_list_item(numbered) == "Do not treat it as one thing."
    bulleted = "- first point\n- second point"
    assert bs.first_list_item(bulleted) == "first point"
    # no list -> falls back to the first sentence
    assert bs.first_list_item("Just prose here, no list at all.") == \
        "Just prose here, no list at all."


def test_prose_blocks_bullets_with_intro_and_continuations():
    text = ("This synthesis holds within the following scope:\n\n"
            "- Domain: a turbid estuary\n  (the Westerschelde).\n"
            "- Processing chain: fully open-source Acolite.")
    html = bs.prose_blocks(text)
    assert "<p>This synthesis holds within the following scope:</p>" in html
    assert html.count("<li>") == 2
    # the indented continuation line joins its item, not a new one
    assert "a turbid estuary (the Westerschelde)." in html
    assert "<ul" in html


def test_prose_blocks_numbered_becomes_ol():
    text = "1. First recommendation here.\n2. Second recommendation here."
    html = bs.prose_blocks(text)
    assert "<ol" in html and html.count("<li>") == 2


def test_prose_blocks_plain_paragraphs():
    html = bs.prose_blocks("Para one.\n\nPara two.")
    assert html.count("<p>") == 2 and "<ul" not in html and "<ol" not in html


def test_raw_to_blob():
    raw = "https://raw.githubusercontent.com/annefou/sado-estuary/main/figures/study_area.png"
    assert bs.raw_to_blob(raw) == \
        "https://github.com/annefou/sado-estuary/blob/main/figures/study_area.png"
    # anything that is not a raw URL is returned unchanged
    other = "https://doi.org/10.3390/rs13051043"
    assert bs.raw_to_blob(other) == other


def test_verdict_class_mapping():
    assert bs.VERDICT_CLASS["validated"] == "ok"
    assert bs.VERDICT_CLASS["partiallysupported"] == "warn"
    assert bs.VERDICT_CLASS["contradicted"] == "bad"


def test_load_style_reads_committed_asset():
    style = bs.load_style()
    assert style.startswith("<style>") and style.rstrip().endswith("</style>")
    # the Science Live palette must be present (self-contained, matches the platform)
    assert "--brand:#be2e78" in style          # Science Live magenta
    assert "@font-face" in style               # display font embedded


def test_apex_from_published_prefers_synthesis(tmp_path):
    """The apex is the Research Synthesis (08) when published, else the Outcome (05)."""
    nano = tmp_path / "nanopubs"
    nano.mkdir()
    syn = "https://w3id.org/sciencelive/np/RA" + "S" * 30
    out = "https://w3id.org/sciencelive/np/RA" + "O" * 30
    table = (
        "| Step | Template | URI | Published |\n|---|---|---|---|\n"
        f"| 05 | Outcome | {out} | 2026 |\n"
        f"| 08 | Research Synthesis | {syn} | 2026 |\n")
    (nano / "PUBLISHED.md").write_text(table)
    assert bs.apex_from_published(tmp_path) == syn


def test_apex_from_published_falls_back_to_outcome(tmp_path):
    nano = tmp_path / "nanopubs"
    nano.mkdir()
    out = "https://w3id.org/sciencelive/np/RA" + "O" * 30
    table = (
        "| Step | Template | URI | Published |\n|---|---|---|---|\n"
        f"| 05 | Outcome | {out} | 2026 |\n"
        "| 08 | Research Synthesis | _not yet published_ | |\n")
    (nano / "PUBLISHED.md").write_text(table)
    assert bs.apex_from_published(tmp_path) == out


def test_apex_from_published_none_when_missing(tmp_path):
    assert bs.apex_from_published(tmp_path) is None


def test_load_audiences_attaches_shared_glance(tmp_path):
    p = tmp_path / "audience.json"
    p.write_text('{"glance": {"items": [{"label": "X"}]}, '
                 '"audiences": [{"id": "citizens", "label": "For citizens"}]}')
    auds = bs.load_audiences(str(p))
    assert auds[0]["id"] == "citizens"
    # the one shared glance is attached to each audience for rendering
    assert auds[0]["glance"]["items"][0]["label"] == "X"


def test_load_audiences_empty_when_no_path():
    assert bs.load_audiences(None) == []


def test_glance_card_takes_colour_from_record_not_ai():
    spec = {"title": "T", "items": [{"label": "Muddiness", "says": "reliable"},
                                    {"label": "Algae", "says": "unreliable"}]}
    # verdicts (vclass, verdict) come from the signed record, zipped in limb order
    html = bs.glance_card(spec, [("ok", "Validated"), ("warn", "PartiallySupported")])
    assert '<li class="glance-row ok">' in html and '<li class="glance-row warn">' in html
    assert "✓" in html and "✗" in html          # icon derives from vclass, not the AI text
    # more labels than verdicts -> only the verdict-backed rows render (no orphan rows)
    one = bs.glance_card(spec, [("ok", "Validated")])
    assert one.count('<li class="glance-row') == 1


def test_tab_bar_and_svg_icon():
    bar = bs.tab_bar([{"id": "schools", "label": "For schools", "icon": "graduation-cap"}])
    assert 'data-tab="record"' in bar and 'data-tab="schools"' in bar
    assert bar.count("<svg") == 2                # record (file-lines) + schools (graduation-cap)
    assert bs.svg_icon("nonexistent-icon") == ""  # unknown name -> no icon, no crash


# --- published AI-summary nanopubs -> audience tabs -------------------------

def _rows():
    return [
        {"np": {"value": "https://w3id.org/np/RApub"},
         "audience": {"value": "http://www.wikidata.org/entity/Q2388316"},
         "text": {"value": "First para.\n\nSecond para."},
         "audLabel": {"value": "General public - a non-specialist adult audience"},
         "date": {"value": "2026-07-26T00:00:00Z"}},
        {"np": {"value": "https://w3id.org/np/RAsch"},
         "audience": {"value": "https://w3id.org/sciencelive/o/terms/audience/secondary-13-16"},
         "text": {"value": "For schools."},
         "audLabel": {"value": "Secondary school (ages 13-16) - lower secondary"},
         "isEdu": {"value": "true"},
         "date": {"value": "2026-07-25T00:00:00Z"}},
    ]


def test_fetch_published_summaries_parses_rows(monkeypatch):
    monkeypatch.setattr(bs, "sparql", lambda q: _rows())
    auds = bs.fetch_published_summaries("https://example.org/apex")
    assert len(auds) == 2
    pub = next(a for a in auds if a["id"] == "q2388316")
    assert pub["label"] == "General public"        # label is split off the "label - desc"
    assert pub["icon"] == "users"
    assert pub["np_uri"].endswith("RApub")
    assert pub["sections"] == [{"h": "", "p": "First para.\n\nSecond para."}]
    sch = next(a for a in auds if a["id"] == "secondary-13-16")
    assert sch["icon"] == "graduation-cap"         # a schema:EducationalAudience


def test_fetch_published_summaries_one_per_audience(monkeypatch):
    rows = [
        {"np": {"value": "https://w3id.org/np/RAnew"}, "audience": {"value": "http://www.wikidata.org/entity/Q2388316"},
         "text": {"value": "newer"}, "date": {"value": "2026-07-26"}},
        {"np": {"value": "https://w3id.org/np/RAold"}, "audience": {"value": "http://www.wikidata.org/entity/Q2388316"},
         "text": {"value": "older"}, "date": {"value": "2026-07-01"}},
    ]
    monkeypatch.setattr(bs, "sparql", lambda q: rows)
    auds = bs.fetch_published_summaries("apex")
    assert len(auds) == 1 and auds[0]["np_uri"].endswith("RAnew")  # keeps first (latest by ORDER BY)


def test_fetch_published_summaries_empty_on_error(monkeypatch):
    monkeypatch.setattr(bs, "sparql", lambda q: (_ for _ in ()).throw(RuntimeError("down")))
    assert bs.fetch_published_summaries("apex") == []   # network error -> fall back, never crash
    assert bs.fetch_published_summaries("") == []


def test_render_audience_published_links_to_signed_nanopub():
    aud = {"id": "q2388316", "label": "General public", "icon": "users",
           "sections": [{"h": "", "p": "First para.\n\nSecond para."}],
           "np_uri": "https://w3id.org/np/RAxyz"}
    html = bs.render_audience(aud)
    assert 'class="aud-prov"' in html and "View the nanopublication" in html
    assert "/np/?uri=" in html and "RAxyz" in html
    assert "<h1></h1>" not in html                       # no empty title
    assert '<h2 class="sec"></h2>' not in html           # no empty heading
    assert "<p>First para.</p>" in html                  # flat prose rendered as paragraphs


def test_render_audience_file_backed_has_no_provenance():
    aud = {"id": "citizens", "label": "For citizens",
           "sections": [{"h": "What", "p": "Body."}]}
    html = bs.render_audience(aud)
    assert 'class="aud-prov"' not in html                # only published tabs get the link
    assert '<h2 class="sec">What</h2>' in html           # a real heading still renders
