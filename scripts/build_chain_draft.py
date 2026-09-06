#!/usr/bin/env python3
"""Build ``nanopubs/chain-draft.json`` — the pre-filled hand-off for the Science
Live FORRT-chain wizard. See ``docs/chain-draft-contract.md`` for the format.

This is the **producer** side of the contract, and it is deliberately a plain,
deterministic script — **no Claude, no network**. The whole point is to move the
publish phase off Claude tokens: the researcher's content was drafted once during
the replication; this reads that plus the repo's own metadata and emits one JSON
file the browser wizard consumes.

For each chain step it routes every field to exactly one place:

* **carry**    — the back-reference field the wizard fills from the previous
                 step's published URI (``project``/``aida``/``claim``/``study``/
                 ``work``). Never pre-filled here — the URI doesn't exist yet.
* **metadata** — filled from ``CITATION.cff``: the replicated paper's DOI
                 (``paper``/``source``/``cited``), the Zenodo **version** DOI
                 (``repo``), the release date (``date``), the repo URL.
* **manual**   — the judgment calls, i.e. the template's ``restricted_choice``
                 fields (claim type, validation status, confidence, CiTO
                 relation). Listed in ``manual`` for the wizard; not pre-filled.
* **content**  — the drafted prose (quote, methodology, conclusion, the id slug,
                 …). Read from ``nanopubs/drafts/0X_*.md``.

Placeholder values (unsubstituted ``{{TOKEN}}`` in an uninitialised template, or
empty draft fences) are omitted, per the contract: a field the repo can't fill is
simply absent and the wizard renders it empty.

Run (offline, no special deps beyond ruamel.yaml which CITATION.cff needs):

    pixi run -e tests python scripts/build_chain_draft.py     # writes nanopubs/chain-draft.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML

SCHEMA_VERSION = "1.0"

# The 6-step FORRT backbone, in order. The step-1 anchor is whichever of the
# three alternates the replication kept (the drafter deletes the other two).
CORE_STEPS = ["02_aida", "03_claim", "04_study", "05_outcome", "06_citation"]
ANCHORS = {"01_quote": "paper-rooted", "01_pico": "pico", "01_pcc": "pcc"}
OPTIONAL_STEPS = ["07_research_software", "08_synthesis"]

# step -> the field the wizard fills from the previous step's published URI.
CARRY_FIELD = {
    "02_aida": "project", "03_claim": "aida", "04_study": "claim",
    "05_outcome": "study", "06_citation": "work",
}

# The optional side-branches (07/08) link back to NON-ADJACENT earlier steps, and
# a step may have several such links, so they get their own carry edges rather than
# the linear one-per-step hop. `field` is the platform component's field name (what
# the wizard injects the carried URI into); `placeholder` is the snapshot field id
# to skip when building this step (it differs from `field` for the repeatables,
# e.g. researchOutputs <- placeholder researchoutput). `mode`/`itemKey` tell the
# wizard the target shape. See docs/chain-draft-contract.md.
BACK_LINKS: dict[str, list[dict]] = {
    "07_research_software": [
        {"from": "03_claim", "field": "project", "placeholder": "project"},
        {"from": "05_outcome", "field": "researchOutputs",
         "placeholder": "researchoutput", "mode": "uriList"},
    ],
    "08_synthesis": [
        {"from": "05_outcome", "field": "sources", "placeholder": "source",
         "mode": "uriObjectList", "itemKey": "source"},
    ],
}


def carried_placeholders(step: str) -> set[str]:
    """Snapshot field ids that the wizard fills via carry-forward (skip here)."""
    skip = {CARRY_FIELD[step]} if step in CARRY_FIELD else set()
    skip.update(bl["placeholder"] for bl in BACK_LINKS.get(step, []))
    return skip

# Short slug per step, for the "Short URI suffix" id fields (<org>-<repo>-<step>).
STEP_SLUG = {
    "01_quote": "quote", "01_pico": "pico", "01_pcc": "pcc", "02_aida": "aida",
    "03_claim": "claim", "04_study": "study", "05_outcome": "outcome",
    "06_citation": "citation", "07_research_software": "software", "08_synthesis": "synthesis",
}

# The CiTO citation type suggested from the Outcome's validation status. Keyed by
# the validation-status vocabulary URI's final segment.
CITO = "http://purl.org/spar/cito/"
RELATION_FROM_STATUS = {
    "Validated": CITO + "confirms",
    "PartiallySupported": CITO + "qualifies",
    "Contradicted": CITO + "disputes",
    "Inconclusive": CITO + "discusses",
    "NotTested": CITO + "cites",
}

# Wikidata concept fields — (step, snapshot placeholder id) -> (form field name,
# is_array). The agent lists plain labels in the draft; we resolve each to a
# Wikidata {uri, label} the form can use. `disciplineSelection` is a single
# object (not an array); the rest are arrays. Form field names from the audit.
WIKIDATA_FIELDS = {
    ("02_aida", "topic"): ("topic", True),
    ("04_study", "keyword"): ("keywordSelection", True),
    ("04_study", "discipline"): ("disciplineSelection", False),
    ("08_synthesis", "topic"): ("topicSelection", True),
}

# Repeatable plain-URL list fields — (step, snapshot placeholder id) -> (form
# field name, draft heading). The snapshot label ("URI of published dataset")
# doesn't match the draft's human heading ("Related Datasets"), so we read the
# list from the draft by that heading. The draft lists one URL per bullet; the
# component wants an array of plain strings under the form field name.
REPEATABLE_TEXT_FIELDS = {
    ("07_research_software", "dataset"): ("datasets", "Related Datasets"),
}

# Scalar content fields whose draft heading doesn't contain the placeholder label,
# so label-matching fails — (step, snapshot placeholder id) -> the draft heading to
# read the value from. (The output key stays the placeholder/component field name.)
DRAFT_HEADING_ALIAS = {
    ("07_research_software", "title"): "Software Title",
    ("08_synthesis", "conditions"): "Conditions under which the synthesis applies",
    # The Research Synthesis template labels this field "short URI suffix for
    # OUTCOME ID" — copy-paste from the Outcome template (the field id is
    # `synthesis`). The draft says "synthesis", which is what a person filling
    # it in needs to read, so alias rather than propagate the template's slip.
    ("08_synthesis", "synthesis"): "Short URI suffix for synthesis ID",
    # More template labels a person cannot act on. `date` has an EMPTY label
    # upstream, so nothing could ever match it; the rest are RDF-shaped ("URI of
    # repository where software is published") where the draft says what the
    # researcher actually pastes.
    ("07_research_software", "repository"): "Repository URL",
    ("07_research_software", "researchoutput"): "Related Publications",
    ("08_synthesis", "source"): "Supporting sources",
    ("08_synthesis", "date"): "Completion date",
    ("06_citation", "work"): "Identifier for the citing creative work",
    # The Wikidata pickers: the draft uses the platform's own wording so the
    # drafter recognises the control they will meet in the form.
    ("04_study", "keyword"): "Search keywords (Wikidata)",
    ("04_study", "discipline"): "Search discipline (Wikidata)",
    ("03_claim", "aida"): "Search for an AIDA sentence",
    ("02_aida", "aida"): "AIDA sentence",
    ("02_aida", "topic"): "Select related topics/tags",
    ("02_aida", "project"): "Relates to this nanopublication",
    ("02_aida", "dataset"): "Supported by datasets",
    ("02_aida", "publication"): "Supported by other publications",
    ("01_quote", "paper"): "Cited DOI",
    ("01_pico", "type"): "Question Type",
}


# --- metadata (CITATION.cff) ---------------------------------------------

def _clean(v) -> str | None:
    """A usable value, or None for empty / unsubstituted ``{{TOKEN}}`` placeholders."""
    v = (str(v) if v is not None else "").strip()
    return None if (not v or "{{" in v) else v


def _bare_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi).strip() or None


def load_citation(text: str) -> dict:
    """Extract the metadata the chain needs from CITATION.cff text."""
    data = YAML(typ="safe").load(text) or {}
    out: dict = {}
    out["repo_url"] = _clean(data.get("repository-code"))
    out["date_released"] = _clean(data.get("date-released"))

    for ref in data.get("references") or []:
        if ref.get("type") == "article":
            out["paper_doi"] = _bare_doi(_clean(ref.get("doi")))
            break

    # The release workflow appends a version-DOI identifier whose description
    # says "Version DOI"; the concept DOI's does not.
    for ident in data.get("identifiers") or []:
        if ident.get("type") == "doi" and "version doi" in (ident.get("description") or "").lower():
            out["version_doi"] = _bare_doi(_clean(ident.get("value")))
            break
    return out


def metadata_value(step: str, name: str, cff: dict) -> str | None:
    """The CITATION.cff-derived value for a metadata field, in the form its
    template expects (bare DOI where the template adds the prefix, full URL
    otherwise), or None if this field isn't metadata / the value is absent."""
    paper = cff.get("paper_doi")
    if name == "paper":                       # uri field, template adds https://doi.org/
        return paper
    if name in ("source", "cited"):           # external_uri, wants the full URL
        return f"https://doi.org/{paper}" if paper else None
    if name == "repo" or (step == "07_research_software" and name == "software"):
        v = cff.get("version_doi")
        return f"https://doi.org/{v}" if v else None
    if name == "date":
        return cff.get("date_released")
    if step == "07_research_software" and name == "repository":
        return cff.get("repo_url")
    return None


