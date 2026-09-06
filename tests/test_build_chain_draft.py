"""Tests for scripts/build_chain_draft.py — the chain-draft.json producer.

The generator is a deterministic, offline script (the point is to keep the
publish phase off Claude tokens). These tests build a small fixture repo — a
CITATION.cff, PUBLISHED.md and a couple of filled drafts, plus the repo's real
committed template snapshot — and assert the produced chain-draft.json matches
the contract (docs/chain-draft-contract.md): correct field routing
(carry / metadata / manual / content), DOI forms, token omission, provenance,
and resume.

Run: pixi run -e tests test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_chain_draft as bcd  # noqa: E402

TEMPLATES = ROOT / "nanopubs" / "templates"

CITATION = """\
cff-version: 1.2.0
title: "bombus-thermal-replication"
type: software
repository-code: "https://github.com/annefou/bombus-thermal-replication"
date-released: "2026-06-26"
identifiers:
  - type: doi
    value: "10.5281/zenodo.20943700"
    description: "Concept DOI (resolves to the latest version) — cite the project"
  - type: doi
    value: "10.5281/zenodo.20943752"
    description: "Version DOI for v0.1.0 — pins this exact release; cite this from nanopubs"
references:
  - type: article
    title: "Climate change contributes to widespread declines among bumble bees"
    doi: "10.1126/science.aax8591"
