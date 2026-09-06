#!/usr/bin/env python3
"""Build a Rohub-ready manifest RO-Crate zip from this repository.

The output zip contains a single ``ro-crate-metadata.json`` referencing the
repository's external citable artefacts (GitHub repo, Zenodo concept DOI,
Jupyter Book site, published FORRT nanopubs, the upstream paper DOI, and
each numbered notebook) — *not* a duplicate of the source code. This is the
"manifest RO" pattern: the Rohub Research Object becomes a navigation index
pointing at the artefacts, with semantic typing that Rohub's UI renders
correctly.

Run:

    python3 scripts/build-rohub-manifest.py
    # -> rohub-manifest.zip in the repo root, ready for Rohub import.

Reads four sources to populate the manifest:

1. ``CITATION.cff`` — title, description, author name+ORCID, license, Zenodo DOI.
2. ``nanopubs/PUBLISHED.md`` — published FORRT nanopub URIs (the URI registry).
3. ``notebooks/*.py``      — each becomes a JupyterNotebook resource (raw
                            GitHub URL on the default branch).
4. ``git remote get-url origin`` — GitHub repo URL.

Then zips the JSON into ``rohub-manifest.zip``.

For the Rohub-typing vocabulary this script encodes, see
``docs/rohub-deposit.md``.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


# --- Rohub-recognised @type IRIs (verified against Rohub UI exports) ---
WF_RES = "http://purl.org/wf4ever/wf4ever#Resource"
WF_WEBSERVICE = "http://purl.org/wf4ever/wf4ever#WebService"
WF_DATASET = "http://purl.org/wf4ever/wf4ever#Dataset"
WF_PYTHONSCRIPT = "http://purl.org/wf4ever/wf4ever#PythonScript"
ES_JUPYTERNB = "https://w3id.org/ro/terms/earth-science#JupyterNotebook"
NANOPUB = "http://www.nanopub.org/nschema#Nanopublication"
DCT_BIB = "dct:BibliographicResource"


def parse_citation_cff(path: Path) -> dict:
    """Naive CFF parser — enough for the few fields we need.

    Avoids the PyYAML dependency so the script runs from a minimal env.
    Reads: title, abstract/description, license, authors[0].{name,orcid},
    repository-code, identifiers[0].value (the Zenodo concept DOI).
    """
    text = path.read_text()
    result: dict = {"authors": []}

    title_match = re.search(r'^title:\s*"?([^"\n]+)"?', text, re.MULTILINE)
    if title_match:
        result["title"] = title_match.group(1).strip()

    abstract_match = re.search(
        r"^abstract:\s*[>|]?\s*\n((?:  +.*\n)+)", text, re.MULTILINE
    )
    if abstract_match:
        result["abstract"] = " ".join(
            line.strip() for line in abstract_match.group(1).splitlines() if line.strip()
        )

    license_match = re.search(r"^license:\s*(\S+)", text, re.MULTILINE)
    if license_match:
        result["license"] = license_match.group(1).strip()

    repo_match = re.search(r'^repository-code:\s*"?([^"\n]+)"?', text, re.MULTILINE)
    if repo_match:
        result["repository_code"] = repo_match.group(1).strip()

    # First author's given+family+orcid+affiliation
    author_match = re.search(
        r"^authors:\s*\n((?:  - [^\n]+\n(?:    [^\n]+\n)*)+)",
        text,
        re.MULTILINE,
    )
    if author_match:
        for block in re.findall(
            r"  - [^\n]+\n(?:    [^\n]+\n)*", author_match.group(1)
        ):
            fam = re.search(r"family-names:\s*\"?([^\"\n]+)\"?", block)
            giv = re.search(r"given-names:\s*\"?([^\"\n]+)\"?", block)
            orc = re.search(r"orcid:\s*\"?([^\"\n]+)\"?", block)
            aff = re.search(r"affiliation:\s*\"?([^\"\n]+)\"?", block)
            if fam and giv:
                result["authors"].append(
                    {
                        "name": f"{giv.group(1).strip()} {fam.group(1).strip()}",
                        "orcid": orc.group(1).strip() if orc else None,
                        "affiliation": aff.group(1).strip() if aff else None,
                    }
                )

    # Zenodo concept DOI from identifiers section, first one
    doi_match = re.search(r'^doi:\s*"?(10\.5281/zenodo\.[0-9]+)"?', text, re.MULTILINE)
    if doi_match:
        result["zenodo_doi"] = doi_match.group(1).strip()

    return result


def parse_published_md(path: Path) -> list[dict]:
    """Extract published nanopub URIs and human-readable step names.

    Returns a list of {step, name, uri} dicts. Skips any entries that still
    say "_not yet published_".
    """
    if not path.exists():
        return []
    text = path.read_text()
    rows = []
    # Match Markdown table rows: | step | label | <URI> | (and other variations)
    for line in text.splitlines():
        # Look for w3id URIs anywhere on the line
        uri_match = re.search(r"<(https://w3id\.org/(?:sciencelive/)?np/RA[A-Za-z0-9_-]+)>", line)
        if not uri_match:
            continue
        uri = uri_match.group(1)
        # Extract step / label from the same row if it's a table
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 3:
            step = parts[0]
            template = parts[1]
            rows.append({"step": step, "name": template, "uri": uri})
        else:
            rows.append({"step": "?", "name": "Published nanopub", "uri": uri})
    return rows


def git_remote_url() -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True
        ).strip()
        # Normalise git@github.com:user/repo.git -> https://github.com/user/repo
        m = re.match(r"git@github\.com:(.+?)(?:\.git)?$", url)
        if m:
            return f"https://github.com/{m.group(1)}"
        m = re.match(r"https://github\.com/(.+?)(?:\.git)?$", url)
        if m:
            return f"https://github.com/{m.group(1)}"
        return url
    except subprocess.CalledProcessError:
        return None


def list_notebooks(notebooks_dir: Path) -> list[Path]:
    """Numbered notebook files in notebooks/, excluding underscore-prefixed helpers."""
    if not notebooks_dir.exists():
        return []
    return sorted(
        p
        for p in notebooks_dir.glob("*.py")
        if not p.name.startswith("_") and re.match(r"^\d", p.name)
    )


def build_manifest(repo_root: Path) -> dict:
    cff = parse_citation_cff(repo_root / "CITATION.cff")
    nanopubs = parse_published_md(repo_root / "nanopubs" / "PUBLISHED.md")
    notebooks = list_notebooks(repo_root / "notebooks")
    github_url = git_remote_url() or cff.get("repository_code", "")
    primary_author = cff["authors"][0] if cff.get("authors") else None

    # ISO datetime with microseconds + timezone (Rohub's expected format)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00:00")

    repo_name = github_url.rstrip("/").rsplit("/", 1)[-1] if github_url else "repository"
    branch_raw_prefix = (
        github_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
        + "/refs/heads/main"
        if github_url
        else ""
    )

    # ---- Build @graph entries ----
    graph: list[dict] = [
        {
            "@type": "CreativeWork",
            "@id": "ro-crate-metadata.json",
            "conformsTo": [{"@id": "https://w3id.org/ro/crate/1.2"}],
            "about": {"@id": "./"},
        },
    ]

    has_part: list[dict] = []
    citation: list[dict] = []

    # Author entity
    if primary_author and primary_author.get("orcid"):
        graph.append(
            {
                "@id": primary_author["orcid"],
                "@type": "Person",
                "name": primary_author["name"],
                "affiliation": primary_author.get("affiliation", ""),
            }
        )

    # GitHub repo as WebService resource
    if github_url:
        has_part.append({"@id": github_url})
        graph.append(
            {
                "@id": github_url,
                "@type": ["File", WF_RES, WF_WEBSERVICE],
                "name": "Source code repository",
                "contentUrl": github_url,
            }
        )

    # Zenodo concept DOI as Dataset
    if cff.get("zenodo_doi"):
        zenodo_url = f"https://doi.org/{cff['zenodo_doi']}"
        has_part.append({"@id": zenodo_url})
        citation.append({"@id": zenodo_url})
        graph.append(
            {
                "@id": zenodo_url,
                "@type": ["File", WF_RES, WF_DATASET],
                "name": "Zenodo concept DOI — citable software snapshot",
                "contentUrl": zenodo_url,
            }
        )

    # Jupyter Book site as WebService (assume <user>.github.io/<repo>)
    if github_url and github_url.startswith("https://github.com/"):
        owner, repo = github_url.replace("https://github.com/", "").split("/", 1)
        jbook_url = f"https://{owner}.github.io/{repo}/"
        has_part.append({"@id": jbook_url})
        graph.append(
            {
                "@id": jbook_url,
                "@type": ["File", WF_RES, WF_WEBSERVICE],
                "name": "Jupyter Book — rendered narrative",
                "contentUrl": jbook_url,
            }
        )

    # Each published nanopub as Nanopublication
    for np_row in nanopubs:
        has_part.append({"@id": np_row["uri"]})
        graph.append(
            {
                "@id": np_row["uri"],
                "@type": ["File", WF_RES, NANOPUB],
                "name": f"{np_row['step']} — {np_row['name']}".strip(" -"),
                "contentUrl": np_row["uri"],
            }
        )

    # Each notebook as JupyterNotebook (raw GitHub URL on the default branch)
    if branch_raw_prefix:
        for nb in notebooks:
            url = f"{branch_raw_prefix}/notebooks/{nb.name}"
            has_part.append({"@id": url})
            # Try to extract a friendly title from the notebook's first line
            label = nb.stem.replace("_", " ").title()
            graph.append(
                {
                    "@id": url,
                    "@type": ["File", WF_RES, ES_JUPYTERNB],
                    "name": f"Notebook — {label}",
                    "contentUrl": url,
                    "encodingFormat": "text/x-python",
                }
            )

    # Root entity
    root: dict = {
        "@id": "./",
        "@type": ["Dataset", "ResearchObject"],
        "name": cff.get("title", repo_name),
        "description": cff.get(
            "abstract",
            "Research object aggregating the artefacts (code, data, nanopubs, paper) for this replication.",
        ),
        "license": {"@id": f"https://spdx.org/licenses/{cff.get('license', 'MIT')}"},
        "datePublished": now,
        "dateCreated": now,
        "dateModified": now,
        "hasPart": has_part,
    }
    if primary_author and primary_author.get("orcid"):
        root["publisher"] = {"@id": primary_author["orcid"]}
        root["author"] = [{"@id": primary_author["orcid"]}]
    if cff.get("zenodo_doi"):
        root["identifier"] = f"https://doi.org/{cff['zenodo_doi']}"
    if citation:
        root["citation"] = citation

    graph.insert(1, root)  # right after the ro-crate-metadata entry

    return {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": graph,
    }


def main() -> None:
    repo_root = Path.cwd()
    if not (repo_root / "CITATION.cff").exists():
        sys.exit(
            "Error: CITATION.cff not found in current directory. "
            "Run this script from the repository root."
        )

    manifest = build_manifest(repo_root)

    # Write JSON next to the zip for transparency
    json_path = repo_root / "rohub-manifest.json"
    json_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Zip with the JSON at root (Rohub expects ro-crate-metadata.json at zip root)
    zip_path = repo_root / "rohub-manifest.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ro-crate-metadata.json", json.dumps(manifest, indent=2) + "\n")

    n_nanopubs = sum(
        1
        for e in manifest["@graph"]
        if isinstance(e.get("@type"), list)
        and NANOPUB in e["@type"]
    )
    n_notebooks = sum(
        1
        for e in manifest["@graph"]
        if isinstance(e.get("@type"), list)
        and ES_JUPYTERNB in e["@type"]
    )
    print(f"Wrote {json_path.name} (full JSON for review)")
    print(f"Wrote {zip_path.name} for Rohub upload")
    print(f"  - nanopubs:  {n_nanopubs}")
    print(f"  - notebooks: {n_notebooks}")
    print(f"  - other resources: GitHub + Zenodo + Jupyter Book (if URL inferable)")
    print()
    print("Next: upload rohub-manifest.zip via Rohub's 'Import ZIP Research Object'.")


if __name__ == "__main__":
    main()