# --- published URIs (PUBLISHED.md) ---------------------------------------

_URI_RE = re.compile(r"https?://w3id\.org/(?:sciencelive/)?np/RA[A-Za-z0-9_-]{20,}")


def parse_published(text: str) -> dict:
    """Map ``NN`` -> published URI from the PUBLISHED.md table (``_not yet
    published_`` rows yield nothing)."""
    out: dict = {}
    for line in text.splitlines():
        m = re.match(r"\s*\|\s*(\d{2})\s*\|", line)
        if not m:
            continue
        uri = _URI_RE.search(line)
        if uri:
            out[m.group(1)] = uri.group(0)
    return out


# --- drafted content (nanopubs/drafts/0X_*.md) ---------------------------

_HEADING_RE = re.compile(r"^#{2,4}\s+(.*?)\s*$")


def parse_draft(text: str) -> dict:
    """Extract ``{normalised heading: value}`` for each field section of a draft.

    A field is a ``###`` heading followed by the first fenced ``` block in its
    section. Guidance code fences (which live under other headings or in
    block-quotes) are ignored because we only take the first fence *after a
    field heading and before the next heading*."""
    out: dict = {}
    current = None
    in_fence = False
    buf: list[str] = []
    captured_for_current = False

    def flush():
        nonlocal buf, captured_for_current
        if current is not None and not captured_for_current:
            val = "\n".join(buf).strip()
            if val:
                out[_norm(current)] = val
            captured_for_current = True
        buf = []

    for line in text.splitlines():
        h = _HEADING_RE.match(line)
        if h and not in_fence:
            current = h.group(1)
            captured_for_current = False
            buf = []
            continue
        if line.strip().startswith("```"):
            if in_fence:                       # closing fence
                in_fence = False
                flush()
            elif not captured_for_current:     # opening fence for this field
                in_fence = True
                buf = []
            continue
        if in_fence:
            buf.append(line)
    return out