"""

PUBLISHED = """\
| Step | Template | URI | Published |
|---|---|---|---|
| 01 | Quote | https://w3id.org/sciencelive/np/RAquoteExample0000000000000000000000000000 | 2026-06-27 |
| 02 | AIDA | _not yet published_ | |
"""

QUOTE = """\
# 01 — Quote
### DOI of the paper (starting with '10.')
```
10.1126/science.aax8591
```
### The exact quotation from the paper (max. 500 characters)
```
Bumblebee species are declining where temperatures exceed historical limits.
```
### our interpretation and explanation of why this quotation is relevant (max. 800 characters)
```
We test whether this holds for Iberian Bombus on an equal-area HEALPix grid.
```
"""

OUTCOME = """\
# 05 — Outcome
### short URI suffix for outcome ID
```
iberian-bombus-outcome
```
### plain-text label for the outcome
```
Iberian Bombus thermal-exposure outcome
```
### choose study
```
```
### repository URL
```
{{ZENODO_VERSION_DOI}}
```
### choose completion date
```
{{RELEASE_DATE}}
```
### choose validation status
- [ ] validated
- [x] contradicted
- [ ] inconclusive
### describe the overall conclusion about the original claim
```
The thermal-exposure signal holds on the equal-area grid.
```
### describe the evidence that supports your conclusion
```
GLMM coefficient +0.454 (95% HDI [+0.130, +0.751]).
```
### choose confidence level
- [x] high
- [ ] low
### describe what limits the conclusions of the study
```
Single taxon and region.
```
"""

CLAIM = """\
# 03 — Claim
### label of the claim, to find it later
```
Thermal exposure predicts Iberian Bombus extirpation
```
### Type of FORRT claim
- [ ] statistical significance
- [x] descriptive pattern
- [ ] model performance
"""

STUDY = """\
# 04 — Study
### label/name of replication study
```
Iberian Bombus thermal-exposure replication
```
### choose the study type
- [ ] Reproduction Study
- [x] Replication Study
### Search keywords (Wikidata) (multi-select, optional)
- _Label 1: thermal ecology
- _Label 2: bumblebee
### Search discipline (Wikidata) (search, optional)
- _Discipline label: ecology
"""


SOFTWARE = """\
# 07 — Research Software
### Software Title (text input, required)
```
Iberian Bombus thermal-exposure replication code
```
### Related Datasets (repeatable group, optional)
- _Dataset URL 1: https://doi.org/10.15468/dl.bombus0
- _Dataset URL 2: https://doi.org/10.5281/zenodo.20811600
### Related Publications (repeatable group, optional)
- _Publication URL 1: https://doi.org/10.9999/methods-paper
"""

SYNTHESIS = """\
# 08 — Research Synthesis
### label
```
Thermal exposure and Bombus extirpation - synthesis
```
### Conclusion of the synthesis
```
Increased thermal exposure predicts higher extirpation across regions.
```
### Conditions under which the synthesis applies
```
Bombus occurrence data with pre-1975 and post-2000 baseline coverage.
```
"""


# Offline stand-in for the live Wikidata lookup.
def _mock_wikidata(label: str, *, require_concept: bool = False):
    return {"uri": "http://www.wikidata.org/entity/Q" + str(abs(hash(label)) % 1000),
            "label": label}


def _fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "nanopubs" / "drafts").mkdir(parents=True)
    # real committed template snapshot + registry
    import shutil
    shutil.copytree(TEMPLATES, root / "nanopubs" / "templates")
    (root / "CITATION.cff").write_text(CITATION)
    (root / "nanopubs" / "PUBLISHED.md").write_text(PUBLISHED)
    (root / "nanopubs" / "drafts" / "01_quote.md").write_text(QUOTE)
    (root / "nanopubs" / "drafts" / "03_claim.md").write_text(CLAIM)
    (root / "nanopubs" / "drafts" / "04_study.md").write_text(STUDY)
    (root / "nanopubs" / "drafts" / "05_outcome.md").write_text(OUTCOME)
    for s in ("02_aida", "06_citation"):
        (root / "nanopubs" / "drafts" / f"{s}.md").write_text(f"# {s}\n")
    return root


@pytest.fixture
def draft(tmp_path):
    root = _fixture_repo(tmp_path)
    return bcd.build_chain_draft(root, repository="https://github.com/annefou/bombus-thermal-replication",
                                 commit="abc123", resolve_wikidata=_mock_wikidata)


@pytest.fixture
def draft_full(tmp_path):
    """Fixture repo that ALSO drafts the two optional side-branches (07/08)."""
    root = _fixture_repo(tmp_path)
    d = root / "nanopubs" / "drafts"
    d.joinpath("07_research_software.md").write_text(SOFTWARE)
    d.joinpath("08_synthesis.md").write_text(SYNTHESIS)
    return bcd.build_chain_draft(root, repository="https://github.com/annefou/bombus-thermal-replication",
                                 commit="abc123", resolve_wikidata=_mock_wikidata)


def _step(draft, sid):
    return next(s for s in draft["steps"] if s["step"] == sid)


# --- shape / structure ---------------------------------------------------

def test_shape_and_backbone(draft):
    assert draft["schema_version"] == bcd.SCHEMA_VERSION
    assert draft["chain_shape"] == "paper-rooted"
    assert [s["step"] for s in draft["steps"]] == \
        ["01_quote", "02_aida", "03_claim", "04_study", "05_outcome", "06_citation"]


def test_carry_forward_edges_match_the_contract(draft):
    assert draft["carry_forward"] == [
        {"from": "01_quote", "into": "02_aida", "field": "project"},
        {"from": "02_aida", "into": "03_claim", "field": "aida"},
        {"from": "03_claim", "into": "04_study", "field": "claim"},
        {"from": "04_study", "into": "05_outcome", "field": "study"},
        {"from": "05_outcome", "into": "06_citation", "field": "work"},
    ]


# --- second limb via a custom drafts dir (--drafts-dir) ------------------

def test_custom_drafts_dir_builds_a_second_limb(tmp_path):
    """--drafts-dir points the builder at a sibling drafts set (a second limb)
    while CITATION.cff / PUBLISHED.md / templates still come from the repo root.
    Content is read from the alt dir, provenance labels name it, and the default
    (no drafts_dir) build is unchanged."""
    root = _fixture_repo(tmp_path)
    alt = root / "nanopubs" / "drafts-turbidity"
    alt.mkdir()
    alt.joinpath("01_quote.md").write_text(
        QUOTE.replace("Bumblebee species are declining where temperatures exceed historical limits.",
                      "A distinct second-limb quote sentence."))
    for s in ("02_aida", "03_claim", "04_study", "05_outcome", "06_citation"):
        alt.joinpath(f"{s}.md").write_text(f"# {s}\n")

    d = bcd.build_chain_draft(
        root, repository="https://github.com/annefou/bombus-thermal-replication",
        commit="abc123", resolve_wikidata=_mock_wikidata, drafts_dir=alt)
    # content comes from the alt dir...
    assert _step(d, "01_quote")["prefill"]["quotation"].startswith("A distinct second-limb")
    # ...and provenance names the alt dir, not the default drafts/
    assert _step(d, "01_quote")["provenance"]["quotation"] == "nanopubs/drafts-turbidity/01_quote.md"

    # the default build (no drafts_dir) is unchanged
    d0 = bcd.build_chain_draft(
        root, repository="https://github.com/annefou/bombus-thermal-replication",
        commit="abc123", resolve_wikidata=_mock_wikidata)
    assert _step(d0, "01_quote")["prefill"]["quotation"].startswith("Bumblebee species")
    assert _step(d0, "01_quote")["provenance"]["quotation"] == "nanopubs/drafts/01_quote.md"


# --- metadata routing (CITATION.cff), in the right DOI form --------------

def test_paper_doi_is_bare_on_quote_full_url_elsewhere(draft):
    assert _step(draft, "01_quote")["prefill"]["paper"] == "10.1126/science.aax8591"
    assert _step(draft, "03_claim")["prefill"]["source"] == "https://doi.org/10.1126/science.aax8591"
    # 06_citation's DOI lives in the st02 repeatable row, not a flat key (below).


def test_outcome_uses_version_doi_and_release_date(draft):
    out = _step(draft, "05_outcome")["prefill"]
    assert out["repo"] == "https://doi.org/10.5281/zenodo.20943752"   # version, not concept DOI
    assert out["date"] == "2026-06-26"


def test_placeholder_tokens_in_draft_fences_are_never_emitted(draft):
    # 05_outcome.md had {{ZENODO_VERSION_DOI}}/{{RELEASE_DATE}} in its fences.
    for s in draft["steps"]:
        for v in s["prefill"].values():
            assert "{{" not in v


def test_placeholder_fixtures_have_not_been_substituted():
    """Canary: /init-template must never sed this file.

    The guards in this module are only meaningful while their fixtures still
    contain literal placeholder tokens. If init-template's directory exclusion
    regresses (it is a `--exclude-dir` in SKILL.md Step 4, and was once a
    fragile `grep -v '^\\./tests/'` post-filter that silently matched nothing),
    sed rewrites those fixtures to real values. `assert "{{" not in v` above
    then passes *vacuously* — the regression guard against publishing a raw
    placeholder into a signed nanopub stops guarding, without failing.

    So assert the inputs, not just the outputs. The expected tokens are built
    by concatenation below precisely so that sed — which matches the contiguous
    literal `{{NAME}}` — cannot rewrite this list in step with the fixtures it
    is checking.
    """
    src = Path(__file__).read_text()
    missing = [
        name for name in (
            "ZENODO_VERSION_DOI", "RELEASE_DATE",
            "REPO_ORG", "REPO_NAME", "ZENODO_DOI", "PAPER_DOI",
        )
        if "{{" + name + "}}" not in src
    ]
    assert not missing, (
        f"Placeholder fixtures were substituted (missing: {missing}). Restore "
        f"them with `git checkout -- {Path(__file__).name}` and fix the "
        "directory exclusion in .claude/skills/init-template/SKILL.md Step 4."
    )


# --- content routing (drafts) --------------------------------------------

def test_drafted_content_is_extracted(draft):
    q = _step(draft, "01_quote")["prefill"]
    assert q["quotation"].startswith("Bumblebee species are declining")
    assert q["comment"].startswith("We test whether")
    out = _step(draft, "05_outcome")["prefill"]
    assert out["outcome"] == "iberian-bombus-outcome"          # id slug
    assert out["label"] == "Iberian Bombus thermal-exposure outcome"
    assert out["conclusion"].startswith("The thermal-exposure signal")
    assert out["evidence"].startswith("GLMM coefficient")
    assert out["limitations"] == "Single taxon and region."


def test_provenance_is_recorded(draft):
    prov = _step(draft, "05_outcome")["provenance"]
    assert prov["repo"] == "CITATION.cff"
    assert prov["conclusion"] == "nanopubs/drafts/05_outcome.md"


# --- judgment fields: the agent's recorded choice, pre-filled + flagged --

def test_judgment_fields_prefilled_from_draft_choice_and_flagged(draft):
    """The agent ticked one option per judgment field in the draft; that choice
    is pre-filled (overriding the form default) AND kept in `manual` so the wizard
    shows 'confirm', not left blank."""
    out = _step(draft, "05_outcome")
    assert out["prefill"]["validationStatus"].endswith("Contradicted")
    assert out["prefill"]["confidenceLevel"].endswith("HighConfidence")
    assert set(out["manual"]) == {"validationStatus", "confidenceLevel"}
    claim = _step(draft, "03_claim")
    assert claim["prefill"]["forrtType"].endswith("descriptive_pattern-FORRT-Claim")
    assert claim["manual"] == ["forrtType"]
    assert _step(draft, "04_study")["prefill"]["type"].endswith("Replication-Study")


# --- repeatable CiTO citation --------------------------------------------

def test_citation_is_a_prepared_st02_row(draft):
    """CiTO is the repeatable `st02` array, not flat cites/cited; one row is
    prepared with the relation derived from the validation status."""
    cite = _step(draft, "06_citation")["prefill"]
    assert "cited" not in cite and "cites" not in cite      # not flat
    row = cite["st02"][0]
    assert row["cited"] == "https://doi.org/10.1126/science.aax8591"
    assert row["cites"] == "http://purl.org/spar/cito/disputes"   # Contradicted -> disputes
    assert _step(draft, "06_citation").get("manual", []) == []


# --- generated id slug ---------------------------------------------------

def test_id_slug_is_generated_from_org_repo_step(draft):
    """Steps whose draft has no URI-suffix slug get <org>-<repo>-<step>."""
    assert _step(draft, "03_claim")["prefill"]["claim"] == "annefou-bombus-thermal-replication-claim"
    assert _step(draft, "04_study")["prefill"]["study"] == "annefou-bombus-thermal-replication-study"


# --- Wikidata concept fields (resolved from draft labels) ----------------

def test_wikidata_fields_resolved_to_form_shapes(draft):
    """Keyword labels -> keywordSelection [{uri,label}]; discipline -> a single
    {uri,label} object (not an array), matching the components."""
    study = _step(draft, "04_study")["prefill"]
    assert [k["label"] for k in study["keywordSelection"]] == ["thermal ecology", "bumblebee"]
    assert all(k["uri"].startswith("http://www.wikidata.org/entity/Q") for k in study["keywordSelection"])
    assert study["disciplineSelection"]["label"] == "ecology"          # single object
    assert not isinstance(study["disciplineSelection"], list)


def test_carry_fields_are_absent_from_prefill(draft):
    assert "study" not in _step(draft, "05_outcome")["prefill"]     # carried from 04
    assert "work" not in _step(draft, "06_citation")["prefill"]     # carried from 05
    assert "aida" not in _step(draft, "03_claim")["prefill"]        # carried from 02


# --- resume (PUBLISHED.md) -----------------------------------------------

def test_published_uri_is_read_for_resume(draft):
    assert _step(draft, "01_quote")["published_uri"].endswith("RAquoteExample0000000000000000000000000000")
    assert _step(draft, "02_aida")["published_uri"] is None


# --- unit helpers --------------------------------------------------------

def test_load_citation_ignores_placeholder_tokens():
    cff = bcd.load_citation('title: x\nrepository-code: "https://github.com/{{REPO_ORG}}/{{REPO_NAME}}"\n'
                            'date-released: "{{RELEASE_DATE}}"\n')
    assert cff.get("repo_url") is None and cff.get("date_released") is None


def test_bare_doi_strips_resolver_prefix():
    assert bcd._bare_doi("https://doi.org/10.1/x") == "10.1/x"
    assert bcd._bare_doi("10.1/x") == "10.1/x"


def test_parse_published_skips_unpublished_rows():
    pub = bcd.parse_published(PUBLISHED)
    assert "01" in pub and "02" not in pub


# --- optional side-branches (07 software, 08 synthesis) + their back-links ---

def test_optional_steps_appended_when_drafted(draft_full):
    # (the not-drafted -> absent case is covered by test_shape_and_backbone)
    assert [s["step"] for s in draft_full["steps"]] == \
        ["01_quote", "02_aida", "03_claim", "04_study", "05_outcome",
         "06_citation", "07_research_software", "08_synthesis"]


def test_back_link_carry_edges_are_emitted(draft_full):
    """07/08 link back to NON-ADJACENT steps, with several links and shaped
    targets. The linear 01->06 edges are unchanged; the back-links are added."""
    edges = draft_full["carry_forward"]
    # linear edges still present and unchanged
    assert {"from": "05_outcome", "into": "06_citation", "field": "work"} in edges
    # 07 <- Claim (scalar) + Outcome (array of strings)
    assert {"from": "03_claim", "into": "07_research_software", "field": "project"} in edges
    assert {"from": "05_outcome", "into": "07_research_software",
            "field": "researchOutputs", "mode": "uriList"} in edges
    # 08 <- Outcome (array of {source} objects)
    assert {"from": "05_outcome", "into": "08_synthesis", "field": "sources",
            "mode": "uriObjectList", "itemKey": "source"} in edges


def test_back_link_fields_are_absent_from_prefill(draft_full):
    """The carried back-links must not be content/metadata-filled here — the
    wizard injects them from the referenced steps' published URIs."""
    sw = _step(draft_full, "07_research_software")["prefill"]
    assert "project" not in sw
    assert "researchOutputs" not in sw and "researchoutput" not in sw
    syn = _step(draft_full, "08_synthesis")["prefill"]
    assert "sources" not in syn and "source" not in syn     # NOT the paper DOI from metadata
    # ...but the non-carried fields of these steps are still produced
    assert sw["software"] == "https://doi.org/10.5281/zenodo.20943752"   # CFF version DOI
    assert sw["title"].startswith("Iberian Bombus")
    assert syn["synthesis"] == "annefou-bombus-thermal-replication-synthesis"   # id slug
    assert syn["conclusion"].startswith("Increased thermal exposure")


