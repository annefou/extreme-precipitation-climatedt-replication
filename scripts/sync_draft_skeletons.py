#!/usr/bin/env python3
"""Regenerate the field headings in ``nanopubs/drafts/*.md`` from the templates.

The templates are the schema. A draft skeleton restates their field list so a
person has somewhere to write, and that restatement is the one part of a draft
that duplicates the templates — so it is the one part that drifts. It did: the
skeletons were written from ``docs/forrt-form-fields.md`` (the platform's UI
wording, "Quoted Text") while ``build_chain_draft.py`` matches the template's
own label ("The exact quotation from the paper"), and eight fields silently
extracted nothing from a filled draft.

This script removes that class of bug rather than patching instances of it. It
regenerates each field's ``###`` heading from the template label, so a heading
cannot disagree with the template it is generated from, and rewrites
restricted-choice option lists from the template vocabulary.

Everything a human wrote is preserved: the preamble, the per-field guidance
prose, the values already drafted, and the trailing notes. Sections are matched
by a ``<!-- field: id -->`` marker, so preservation survives a template renaming
a label — the case plain text-matching cannot handle. A draft with no markers
yet is adopted by label on the first run, and emitted with markers afterwards.

    pixi run sync-drafts            # rewrite the skeletons
    pixi run sync-drafts --check    # fail if they are out of date (CI)

Offline: reads the committed snapshot, never the network. Run it after
``check_template_drift.py --update`` re-vendors that snapshot.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_chain_draft import (  # noqa: E402  (one normaliser + the same maps)
    DRAFT_HEADING_ALIAS,
    REPEATABLE_TEXT_FIELDS,
    _norm,
)

MARKER_RE = re.compile(r"^<!--\s*field:\s*([A-Za-z0-9_-]+)\s*-->\s*$")
FIELD_HEADING_RE = re.compile(r"^###\s+")
SECTION_END_RE = re.compile(r"^##\s+")          # a level-2 heading ends the field area

# How each template placeholder kind presents in the platform form. Shown in the
# heading so a drafter knows what they are filling; `_norm` drops parentheticals,
# so this hint never affects matching.
KIND_HINT = {
    "literal": "text input",
    "long_literal": "textarea",
    "uri": "text input",
    "external_uri": "text input",
    "auto_escape_uri": "text input",
    "guided_choice": "search/select",
    "restricted_choice": "dropdown",
}


# Template fields the draft deliberately does NOT give their own section: the
# platform renders them inside a repeatable group, and the draft mirrors that.
# 06's citation rows carry a relation and a target each, under "List citations".
# Without this the generator would append flat sections for them and the draft
# would ask for the same thing twice.
GROUPED_FIELDS = {
    ("06_citation", "cites"),
    ("06_citation", "cited"),
}


def draft_label(step_id: str, field: dict) -> str:
    """The wording a draft should use for this field.

    Normally the template's own label — that is the whole point, since
    ``build_chain_draft`` matches against it. Two maps in build_chain_draft
    deliberately override it: DRAFT_HEADING_ALIAS where the template's label is
    wrong or unhelpful for a person (08_synthesis's "outcome ID" slip), and
    REPEATABLE_TEXT_FIELDS where the draft collects a bullet list under its own
    heading. Honour both, or this generator would rewrite the heading to
    something the reader cannot match."""
    alias = DRAFT_HEADING_ALIAS.get((step_id, field["id"]))
    if alias:
        return alias
    repeatable = REPEATABLE_TEXT_FIELDS.get((step_id, field["id"]))
    if repeatable:
        return repeatable[1]
    return field["label"]


def heading_for(step_id: str, field: dict) -> str:
    """The generated ``###`` line for a template field."""
    hint = KIND_HINT.get(field["kind"], field["kind"])
    req = "required" if field.get("required") else "optional"
    label = draft_label(step_id, field)
    # Sentence-case the template's own wording ("label of the claim, to find it
    # later"). `_norm` lowercases, so this is cosmetic only and never affects
    # whether build_chain_draft finds the heading.
    label = label[:1].upper() + label[1:] if label else label
    return f"### {label} ({hint}, {req})"


def options_for(field: dict, ticked: set[str] | None = None) -> list[str]:
    """Checkbox list for a restricted-choice field, from the template vocabulary.

    Options whose label was already ticked stay ticked: the selection is a human
    choice that build_chain_draft reads to pre-fill the wizard, not template text
    to redraw blank. Labels are matched normalised, so a cosmetic difference
    (parentheticals, case) does not lose the tick."""
    ticked = ticked or set()
    out = []
    for v in field.get("possible_values") or []:
        label = v["label"] if isinstance(v, dict) else v
        mark = "x" if _norm(label) in ticked else " "
        out.append(f"- [{mark}] {label}")
    return out


def split_draft(text: str) -> tuple[list[str], list[dict], list[str]]:
    """(preamble, sections, trailer). A section is one ``###`` field block."""
    lines = text.split("\n")
    preamble: list[str] = []
    sections: list[dict] = []
    trailer: list[str] = []
    i, n = 0, len(lines)

    while i < n and not FIELD_HEADING_RE.match(lines[i]):
        preamble.append(lines[i])
        i += 1
    # a marker immediately before the first heading belongs to it, not the preamble
    while preamble and MARKER_RE.match(preamble[-1]):
        i -= 1
        preamble.pop()
    while preamble and not preamble[-1].strip():
        preamble.pop()

    while i < n:
        marker = None
        if MARKER_RE.match(lines[i]):
            marker = MARKER_RE.match(lines[i]).group(1)
            i += 1
        if i >= n or not FIELD_HEADING_RE.match(lines[i]):
            break
        heading = lines[i]
        i += 1
        body: list[str] = []
        while i < n:
            if MARKER_RE.match(lines[i]) or FIELD_HEADING_RE.match(lines[i]):
                break
            if SECTION_END_RE.match(lines[i]):
                break
            body.append(lines[i])
            i += 1
        sections.append({"id": marker, "heading": heading, "body": body})
        if i < n and SECTION_END_RE.match(lines[i]):
            trailer = lines[i:]
            break

    while sections and not sections[-1]["body"] or (
        sections and sections[-1]["body"] and not sections[-1]["body"][-1].strip()
    ):
        if sections[-1]["body"] and not sections[-1]["body"][-1].strip():
            sections[-1]["body"].pop()
        else:
            break
    return preamble, sections, trailer


def adopt(step_id: str, sections: list[dict], fields: list[dict]) -> dict[int, dict]:
    """section index -> the template field it carries, by marker then by label.

    Label adoption is the one-time bootstrap for skeletons written before markers
    existed; once a draft is emitted with markers, ids do the work and a template
    relabelling no longer loses the prose."""
    owner: dict[int, dict] = {}
    claimed: set[str] = set()
    by_id = {f["id"]: f for f in fields}

    for idx, s in enumerate(sections):          # markers are authoritative
        if s["id"] and s["id"] in by_id:
            owner[idx] = by_id[s["id"]]
            claimed.add(s["id"])

    for idx, s in enumerate(sections):          # then bootstrap by label
        if idx in owner:
            continue
        hk = _norm(re.sub(r"^###\s+", "", s["heading"]))
        for field in fields:
            if field["id"] in claimed:
                continue
            key = _norm(draft_label(step_id, field))
            if hk and key and (hk in key or key in hk):
                owner[idx] = field
                claimed.add(field["id"])
                break
    return owner


def _trim(lines: list[str]) -> list[str]:
    """Drop trailing blank lines. Each section is emitted with a leading blank,
    so keeping the body's trailing one too would add a line on every run and the
    generator would never reach a fixed point."""
    out = list(lines)
    while out and not out[-1].strip():
        out.pop()
    return out


def render(step_id: str, body: dict, draft_text: str) -> tuple[str, list[str], list[str]]:
    """Rewrite a draft's field headings from the templates. Non-destructive:
    sections are walked in their existing order and only the heading line of a
    recognised field is replaced. A section this script cannot place is emitted
    verbatim and reported — losing a researcher's guidance to a parsing miss
    would be a far worse bug than the drift this fixes."""
    fields = body.get("fields", [])
    preamble, sections, trailer = split_draft(draft_text)
    owner = adopt(step_id, sections, fields)

    out = list(preamble)
    for idx, section in enumerate(sections):
        field = owner.get(idx)
        if field is None:                       # unrecognised — keep exactly as-is
            out += ["", section["heading"]] + _trim(section["body"])
            continue
        out += ["", f"<!-- field: {field['id']} -->", heading_for(step_id, field)]
        kept = list(section["body"])
        if field["kind"] == "restricted_choice" and options_for(field):
            # the vocabulary belongs to the template; keep the prose AND the
            # drafter's tick, redraw the list. The tick is a human choice
            # build_chain_draft reads — preserve it like a fenced value.
            ticked = {
                _norm(m.group(1))
                for ln in kept
                if (m := re.match(r"^- \[[xX]\] (.+)$", ln))
            }
            kept = [ln for ln in kept if not re.match(r"^- \[[ xX]\] ", ln)]
            while kept and not kept[-1].strip():
                kept.pop()
            kept += [""] + options_for(field, ticked)
        out += _trim(kept)

    placed = {f["id"] for f in owner.values()}
    added = []
    for field in fields:                        # a template field with no section
        if field["id"] in placed or (step_id, field["id"]) in GROUPED_FIELDS:
            continue
        added.append(field["id"])
        out += ["", f"<!-- field: {field['id']} -->", heading_for(step_id, field), "",
                "_New field from the template — add guidance, then the value below._"]
        out += ([""] + options_for(field) if field["kind"] == "restricted_choice"
                else ["", "```", "", "```"])

    orphans = [re.sub(r"^###\s+", "", sections[i]["heading"])
               for i in range(len(sections)) if i not in owner]
    if trailer:
        out += [""] + trailer
    return "\n".join(out).rstrip("\n") + "\n", orphans, added


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--repo-root", default=".")
    p.add_argument("--check", action="store_true",
                   help="Exit 1 if any skeleton would change; write nothing.")
    args = p.parse_args(argv)

    root = Path(args.repo_root).resolve()
    snapshot = json.loads(
        (root / "nanopubs" / "templates" / "fields.snapshot.json").read_text())
    stale, changed = [], []

    for step_id, body in snapshot["steps"].items():
        path = root / "nanopubs" / "drafts" / f"{step_id}.md"
        if not path.exists():
            continue
        current = path.read_text()
        new, orphans, added = render(step_id, body, current)
        for heading in orphans:
            print(f"{step_id}: kept section {heading!r} as-is — it matches no "
                  f"template field. Check whether it is still wanted.", file=sys.stderr)
        for fid in added:
            print(f"{step_id}: added new template field {fid!r} — it needs guidance "
                  f"and a value.", file=sys.stderr)
        if new != current:
            (stale if args.check else changed).append(step_id)
            if not args.check:
                path.write_text(new)

    if args.check and stale:
        print(f"Draft skeletons are out of date with the templates: "
              f"{', '.join(stale)}. Run `pixi run sync-drafts`.", file=sys.stderr)
        return 1
    print(f"{'Would rewrite' if args.check else 'Rewrote'} "
          f"{len(stale or changed)} skeleton(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