_STRIP_PREFIXES = (
    "choose ", "select ", "describe ", "search for ", "plain-text ",
    "short uri suffix for ", "short uri suffix as ", "label/name of ",
    "the ", "your ",
)


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\([^)]*\)", "", s)            # drop "(text input, required)" etc.
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        for p in _STRIP_PREFIXES:
            if s.startswith(p):
                s = s[len(p):]
                changed = True
    return s.strip()


def draft_content(draft_text: str, field) -> str | None:
    """Best-effort value for one content field from a draft, matched by label."""
    sections = parse_draft(draft_text)
    key = _norm(field["label"])
    if key in sections:
        return _draft_clean(sections[key])
    # loose containment either way, for hand-authored headings that drift
    for hk, hv in sections.items():
        if hk and (hk in key or key in hk):
            return _draft_clean(hv)
    return None


def _draft_clean(v: str) -> str | None:
    v = v.strip()
    if not v or "{{" in v or v.startswith("<") or v.lower().startswith("_vocabulary"):
        return None
    return v


def _draft_sections(text: str) -> dict:
    """heading (normalised) -> raw section body (lines until the next heading)."""
    out: dict = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        h = _HEADING_RE.match(line)
        if h:
            if current is not None:
                out[_norm(current)] = "\n".join(buf)
            current, buf = h.group(1), []
        else:
            buf.append(line)
    if current is not None:
        out[_norm(current)] = "\n".join(buf)
    return out