def test_datasets_repeatable_is_filled_from_draft_as_string_list(draft_full):
    """07's optional Related Datasets — read from the draft by its heading and
    emitted under the component field name `datasets` as a list of plain URLs
    (the singular placeholder `dataset` never leaks; Related Publications, which
    is the carried back-link, is not scraped here)."""
    sw = _step(draft_full, "07_research_software")["prefill"]
    assert sw["datasets"] == [
        "https://doi.org/10.15468/dl.bombus0",
        "https://doi.org/10.5281/zenodo.20811600",
    ]
    assert "dataset" not in sw                                  # not the placeholder name
    assert "researchOutputs" not in sw                         # carried, not scraped from draft


def test_content_fields_with_mismatched_headings_use_alias(draft_full):
    """07 `title` and 08 `conditions` have draft headings that don't contain the
    placeholder label; a heading alias reads them so they don't fall through
    empty. (The drafts here use the real human headings, so no alias == blank.)"""
    assert _step(draft_full, "07_research_software")["prefill"]["title"] == \
        "Iberian Bombus thermal-exposure replication code"
    assert _step(draft_full, "08_synthesis")["prefill"]["conditions"] == \
        "Bombus occurrence data with pre-1975 and post-2000 baseline coverage."


def test_back_links_omitted_when_targets_not_in_chain(draft):
    """No 07/08 in this chain -> no back-link edges leak into the linear draft."""
    assert all(e["into"] not in ("07_research_software", "08_synthesis")
               for e in draft["carry_forward"])


