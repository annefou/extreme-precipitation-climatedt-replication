#!/usr/bin/env python3
"""Infrastructure-layer inheritance for a nanopub-rooted replication.

This is Step 5 of the ``/import-from-nanopub`` skill. By the time it runs,
the skill has already called the Science Live platform's
``/np/constellation`` endpoint and cached the response at
``nanopubs/imported/constellation.json``. That JSON *is* the claim-layer
import — it carries every reachable chain step and its prose inline, so
this script does no network discovery of its own.

What it does: read the constellation's Outcome steps, take each one's
``repository`` (a GitHub URL or a Zenodo DOI), resolve Zenodo DOIs to their
GitHub repo, ``git clone`` each unique sibling repository next to the
current one, stage a curated set of reusable starter files into
``_template_from_prior/``, and write ``nanopubs/imported/SETUP_INHERITED.md``
documenting all of it. This gives the new replication a workspace that
starts where the prior one ended, rather than a blank one.

    pixi run python scripts/inherit_sibling_repos.py \\
        --constellation-json nanopubs/imported/constellation.json

The claim layer — walking the chain, classifying step types, summarising
Quote → AIDA → Claim → Study → Outcome → CiTO — is NOT done here. It moved
to the platform's ``/np/constellation`` API (see the ``/import-from-nanopub``
skill). An earlier version of this script re-implemented that walk with its
own SPARQL BFS; the platform's ``api/src/np/constellation.ts`` supersedes it
and is the single source of truth, so the walk was removed rather than
maintained as a divergent second copy.

Output (under ``nanopubs/imported/``, which is gitignored):

* ``SETUP_INHERITED.md`` — which sibling repos were resolved, where they
  were cloned, and which starter files were staged for review.
* ``_template_from_prior/`` — the staged starter files themselves, each with
  a provenance header. One-shot reference area; review, merge, then delete.

Dependencies: Python standard library only. Network access is used to
resolve Zenodo DOIs (``zenodo.org``) and to ``git clone`` the siblings.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# --- URI matching --------------------------------------------------------

_ZENODO_DOI_RE = re.compile(
    r"https?://(?:doi\.org/)?10\.5281/zenodo\.(\d+)", re.IGNORECASE,
)
_GITHUB_RE = re.compile(
    r"https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", re.IGNORECASE,
)

# Files inherited from a sibling chain's repository. Conservative list:
# only files that are realistically reusable across replications of the same
# mechanism. The user reviews `_template_from_prior/` after import and
# merges what they want into the new repo. Add to this list iteratively
# as patterns emerge.
SIBLING_INHERITED_FILES = [
    "pixi.toml",
    "pixi.lock",
    "Snakefile",
    "notebooks/01_data_download.py",
    "notebooks/02_data_clean.py",
    "Dockerfile",
]

# Default location for sibling-repo clones — matches the per-project
# convention of placing related repos as siblings to the new replication
# (i.e. ~/Documents/ScienceLive/<repo>/). Configurable via CLI.
DEFAULT_SIBLINGS_DIR = "../"


# --- Reading the constellation -------------------------------------------

def read_outcome_repos(constellation_path: Path) -> list[tuple[str, str]]:
    """Return ``(outcome_uri, repository)`` pairs from the constellation's
    Outcome steps, in a deterministic order (chain order, step order).

    The constellation JSON is the ``/np/constellation`` response: its
    ``chains[].steps[]`` entries carry ``step`` (``"AIDA"`` / ``"Claim"`` /
    ``"Study"`` / ``"Outcome"`` / ``"CiTO"``) and, on Outcome steps, a
    ``repository`` field (a GitHub URL or a Zenodo DOI).
    """
    try:
        data = json.loads(constellation_path.read_text())
    except FileNotFoundError:
        print(f"ERROR: constellation JSON not found at {constellation_path}. "
              "Run the /import-from-nanopub skill's constellation step first.",
              file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: {constellation_path} is not valid JSON: {e}",
              file=sys.stderr)
        raise SystemExit(2)

    out: list[tuple[str, str]] = []
    for chain in data.get("chains", []) or []:
        for step in chain.get("steps", []) or []:
            if step.get("step") != "Outcome":
                continue
            repo = (step.get("repository") or "").strip()
            if repo:
                out.append((step.get("uri", ""), repo))
    return out


# --- Resolving a repository reference to a GitHub URL --------------------

def zenodo_doi_to_github(zenodo_doi: str, *, timeout: int = 20) -> str | None:
    """Resolve a Zenodo DOI to its associated GitHub repository URL via
    the Zenodo REST API's `related_identifiers` metadata.
    """
    m = _ZENODO_DOI_RE.search(zenodo_doi)
    if not m:
        return None
    record_id = m.group(1)
    api_url = f"https://zenodo.org/api/records/{record_id}"
    try:
        with urllib.request.urlopen(api_url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"    ! Zenodo API failed for {zenodo_doi}: {e}", file=sys.stderr)
        return None
    related = data.get("metadata", {}).get("related_identifiers", [])
    # Prefer `isSupplementTo` → `isDerivedFrom` → any github URL.
    for relation_preference in ("isSupplementTo", "isDerivedFrom", None):
        for ri in related:
            ident = ri.get("identifier", "")
            if _GITHUB_RE.search(ident):
                if relation_preference is None or ri.get("relation") == relation_preference:
                    # Strip /tree/..., /blob/..., trailing slashes.
                    cleaned = ident.split("/tree/")[0].split("/blob/")[0].rstrip("/")
                    return cleaned
    return None


def resolve_repo_url(raw: str, *, timeout: int = 20) -> str | None:
    """Normalise a repository reference to a GitHub URL. Accepts a GitHub
    URL directly or a Zenodo DOI (resolves via the Zenodo API).
    """
    raw = raw.strip()
    m = _GITHUB_RE.search(raw)
    if m:
        return m.group(0).rstrip("/")
    if _ZENODO_DOI_RE.search(raw):
        return zenodo_doi_to_github(raw, timeout=timeout)
    return None


# --- Cloning + staging ---------------------------------------------------

def clone_sibling(github_url: str, target_dir: Path) -> Path | None:
    """`git clone` if not already present at `target_dir`. Returns the
    local clone path on success (or if already present), else None.
    """
    if target_dir.exists():
        # Already present — assume it's a valid clone of the same repo.
        return target_dir
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"    cloning {github_url} → {target_dir}", file=sys.stderr)
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", "--quiet", github_url, str(target_dir)],
            check=True, capture_output=True, timeout=120,
        )
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or b"").decode(errors="replace").strip()
        print(f"    ! clone failed: {msg}", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"    ! clone timed out after 120 s", file=sys.stderr)
        return None
    return target_dir


def copy_inherited_files(sibling_dir: Path, staging_dir: Path,
                          sibling_name: str) -> list[str]:
    """Copy a curated set of files from `sibling_dir` to `staging_dir`,
    prepending a provenance header to each. Returns the list of relative
    paths copied.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for rel in SIBLING_INHERITED_FILES:
        src = sibling_dir / rel
        if not src.is_file():
            continue
        dst = staging_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        content = src.read_text(errors="replace")
        # Choose a sensible comment prefix per extension.
        ext = src.suffix.lower()
        if ext in (".py", ".yml", ".yaml", ".dockerfile") or src.name == "Dockerfile":
            comment = "# "
        elif ext == ".md":
            comment = ""
        else:
            comment = "# "  # fallback
        header_lines = [
            f"{comment}Inherited from prior FORRT chain sibling: {sibling_name}",
            f"{comment}Source: <sibling-repo>/{rel}",
            f"{comment}Review and merge into your replication's own file at the corresponding path,",
            f"{comment}then remove this staging copy. _template_from_prior/ is a reference area",
            f"{comment}only — not the source of truth for this replication.",
            "",
        ]
        dst.write_text("\n".join(header_lines) + content)
        copied.append(rel)
    return copied