def draft_choice(draft_text: str, field: dict) -> str | None:
    """The vocabulary URI the agent checked for a restricted_choice field.

    The draft records the choice as a ticked checkbox (``- [x] Label``). Match
    that label against the field's ``possible_values`` by normalised label or by
    the value URI's final segment — hand-authored drafts often use a short label
    (``Replication Study``) where the template's is longer (``Replication Study -
    replication with different …``)."""
    body = _draft_sections(draft_text).get(_norm(field["label"]))
    if body is None:
        key = _norm(field["label"])
        for hk, hv in _draft_sections(draft_text).items():
            if hk and (hk in key or key in hk):
                body = hv
                break
    if not body:
        return None
    m = re.search(r"^\s*[-*]\s*\[[xX]\]\s*(.+?)\s*$", body, re.M)
    if not m:
        return None
    checked = _norm(m.group(1))
    for c in field.get("possible_values", []):
        label = _norm(c["label"])
        seg = _norm(re.sub(r"[-_]", " ", c["uri"].rsplit("/", 1)[-1]))
        if checked in (label, seg) or label.startswith(checked) or seg == checked:
            return c["uri"]
    return None


def slug_for(step: str, org: str | None, repo: str | None) -> str | None:
    ident = [p for p in (org, repo) if p]
    if not ident:                       # no repo identity (uninitialised template)
        return None
    s = re.sub(r"[^a-z0-9-]+", "-", "-".join([*ident, STEP_SLUG[step]]).lower()).strip("-")
    return s or None


def draft_labels(draft_text: str, field: dict) -> list[str]:
    """The plain labels the agent listed for a Wikidata field (best-effort).

    The draft lists them as bullets, optionally ``- _Label 1: <value>``. Take the
    text after a colon, or the bullet text, dropping empty/placeholder entries."""
    body = _draft_sections(draft_text).get(_norm(field["label"]))
    if body is None:
        key = _norm(field["label"])
        for hk, hv in _draft_sections(draft_text).items():
            if hk and (hk in key or key in hk):
                body = hv
                break
    if not body:
        return []
    out: list[str] = []
    for line in body.splitlines():
        m = re.match(r"\s*[-*]\s*_?[^:]*:\s*(.+?)\s*$", line) or re.match(r"\s*[-*]\s+(.+?)\s*$", line)
        if not m:
            continue
        v = m.group(1).strip().strip("_").strip()
        if v and v != "___" and "___" not in v and not v.startswith("<"):
            out.append(v)
    return out


# The url-encoded owl:Class that a template's typed value source names when it
# constrains a field to a *concept*. Today only 02_aida/topic carries it.
OWL_CLASS_ENCODED = "owl%23Class"