def test_repo_drafts_build_a_well_formed_chain():
    """Run against the repo's own drafts, whatever state they are in.

    This used to assert every prefill was empty, on the premise that the repo is
    an uninitialised template. That premise holds here and is false in every repo
    built from this template: once /init-template puts a real paper DOI and
    release date in CITATION.cff, those values correctly propagate into the
    01/03/05/06/08 prefills, so the assertion was a guaranteed failure on a
    user's first push -- red CI that looks like a broken template.

    The empty-prefill guarantee is a property of *token input*, not of this
    repo's checkout, so it is asserted against a fixture below
    (test_placeholder_tokens_are_never_prefilled). What is invariant either way
    is the shape: the steps enumerate and the manual fields stand.
    """
    d = bcd.build_chain_draft(ROOT, repository="x", commit="y",
                              resolve_wikidata=lambda label, **kw: None)
    assert d["steps"], "the repo's drafts should yield at least one chain step"
    assert all({"step", "template_uri", "prefill"} <= set(s) for s in d["steps"])
    assert _step(d, "05_outcome")["manual"] == ["validationStatus", "confidenceLevel"]


def test_placeholder_tokens_are_never_prefilled(tmp_path):
    """A wholly unsubstituted repo pre-fills nothing -- fixture-based, so it keeps
    holding after /init-template has edited the real drafts."""
    root = _fixture_repo(tmp_path)
    (root / "CITATION.cff").write_text(
        'cff-version: 1.2.0\ntitle: "{{REPO_NAME}}"\n'
        'repository-code: "https://github.com/{{REPO_ORG}}/{{REPO_NAME}}"\n'
        'date-released: "{{RELEASE_DATE}}"\ndoi: "{{ZENODO_DOI}}"\n'
        'references:\n  - type: article\n    doi: "{{PAPER_DOI}}"\n'
    )
    for f in (root / "nanopubs" / "drafts").glob("*.md"):
        f.write_text(f"# {f.stem}\n\n{{{{PLACEHOLDER}}}}\n")
    d = bcd.build_chain_draft(root, repository="x", commit="y",
                              resolve_wikidata=lambda label, **kw: None)
    assert all(s["prefill"] == {} for s in d["steps"])