def write_setup_inherited(out_path: Path,
                            resolved_repos: list[dict],
                            staging_dir_rel: str) -> None:
    """Write `nanopubs/imported/SETUP_INHERITED.md` documenting what's been
    cloned and what's been staged for review.
    """
    lines = [
        "# Setup inherited from the prior FORRT chain(s)",
        "",
        "Companion to `CHAIN_SUMMARY.md`. The summary documents the *claims*",
        "of the prior chain; this file documents the *infrastructure*",
        "(GitHub repositories, local clones, code/environment scaffolding)",
        "that the import skill has discovered or copied so you can start",
        "the new replication where the prior one ended.",
        "",
        "## Prior-chain repositories",
        "",
    ]
    if not resolved_repos:
        lines.append("*(no Outcome `repository` values were present in the imported")
        lines.append("constellation — either the chains don't expose them or the")
        lines.append("`/np/constellation` response predates that field)*")
        lines.append("")
    else:
        lines.append("| Outcome nanopub | Repository URL | Local clone |")
        lines.append("|---|---|---|")
        for r in resolved_repos:
            lines.append(
                f"| `{r['source_nanopub']}` | {r['github_url'] or r['raw_repo_uri']} | "
                f"`{r.get('clone_path') or '(not cloned)'}` |"
            )
        lines.append("")

    if any(r.get("copied_files") for r in resolved_repos):
        lines.append(f"## Files copied to `{staging_dir_rel}` for review")
        lines.append("")
        lines.append("These are starter files from the canonical sibling chain. **They are")
        lines.append("not the source of truth for this replication** — review each one,")
        lines.append("merge with (or replace) your own equivalent in the corresponding")
        lines.append("location, then delete `_template_from_prior/`.")
        lines.append("")
        for r in resolved_repos:
            if not r.get("copied_files"):
                continue
            lines.append(f"### From `{r.get('clone_path') or r['github_url']}`")
            lines.append("")
            for rel in r["copied_files"]:
                lines.append(f"- `{rel}`")
            lines.append("")

    lines.extend([
        "## Suggested next steps",
        "",
        "1. Open `_template_from_prior/pixi.toml` and merge its declared",
        "   dependencies into your own `pixi.toml`; the matching",
        "   `_template_from_prior/pixi.lock` carries the prior chain's",
        "   per-platform pinned versions. After merging, run `pixi install`",
        "   to refresh your own `pixi.lock`, then commit both files.",
        "2. Open `_template_from_prior/notebooks/01_data_download.py` to see",
        "   how the prior chain fetched climate / occurrence / paper data.",
        "   The patterns there — GBIF pre-minted-download style, Polytope",
        "   for DestinE Climate DT, Figshare for CRU TS — generalise to most",
        "   biodiversity-x-climate replications. Adapt the constants",
        "   (download keys, DOIs, file paths) for your replication.",
        "3. If the prior chain has cached data on disk that your replication",
        "   can reuse (CRU TS, DestinE GRIB files, etc.), wire a",
        "   `<REPO_NAME>_SHARED_DATA_DIR` env-var fallback into your",
        "   `01_data_download.py` so locally-cached data is preferred over",
        "   re-downloading. The fallback path goes to the freshly-cloned",
        "   sibling under the local clone path listed in the table above.",
        "4. Delete `_template_from_prior/` once you've merged everything you",
        "   want — it's a one-shot staging area, not durable repo state.",
    ])
    out_path.write_text("\n".join(lines))