def declares_concept_type(field: dict) -> bool:
    """Does the template constrain this field to ``owl:Class`` (i.e. a concept)?

    Read from the field's own ``values_from_api``, so the rule follows the
    template rather than a hard-coded list here: if a template later constrains
    another field, this picks it up, and fields the template leaves untyped stay
    untyped. Never impose a type the template does not declare."""
    return any(OWL_CLASS_ENCODED in (a or "")
               for a in (field.get("values_from_api") or []))


# Wikimedia's API policy requires a descriptive User-Agent and answers the
# default Python urllib one with 403. Without this header every lookup below
# failed and was swallowed by the except, so every Wikidata field silently came
# back empty — a whole feature quietly doing nothing.
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_UA = ("forrt-replication-template/1.0 "
               "(+https://github.com/ScienceLiveHub/forrt-replication-template)")


def _wikidata_get(params: dict, timeout: int) -> dict | None:
    """One Wikidata API call. None on failure, with a warning — never silent:
    a lookup that fails leaves a field empty, and the researcher needs to know
    that happened rather than discover it after publishing."""
    import urllib.parse
    import urllib.request
    url = WIKIDATA_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": WIKIDATA_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Wikidata lookup failed ({params.get('search') or params.get('entity')}): "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def _wikidata_search(label: str, limit: int, timeout: int) -> list:
    """wbsearchentities hits for a label; [] on any failure."""
    d = _wikidata_get({
        "action": "wbsearchentities", "language": "en", "format": "json",
        "limit": str(limit), "search": label,
    }, timeout)
    return (d or {}).get("search") or []


def _wikidata_claims(qid: str, prop: str, *, timeout: int = 15) -> list:
    """Statements of one property for an entity; [] on any failure."""
    d = _wikidata_get({
        "action": "wbgetclaims", "property": prop, "format": "json", "entity": qid,
    }, timeout)
    return ((d or {}).get("claims") or {}).get(prop) or []


def resolve_wikidata(label: str, *, require_concept: bool = False,
                     timeout: int = 15) -> dict | None:
    """Resolve a label to a Wikidata ``{uri, label}``, or None. Network; failures
    return None so the generator degrades to leaving the field empty.

    ``require_concept`` — for a field whose template declares ``owl:Class``. A
    Wikidata *class* carries ``P279`` (subclass of); an instance of a work, a
    person or a place does not. Untyped ``wbsearchentities`` mixes them freely:
    searching "atmospheric river" returns the concept (Q4817119, P279 -> weather
    phenomenon), a painting, and a scholarly article. So widen the search and take
    the first candidate that is actually a class, and return None rather than bind
    a wrong one — an empty field is recoverable, a wrong signed value is not.
    """
    hits = _wikidata_search(label, 7 if require_concept else 1, timeout)
    if not hits:
        return None

    def as_item(h: dict) -> dict:
        return {
            "uri": h.get("concepturi") or f"http://www.wikidata.org/entity/{h['id']}",
            "label": h.get("label") or label,
        }

    if not require_concept:
        return as_item(hits[0])
    for h in hits:
        if _wikidata_claims(h["id"], "P279", timeout=timeout):
            return as_item(h)
    # Nothing in the results is a class. Either the term matches only works and
    # people, or it is a genuine concept Wikidata has not modelled with P279.
    # Leave the field empty rather than bind a wrong entity — but say so, or the
    # topic vanishes from the chain with nobody the wiser.
    print(f"Wikidata: no concept (owl:Class) found for {label!r} among "
          f"{len(hits)} results — leaving the field empty. Pick the QID by hand "
          f"if you know the right one.", file=sys.stderr)
    return None


# --- assembly ------------------------------------------------------------

def is_metadata_field(step: str, name: str) -> bool:
    """Whether a field is filled from CITATION.cff (structurally — independent of
    whether the value is present in this repo)."""
    if name in ("paper", "source", "cited", "repo", "date"):
        return True
    return step == "07_research_software" and name in ("software", "repository")