# --------------------------------------------------------------- headline figure

def _figures(root: Path, *names: str) -> None:
    d = root / "figures"
    d.mkdir(exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"\x89PNG\r\n")


def test_no_figure_directory_leaves_source_without_a_figure(tmp_path):
    root = _fixture_repo(tmp_path)
    d = bcd.build_chain_draft(root, repository="https://github.com/o/r", commit="abc123",
                              resolve_wikidata=_mock_wikidata)
    assert "figure" not in d["source"]


def test_empty_figure_directory_leaves_source_without_a_figure(tmp_path):
    root = _fixture_repo(tmp_path)
    (root / "figures").mkdir()
    (root / "figures" / "notes.txt").write_text("not an image")
    d = bcd.build_chain_draft(root, repository="https://github.com/o/r", commit="abc123",
                              resolve_wikidata=_mock_wikidata)
    assert "figure" not in d["source"]


def test_single_figure_is_recorded_relative_to_the_repo(tmp_path):
    root = _fixture_repo(tmp_path)
    _figures(root, "whatever-name.png")
    d = bcd.build_chain_draft(root, repository="https://github.com/o/r", commit="abc123",
                              resolve_wikidata=_mock_wikidata)
    assert d["source"]["figure"] == "figures/whatever-name.png"


def test_named_result_wins_over_alphabetical_order(tmp_path):
    """A headline name beats plain sorting - otherwise 'appendix.png' would win."""
    root = _fixture_repo(tmp_path)
    _figures(root, "appendix.png", "main_result.png", "zz-extra.png")
    d = bcd.build_chain_draft(root, repository="https://github.com/o/r", commit="abc123",
                              resolve_wikidata=_mock_wikidata)
    assert d["source"]["figure"] == "figures/main_result.png"


