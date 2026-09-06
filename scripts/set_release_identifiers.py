#!/usr/bin/env python3
"""Write a release's persistent identifiers into this repo's metadata files.

Run once per release, from .github/workflows/release-identifiers.yml. Given the
repository, the tag, and the tag's *commit*, this resolves and records:

  * the **version DOI**  — pins this exact release forever
  * the **concept DOI**  — names the project, resolves to whatever is latest
  * the **SWHID**        — forge-agnostic identity of the exact source tree

into CITATION.cff, codemeta.json and ro-crate-metadata.json, from one lookup,
in one fixed shape.

WHY THIS EXISTS
---------------
Every one of these identifiers already existed at release time and none of them
were captured. The version DOI was minted by Zenodo alongside the concept DOI
and then dropped on the floor; the SWHID was never even retrieved. What got
recorded, by hand, was the concept DOI — the one identifier that is *designed to
move*. Two repos built from this template recorded the version DOI two different
ways (one a structured CITATION.cff identifier, one a prose comment) because
CITATION.cff said "run /init-template again or edit by hand" and /init-template
deletes itself as its last step. So "edit by hand" was the only surviving path,
and hands improvise.

The distinction is not pedantry. A **concept DOI resolves to the latest
version**. When it appears in a signed, immutable nanopub as "the software that
produced this outcome", the assertion silently starts describing different code
the moment a v0.2.0 is cut — with no signature breakage and no edit path, since
nanopubs can only be retracted or superseded. The **version DOI** is what pins a
snapshot, and it must be what the Outcome and Research Software nanopubs cite.

ROLES (do not mix these up)
---------------------------
  concept DOI  -> CITATION.cff `doi:`         "cite this project"  (floating is CORRECT here)
  version DOI  -> nanopubs, RO-Crate          "this exact code produced this number"
  SWHID        -> preservation-backed identity, survives the forge disappearing

Idempotent: re-running with the same inputs rewrites the same bytes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

try:
    from ruamel.yaml import YAML
except ImportError:  # pragma: no cover - environment problem, not logic
    sys.exit(
        "ruamel.yaml is required (it round-trips YAML *with* comments; pyyaml would\n"
        "silently delete every explanatory comment in CITATION.cff).\n"
        "Install with: pixi add ruamel.yaml"
    )

ZENODO_API = "https://zenodo.org/api/records"
SWH_RESOLVE = "https://archive.softwareheritage.org/api/1/resolve"

Fetcher = Callable[[str], dict]


# --------------------------------------------------------------------------
# network seam — every network call goes through this one function so the
# whole module is testable against fixtures with no HTTP.
# --------------------------------------------------------------------------
def http_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def swhid_for(commit: str, origin: str) -> str:
    """Build the SWHID of a git commit.

    Software Heritage reuses git's object hashing, so a revision's SWHID *is*
    the commit SHA — no API round-trip, no waiting for the archival visit.

    The `;origin=` qualifier is not decoration: a bare swh:1:rev: is globally
    unique but says nothing about where the code came from, and SWH's own
    citation guidance is to qualify it.

    NOTE the trap this function exists to avoid: for an ANNOTATED tag,
    `git rev-parse v0.1.0` returns the *tag object*, not the commit. Feeding
    that here yields swh:1:rev:<tagobj>, which is well-formed and resolves to
    NOTHING. The caller must pass `git rev-parse "<tag>^{commit}"`.
    """
    if len(commit) != 40 or not all(c in "0123456789abcdef" for c in commit.lower()):
        raise ValueError(
            f"{commit!r} is not a 40-hex-char git commit SHA. If this came from "
            f'`git rev-parse <tag>` on an annotated tag it is the tag object — '
            f'use `git rev-parse "<tag>^{{commit}}"` instead.'
        )
    return f"swh:1:rev:{commit.lower()};origin={origin}"


def find_zenodo_record(
    repo: str,
    tag: str,
    fetch: Fetcher = http_json,
    attempts: int = 10,
    delay: int = 30,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Resolve the Zenodo record for a GitHub release.

    The GitHub->Zenodo webhook stamps the exact tree URL into the record's
    related_identifiers, which makes this an exact lookup rather than a title
    guess:

        {"identifier": "https://github.com/OWNER/REPO/tree/TAG",
         "relation": "isSupplementTo", "scheme": "url"}

    The `metadata.` prefix on the query field is required — `related_identifiers.
    identifier:"..."` (without it) silently returns zero hits rather than an error.

    Polls because the webhook mints the record *concurrently* with the release
    event that triggers this workflow, so the record frequently does not exist
    for the first few seconds.
    """
    tree = f"https://github.com/{repo}/tree/{tag}"
    query = urllib.parse.urlencode(
        {"q": f'metadata.related_identifiers.identifier:"{tree}"', "size": "5"}
    )
    url = f"{ZENODO_API}?{query}"

    for attempt in range(1, attempts + 1):
        try:
            hits = fetch(url).get("hits", {}).get("hits", [])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            hits = []
            print(f"  attempt {attempt}/{attempts}: Zenodo lookup failed ({e})", file=sys.stderr)
        else:
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                dois = ", ".join(h.get("doi", "?") for h in hits)
                raise SystemExit(
                    f"Zenodo returned {len(hits)} records for {tree} ({dois}). "
                    f"Refusing to guess which one pins this release."
                )
            print(f"  attempt {attempt}/{attempts}: no Zenodo record for {tree} yet", file=sys.stderr)
        if attempt < attempts:
            sleep(delay)

    raise SystemExit(
        f"No Zenodo record found for {tree} after {attempts} attempts.\n"
        f"Either the GitHub<->Zenodo webhook is not enabled for this repository "
        f"(check https://zenodo.org/account/settings/github/), or it has not "
        f"minted the record yet. Re-run this workflow once the Zenodo record exists."
    )