def is_content_field(step: str, idx: int, f: dict) -> bool:
    """Content = drafted prose. Literals and the AIDA sentence are always content;
    a bare ``uri`` field is content only when it's the step's id slug (the first
    field) and not itself a metadata field. Optional topic/keyword/dataset URIs
    are left for the user (omitted)."""
    if f["kind"] in ("literal", "long_literal", "auto_escape_uri"):
        return True
    if f["kind"] == "uri":
        return idx == 0 and not is_metadata_field(step, f["id"])
    return False


def _org_repo(repository: str) -> tuple[str | None, str | None]:
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", repository or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def _finish(step, registry_meta, prefill, provenance, manual, published_uri) -> dict:
    out = {
        "step": step,
        "template_key": registry_meta["key"],
        "template_uri": registry_meta["current"],
        "prefill": prefill,
    }
    if provenance:
        out["provenance"] = provenance
    if manual:
        out["manual"] = manual
    out["published_uri"] = published_uri
    return out


def build_step(step: str, spec: dict, registry_meta: dict, cff: dict,
               draft_text: str | None, published_uri: str | None, *,
               org: str | None = None, repo: str | None = None,
               cito_relation: str | None = None, resolve=None,
               drafts_label: str = "nanopubs/drafts") -> dict:
    prefill: dict = {}
    provenance: dict = {}
    manual: list[str] = []

    # The CiTO citation is a REQUIRED repeatable group. Its form field is `st02`,
    # an array of {cites, cited} — not flat cites/cited (see the component audit in
    # docs/chain-draft-contract.md). Prepare one row: the relation suggested from
    # the Outcome's validation status, cited = the replicated paper.
    if step == "06_citation":
        row: dict = {}
        if cito_relation:
            row["cites"] = cito_relation
        paper = metadata_value(step, "cited", cff)
        if paper:
            row["cited"] = paper
        if row:
            prefill["st02"] = [row]
            provenance["st02"] = ("cites = validation status (see 05_outcome); "
                                  "cited = CITATION.cff references[article]")
        return _finish(step, registry_meta, prefill, provenance, manual, published_uri)

    carried = carried_placeholders(step)
    for idx, f in enumerate(spec["fields"]):
        name = f["id"]
        if name in carried:
            continue                                   # wizard fills from a prior URI
        if f["kind"] == "restricted_choice":
            manual.append(name)                        # flag: agent's call, confirm it
            choice = draft_choice(draft_text, f) if draft_text else None
            if choice is not None:
                prefill[name] = choice                 # ...but pre-fill the recorded choice
                provenance[name] = f"{drafts_label}/{step}.md"
            continue
        wk = WIKIDATA_FIELDS.get((step, name))
        if wk:                                         # Wikidata concept field
            form_field, is_array = wk
            items = []
            if draft_text and resolve is not None:
                needs_concept = declares_concept_type(f)
                wk_alias = DRAFT_HEADING_ALIAS.get((step, name))
                wk_lookup = {"label": wk_alias} if wk_alias else f
                for label in draft_labels(draft_text, wk_lookup):
                    r = resolve(label, require_concept=needs_concept)
                    if r:
                        items.append(r)
            if items:
                prefill[form_field] = items if is_array else items[0]
                provenance[form_field] = f"{drafts_label}/{step}.md + Wikidata"
            continue
        rt = REPEATABLE_TEXT_FIELDS.get((step, name))
        if rt:                                         # repeatable plain-URL list
            form_field, heading = rt
            urls = draft_labels(draft_text, {"label": heading}) if draft_text else []
            if urls:
                prefill[form_field] = urls             # array of plain strings
                provenance[form_field] = f"{drafts_label}/{step}.md"
            continue
        mv = metadata_value(step, name, cff)
        if mv is not None:
            prefill[name] = mv
            provenance[name] = "CITATION.cff"
            continue
        if is_content_field(step, idx, f):
            alias = DRAFT_HEADING_ALIAS.get((step, name))
            lookup = {"label": alias} if alias else f
            val = draft_content(draft_text, lookup) if draft_text else None
            prov = f"{drafts_label}/{step}.md"
            if val is None and idx == 0 and f["kind"] == "uri":   # the id slug
                val = slug_for(step, org, repo)
                prov = "derived (<org>-<repo>-<step>)"
            if val is not None:
                prefill[name] = val
                provenance[name] = prov

    return _finish(step, registry_meta, prefill, provenance, manual, published_uri)