def test_figure_choice_is_deterministic_regardless_of_directory_order(tmp_path):
    """Same set of unremarkable names -> same pick, every run and every machine."""
    picks = set()
    for order in (("b.png", "a.png", "c.png"), ("c.png", "b.png", "a.png")):
        root = _fixture_repo(tmp_path / order[0])
        _figures(root, *order)
        d = bcd.build_chain_draft(root, repository="https://github.com/o/r", commit="abc123",
                                  resolve_wikidata=_mock_wikidata)
        picks.add(d["source"]["figure"])
    assert picks == {"figures/a.png"}


def test_results_directory_is_not_scanned(tmp_path):
    """results/ holds run artefacts and diagnostics - never the headline figure."""
    root = _fixture_repo(tmp_path)
    (root / "results").mkdir()
    (root / "results" / "main_result.png").write_bytes(b"\x89PNG\r\n")
    d = bcd.build_chain_draft(root, repository="https://github.com/o/r", commit="abc123",
                              resolve_wikidata=_mock_wikidata)
    assert "figure" not in d["source"]



# --------------------------------------- shipped skeletons match the templates

def test_every_shipped_skeleton_heading_matches_its_template_field():
    """The drafts a real replication actually fills must be extractable.

    build_chain_draft matches a draft's ### heading to the template field label
    (via _norm + loose containment, or DRAFT_HEADING_ALIAS). Nothing checked that
    the *shipped* skeletons satisfy it: the fixtures in this file were written
    from the template labels, while the skeletons were written from
    docs/forrt-form-fields.md's UI wording, and the two drifted. A filled
    01_quote.md silently yielded no quotation and no comment at all.

    The uninitialised-prefill test cannot catch this — it asserts prefill is
    *empty*, which is true whether the headings match or not."""
    snapshot = json.loads((TEMPLATES / "fields.snapshot.json").read_text())
    missing = []
    for step_id, body in snapshot["steps"].items():
        skeleton = ROOT / "nanopubs" / "drafts" / f"{step_id}.md"
        if not skeleton.exists():
            continue
        headings = bcd._draft_sections(skeleton.read_text())
        for i, field in enumerate(body.get("fields", [])):
            if not bcd.is_content_field(step_id, i, field):
                continue
            alias = bcd.DRAFT_HEADING_ALIAS.get((step_id, field["id"]))
            key = bcd._norm(alias or field["label"])
            found = key in headings or any(
                h and (h in key or key in h) for h in headings
            )
            if not found:
                missing.append(f"{step_id}.{field['id']} (expects a heading matching {key!r})")
    assert not missing, (
        "these fields would silently extract nothing from a filled draft:\n  "
        + "\n  ".join(missing)
    )

