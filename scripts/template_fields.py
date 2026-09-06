#!/usr/bin/env python3
"""Extract the field specification from a Science Live nanopub *template*.

A nanopub template is itself a nanopublication whose assertion graph is an
`nt:AssertionTemplate`: a set of `nt:hasStatement` triples, each a reified
`(rdf:subject, rdf:predicate, rdf:object)` in which one or more terms is a typed
*placeholder* — a literal input, a URI input, or a restricted/guided choice.
The placeholder's `rdfs:label` is the field prompt; `nt:OptionalStatement` /
`nt:RepeatableStatement` mark its statement (and so its field) optional /
repeatable; a choice placeholder enumerates or points at its allowed values;
`nt:hasRegex` / `nt:hasPrefix` / `nt:hasDatatype` carry the input constraints
(this is where a Quote's 500-char / 800-char caps actually live).

That structure *is* the schema for the corresponding FORRT chain step. This
module turns it into a plain, ordered `list[Field]` so the rest of the toolchain
(the committed snapshot, the drift check, the drafter docs) can be pinned to the
template instead of to a hand transcription that silently drifts from it. See
`docs/forrt-form-fields.md` and `nanopubs/templates/`.

Pure function over TriG text → spec. No network here; fetching lives in
`check_template_drift.py`, so this stays offline-testable against the committed
fixtures in `tests/fixtures/`.

Dependency: `rdflib` (declared in pixi.toml). Parsing RDF with a regex is
exactly the hand-rolled fragility this tier exists to remove, so we parse it as
RDF.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rdflib import RDF, RDFS, Dataset, Graph, Namespace
from rdflib.term import Literal, URIRef

NT = Namespace("https://w3id.org/np/o/ntemplate/")

# Placeholder rdf:type → the `kind` we report, in priority order (a node can
# carry several types at once, e.g. IntroducedResource + LocalResource +
# UriPlaceholder; the first match wins, so list the specific input kinds first).
_PLACEHOLDER_KINDS = [
    (NT.RestrictedChoicePlaceholder, "restricted_choice"),
    (NT.GuidedChoicePlaceholder, "guided_choice"),
    (NT.ExternalUriPlaceholder, "external_uri"),
    (NT.AutoEscapeUriPlaceholder, "auto_escape_uri"),
    (NT.UriPlaceholder, "uri"),
    (NT.LongLiteralPlaceholder, "long_literal"),
    (NT.LiteralPlaceholder, "literal"),
]


@dataclass
class Choice:
    uri: str
    label: str


@dataclass
class Field:
    """One form field, derived from a placeholder term of one statement."""
    id: str                 # local placeholder name, e.g. "forrtType"
    label: str              # rdfs:label — the prompt shown to the user
    kind: str               # see _PLACEHOLDER_KINDS
    required: bool          # False when the statement is nt:OptionalStatement
    repeatable: bool = False  # True when the statement is nt:RepeatableStatement
    predicate: str = ""     # the statement predicate (context for the field)
    possible_values: list[Choice] = field(default_factory=list)  # inline possibleValue
    values_from: list[str] = field(default_factory=list)      # possibleValuesFrom — value-list nanopub(s)
    values_from_api: list[str] = field(default_factory=list)  # possibleValuesFromApi — search API(s)
    regex: str | None = None             # nt:hasRegex — length / format constraint
    prefix: str | None = None            # nt:hasPrefix — required URI prefix
    datatype: str | None = None          # nt:hasDatatype


@dataclass
class TemplateSpec:
    template_uri: str
    label: str              # the AssertionTemplate's rdfs:label (the template title)
    tag: str | None         # nt:hasTag, e.g. "FORRT"
    fields: list[Field]


def _local(term: URIRef, template_uri: str) -> str:
    """Short name for a placeholder node: strip the template's `sub:` base."""
    s = str(term)
    for base in (f"{template_uri}/", f"{template_uri}#", template_uri):
        if s.startswith(base):
            return s[len(base):] or s
    return s.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _all(graph: Graph, node, pred) -> list[str]:
    """All values of `pred`, sorted. rdflib's store iteration order depends on
    term hashing (so it varies with PYTHONHASHSEED across processes); sorting
    makes the extracted spec deterministic. Several placeholder properties are
    genuinely multi-valued — e.g. a guided choice with both a nanopub-query and
    a Wikidata `possibleValuesFromApi`."""
    return sorted(str(o) for o in graph.objects(node, pred))


def _first(graph: Graph, node, pred) -> str | None:
    """Deterministic single value (first after sorting), or None."""
    vals = _all(graph, node, pred)
    return vals[0] if vals else None


def _label(graph: Graph, node) -> str:
    labels = sorted(str(o) for o in graph.objects(node, RDFS.label) if isinstance(o, Literal))
    return labels[0] if labels else ""


def _placeholder_kind(graph: Graph, node) -> str | None:
    if not isinstance(node, URIRef):
        return None
    types = set(graph.objects(node, RDF.type))
    for type_uri, kind in _PLACEHOLDER_KINDS:
        if type_uri in types:
            return kind
    return None