def run_inheritance(
    outcome_repos: list[tuple[str, str]],
    siblings_dir: Path,
    staging_dir: Path,
    enable_clone: bool,
) -> list[dict]:
    """Resolve prior-chain repos, optionally clone them, and copy curated
    files to the staging area. Returns a list of per-repo result dicts for
    the SETUP_INHERITED.md report.
    """
    results: list[dict] = []
    if not outcome_repos:
        print("  (no Outcome `repository` values in the constellation — "
              "nothing to inherit)", file=sys.stderr)
        return results

    # Deduplicate raw repo URIs (multiple Outcomes can point at the same one)
    seen_raw: set[str] = set()
    unique_repos = []
    for src, raw in outcome_repos:
        if raw in seen_raw:
            continue
        seen_raw.add(raw)
        unique_repos.append((src, raw))

    for source_uri, raw_repo in unique_repos:
        github_url = resolve_repo_url(raw_repo)
        result = {
            "source_nanopub": source_uri,
            "raw_repo_uri": raw_repo,
            "github_url": github_url,
            "clone_path": None,
            "copied_files": [],
        }
        if not github_url:
            print(f"  ! could not resolve {raw_repo} to a GitHub URL", file=sys.stderr)
            results.append(result)
            continue

        repo_name = github_url.rstrip("/").split("/")[-1]
        clone_path = siblings_dir / repo_name
        if enable_clone:
            clone_result = clone_sibling(github_url, clone_path)
            if clone_result is None:
                results.append(result)
                continue
        else:
            if not clone_path.exists():
                print(f"  --no-clone-siblings: {clone_path} not present locally",
                      file=sys.stderr)
                results.append(result)
                continue

        result["clone_path"] = str(clone_path)
        # Only copy files from the FIRST resolvable sibling (canonical) by
        # default, to avoid clobbering staging with duplicates from each
        # sibling. We mark this as the canonical by being the first repo we
        # successfully clone.
        already_copied = any(r.get("copied_files") for r in results)
        if not already_copied:
            copied = copy_inherited_files(clone_path, staging_dir, repo_name)
            result["copied_files"] = copied
            if copied:
                print(f"    copied {len(copied)} files → {staging_dir}",
                      file=sys.stderr)
        results.append(result)
    return results