# ------------------------------------------------- wikidata concept typing

def _field(*apis):
    return {"values_from_api": list(apis)}


OWL_CLASS_API = ("http://purl.org/nanopub/api/find_signed_things"
                 "?type=http%3A%2F%2Fwww.w3.org%2F2002%2F07%2Fowl%23Class&searchterm=")
PLAIN_WIKIDATA_API = ("https://www.wikidata.org/w/api.php?action=wbsearchentities"
                      "&language=en&format=json&limit=5&search=")


def test_concept_type_is_read_from_the_template_not_hardcoded():
    """Only a field whose template names owl:Class is type-constrained."""
    assert bcd.declares_concept_type(_field(OWL_CLASS_API, PLAIN_WIKIDATA_API)) is True
    assert bcd.declares_concept_type(_field(PLAIN_WIKIDATA_API)) is False
    assert bcd.declares_concept_type(_field()) is False


def test_only_the_aida_topic_is_concept_typed_in_the_real_templates():
    """Guard against imposing a type the template does not declare.

    08_synthesis has a field also called `topic`, but its template names no type,
    so it must stay unconstrained — matching on the field *name* would silently
    add a constraint the schema never asked for."""
    snapshot = json.loads((TEMPLATES / "fields.snapshot.json").read_text())
    typed = {
        (step_id, f["id"])
        for step_id, body in snapshot["steps"].items()
        for f in body.get("fields", [])
        if bcd.declares_concept_type(f)
    }
    assert typed == {("02_aida", "topic")}


def test_untyped_field_resolves_to_the_first_hit(monkeypatch):
    """No type declared -> existence only; the first search hit is used as-is."""
    monkeypatch.setattr(bcd, "_wikidata_claims",
                        lambda *a, **k: pytest.fail("must not type-check an untyped field"))
    monkeypatch.setattr(bcd, "_wikidata_search",
                        lambda label, limit, timeout: [{"id": "Q1", "label": "first"}])
    assert bcd.resolve_wikidata("ecology")["uri"].endswith("Q1")


def test_concept_field_skips_non_classes_and_takes_the_first_class(monkeypatch):
    """The real failure: searching "atmospheric river" returns a painting and a
    scholarly article alongside the concept. Only the class (P279) is acceptable."""
    monkeypatch.setattr(bcd, "_wikidata_search", lambda label, limit, timeout: [
        {"id": "Q111802562", "label": "Atmospheric river landscape"},  # a painting
        {"id": "Q136915521", "label": "Atmospheric rivers' orientation..."},  # a paper
        {"id": "Q4817119", "label": "atmospheric river"},               # the concept
    ])
    # only the concept carries P279 (subclass of)
    monkeypatch.setattr(bcd, "_wikidata_claims",
                        lambda qid, prop, **k: [{}] if qid == "Q4817119" else [])
    got = bcd.resolve_wikidata("atmospheric river", require_concept=True)
    assert got["uri"].endswith("Q4817119")
    assert got["label"] == "atmospheric river"


def test_concept_field_returns_none_rather_than_binding_a_non_class(monkeypatch):
    """An empty field is recoverable; a wrong value signed into a nanopub is not."""
    monkeypatch.setattr(bcd, "_wikidata_search", lambda label, limit, timeout: [
        {"id": "Q136915521", "label": "some paper"},
    ])
    monkeypatch.setattr(bcd, "_wikidata_claims", lambda qid, prop, **k: [])
    assert bcd.resolve_wikidata("atmospheric river", require_concept=True) is None