def detect_anchor(drafts_dir: Path) -> str:
    present = [a for a in ANCHORS if (drafts_dir / f"{a}.md").exists()]
    if len(present) == 1:
        return present[0]
    # Uninitialised template keeps all three; default to paper-rooted.
    return "01_quote"


def build_chain_draft(repo_root: Path, *, repository: str, commit: str,
                      resolve_wikidata=resolve_wikidata,
                      drafts_dir: Path | None = None) -> dict:
    templates = repo_root / "nanopubs" / "templates"
    registry = json.loads((templates / "registry.json").read_text())
    snapshot = json.loads((templates / "fields.snapshot.json").read_text())["steps"]
    # CITATION.cff / PUBLISHED.md / templates always come from repo_root; only the
    # drafts dir is overridable, so a second limb (e.g. nanopubs/drafts-turbidity/)
    # builds its own chain-draft.json against the same repo metadata. See --drafts-dir.
    if drafts_dir is None:
        drafts_dir = repo_root / "nanopubs" / "drafts"
    drafts_label = (drafts_dir.relative_to(repo_root).as_posix()
                    if drafts_dir.is_relative_to(repo_root) else str(drafts_dir))

    cff_path = repo_root / "CITATION.cff"
    cff = load_citation(cff_path.read_text()) if cff_path.exists() else {}
    pub_path = repo_root / "nanopubs" / "PUBLISHED.md"
    published = parse_published(pub_path.read_text()) if pub_path.exists() else {}

    anchor = detect_anchor(drafts_dir)
    step_ids = [anchor] + CORE_STEPS
    for opt in OPTIONAL_STEPS:                     # append only if actually drafted
        p = drafts_dir / f"{opt}.md"
        if p.exists() and draft_has_content(p.read_text(), snapshot.get(opt, {}), opt):
            step_ids.append(opt)

    org, repo = _org_repo(repository)
    steps = []
    outcome_status: str | None = None
    for step in step_ids:
        if step not in snapshot:
            continue
        dp = drafts_dir / f"{step}.md"
        # The citation type is suggested from the Outcome's validation status.
        relation = None
        if step == "06_citation" and outcome_status:
            relation = RELATION_FROM_STATUS.get(outcome_status.rsplit("/", 1)[-1])
        st = build_step(
            step, snapshot[step], registry["steps"][step], cff,
            dp.read_text() if dp.exists() else None, published.get(step[:2]),
            org=org, repo=repo, cito_relation=relation, resolve=resolve_wikidata,
            drafts_label=drafts_label,
        )
        if step == "05_outcome":
            outcome_status = st["prefill"].get("validationStatus")
        steps.append(st)

    carry = [{"from": a, "into": b, "field": CARRY_FIELD[b]}
             for a, b in zip(step_ids, step_ids[1:]) if b in CARRY_FIELD]
    present = set(step_ids)
    for target, links in BACK_LINKS.items():                # side-branch back-links
        if target not in present:
            continue
        for bl in links:
            if bl["from"] not in present:
                continue
            edge = {"from": bl["from"], "into": target, "field": bl["field"]}
            for k in ("mode", "itemKey"):
                if k in bl:
                    edge[k] = bl[k]
            carry.append(edge)

    source = {"repository": repository, "commit": commit}
    figure = find_figure(repo_root)
    if figure:
        source["figure"] = figure

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "forrt-chain-draft",
        "chain_shape": ANCHORS[anchor],
        "source": source,
        "steps": steps,
        "carry_forward": carry,
    }