# --- CLI -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Clone the sibling repositories of a prior FORRT chain "
                    "and stage reusable starter files, driven by a cached "
                    "/np/constellation response.",
    )
    p.add_argument("--constellation-json", default="nanopubs/imported/constellation.json",
                   help="Path to the cached /np/constellation response "
                        "(default 'nanopubs/imported/constellation.json').")
    p.add_argument("--out-dir", default="nanopubs/imported",
                   help="Where to write SETUP_INHERITED.md (default "
                        "'nanopubs/imported').")
    p.add_argument("--siblings-dir", default=DEFAULT_SIBLINGS_DIR,
                   help="Where to clone sibling-chain repositories (default '../', "
                        "matching the convention of putting related repos side-by-side).")
    p.add_argument("--staging-dir", default="_template_from_prior",
                   help="Where to stage inherited files for review "
                        "(default '_template_from_prior'). Review + merge then delete.")
    p.add_argument("--no-clone-siblings", action="store_true",
                   help="Skip git-cloning sibling repos. Inheritance only proceeds "
                        "if siblings happen to be cloned already at --siblings-dir.")
    args = p.parse_args(argv)

    constellation_path = Path(args.constellation_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading constellation from {constellation_path}", file=sys.stderr)
    outcome_repos = read_outcome_repos(constellation_path)
    print(f"  {len(outcome_repos)} Outcome repository reference(s) found",
          file=sys.stderr)

    results = run_inheritance(
        outcome_repos,
        siblings_dir=Path(args.siblings_dir),
        staging_dir=Path(args.staging_dir),
        enable_clone=not args.no_clone_siblings,
    )

    setup_path = out_dir / "SETUP_INHERITED.md"
    write_setup_inherited(setup_path, results, args.staging_dir)
    print(f"Wrote {setup_path}", file=sys.stderr)

    cloned = sum(1 for r in results if r.get("clone_path"))
    staged = sum(len(r.get("copied_files", [])) for r in results)
    print(f"Resolved {len(results)} repo(s), cloned {cloned}, staged {staged} file(s).",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
