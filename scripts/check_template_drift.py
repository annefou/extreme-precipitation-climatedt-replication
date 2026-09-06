#!/usr/bin/env python3
"""Fail when a FORRT chain-step template drifts from the committed snapshot.

The templates in `nanopubs/templates/registry.json` are the schema for the six
FORRT chain steps (plus the PICO/PCC anchors, Research Software and Synthesis).
`fields.snapshot.json` pins each current template's extracted field spec. This
script fetches the live templates from the nanopub network, extracts their specs
with `template_fields.py`, and diffs them against the snapshot:

    pixi run -e tests python scripts/check_template_drift.py            # check, exit 1 on drift
    pixi run -e tests python scripts/check_template_drift.py --update   # re-vendor the snapshot

Drift is expected and legitimate — it means a template was superseded upstream.
When it happens, a human runs `--update`, reviews the JSON diff (which is exactly
the set of field / vocabulary / cap changes that would otherwise have silently
rotted `docs/forrt-form-fields.md` and the drafts), updates those hand docs to
match, and commits the new snapshot. The point is that the drift becomes a
loud, reviewable event instead of a slow divergence nobody notices.

This is the ONLY networked piece of the toolchain, so it is NOT wired into the
per-PR CI gate (which is deliberately network-free). It runs on a schedule and
on demand — see .github/workflows/template-drift.yml. The extractor it depends
on is covered offline by tests/test_template_fields.py.

Dependency: rdflib (via template_fields), stdlib otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from template_fields import parse_template, spec_to_dict  # noqa: E402

HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE.parent / "nanopubs" / "templates"
REGISTRY = TEMPLATES_DIR / "registry.json"
SNAPSHOT = TEMPLATES_DIR / "fields.snapshot.json"


def fetch_trig(uri: str, *, timeout: int = 30) -> str:
    """Fetch a nanopub's TriG. The bare `w3id.org/np/` form serves RDF; the
    `/sciencelive/np/` form redirects to an HTML viewer, so normalise to bare."""
    resolver = uri.replace("/sciencelive/np/", "/np/")
    req = urllib.request.Request(resolver, headers={"Accept": "application/trig"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def live_specs(registry: dict, *, timeout: int = 30) -> dict:
    """Fetch + extract the field spec of every current template, keyed by step."""
    specs: dict = {}
    for step, meta in registry["steps"].items():
        uri = meta["current"]
        print(f"  fetch {step:<22} {uri}", file=sys.stderr)
        trig = fetch_trig(uri, timeout=timeout)
        specs[step] = spec_to_dict(parse_template(trig, uri))
    return specs


# --- diffing -------------------------------------------------------------

def _fields_by_id(spec: dict) -> dict:
    return {f["id"]: f for f in spec.get("fields", [])}


def diff_step(step: str, snap: dict | None, live: dict | None) -> list[str]:
    """Human-readable drift lines for one step ([] == no drift)."""
    if snap is None:
        return [f"[{step}] NEW in registry — not in snapshot (run --update)"]
    if live is None:
        return [f"[{step}] in snapshot but not fetched live"]

    out: list[str] = []
    if snap.get("template_uri") != live.get("template_uri"):
        out.append(f"[{step}] template_uri: {snap.get('template_uri')} -> {live.get('template_uri')}")
    if snap.get("label") != live.get("label"):
        out.append(f"[{step}] label: {snap.get('label')!r} -> {live.get('label')!r}")

    snap_f, live_f = _fields_by_id(snap), _fields_by_id(live)
    for fid in [f["id"] for f in snap.get("fields", []) if f["id"] not in live_f]:
        out.append(f"[{step}] field removed: {fid}")
    for fid in [f["id"] for f in live.get("fields", []) if f["id"] not in snap_f]:
        out.append(f"[{step}] field added:   {fid}")
    for fid in [f["id"] for f in snap.get("fields", []) if f["id"] in live_f]:
        a, b = snap_f[fid], live_f[fid]
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                out.append(f"[{step}] field {fid}.{key}: {a.get(key)!r} -> {b.get(key)!r}")
    # Order changes matter (form order): flag if the id sequence differs.
    if [f["id"] for f in snap.get("fields", [])] != [f["id"] for f in live.get("fields", [])] \
            and not any("field removed" in l or "field added" in l for l in out):
        out.append(f"[{step}] field order changed")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--update", action="store_true",
                   help="Re-fetch the live templates and overwrite fields.snapshot.json.")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout per fetch (s).")
    args = p.parse_args(argv)

    registry = json.loads(REGISTRY.read_text())

    try:
        specs = live_specs(registry, timeout=args.timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"ERROR: could not fetch templates ({e}). Network required.", file=sys.stderr)
        return 2

    if args.update:
        payload = {
            "_comment": (
                "Extracted field spec of each current FORRT chain-step template. "
                "GENERATED by scripts/check_template_drift.py --update from the URIs in "
                "registry.json — do not hand-edit. When this changes, a template was "
                "superseded upstream; update docs/forrt-form-fields.md to match."
            ),
            "steps": specs,
        }
        SNAPSHOT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote {SNAPSHOT} ({len(specs)} templates).", file=sys.stderr)
        return 0

    if not SNAPSHOT.exists():
        print(f"ERROR: {SNAPSHOT} missing. Run --update to create it.", file=sys.stderr)
        return 2
    snapshot = json.loads(SNAPSHOT.read_text()).get("steps", {})

    drift: list[str] = []
    for step in sorted(set(snapshot) | set(specs)):
        drift.extend(diff_step(step, snapshot.get(step), specs.get(step)))

    if drift:
        print("TEMPLATE DRIFT DETECTED — the live templates no longer match the snapshot:\n",
              file=sys.stderr)
        print("\n".join(drift), file=sys.stderr)
        print("\nThis usually means a template was superseded upstream. Re-vendor with "
              "`--update`, reconcile docs/forrt-form-fields.md + nanopubs/drafts/ with the "
              "changes above, and commit the new snapshot.", file=sys.stderr)
        return 1

    print(f"OK — {len(specs)} templates match the snapshot.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