def extract_dois(record: dict) -> tuple[str, str]:
    """Pull (version_doi, concept_doi) out of a Zenodo record.

    Zenodo mints BOTH at once: `doi` is this version, `conceptdoi` names the
    project across versions. Adjacent integers, entirely different semantics.
    """
    version_doi = record.get("doi")
    concept_doi = record.get("conceptdoi")
    if not version_doi:
        raise SystemExit(f"Zenodo record has no `doi` field: {json.dumps(record)[:300]}")
    if not concept_doi:
        raise SystemExit(
            f"Zenodo record {version_doi} has no `conceptdoi`. That normally means the "
            f"deposit was made outside Zenodo's versioning (no concept record), which "
            f"this template does not support — its CITATION.cff `doi:` is defined as the "
            f"concept DOI."
        )
    return version_doi, concept_doi


# --------------------------------------------------------------------------
# writers — each takes the parsed file and mutates it in place
# --------------------------------------------------------------------------
def update_citation_cff(path: Path, version_doi: str, concept_doi: str, swhid: str, tag: str) -> None:
    """CITATION.cff: `doi:` stays the CONCEPT doi (floating is right for "cite
    this project"); `identifiers:` gains the version DOI and the SWHID.

    `swh` is a first-class CFF 1.2.0 identifier type, so this is not a hack.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    # Default width wraps long scalars onto continuation lines. Semantically
    # harmless, but a wrapped SWHID is unreadable to a human skimming the file
    # for the value to paste into a nanopub form.
    yaml.width = 4096
    data = yaml.load(path.read_text())

    data["doi"] = concept_doi

    wanted = [
        ("doi", concept_doi, "Concept DOI (resolves to the latest version) — cite the project"),
        ("doi", version_doi, f"Version DOI for {tag} — pins this exact release; cite this from nanopubs"),
        ("swh", swhid, f"Software Heritage ID of the {tag} source tree"),
    ]

    existing = data.get("identifiers") or []
    # Replace wholesale rather than append: re-running must not accumulate
    # duplicate or stale entries. Anything we do not own (a user's own extra
    # identifier) is preserved — EXCEPT unsubstituted template placeholders.
    #
    # That exception is not hypothetical: init-template deliberately leaves
    # {{ZENODO_DOI}} in place ("minted at first release"), so every real repo
    # reaches this code with a placeholder identifier entry still present. Without
    # this filter it survives alongside the real DOIs, and CITATION.cff ships a
    # literal "{{ZENODO_DOI}}" as a citable identifier. (lint.yml would catch it
    # on the commit-back, but producing it and then failing CI is worse than not
    # producing it.)
    ours = {concept_doi, version_doi, swhid}

    def is_placeholder(entry) -> bool:
        return "{{" in str(entry.get("value", ""))

    kept = [e for e in existing if e.get("value") not in ours and not is_placeholder(e)]
    rebuilt = [{"type": t, "value": v, "description": d} for t, v, d in wanted] + kept
    data["identifiers"] = rebuilt

    with path.open("w") as fh:
        yaml.dump(data, fh)


def update_codemeta(path: Path, version_doi: str, concept_doi: str, swhid: str) -> None:
    """codemeta.json: `@id` stays the concept DOI (stable project identity);
    `identifier` becomes the full list so a machine reading codemeta — which is
    the machine-readable surface, and what Replication Radar's FAIR check reads —
    can see the pinned version and the preservation identity, not just the
    floating one.
    """
    data = json.loads(path.read_text())
    data["@id"] = f"https://doi.org/{concept_doi}"
    data["identifier"] = [
        f"https://doi.org/{concept_doi}",
        f"https://doi.org/{version_doi}",
        swhid,
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def update_ro_crate(path: Path, version_doi: str, swhid: str, tag: str) -> None:
    """RO-Crate root entity: `identifier` + `version`.

    docs/ro-crate.md instructs authors to do this at release; neither real repo
    built from this template ever did, so both Crates shipped anonymous and
    unversioned. The Crate gets the VERSION doi: an RO-Crate describes a
    specific packaged research object, not a floating project.
    """
    data = json.loads(path.read_text())
    for entity in data.get("@graph", []):
        if entity.get("@id") == "./":
            entity["identifier"] = [f"https://doi.org/{version_doi}", swhid]
            entity["version"] = tag.lstrip("v")
            break
    else:
        raise SystemExit("ro-crate-metadata.json has no './' root entity to annotate.")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


DOI_TOKEN = "{{ZENODO_DOI}}"


def substitute_prose_doi(path: Path, concept_doi: str) -> bool:
    """Fill the {{ZENODO_DOI}} placeholder in a prose/badge file (README.md,
    index.md) with the CONCEPT DOI. The token is used in two shapes that need
    different forms: a Zenodo badge image path wants the BARE DOI, while a
    markdown link target wants the RESOLVER URL. The metadata writers above only
    ever touched CITATION.cff / codemeta / ro-crate, so these badges shipped
    still showing the literal token after the first release — and the FAIR4RS
    checklist audit excludes the token, so nothing flagged it.

    Returns True if the file changed; a no-op if the file is absent or the token
    is already gone (so it is safe to re-run and safe when index.md does not
    exist).
    """
    if not path.exists():
        return False
    original = path.read_text()
    url = f"https://doi.org/{concept_doi}"
    text = (
        original
        .replace(f"DOI/{DOI_TOKEN}.svg", f"DOI/{concept_doi}.svg")  # badge image path -> bare DOI
        .replace(f"[{DOI_TOKEN}]", f"[{concept_doi}]")             # link/label text -> bare DOI
        .replace(f"({DOI_TOKEN})", f"({url})")                     # markdown link target -> resolver URL
        .replace(DOI_TOKEN, url)                                   # any remainder -> resolver URL
    )
    if text != original:
        path.write_text(text)
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", required=True, help="owner/name")
    p.add_argument("--tag", required=True, help="release tag, e.g. v0.1.0")
    p.add_argument(
        "--commit",
        required=True,
        help='the tag\'s COMMIT sha — `git rev-parse "<tag>^{commit}"`, NOT `git rev-parse <tag>`',
    )
    p.add_argument("--root", default=".", type=Path)
    p.add_argument("--attempts", type=int, default=10)
    p.add_argument("--delay", type=int, default=30)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    origin = f"https://github.com/{args.repo}"
    swhid = swhid_for(args.commit, origin)

    print(f"Resolving Zenodo record for {args.repo}@{args.tag} ...", file=sys.stderr)
    record = find_zenodo_record(args.repo, args.tag, attempts=args.attempts, delay=args.delay)
    version_doi, concept_doi = extract_dois(record)

    print(f"  concept DOI : {concept_doi}   (floating — 'cite this project')")
    print(f"  version DOI : {version_doi}   (pinned — cite this from nanopubs)")
    print(f"  SWHID       : {swhid}")

    if args.dry_run:
        print("\n--dry-run: no files written.")
        return 0

    update_citation_cff(args.root / "CITATION.cff", version_doi, concept_doi, swhid, args.tag)
    update_codemeta(args.root / "codemeta.json", version_doi, concept_doi, swhid)
    update_ro_crate(args.root / "ro-crate-metadata.json", version_doi, swhid, args.tag)
    wrote = ["CITATION.cff", "codemeta.json", "ro-crate-metadata.json"]
    for name in ("README.md", "index.md"):
        # the concept DOI is the "cite this project" identity the README badge shows
        if substitute_prose_doi(args.root / name, concept_doi):
            wrote.append(name)
    print("\nWrote " + ", ".join(wrote))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