FIGURE_DIR = "figures"
FIGURE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
# Names an author reaches for when one image is THE result. Kept in step with the
# platform's own resolver so both pick the same file out of a folder of several.
FIGURE_PREFERRED_RE = re.compile(r"main|result|headline|hero", re.I)


def find_figure(root: Path) -> str | None:
    """The repo's headline figure, as a repo-relative path, or None.

    Deterministic by construction: only ``figures/`` is scanned (never
    ``results/``, which collects run artefacts and diagnostics), candidates are
    sorted, and a name matching FIGURE_PREFERRED_RE wins over plain alphabetical
    order. Ties can't happen — filenames are unique within a directory.

    The story page the platform generates from the published chain resolves the
    figure the same way, from the repo behind the chain's Zenodo DOI. Committing
    the file is what makes it reachable: a figure written to a git-ignored path
    exists only on the machine that ran the experiment.
    """
    figures = root / FIGURE_DIR
    if not figures.is_dir():
        return None
    candidates = sorted(
        p for p in figures.iterdir()
        if p.is_file() and p.suffix.lower() in FIGURE_EXTS
    )
    if not candidates:
        return None
    preferred = [p for p in candidates if FIGURE_PREFERRED_RE.search(p.name)]
    chosen = (preferred or candidates)[0]
    return f"{FIGURE_DIR}/{chosen.name}"


def draft_has_content(text: str, spec: dict, step: str = "") -> bool:
    """Was this (optional) draft actually filled in? Mirrors build_step's routing
    so the same value would be extracted: content fields (with heading alias) and
    repeatable plain-URL lists both count."""
    for i, f in enumerate(spec.get("fields", [])):
        if is_content_field(step, i, f):
            alias = DRAFT_HEADING_ALIAS.get((step, f["id"]))
            if draft_content(text, {"label": alias} if alias else f) is not None:
                return True
        rt = REPEATABLE_TEXT_FIELDS.get((step, f["id"]))
        if rt and draft_labels(text, {"label": rt[1]}):
            return True
    return False


def _git(repo_root: Path, *args: str, default: str = "") -> str:
    try:
        return subprocess.run(["git", "-C", str(repo_root), *args],
                              capture_output=True, text=True, timeout=10).stdout.strip() or default
    except Exception:  # noqa: BLE001
        return default


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo-root", default=".", help="Repository root (default: cwd).")
    p.add_argument("-o", "--out", default=None,
                   help="Output path (default: <repo-root>/nanopubs/chain-draft.json).")
    p.add_argument("--drafts-dir", default=None,
                   help="Drafts directory (default: <repo-root>/nanopubs/drafts). Point "
                        "at a sibling set (e.g. nanopubs/drafts-turbidity/) to build a "
                        "second limb's chain from the same CITATION.cff and templates.")
    args = p.parse_args(argv)

    root = Path(args.repo_root).resolve()
    repo_url = _git(root, "config", "--get", "remote.origin.url",
                    default=f"https://github.com/OWNER/{root.name}")
    repo_url = re.sub(r"^git@github\.com:", "https://github.com/", repo_url)
    repo_url = re.sub(r"\.git$", "", repo_url)
    commit = _git(root, "rev-parse", "HEAD", default="HEAD")

    drafts_dir = Path(args.drafts_dir).resolve() if args.drafts_dir else None
    draft = build_chain_draft(root, repository=repo_url, commit=commit,
                              drafts_dir=drafts_dir)
    out = Path(args.out) if args.out else root / "nanopubs" / "chain-draft.json"
    out.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n")

    filled = sum(len(s["prefill"]) for s in draft["steps"])
    print(f"Wrote {out} — {len(draft['steps'])} steps, {filled} fields pre-filled "
          f"({draft['chain_shape']}).", file=sys.stderr)
    figure = draft["source"].get("figure")
    if figure:
        print(f"Headline figure: {figure}", file=sys.stderr)
    else:
        print(f"No headline figure found in {FIGURE_DIR}/ — the published chain's "
              f"story page will have no image. Commit one image there (a "
              f"git-ignored figure does not count).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