def _statement_order_key(name: str) -> tuple:
    """Order statements by their local name (st00, st00.2, st01, …) so the
    field order matches the on-screen form. Non-`st` names sort last, by name."""
    digits = name[2:] if name.startswith("st") else name
    try:
        return (0, tuple(int(p) for p in digits.split(".")))
    except ValueError:
        return (1, (0,), name)


def _build_field(graph, term, template_uri, *, required, repeatable, predicate) -> Field:
    kind = _placeholder_kind(graph, term)
    values: list[Choice] = []
    if kind == "restricted_choice":
        for v in graph.objects(term, NT.possibleValue):
            values.append(Choice(uri=str(v), label=_label(graph, v)))
        values.sort(key=lambda c: c.uri)  # deterministic snapshot order
    return Field(
        id=_local(term, template_uri),
        label=_label(graph, term),
        kind=kind or "",
        required=required,
        repeatable=repeatable,
        predicate=predicate,
        possible_values=values,
        values_from=_all(graph, term, NT.possibleValuesFrom),
        values_from_api=_all(graph, term, NT.possibleValuesFromApi),
        regex=_first(graph, term, NT.hasRegex),
        prefix=_first(graph, term, NT.hasPrefix),
        datatype=_first(graph, term, NT.hasDatatype),
    )


def parse_template(trig_text: str, template_uri: str) -> TemplateSpec:
    """Parse a template nanopub's TriG into an ordered `TemplateSpec`.

    `template_uri` is the nanopub's own URI (the `this:` subject), used to
    resolve `sub:`-relative placeholder names to short ids.
    """
    # TriG parsing needs a context-aware store, so parse into a Dataset, then
    # flatten every named graph into one plain Graph. Querying the plain Graph
    # keeps all triples in view (the template's field labels and value labels
    # live in the assertion graph) without touching rdflib's deprecated
    # union-context query path.
    dataset = Dataset()
    dataset.parse(data=trig_text, format="trig")
    graph = Graph()
    for ctx in dataset.graphs():
        graph += ctx

    tmpl_nodes = sorted(graph.subjects(RDF.type, NT.AssertionTemplate), key=str)
    if not tmpl_nodes:
        raise ValueError("no nt:AssertionTemplate found — not a template nanopub")
    tmpl = tmpl_nodes[0]
    tag = _first(graph, tmpl, NT.hasTag)

    # nt:hasStatement is an unordered RDF property; the statement *nodes* carry
    # the intended order in their local names. Sort by that.
    statements = sorted(
        graph.objects(tmpl, NT.hasStatement),
        key=lambda s: _statement_order_key(_local(s, template_uri)),
    )

    fields: list[Field] = []
    seen: set[str] = set()
    for stmt in statements:
        stmt_types = set(graph.objects(stmt, RDF.type))
        required = NT.OptionalStatement not in stmt_types
        repeatable = NT.RepeatableStatement in stmt_types
        predicate = next(graph.objects(stmt, RDF.predicate), None)
        pred_str = str(predicate) if predicate else ""

        # A statement can carry a placeholder in any of its three positions
        # (the CiTO template puts the citation-type choice in the *predicate*).
        # Collect every placeholder term, once each, in S-P-O reading order.
        for role in (RDF.subject, RDF.predicate, RDF.object):
            term = next(graph.objects(stmt, role), None)
            if _placeholder_kind(graph, term) is None:
                continue
            fid = _local(term, template_uri)
            if fid in seen:
                continue
            seen.add(fid)
            fields.append(_build_field(
                graph, term, template_uri,
                required=required, repeatable=repeatable, predicate=pred_str,
            ))

    return TemplateSpec(
        template_uri=template_uri,
        label=_label(graph, tmpl),
        tag=tag,
        fields=fields,
    )


def spec_to_dict(spec: TemplateSpec) -> dict:
    """JSON-serialisable form, with empty/default fields dropped for a clean snapshot."""
    out: dict = {"template_uri": spec.template_uri, "label": spec.label}
    if spec.tag:
        out["tag"] = spec.tag
    out["fields"] = []
    for f in spec.fields:
        d: dict = {"id": f.id, "label": f.label, "kind": f.kind, "required": f.required}
        if f.repeatable:
            d["repeatable"] = True
        if f.predicate:
            d["predicate"] = f.predicate
        if f.possible_values:
            d["possible_values"] = [asdict(c) for c in f.possible_values]
        for key, val in (("values_from", f.values_from),
                         ("values_from_api", f.values_from_api),
                         ("regex", f.regex), ("prefix", f.prefix),
                         ("datatype", f.datatype)):
            if val:
                d[key] = val
        out["fields"].append(d)
    return out


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: template_fields.py <template.trig> <template-uri>", file=sys.stderr)
        return 2
    spec = parse_template(Path(argv[0]).read_text(), argv[1])
    print(json.dumps(spec_to_dict(spec), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
