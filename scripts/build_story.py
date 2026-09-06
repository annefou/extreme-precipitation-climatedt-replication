"""Generate a replication story page from ANY FORRT chain.

The page is an AGGREGATION of what the Science Live platform already displays for
each nanopublication — same fields, same labels, same citation rule — restyled and
reordered into an article. Nothing invented, nothing hard-coded per chain.

Field sets and labels are copied from the platform's view components:
  ViewPICOResearchQuestion, ViewPCCResearchQuestion, ViewAIDASentence,
  ViewFORRTClaim, ViewFORRTReplication, ViewFORRTReplicationOutcome,
  ViewCitationWithCiTO
Citations follow lib/nanopub-store.ts generateCitation():
  "{creator's foaf:name}. ({year}). {rdfs:label in pubinfo} [Nanopublication]. {uri}"

It handles both a single replication chain and a research synthesis (several
chains composed into one finding) — the shape is detected from the constellation.

Usage
-----
    pixi run build-story                       # read the apex from nanopubs/PUBLISHED.md
    python scripts/build_story.py <uri> -o out.html

Needs ``SCIENCELIVE_API_KEY`` in the environment (the key you publish chains
with). The endpoint defaults to production; set ``SCIENCELIVE_API`` to override
(e.g. the dev constellation). Deterministic: run it once, commit the HTML, and
publish it wherever the repository already publishes (e.g. GitHub Pages).
"""
import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "curl/8.5.0"}
# `or` (not a default arg) so an empty env value — e.g. an unset GitHub Actions
# `vars.SCIENCELIVE_API` — falls back to production rather than becoming "".
API = os.environ.get("SCIENCELIVE_API") or "https://api.sciencelive4all.org/np/constellation"
# The platform the "View on Science Live" link points at. Defaults to production;
# a dev-network replication sets SCIENCELIVE_PLATFORM to its dev host.
PLATFORM = (os.environ.get("SCIENCELIVE_PLATFORM") or "https://platform.sciencelive4all.org").rstrip("/")
SPARQL = "https://query.knowledgepixels.com/repo/full"


def _api_key():
    """The Science Live API key, read lazily so the module imports without it
    (offline tests import these helpers; only a live build needs the key)."""
    key = os.environ.get("SCIENCELIVE_API_KEY")
    if not key:
        raise SystemExit("SCIENCELIVE_API_KEY is not set — export the key you "
                         "publish chains with, then re-run.")
    return key


# ------------------------------------------------------------------ fetching
GH_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _get(url, headers=None, timeout=60):
    extra = dict(headers or {})
    # unauthenticated GitHub is 60 requests/hour - far too few to sweep every chain
    if GH_TOKEN and url.startswith("https://api.github.com/"):
        extra.setdefault("Authorization", f"Bearer {GH_TOKEN}")
    req = urllib.request.Request(url, headers={**UA, **extra})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def sparql(q):
    data = urllib.parse.urlencode({"query": q}).encode()
    req = urllib.request.Request(SPARQL, data=data,
                                 headers={**UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["results"]["bindings"]


def graph_of(np_uri, which="assertion"):
    """Triples of a nanopub's assertion or pubinfo, keyed by predicate local name."""
    pred = "hasAssertion" if which == "assertion" else "hasPublicationInfo"
    rows = sparql(f"""PREFIX np: <http://www.nanopub.org/nschema#>
SELECT ?s ?p ?o WHERE {{ GRAPH ?h {{ <{np_uri}> np:{pred} ?g . }} GRAPH ?g {{ ?s ?p ?o . }} }}""")
    out = {}
    for r in rows:
        k = r["p"]["value"].split("/")[-1].split("#")[-1]
        pair = (r["s"]["value"], r["o"]["value"])
        if pair not in out.setdefault(k, []):
            out[k].append(pair)
    return out


_cache = {}


def cached(key, fn):
    if key not in _cache:
        try:
            _cache[key] = fn()
        except Exception:
            _cache[key] = None
    return _cache[key]


def wikidata_label(uri):
    qid = uri.rsplit("/", 1)[-1]
    got = cached("wd:" + qid, lambda: json.loads(_get(
        "https://www.wikidata.org/w/api.php?action=wbgetentities"
        f"&ids={qid}&props=labels&languages=en&format=json", timeout=30)
    )["entities"][qid]["labels"]["en"]["value"])
    return got or qid


def github_meta(repo_url):
    slug = repo_url.split("github.com/")[1].strip("/")
    return cached("gh:" + slug,
                  lambda: json.loads(_get(f"https://api.github.com/repos/{slug}", timeout=30))) or {}


def link_label(url):
    """What is this thing? DOI metadata when available, else the page's own title."""
    def fetch():
        if "doi.org/" in url:
            d = json.loads(_get(url, {"Accept": "application/vnd.citationstyles.csl+json"}, 40))
            who = ", ".join(a.get("family", "") for a in (d.get("author") or [])[:3] if a.get("family"))
            yr = (d.get("issued", {}).get("date-parts") or [[None]])[0][0]
            bits = [b for b in (who, str(yr) if yr else "", d.get("container-title")) if b]
            return {"title": d.get("title"), "sub": " \u00b7 ".join(bits)}
        page = _get(url, {"Accept": "text/html"}, 30)
        m = (re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page, re.I)
             or re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S))
        t = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else None
        return {"title": t, "sub": urllib.parse.urlparse(url).netloc}
    got = cached("ll:" + url, fetch)
    return got or {"title": None, "sub": urllib.parse.urlparse(url).netloc}


def archive_label(url):
    """Not every archived release is a DOI - label it for what it actually is."""
    if not url:
        return None, None
    if "doi.org/" in url:
        return "Archived release", "DOI: " + url.split("doi.org/", 1)[1]
    host = urllib.parse.urlparse(url).netloc
    if "github.com" in host:
        return "Source repository", url.split("github.com/", 1)[1]
    return "Archived release", host


def raw_to_blob(url):
    """A raw githubusercontent URL -> its viewable github.com/blob page, so a
    figure caption can link to the source file in the repository."""
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([^/]+)/(.+)", url or "")
    return f"https://github.com/{m.group(1)}/blob/{m.group(2)}/{m.group(3)}" if m else url


def site_icon(host):
    """A host's own declared icon, inlined. Deterministic and works for any host:
    read <link rel=icon> from the homepage, else fall back to /favicon.ico."""
    def fetch():
        import io
        base = "https://" + host
        cands = []
        try:
            page = urllib.request.urlopen(
                urllib.request.Request(base, headers=UA), timeout=25).read().decode("utf-8", "ignore")
            for m in re.finditer(r"<link[^>]+rel=[\"']([^\"']*icon[^\"']*)[\"'][^>]*>", page, re.I):
                tag = m.group(0)
                href = re.search(r"href=[\"']([^\"']+)[\"']", tag, re.I)
                if not href:
                    continue
                sizes = re.search(r"sizes=[\"'](\d+)", tag, re.I)
                cands.append((int(sizes.group(1)) if sizes else (999 if ".svg" in href.group(1) else 16),
                              urllib.parse.urljoin(base + "/", href.group(1))))
        except Exception:
            pass
        cands.sort(reverse=True)
        cands.append((0, base + "/favicon.ico"))
        for _, u in cands:
            try:
                raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25).read()
                if not raw or len(raw) > 400_000:
                    continue
                if u.lower().endswith(".svg"):
                    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
                from PIL import Image
                im = Image.open(io.BytesIO(raw))
                im = im.convert("RGBA")
                im.thumbnail((64, 64), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, format="PNG", optimize=True)
                return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            except Exception:
                continue
        return None
    return cached("icon:" + host, fetch)


def zenodo_repo(doi_url):
    """A Zenodo record usually names its source repository in related identifiers."""
    m = re.search(r"zenodo\.(\d+)", doi_url or "")
    if not m:
        return None
    def fetch():
        d = json.loads(_get(f"https://zenodo.org/api/records/{m.group(1)}", timeout=40))
        cands = [r.get("identifier", "") for r in (d.get("metadata", {}).get("related_identifiers") or [])]
        cands += [d.get("metadata", {}).get("custom", {}).get("code:codeRepository", "")]
        for c in cands:
            g = re.search(r"https://github\.com/[\w.\-]+/[\w.\-]+", c or "")
            if g:
                return g.group(0)
        return None
    return cached("zr:" + m.group(1), fetch)


def repo_figure(slug, branch):
    """No figure named in the evidence? Take the first image the repo publishes
    in a figures/ directory. Deterministic, and works for any repo."""
    def fetch():
        for folder in ("figures", "fig", "images"):
            try:
                items = json.loads(_get(
                    f"https://api.github.com/repos/{slug}/contents/{folder}?ref={branch}", timeout=30))
            except Exception:
                continue
            imgs = sorted([i["name"] for i in items
                           if i.get("type") == "file"
                           and i["name"].lower().endswith((".png", ".jpg", ".jpeg"))])
            if not imgs:
                continue
            pref = [n for n in imgs if re.search(r"main|result|headline|hero", n, re.I)]
            return f"{folder}/{(pref or imgs)[0]}"
        return None
    return cached("rf:" + slug + branch, fetch)


def repo_images(slug, branch):
    """Every image a repo publishes in its figures/ directory (name + raw URL).
    Used to find a synthesis hero figure — one the individual limbs don't show."""
    def fetch():
        for folder in ("figures", "fig", "images"):
            try:
                items = json.loads(_get(
                    f"https://api.github.com/repos/{slug}/contents/{folder}?ref={branch}", timeout=30))
            except Exception:
                continue
            imgs = sorted(i["name"] for i in items
                          if i.get("type") == "file"
                          and i["name"].lower().endswith((".png", ".jpg", ".jpeg")))
            if imgs:
                return [(n, f"https://raw.githubusercontent.com/{slug}/{branch}/{folder}/{n}")
                        for n in imgs]
        return []
    return cached("ri:" + slug + branch, fetch) or []


# What reads as an overview/context figure for a whole synthesis, most-preferred
# first. A synthesis has no figure field of its own, so the hero is discovered
# from the shared repository — and, being "another figure", excludes the images
# the individual limbs already show.
HERO_PREF = ("study_area", "study-area", "studyarea", "overview", "synthesis",
             "composite", "summary", "context", "site", "area", "map",
             "hero", "headline", "main", "result")


def synth_hero(limbs):
    """A hero figure for the whole synthesis: an overview image from the shared
    repo that the limbs don't already display. Deterministic; None if none fits."""
    used = {(d["figure"][1].rsplit("/", 1)[-1]).lower() for d in limbs if d.get("figure")}
    seen, cands = set(), []
    for d in limbs:
        if not d.get("repo"):
            continue
        gh = github_meta(d["repo"])
        slug = gh.get("full_name")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        cands += repo_images(slug, gh.get("default_branch", "main"))
    avail = [(n, u) for n, u in cands if n.lower() not in used]
    for tok in HERO_PREF:
        for n, u in avail:
            if tok in n.lower() and url_ok(u):
                return (u, n)
    for n, u in avail:                      # any unused image beats no hero
        if url_ok(u):
            return (u, n)
    return None


def myst_figure(book_url):
    """Figures published by a MyST book. The served HTML is client-rendered, so read
    the book's own JSON: myst.xref.json -> page JSON -> image/figure nodes."""
    if not book_url:
        return None

    def fetch():
        base = book_url if book_url.endswith("/") else book_url + "/"
        xref = json.loads(_get(urllib.parse.urljoin(base, "myst.xref.json"), timeout=35))
        pages = sorted({r["data"] for r in xref.get("references", []) if r.get("data")})
        found = []

        def walk(n):
            if isinstance(n, dict):
                if n.get("type") in ("image", "figure") and n.get("url"):
                    found.append(n["url"])
                for v in n.values():
                    walk(v)
            elif isinstance(n, list):
                for v in n:
                    walk(v)

        for pg in pages:
            try:
                walk(json.loads(_get(urllib.parse.urljoin(base, pg.lstrip("/")), timeout=35)))
            except Exception:
                continue
        if not found:
            return None
        pref = [u for u in found if re.search(r"main|result|headline|hero", u, re.I)]
        return urllib.parse.urljoin(base, (pref or found)[0].lstrip("/"))

    return cached("myst:" + book_url, fetch)


def inline_figure(url, max_w=1200):
    """Downscale and base64-inline a figure so it renders anywhere (no external request)."""
    import io
    try:
        from PIL import Image
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
        im = Image.open(io.BytesIO(raw))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=86, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return url  # fall back to the remote URL


def url_ok(url):
    try:
        req = urllib.request.Request(url, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=25) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


# ------------------------------------------------------------------ labels
def esc(t):
    return html.escape(str(t or ""), quote=True)


ACRONYMS = {"pcc": "PCC", "pico": "PICO", "aida": "AIDA", "cito": "CiTO", "forrt": "FORRT"}


def term_label(uri):
    """Vocabulary URI -> readable term (what the platform's getLabel would show)."""
    if not uri:
        return ""
    if "wikidata.org" in uri:
        return wikidata_label(uri)
    tail = uri.rstrip("/").rsplit("/", 1)[-1].split("#")[-1]
    tail = tail.replace("_", " ").replace("-", " ")
    tail = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tail)
    return " ".join(ACRONYMS.get(w.lower(), w) for w in tail.split())


def rel_label(uri):
    """CiTO relations read as a phrase: citesAsDataSource -> 'Cites as data source'."""
    w = term_label(uri).split()
    return " ".join([w[0].capitalize()] + [x.lower() for x in w[1:]]) if w else ""


def deref(a, val):
    """A component node (PICO/PCC part) carries its text as its own description."""
    if isinstance(val, str) and val.startswith("http"):
        for s_, o in a.get("description", []):
            if s_ == val:
                return o
    return val


def one(d, pred):
    v = d.get(pred)
    return v[0][1] if v else None


def many(d, pred):
    return [o for _, o in d.get(pred, [])]


# --------------------------------------------------- platform field specs
PROSE, TERM, LINK, LINKS, TERMS, DATE = "prose", "term", "link", "links", "terms", "date"

# (label, predicate, renderer). Labels copied verbatim from the view components.
SPEC = {
    "PICO": [("Population (P)", "population", PROSE),
             ("Intervention (I)", "interventionGroup", PROSE),
             ("Comparator (C)", "comparatorGroup", PROSE),
             ("Outcome (O)", "outcomeGroup", PROSE)],
    "Quote": [],  # a quotation has no parts; its text and comment carry the content
    "PCC": [("Population", "hasPccPopulation", PROSE),
            ("Concept", "hasPccConcept", PROSE),
            ("Context", "hasPccContext", PROSE)],
    "AIDA": [("Topics", "about", TERMS), ("Supported by", "obtainsSupportFrom", LINKS)],
    "Claim": [("FORRT Type", "type", TERM), ("Source", "source", LINK)],
    "Study": [("Study Type", "type", TERM),
              ("Scope", "hasScopeDescription", PROSE),
              ("Methodology", "hasMethodologyDescription", PROSE),
              ("Deviations", "hasDeviationDescription", PROSE),
              ("Keywords", "related", TERMS),
              ("Discipline", "hasDiscipline", TERM)],
    "Outcome": [("Validation Status", "hasValidationStatus", TERM),
                ("Confidence Level", "hasConfidenceLevel", TERM),
                ("Conclusion", "hasConclusionDescription", PROSE),
                ("Evidence", "hasEvidenceDescription", PROSE),
                ("Limitations", "hasLimitationsDescription", PROSE),
                ("Repository", "hasOutcomeRepository", LINK),
                ("Completed", "endDate", DATE)],
}

# shown as narrative paragraphs, so not repeated in the compact field list
NARRATIVE = {"Study": ["Scope", "Methodology", "Deviations"],
             "Outcome": ["Conclusion", "Evidence", "Limitations"]}

GENERIC_TYPES = ("FORRT-Claim", "FORRT-Replication-Study", "FORRT-Replication-Outcome",
                 "AIDA-Sentence", "PICO", "PccReviewQuestion")


def root_body(a, kind):
    """The question's own description - i.e. the one that is not a P/I/C/O part."""
    parts = {o for _, pred, _ in SPEC.get(kind, []) for o in many(a, pred)}
    for s_, o in a.get("description", []):
        if s_ not in parts:
            return o
    return ""


def pick_type(a):
    """A step carries several rdf:types; show the specific one, not the generic marker."""
    vals = many(a, "type")
    specific = [v for v in vals if not v.rstrip("/").rsplit("/", 1)[-1] in GENERIC_TYPES]
    return (specific or vals or [None])[0]


def field_html(label, pred, kind, a):
    if kind == TERMS:
        vals = many(a, pred)
        if not vals:
            return ""
        body = " ".join(f'<a class="tag" href="{esc(v)}">{esc(term_label(v))}</a>' for v in vals)
    elif kind == LINKS:
        vals = many(a, pred)
        if not vals:
            return ""
        body = '<ul class="reflist">' + "".join(
            f'<li><a class="u" href="{esc(v)}">{esc(v)}</a></li>' for v in vals) + "</ul>"
    elif kind == TERM:
        v = pick_type(a) if pred == "type" else one(a, pred)
        if not v:
            return ""
        body = f'<a class="tag" href="{esc(v)}">{esc(term_label(v))}</a>'
    elif kind == LINK:
        v = one(a, pred)
        if not v:
            return ""
        body = f'<a class="u" href="{esc(v)}">{esc(v)}</a>'
    elif kind == DATE:
        v = one(a, pred)
        if not v:
            return ""
        body = f"<span>{esc(v[:10])}</span>"
    else:
        v = one(a, pred)
        if not v:
            return ""
        body = f'<p class="fieldprose">{esc(v)}</p>'
    return f'<div class="fieldrow"><span class="fieldlabel">{esc(label)}</span><div>{body}</div></div>'


def part_chips(kind, a):
    """PICO/PCC parts as compact chips with hover popups — the platform's labels,
    the blog's presentation."""
    items = ""
    for label, pred, _ in SPEC.get(kind, []):
        val = deref(a, one(a, pred))
        if not val:
            continue
        items += (f'<li class="hint left"><span class="picochip" tabindex="0">{esc(label)}</span>'
                  f'<span class="box" role="tooltip"><strong>{esc(label)}</strong>{esc(val)}</span></li>')
    return f'<ul class="picorow">{items}</ul>' if items else ""


def meta_chips(pairs):
    """Small facts that belong at the top of an article, not in a table."""
    out = ""
    for label, val, href in pairs:
        if not val:
            continue
        inner = f'{esc(label)}: <strong>{esc(val)}</strong>'
        out += (f'<a class="tag" href="{esc(href)}">{inner}</a>' if href
                else f'<span class="tag">{inner}</span>')
    return out


def fields(kind, a, skip=()):
    rows = "".join(field_html(l, p, k, a) for l, p, k in SPEC.get(kind, []) if l not in skip)
    return f'<div class="fieldset">{rows}</div>' if rows else ""


def narrative(kind, a):
    out = ""
    for label, pred, k in SPEC.get(kind, []):
        if label in NARRATIVE.get(kind, []) and one(a, pred):
            out += f'<h3 class="sub">{esc(label)}</h3><p>{esc(one(a, pred))}</p>'
    return out


# ------------------------------------------------------------------ citation
def creator_name(creator, graphs):
    if not creator:
        return None
    for g in graphs:
        for s, o in g.get("name", []):
            if s == creator:
                return o
    rows = cached("nm:" + creator, lambda: sparql(
        f"""PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?n WHERE {{ GRAPH ?g {{ <{creator}> foaf:name ?n . }} }} LIMIT 1"""))
    return rows[0]["n"]["value"] if rows else None


def citation_parts(uri, pub, a):
    """Mirrors generateCitation(): creator's foaf:name, year, rdfs:label from pubinfo."""
    creator = one(pub, "creator")
    name = creator_name(creator, (pub, a)) or "Unknown Author"
    created = one(pub, "created") or ""
    year = created[:4] if created else "n.d."
    title = one(pub, "label")
    if (not title) or str(title).startswith("NP created using"):
        intro = one(pub, "introduces")
        title = (intro.rsplit("/", 1)[-1].replace("-", " ") if intro
                 else uri.rsplit("/", 1)[-1][:10])
    return name, year, title


def citation(uri, pub, a):
    n, y, t = citation_parts(uri, pub, a)
    return f"{n}. ({y}). {t} [Nanopublication]. {uri}"


# ------------------------------------------------------ structured prose
# A synthesis's conditions / limitations / recommendations are long free text
# written as bullet or numbered lists with indented continuation lines. Render
# them as real lists/paragraphs — deterministically, nothing added or reworded.
_BULLET = r"^\s*-\s+"
_NUMBER = r"^\s*\d+[.)]\s+"


def _list_items(lines, pat):
    """Group lines into items: a line matching `pat` starts an item, the lines
    under it (indented continuations, blank lines) belong to that same item."""
    items, cur = [], None
    for ln in lines:
        if re.match(pat, ln):
            if cur is not None:
                items.append(cur.strip())
            cur = re.sub(pat, "", ln.strip())
        elif cur is not None:
            cur = (cur + " " + ln.strip()).strip()
    if cur is not None:
        items.append(cur.strip())
    return [it for it in items if it]


_ABBR = ("et al.", "e.g.", "i.e.", "vs.", "cf.", "fig.", "al.", "approx.", "incl.", "no.")


def first_sentence(text):
    """The first real sentence of a passage — a deterministic lead for a tightened
    card. Whitespace-collapsed; won't split on common abbreviations (et al., e.g.)."""
    t = " ".join((text or "").split())
    for m in re.finditer(r"[.!?](?=\s|$)", t):
        head = t[:m.end()]
        if any(head.lower().rstrip().endswith(a) for a in _ABBR):
            continue
        if len(head) >= 40:
            return head
    return t


def first_list_item(text):
    """The first numbered/bulleted item of a passage, verbatim — else its first
    sentence. Used to lift a headline recommendation into the bottom-line callout."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    for pat in (_NUMBER, _BULLET):
        idx = next((i for i, ln in enumerate(lines) if re.match(pat, ln)), None)
        if idx is not None:
            items = _list_items(lines[idx:], pat)
            if items:
                return items[0]
    return first_sentence(text)


def prose_blocks(text):
    """HTML for a block of prose: numbered/bulleted stretches become <ol>/<ul>,
    an optional lead sentence before the list stays a paragraph, everything else
    splits into paragraphs on blank lines."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").strip()
    lines = text.split("\n")
    for pat, wrap in ((_NUMBER, "ol"), (_BULLET, "ul")):
        if sum(1 for ln in lines if re.match(pat, ln)) >= 2:
            idx = next(i for i, ln in enumerate(lines) if re.match(pat, ln))
            intro = " ".join(x.strip() for x in lines[:idx]).strip()
            items = _list_items(lines[idx:], pat)
            lis = "".join(f"<li>{esc(it)}</li>" for it in items)
            return ((f"<p>{esc(intro)}</p>" if intro else "")
                    + f'<{wrap} class="prose-list">{lis}</{wrap}>')
    return "".join(
        f'<p>{esc(" ".join(x.strip() for x in blk.split(chr(10))).strip())}</p>'
        for blk in re.split(r"\n\s*\n", text) if blk.strip())


# ------------------------------------------------------------------ build
def fetch_con(entry):
    return json.loads(_get(API + "?uri=" + urllib.parse.quote(entry, safe=""),
                           {"x-api-key": _api_key(), "Accept": "application/json"}, 90))


def build(entry, con=None):
    con = con or fetch_con(entry)
    chain = (con.get("chains") or [None])[0]
    if not chain:
        raise SystemExit("no chain returned")
    return build_chain(con, chain)


def build_chain(con, chain):
    steps = {s["step"]: s for s in chain["steps"]}
    d = {"con": con, "chain": chain, "steps": steps, "a": {}, "pub": {}}

    for kind, s in steps.items():
        d["a"][kind] = graph_of(s["uri"])
        d["pub"][kind] = graph_of(s["uri"], "pubinfo")

    # the root is one hop past the constellation, via the AIDA's skos:related
    d["root"] = None
    rel = many(d["a"].get("AIDA", {}), "related")
    if rel:
        ra = graph_of(rel[0])
        types = [t.split("/")[-1].split("#")[-1] for t in many(ra, "type")]
        if one(ra, "hasQuotedText"):
            kind = "Quote"
        elif any("Pcc" in t for t in types):
            kind = "PCC"
        else:
            kind = "PICO"
        d["root"] = {
            "uri": rel[0], "types": types, "a": ra, "kind": kind,
            "pub": graph_of(rel[0], "pubinfo"),
            "label": one(ra, "label") or (one(ra, "hasQuotedText") if kind == "Quote" else ""),
            "body": root_body(ra, kind) or (one(ra, "comment") if kind == "Quote" else ""),
            "quotes": one(ra, "quotes") if kind == "Quote" else None,
        }

    d["order"] = ([("Question", d["root"]["uri"])] if d["root"] else []) + \
                 [(k, steps[k]["uri"]) for k in ("AIDA", "Claim", "Study", "Outcome", "CiTO")
                  if k in steps]

    # CiTO relations, as ViewCitationWithCiTO lists them
    d["cites"] = []
    cito_a = d["a"].get("CiTO", {})
    for pred, pairs in cito_a.items():
        if pred in ("type", "label"):
            continue
        for _, o in pairs:
            if str(o).startswith("http") and "cito" not in str(o):
                d["cites"].append((pred, o))
    if not d["cites"]:
        rels = steps.get("CiTO", {}).get("relations") or []
        for t in (steps.get("CiTO", {}).get("targets") or []):
            d["cites"].append((rels[0] if rels else "cites", t))

    ev = one(d["a"].get("Outcome", {}), "hasEvidenceDescription") or ""
    repos = re.findall(r"https://github\.com/[\w.\-]+/[\w.\-]+", ev)
    archived = one(d["a"].get("Outcome", {}), "hasOutcomeRepository")
    d["repo"] = (repos[0] if repos
                 else (archived if archived and "github.com" in archived
                       else zenodo_repo(archived)))
    gh = github_meta(d["repo"]) if d["repo"] else {}
    d["book"] = gh.get("homepage") if gh.get("has_pages") else None
    d["history"] = next(iter(re.findall(r"https://usegalaxy\.eu/histories/\S+?(?=[\s)]|$)", ev)), None)
    urls = set()
    for kind, g in d["a"].items():
        for pairs in g.values():
            for _, o in pairs:
                if isinstance(o, str) and o.startswith("http"):
                    urls.add(o)
    for u in (d.get("repo"), d.get("book"), d.get("history"),
              one(d["a"].get("Outcome", {}), "hasOutcomeRepository"),
              one(d["pub"].get("Outcome", {}), "creator")):
        if u:
            urls.add(u)
    hosts, seen_h = [], set()
    for u in sorted(urls):
        h = urllib.parse.urlparse(u).netloc
        if h and h not in seen_h:
            seen_h.add(h)
            hosts.append((h, f"https://{h}"))
    d["hosts"] = hosts[:10]

    d["figure"] = None
    named = re.findall(r"((?:figures|fig)/[\w.\-/]+\.(?:png|jpg|jpeg|svg))", ev)
    if not named and gh.get("full_name"):
        found = repo_figure(gh["full_name"], gh.get("default_branch", "main"))
        named = [found] if found else []
    if not named:
        mf = myst_figure(d.get("book"))
        if mf:
            d["figure"] = (mf, mf.rsplit("/", 1)[-1])
    for rel_path in named:
        if gh.get("full_name"):
            raw = (f"https://raw.githubusercontent.com/{gh['full_name']}/"
                   f"{gh.get('default_branch', 'main')}/{rel_path}")
            if url_ok(raw):
                d["figure"] = (raw, rel_path)
                break
    return d


# --------------------------------------------------------- synthesis build
def build_synthesis(entry, con=None):
    """A research synthesis composes several replication limbs into one finding.
    Build each limb with the same per-chain logic, plus the synthesis nanopub's
    own assertion/pubinfo for the byline and the composed prose the constellation
    surfaces (label, synthesis, conditions, limitations, recommendations)."""
    con = con or fetch_con(entry)
    rs = con.get("researchSynthesis") or {}
    limbs = [build_chain(con, c) for c in (con.get("chains") or [])]
    a = graph_of(entry)
    return {
        "con": con,
        "rs": rs,
        "limbs": limbs,
        "uri": entry,
        "a": a,
        "pub": graph_of(entry, "pubinfo"),
        "paperDoi": con.get("paperDoi"),
        "topics": many(a, "subject"),          # synthesis-level Wikidata topics
        "hero": synth_hero(limbs),             # an overview figure the limbs don't show
    }


VERDICT_CLASS = {"validated": "ok", "partiallysupported": "warn",
                 "contradicted": "bad", "refuted": "bad"}


def _limb_view(d):
    """The facts a synthesis card shows for one limb — read from its own chain."""
    out = d["a"].get("Outcome", {})
    claim = d["a"].get("Claim", {})
    verdict = term_label(one(out, "hasValidationStatus"))
    rels = d["chain"].get("citoRelations") or [p for p, _ in d["cites"]]
    return {
        "heading": one(claim, "label") or one(out, "label") or "Replication limb",
        "question": (d.get("root") or {}).get("label") or "",
        "verdict": verdict,
        "vclass": VERDICT_CLASS.get(re.sub(r"\s+", "", verdict.lower()), "ok"),
        "confidence": term_label(one(out, "hasConfidenceLevel")),
        "relation": rel_label(rels[0]) if rels else "",
        "conclusion": one(out, "hasConclusionDescription") or "",
        "outcome_uri": d["steps"].get("Outcome", {}).get("uri", ""),
        "cito_uri": d["steps"].get("CiTO", {}).get("uri", ""),   # signs the confirms/qualifies
        "repo": d.get("repo"),
        "book": d.get("book"),
        "archive": one(out, "hasOutcomeRepository"),
        "figure": d.get("figure"),
    }


# -------------------------------------------------------- audience tabs
# An OPTIONAL layer. The deterministic "Record" tab is always the page; audience
# tabs are added only when an audience.json is supplied. That file is produced
# ONCE at build time by an opt-in AI step (a constrained rewrite of the record's
# own text for a lay audience) and baked into the static HTML — so the reader
# spends no tokens and nothing AI-written ever leaks into the Record tab.
def load_audiences(path):
    if not path:
        return []
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        return data or []
    auds = data.get("audiences", [])
    shared = data.get("glance")          # one glance spec, shared by every audience
    if shared:
        for a in auds:
            a.setdefault("glance", shared)
    return auds


def fetch_published_summaries(apex):
    """The audience tabs, sourced from the *network* instead of a local file: any
    AI plain-language summary nanopub published `schema:about` this apex (see the
    AI-summary template). Each is a signed, agent-attributed nanopublication, so the
    tab links back to it. Returns [] on any network error, so the caller falls back
    to a committed audience.json. One (latest, live) summary per audience."""
    if not apex:
        return []
    q = f"""PREFIX schema: <https://schema.org/>
PREFIX npa: <http://purl.org/nanopub/admin/>
PREFIX npx: <http://purl.org/nanopub/x/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?np ?audience ?text ?audLabel ?isEdu ?date WHERE {{
  GRAPH ?a {{ ?s schema:about <{apex}> ; schema:audience ?audience ; rdfs:comment ?text . }}
  GRAPH npa:graph {{ ?np npa:hasGraph ?a ; dct:created ?date . }}
  FILTER NOT EXISTS {{ ?inv npx:invalidates ?np . }}
  FILTER NOT EXISTS {{ ?sup npx:supersedes ?np . }}
  OPTIONAL {{ GRAPH ?va {{ ?audience rdfs:label ?audLabel . }} }}
  OPTIONAL {{ GRAPH ?vt {{ ?audience a schema:EducationalAudience . BIND(true AS ?isEdu) }} }}
}} ORDER BY DESC(?date)"""
    try:
        rows = sparql(q)
    except Exception:
        return []
    seen, out = set(), []
    for r in rows:
        aud = r["audience"]["value"]
        if aud in seen:                              # one (latest) per audience term
            continue
        seen.add(aud)
        raw = (r.get("audLabel") or {}).get("value", "")
        label = raw.split(" - ", 1)[0].strip() or aud.rstrip("/").rsplit("/", 1)[-1]
        slug = re.sub(r"[^a-z0-9]+", "-", aud.rstrip("/").rsplit("/", 1)[-1].lower()).strip("-")
        out.append({
            "id": slug or "audience",
            "label": label,
            "icon": "graduation-cap" if "isEdu" in r else "users",
            # the signed nanopub's rdfs:comment is flat prose — render as one section
            "sections": [{"h": "", "p": r["text"]["value"]}],
            "np_uri": r["np"]["value"],
        })
    return out


# Inlined Font Awesome Free 6.5.1 icons (CC BY 4.0, https://fontawesome.com) — the
# same icon family the Science Live site uses. Inlined (not a CDN link) so the page
# stays self-contained. (viewBox, path).
ICONS = {
    "file-lines": ("0 0 384 512", "M64 0C28.7 0 0 28.7 0 64V448c0 35.3 28.7 64 64 64H320c35.3 0 64-28.7 64-64V160H256c-17.7 0-32-14.3-32-32V0H64zM256 0V128H384L256 0zM112 256H272c8.8 0 16 7.2 16 16s-7.2 16-16 16H112c-8.8 0-16-7.2-16-16s7.2-16 16-16zm0 64H272c8.8 0 16 7.2 16 16s-7.2 16-16 16H112c-8.8 0-16-7.2-16-16s7.2-16 16-16zm0 64H272c8.8 0 16 7.2 16 16s-7.2 16-16 16H112c-8.8 0-16-7.2-16-16s7.2-16 16-16z"),
    "users": ("0 0 640 512", "M144 0a80 80 0 1 1 0 160A80 80 0 1 1 144 0zM512 0a80 80 0 1 1 0 160A80 80 0 1 1 512 0zM0 298.7C0 239.8 47.8 192 106.7 192h42.7c15.9 0 31 3.5 44.6 9.7c-1.3 7.2-1.9 14.7-1.9 22.3c0 38.2 16.8 72.5 43.3 96c-.2 0-.4 0-.7 0H21.3C9.6 320 0 310.4 0 298.7zM405.3 320c-.2 0-.4 0-.7 0c26.6-23.5 43.3-57.8 43.3-96c0-7.6-.7-15-1.9-22.3c13.6-6.3 28.7-9.7 44.6-9.7h42.7C592.2 192 640 239.8 640 298.7c0 11.8-9.6 21.3-21.3 21.3H405.3zM224 224a96 96 0 1 1 192 0 96 96 0 1 1 -192 0zM128 485.3C128 411.7 187.7 352 261.3 352H378.7C452.3 352 512 411.7 512 485.3c0 14.7-11.9 26.7-26.7 26.7H154.7c-14.7 0-26.7-11.9-26.7-26.7z"),
    "graduation-cap": ("0 0 640 512", "M320 32c-8.1 0-16.1 1.4-23.7 4.1L15.8 137.4C6.3 140.9 0 149.9 0 160s6.3 19.1 15.8 22.6l57.9 20.9C57.3 229.3 48 259.8 48 291.9v28.1c0 28.4-10.8 57.7-22.3 80.8c-6.5 13-13.9 25.8-22.5 37.6C0 442.7-.9 448.3 .9 453.4s6 8.9 11.2 10.2l64 16c4.2 1.1 8.7 .3 12.4-2s6.3-6.1 7.1-10.4c8.6-42.8 4.3-81.2-2.1-108.7C90.3 344.3 86 329.8 80 316.5V291.9c0-30.2 10.2-58.7 27.9-81.5c12.9-15.5 29.6-28 49.2-35.7l157-61.7c8.2-3.2 17.5 .8 20.7 9s-.8 17.5-9 20.7l-157 61.7c-12.4 4.9-23.3 12.4-32.2 21.6l159.6 57.6c7.6 2.7 15.6 4.1 23.7 4.1s16.1-1.4 23.7-4.1L624.2 182.6c9.5-3.4 15.8-12.5 15.8-22.6s-6.3-19.1-15.8-22.6L343.7 36.1C336.1 33.4 328.1 32 320 32zM128 408c0 35.3 86 72 192 72s192-36.7 192-72L496.7 262.6 354.5 314c-11.1 4-22.8 6-34.5 6s-23.5-2-34.5-6L143.3 262.6 128 408z"),
}


def svg_icon(name):
    spec = ICONS.get(name or "")
    if not spec:
        return ""
    vb, d = spec
    return (f'<svg class="tab-ico" viewBox="{vb}" aria-hidden="true" focusable="false" '
            f'fill="currentColor"><path d="{d}"/></svg>')


def tab_bar(audiences):
    tabs = ('<button class="tab active" type="button" data-tab="record">'
            f'{svg_icon("file-lines")}The record</button>')
    for a in audiences:
        icon = svg_icon(a.get("icon"))
        tabs += (f'<button class="tab" type="button" data-tab="{esc(a["id"])}">'
                 f'{icon}{esc(a["label"])}</button>')
    return f'<div class="tabbar" role="tablist">{tabs}</div>'


GLANCE_ICON = {"ok": "✓", "warn": "✗", "bad": "✗"}   # ✓ / ✗


def glance_card(spec, verdicts):
    """An 'at a glance' infographic for a lay audience. The lay LABELS come from the
    audience spec; the row colour and the ✓/✗ come from the signed record's verdicts
    (zipped in chain order), so the graphic cannot disagree with the science."""
    items = (spec or {}).get("items") or []
    rows = ""
    for item, (vclass, verdict) in zip(items, verdicts):
        sub = f' <small>({esc(item["sub"])})</small>' if item.get("sub") else ""
        says = f'<span class="glance-says">{esc(item["says"])}</span>' if item.get("says") else ""
        rows += (f'<li class="glance-row {esc(vclass)}"><span class="glance-dot"></span>'
                 f'<span class="glance-label">{esc(item.get("label", ""))}{sub}</span>'
                 f'{says}<span class="glance-icon" title="{esc(verdict)}">'
                 f'{GLANCE_ICON.get(vclass, "")}</span></li>')
    if not rows:
        return ""
    title = f'<figcaption class="glance-title">{esc(spec.get("title", ""))}</figcaption>' if spec.get("title") else ""
    note = f'<p class="glance-note">{esc(spec["note"])}</p>' if spec.get("note") else ""
    return f'<figure class="glance">{title}<ul class="glance-rows">{rows}</ul>{note}</figure>'


def render_audience(aud, verdicts=(), hero=None):
    """One audience panel: a labelled AI banner, a real (accessible) hero image and
    an accurate-by-construction 'at a glance' graphic, then the plain-language
    retelling (title, lead, titled sections, closing) — the words supplied by the
    build-time AI step, the image and the graphic's colours/ticks from the record."""
    who = aud.get("label", "a general audience").strip()
    who = who[4:] if who.lower().startswith("for ") else who
    level = (f'<p class="aud-level"><span class="aud-i" aria-hidden="true">i</span>'
             f'Recommended reading level &mdash; {esc(aud["level"])}</p>'
             if aud.get("level") else "")
    deck = f'<p class="deck">{esc(aud["lead"])}</p>' if aud.get("lead") else ""
    # the same real overview figure the Record tab uses — an accessible anchor, no
    # invented caption (the plain-language cap can be supplied by the AI layer)
    cap = f'<figcaption>{esc(aud["hero_caption"])}</figcaption>' if aud.get("hero_caption") else ""
    hero_html = (f'<figure class="fig wide"><img src="{esc(inline_figure(hero[0]))}" '
                 f'alt="Overview image of the study">{cap}</figure>' if hero else "")
    glance = glance_card(aud.get("glance"), verdicts)
    # section headings are optional — a published summary is one untitled prose block
    secs = "".join((f'<h2 class="sec">{esc(s["h"])}</h2>' if s.get("h") else "")
                   + prose_blocks(s.get("p", ""))
                   for s in aud.get("sections", []))
    closing = f'<p class="aud-closing">{esc(aud["closing"])}</p>' if aud.get("closing") else ""
    title_html = f'<h1>{esc(aud["title"])}</h1>' if aud.get("title") else ""
    # when the tab is sourced from a published nanopub, link back to that signed,
    # agent-attributed artefact — the point of putting the summary on the network
    prov = ""
    if aud.get("np_uri"):
        npurl = PLATFORM + "/np/?uri=" + urllib.parse.quote(aud["np_uri"], safe="")
        prov = (f'<p class="aud-prov">Published as a signed nanopublication, attributed to an '
                f'AI software agent. <a href="{esc(npurl)}" target="_blank" rel="noopener">'
                f'View the nanopublication &#8599;</a></p>')
    return (f'<article class="article">'
            f'<div class="ai-banner"><span class="ai-tag">AI-generated summary</span>'
            f'A plain-language retelling for {esc(who)}, written by an AI from the verified '
            f'record. It simplifies and never overrides the signed science. '
            f'<a href="#" data-goto="record">Read the full record &rarr;</a></div>{prov}'
            f'<p class="eyebrow">Plain-language summary</p>'
            f'{title_html}{level}{deck}{hero_html}{glance}{secs}{closing}</article>')


def tabs_wrap(audiences, verdicts=(), hero=None):
    """(open, close) markup to wrap the record article in a tab shell. Empty when
    there are no audiences, so a page with none is byte-identical to before.
    `verdicts` is the record's per-limb (vclass, verdict) for the glance graphic;
    `hero` is the record's overview figure, reused as each audience tab's image."""
    if not audiences:
        return "", ""
    open_ = tab_bar(audiences) + '<div class="tabpanel active" data-panel="record">'
    close = '</div>' + "".join(
        f'<div class="tabpanel" data-panel="{esc(a["id"])}">{render_audience(a, verdicts, hero)}</div>'
        for a in audiences)
    return open_, close


# ------------------------------------------------------------------ render
def platform_view_button(uri):
    """This page is a static mirror; the live, regenerable version lives on the
    Science Live platform. Link there rather than showing a dead 'Regenerate'
    control the static page cannot honour."""
    if not uri:
        return ""
    url = PLATFORM + "/np/?uri=" + urllib.parse.quote(uri, safe="")
    return (f'<a class="btn" href="{esc(url)}" target="_blank" rel="noopener" '
            f'title="Open the live, authoritative version on the Science Live platform">'
            f'&#8599; View on Science Live</a>')


def render(d, style, audiences=()):
    a, pub, steps = d["a"], d["pub"], d["steps"]
    root = d["root"]
    claim, study, out = a.get("Claim", {}), a.get("Study", {}), a.get("Outcome", {})
    name, _, _ = citation_parts(steps.get("Outcome", {}).get("uri", ""),
                                pub.get("Outcome", {}), out)
    creator = one(pub.get("Outcome", {}), "creator") or ""
    parts_ = [w for w in re.split(r"[\s,]+", name or "") if w]
    initials = ((parts_[0][:1] + parts_[-1][:1]) if len(parts_) > 1
                else (parts_[0][:2] if parts_ else "?")).upper()
    created = (one(pub.get("Outcome", {}), "created") or "")[:10]
    verdict = term_label(one(out, "hasValidationStatus"))
    conf = term_label(one(out, "hasConfidenceLevel"))

    # --- the same credit/provenance treatment as the synthesis page ---
    outcome_uri = steps.get("Outcome", {}).get("uri", "")
    vclass = VERDICT_CLASS.get(re.sub(r"\s+", "", verdict.lower()), "ok") if verdict else "ok"
    tabbar_open, panels_close = tabs_wrap(audiences, [(vclass, verdict)] if verdict else [])
    # verdict + confidence chips link to the Outcome nanopublication that asserts them
    if verdict:
        vchip = (f'<a class="verdict {vclass}" href="{esc(outcome_uri)}" '
                 f'title="Validation status &mdash; from the signed Outcome nanopublication">'
                 f'<span class="dot"></span> {esc(verdict)}</a>' if outcome_uri else
                 f'<span class="verdict {vclass}"><span class="dot"></span> {esc(verdict)}</span>')
    else:
        vchip = ""
    cchip = ""
    if conf:
        cchip = (f'<a class="tag" href="{esc(outcome_uri)}" '
                 f'title="Confidence level &mdash; from the signed Outcome nanopublication">{esc(conf)}</a>'
                 if outcome_uri else f'<span class="tag">{esc(conf)}</span>')
    # ORCID-aware byline
    if creator and "orcid.org" in creator:
        oid = creator.rstrip("/").rsplit("/", 1)[-1]
        orcid_html = (f'<span class="orcidline"><span class="oi"></span>'
                      f'<a href="{esc(creator)}">ORCID {esc(oid)}</a></span>')
    elif creator:
        orcid_html = f'<a href="{esc(creator)}">{esc(creator)}</a>'
    else:
        orcid_html = ""
    # prominent, collapsible "cite this replication" — apex is the Outcome nanopub
    cite_title = one(claim, "label") or one(out, "label") or "Replication"
    cite_text = f'{name}. ({created[:4] or "n.d."}). {cite_title} [Nanopublication]. {outcome_uri}'
    cite_html = (f'<details class="citecard" id="cite"><summary class="cc-label">Cite this replication</summary>'
                 f'<div class="cc-body">'
                 f'<div class="citetext" id="citetext">{esc(cite_text)}</div>'
                 f'<button class="copybtn" type="button" data-copy="citetext">Copy citation</button>'
                 f'<p class="cc-note">This replication chain has a permanent identifier, '
                 f'<a class="u" href="{esc(outcome_uri)}">{esc(outcome_uri)}</a>, that always resolves to '
                 f'the signed record. Citing it credits the replication and its author.</p>'
                 f'</div></details>') if outcome_uri else ""
    platform_view_btn = platform_view_button(outcome_uri)

    cites_items = ""
    for p_, o in d["cites"]:
        ll = link_label(o)
        cites_items += (f'<li><span class="relpill">{esc(rel_label(p_))}</span>'
                        f'<span class="ctitle">{esc(ll["title"] or o)}</span>'
                        f'<a class="cu" href="{esc(o)}">{esc(o)}</a></li>')
    cito_chip = (f'<span class="hint"><a class="tag citochip" href="#cites">CiTO &rarr; '
                 f'{len(d["cites"])}</a><span class="box" role="tooltip">'
                 f'<strong>cites the following:</strong>'
                 f'<ul class="creditlist">{cites_items}</ul></span></span>') if d["cites"] else ""

    def _shorturl(u):
        return re.sub(r"^https?://(www\.)?", "", u).rstrip("/")

    res = "".join(
        f'<li><a href="{esc(u)}">{esc(t)}</a><span class="what">{esc(w)}</span>'
        f'<a class="reslink" href="{esc(u)}">{esc(_shorturl(u))}</a></li>'
        for u, t, w in ((d.get("book"), "Read the Jupyter Book", "The rendered narrative, notebooks and figures."),
                        (d.get("repo"), "Repository", "Code, workflow and notebooks."),
                        (d.get("history"), "Live run", "The actual execution, public."),
                        (one(out, "hasOutcomeRepository"), archive_label(one(out, "hasOutcomeRepository"))[0] or "Archived release",
                         archive_label(one(out, "hasOutcomeRepository"))[1] or "Citable, frozen snapshot."))
        if u)

    refs = ""
    for kind, uri in d["order"]:
        p = root["pub"] if kind == "Question" and root else pub.get(kind, {})
        g = root["a"] if kind == "Question" and root else a.get(kind, {})
        n, y, t = citation_parts(uri, p, g)
        badge = ((" / ".join(term_label(x) for x in root["types"]) or root["kind"])
                 if kind == "Question" and root else kind)
        refs += (f'<li>{esc(n)}. ({esc(y)}). {esc(t)} [Nanopublication]. '
                 f'<a class="u" href="{esc(uri)}">{esc(uri)}</a> '
                 f'<span class="nptype">{esc(badge)}</span></li>')

    fig = (f'<figure class="fig wide"><img src="{esc(inline_figure(d["figure"][0]))}" alt="Figure from the replication">'
           f'<figcaption><strong>The result.</strong> '
           f'<a class="u" href="{esc(raw_to_blob(d["figure"][0]))}">{esc(d["figure"][1])}</a> &mdash; the headline '
           f'figure named in the Outcome evidence, resolved from the repository.</figcaption></figure>'
           ) if d.get("figure") else ""

    meta = meta_chips([
        ("Study", term_label(pick_type(study)), pick_type(study)),
        ("Claim", term_label(pick_type(claim)), pick_type(claim)),
        ("Work completed", (one(out, "endDate") or "")[:10], None),
    ])
    kw = "".join(f'<a class="tag" href="{esc(v)}">{esc(term_label(v))}</a>'
                 for v in many(study, "related"))
    tp = "".join(f'<a class="tag" href="{esc(v)}">{esc(term_label(v))}</a>'
                 for v in many(a.get("AIDA", {}), "about"))
    supported = ""
    for v in many(a.get("AIDA", {}), "obtainsSupportFrom"):
        ll = link_label(v)
        supported += (f'<li><span class="stitle">{esc(ll["title"] or v)}</span>'
                      f'<span class="smeta">{ll["sub"]}</span>'
                      f'<a class="sdoi" href="{esc(v)}">{esc(v)}</a></li>')

    hoststrip = ""
    for h, hurl in d.get("hosts", []):
        ic = site_icon(h)
        img = f'<img src="{esc(ic)}" alt="">' if ic else ""
        hoststrip += f'<li><a href="{esc(hurl)}">{img}<span>{esc(h)}</span></a></li>'

    aida_text = urllib.parse.unquote_plus((steps.get("AIDA", {}) or {}).get("text", "") or "")
    q_label = ({"PCC": "Review Question", "Quote": "From the original paper",
                "PICO": "Research Question"}.get(root["kind"], "Research Question")
               if root else "Research Question")

    return f"""<title>Replication story &mdash; generated</title>
{style}
{SYNTH_CSS}
<div class="toolbar"><div class="inner">
  <span class="brandmark"><span class="sq"></span> Science Live <span class="sub">&middot; replication story</span></span>
  <span class="tools">
    <a class="btn" href="#cite">&#10077; Cite</a>
    {platform_view_btn}
    <button class="btn" type="button" id="tt"><span id="tticon">&#9789;</span> <span id="ttlabel">Dark</span></button>
  </span></div></div>

{tabbar_open}
<article class="article">
  <header class="head">
    <div class="headtop">
      <p class="eyebrow">Independent replication
        <span class="hint left"><button class="infobtn" type="button" aria-label="How this page is made">i</button>
        <span class="box" role="tooltip"><strong>How this page is made</strong>
        An aggregation of the {len(d["order"])} nanopublications in this chain, using the same fields and
        labels the platform shows for each one &mdash; restyled and reordered. Values are taken verbatim;
        absent fields are omitted rather than filled in.</span></span>
        {f'<a class="tag disciplinechip" href="{esc(one(study, "hasDiscipline"))}">{esc(term_label(one(study, "hasDiscipline")))}</a>' if one(study, "hasDiscipline") else ""}
      </p>
      <div class="statuschips">
        {vchip}
        {cchip}
        {cito_chip}
      </div>
    </div>
    <h1>{esc(one(claim, "label") or one(out, "label") or "Replication")}</h1>
    {f'<p class="deck">{esc(root["label"])}</p>' if root else ""}
    <div class="authorrow">
      <span class="avatar" aria-hidden="true">{esc(initials)}</span>
      <span class="who"><span class="name">{esc(name)}</span>
        <span class="meta">{orcid_html} &middot; published {esc(created)}</span></span>
    </div>
    {f'<ul class="tags">{meta}</ul>' if meta else ""}
    {f'<ul class="tags"><li class="tagslabel">Topics</li>{tp}</ul>' if tp else ""}
    {f'<ul class="tags"><li class="tagslabel">Keywords</li>{kw}</ul>' if kw else ""}
  </header>

  {cite_html}

  {fig}

  {f'''<p class="seclabel">{q_label}</p>
  <p class="bigq">{esc(root["label"])}</p>
  {f'<p class="lead">{esc(root["body"])}</p>' if root["body"] else ""}
  {f'<p class="srcline">Quoted from: <a href="{esc(root["quotes"])}">{esc(root["quotes"])}</a></p>' if root.get("quotes") else ""}
  {part_chips(root["kind"], root["a"])}''' if root else ""}

  <h2 class="sec" id="what">What is being replicated</h2>
  <div class="pull"><p class="qlabel">{esc(one(claim, "label") or "")}</p>
    {f'<p>{esc(aida_text)}</p>' if aida_text else ""}</div>
  {f'<p class="srcline">Source: <a href="{esc(one(claim, "source"))}">{esc(one(claim, "source"))}</a></p>' if one(claim, "source") else ""}

  <h2 class="sec">The replication study</h2>
  {narrative("Study", study)}

  <h2 class="sec">The outcome</h2>
  {narrative("Outcome", out)}

  {f'<h2 class="sec" id="cites">Citation &mdash; cites the following:</h2><ul class="creditlist citeslist">{cites_items}</ul>' if d["cites"] else ""}

  {f'<div class="rescard wide"><span class="cardlabel">Follow the work</span><ul class="reslinks">{res}</ul></div>' if res else ""}

  <h2 class="sec">Responses</h2>
  <div class="empty"><strong>No approvals, disapprovals or comments yet.</strong><br>
    Anyone with an ORCID can approve, disapprove or comment on any nanopublication in this chain.</div>

  <section class="refs wide" id="refs">
    <h2>References &mdash; nanopublications in this chain</h2>
    <ol class="bib">{refs}</ol>
    {f'<h3>Supported by</h3><ul class="srcs">{supported}</ul>' if supported else ""}
    <p class="note" style="margin-top:.7rem;">Citations use the platform's rule: author from
      <span class="u">dct:creator</span>&rsquo;s <span class="u">foaf:name</span>, title from
      <span class="u">rdfs:label</span> in the publication info.</p>
  </section>

  <footer class="storyfoot wide">
    <span class="brandmark"><span class="sq"></span> Science Live</span>
    <span>Generated from {len(d["order"])} signed nanopublications &middot; verdict, responses and credits read live from the network.</span>
  </footer>
</article>
{panels_close}
<script>
(function(){{var r=document.documentElement,b=document.getElementById('tt'),
i=document.getElementById('tticon'),l=document.getElementById('ttlabel');
function cur(){{return r.getAttribute('data-theme')||(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');}}
function p(){{var d=cur()==='dark';i.innerHTML=d?'&#9788;':'&#9789;';l.textContent=d?'Light':'Dark';}}
b.addEventListener('click',function(){{r.setAttribute('data-theme',cur()==='dark'?'light':'dark');p();}});p();}})();
(function(){{
Array.prototype.forEach.call(document.querySelectorAll('.copybtn'),function(btn){{
  btn.addEventListener('click',function(){{
    var el=document.getElementById(btn.getAttribute('data-copy'));if(!el)return;
    var txt=el.textContent,ok=false;
    try{{if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(txt);ok=true;}}}}catch(e){{}}
    if(!ok){{try{{var rg=document.createRange();rg.selectNodeContents(el);var s=getSelection();
      s.removeAllRanges();s.addRange(rg);document.execCommand('copy');s.removeAllRanges();ok=true;}}catch(e){{}}}}
    var old=btn.textContent;btn.textContent=ok?'Copied':'Press Ctrl/Cmd+C';
    setTimeout(function(){{btn.textContent=old;}},1600);
  }});
}});
}})();
(function(){{document.addEventListener('click',function(e){{
  var a=e.target.closest?e.target.closest('a[href^="#"]'):null;if(!a)return;
  var el=document.getElementById(a.getAttribute('href').slice(1));
  if(el&&el.tagName==='DETAILS')el.open=true;
}});}})();
(function(){{
  var tabs=document.querySelectorAll('.tab'),panels=document.querySelectorAll('.tabpanel');
  if(!tabs.length)return;
  function show(id){{
    tabs.forEach(function(t){{t.classList.toggle('active',t.getAttribute('data-tab')===id);}});
    panels.forEach(function(p){{p.classList.toggle('active',p.getAttribute('data-panel')===id);}});
    try{{scrollTo({{top:0}});}}catch(e){{}}
  }}
  tabs.forEach(function(t){{t.addEventListener('click',function(){{show(t.getAttribute('data-tab'));}});}});
  document.addEventListener('click',function(e){{
    var g=e.target.closest&&e.target.closest('[data-goto]');
    if(g){{e.preventDefault();show(g.getAttribute('data-goto'));}}
  }});
}})();
</script>
"""


SYNTH_CSS = """<style>
/* audience tabs — the Record tab is the deterministic page; audience tabs are
   the opt-in AI layer, clearly banner-labelled */
.tabbar{display:flex;gap:.15rem;flex-wrap:wrap;max-width:var(--col);margin:1.3rem auto 0;
  padding:0 var(--gutter);border-bottom:1px solid var(--hairline);}
.tab{display:inline-flex;align-items:center;gap:.45rem;font-family:var(--sans);font-size:.9rem;
  font-weight:600;color:var(--muted);background:transparent;border:none;
  border-bottom:2.5px solid transparent;padding:.55rem .9rem;margin-bottom:-1px;cursor:pointer;}
.tab-ico{width:.95em;height:.95em;flex:none;}
.tab:hover{color:var(--ink);}
.tab.active{color:var(--brand);border-bottom-color:var(--brand);}
.tabpanel{display:none;}
.tabpanel.active{display:block;}
.ai-banner{margin:1.6rem 0 .4rem;padding:.9rem 1.1rem;background:var(--accent-dim);
  border:1px solid var(--accent);border-radius:10px;font-family:var(--sans);font-size:.88rem;
  line-height:1.5;color:var(--ink);}
.ai-tag{display:inline-block;font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:#fff;background:var(--accent);border-radius:999px;padding:.14rem .55rem;margin-right:.5rem;}
.ai-banner a{color:var(--accent);font-weight:700;white-space:nowrap;}
.aud-prov{margin:.55rem 0 0;font-family:var(--sans);font-size:.8rem;color:var(--muted);}
.aud-prov a{color:var(--accent);font-weight:600;white-space:nowrap;}
.aud-closing{margin:1.7rem 0;font-family:var(--serif);font-size:1.2rem;font-weight:600;line-height:1.4;
  border-left:4px solid var(--brand);padding-left:1.1rem;color:var(--ink);}
.aud-level{display:flex;align-items:center;gap:.5rem;font-family:var(--sans);font-size:.85rem;
  color:var(--muted);margin:-.4rem 0 1.3rem;padding:.55rem .8rem;background:var(--sunken);
  border-radius:8px;}
.aud-i{flex:none;width:1.15rem;height:1.15rem;border-radius:50%;background:var(--accent);color:#fff;
  font-family:var(--serif);font-style:italic;font-weight:700;font-size:.8rem;line-height:1.15rem;
  text-align:center;}
/* "at a glance" infographic — colours + ticks come from the record's verdicts */
.glance{margin:1.4rem 0 1.6rem;border:1px solid var(--hairline);border-radius:12px;
  padding:1.2rem 1.4rem;background:var(--surface);}
.glance-title{font-family:var(--sans);font-size:.74rem;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;color:var(--muted);margin:0 0 .8rem;}
.glance-rows{list-style:none;margin:0;padding:0;}
.glance-row{display:flex;align-items:center;gap:.7rem;padding:.55rem 0;
  border-top:1px solid var(--hairline);font-family:var(--sans);}
.glance-row:first-child{border-top:none;}
.glance-dot{width:.85rem;height:.85rem;border-radius:50%;flex:none;}
.glance-row.ok .glance-dot{background:var(--ok);} .glance-row.warn .glance-dot{background:var(--warn);}
.glance-row.bad .glance-dot{background:var(--bad);}
.glance-label{font-size:1.05rem;font-weight:600;color:var(--ink);flex:1;}
.glance-label small{font-weight:400;color:var(--muted);font-size:.85rem;}
.glance-says{font-size:.92rem;font-weight:600;}
.glance-row.ok .glance-says{color:var(--ok);} .glance-row.warn .glance-says{color:var(--warn);}
.glance-row.bad .glance-says{color:var(--bad);}
.glance-icon{font-size:1.15rem;font-weight:700;width:1.3rem;text-align:center;flex:none;}
.glance-row.ok .glance-icon{color:var(--ok);} .glance-row.warn .glance-icon{color:var(--warn);}
.glance-row.bad .glance-icon{color:var(--bad);}
.glance-note{font-family:var(--sans);font-size:.9rem;color:var(--muted);margin:.9rem 0 0;
  font-style:italic;line-height:1.45;}
/* the info popup is nested in .eyebrow and inherits its uppercasing — reset the
   body to normal case, keep only the tooltip title uppercase */
.eyebrow .box{text-transform:none;}
.eyebrow .box strong{text-transform:uppercase;letter-spacing:.05em;}
.synthlead{font-size:1.12rem;line-height:1.62;}
.synthlead p{margin:0 0 1rem;}
.prose-list{margin:.3rem 0 1.2rem;padding-left:1.3rem;}
.prose-list li{margin:.55rem 0;line-height:1.55;}
/* Each limb is a full-width section, so its figure gets the whole column width
   (the same as the hero) instead of a cramped half. Stacking also scales cleanly
   to any number of replications — the hero pills jump-link to each one. */
.limbwrap{display:flex;flex-direction:column;gap:2.2rem;margin:1rem 0 1.4rem;}
.limb{border:1.5px solid var(--hairline);border-radius:12px;padding:1.6rem 1.8rem 1.4rem;
  background:var(--surface);scroll-margin-top:5rem;}
.limb.ok{border-top:4px solid var(--ok);} .limb.warn{border-top:4px solid var(--warn);}
.limb.bad{border-top:4px solid var(--bad);}
.limbhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35rem 1rem;}
.limbindex{font-family:var(--sans);font-size:.74rem;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;color:var(--muted);flex-basis:100%;}
.limb h3{font-family:var(--serif);font-size:clamp(1.25rem,2.4vw,1.6rem);line-height:1.2;
  margin:.15rem 0 .55rem;flex-basis:100%;}
.limbq{font-size:.9rem;color:var(--muted);margin:0 0 .9rem;line-height:1.5;}
.limbmeta{display:flex;flex-wrap:wrap;gap:.45rem;margin:.2rem 0 1.1rem;}
.verdict.warn{color:var(--warn);} .verdict.bad{color:var(--bad);}
a.verdict,a.relpill,a.tag{text-decoration:none;}
a.verdict:hover,a.relpill:hover,a.tag:hover{filter:brightness(1.08);text-decoration:underline;}
.limb .concl{font-size:1rem;line-height:1.6;margin:1rem 0 1.1rem;}
.limbfig{margin:.4rem 0 .3rem;border-radius:8px;overflow:hidden;border:1px solid var(--hairline);}
.limbfig img{display:block;width:100%;}
.limbfig figcaption{font-family:var(--sans);font-size:.8rem;color:var(--muted);
  padding:.55rem .8rem;background:var(--sunken);line-height:1.45;}
.limblinks{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-family:var(--sans);font-size:.83rem;
  padding-top:.9rem;margin-top:.4rem;border-top:1px solid var(--hairline);}
.limblinks a{color:var(--accent);text-decoration:none;font-weight:600;}
.limblinks a:hover{text-decoration:underline;}
/* three parallel groups in References — each colour-keyed to its limb above */
.refgroup{border:1px solid var(--hairline);border-left:5px solid var(--hairline);
  border-radius:0 8px 8px 0;padding:1.2rem 1.4rem 1.3rem;margin:2.4rem 0;}
.refgroup:first-of-type{margin-top:1.4rem;}
.refgroup.accent{border-left-color:var(--accent);}
.refgroup.ok{border-left-color:var(--ok);}
.refgroup.warn{border-left-color:var(--warn);}
.refgroup.bad{border-left-color:var(--bad);}
.refgroup-h{font-family:var(--serif);font-size:1.16rem;font-weight:600;line-height:1.25;
  color:var(--ink);margin:0 0 .3rem;}
.refgroup-k{font-family:var(--sans);font-size:.72rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.09em;margin:0 0 .5rem;}
.refgroup.accent .refgroup-k{color:var(--accent);}
.refgroup.ok .refgroup-k{color:var(--ok);}
.refgroup.warn .refgroup-k{color:var(--warn);}
.refgroup.bad .refgroup-k{color:var(--bad);}
.subref{font-family:var(--sans);font-size:.7rem;font-weight:700;text-transform:uppercase;
  letter-spacing:.09em;color:var(--muted);margin:.9rem 0 .3rem;}
/* bottom-line callout — the payoff in the first screen */
.bottomline{border:1.5px solid var(--accent);background:var(--accent-dim);border-radius:12px;
  padding:1.3rem 1.5rem;margin:1.5rem 0 2rem;}
.bl-label{display:block;font-family:var(--sans);font-size:.74rem;font-weight:700;letter-spacing:.1em;
  text-transform:uppercase;color:var(--accent);margin-bottom:.75rem;}
.bl-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.9rem;}
.bl-rec{margin:0;font-size:1.02rem;line-height:1.55;color:var(--ink);}
.bl-rec b{font-weight:700;color:var(--accent);}
/* tightened limb: a one-line lead, full verbatim conclusion folded away */
.limblead{font-size:1.02rem;line-height:1.55;font-weight:600;margin:1rem 0 .5rem;}
details.limbmore{margin:.1rem 0 1rem;}
details.limbmore>summary{cursor:pointer;font-family:var(--sans);font-size:.82rem;font-weight:700;
  color:var(--accent);list-style:none;}
details.limbmore>summary::-webkit-details-marker{display:none;}
details.limbmore>summary::before{content:"\\25B8  ";}
details.limbmore[open]>summary::before{content:"\\25BE  ";}
details.limbmore .cbody{margin:.6rem 0 0;font-size:.95rem;line-height:1.55;}
/* credit + citation */
.orcidline{display:inline-flex;align-items:center;gap:.3rem;}
.orcidline .oi{width:.85rem;height:.85rem;border-radius:50%;background:#a6ce39;display:inline-block;}
.citecard{border:1.5px solid var(--hairline);border-left:5px solid var(--brand);
  background:var(--surface);border-radius:0 12px 12px 0;padding:1.1rem 1.5rem;
  margin:1.3rem 0 1.8rem;scroll-margin-top:5rem;}
.cc-label{display:flex;align-items:center;gap:.4rem;cursor:pointer;list-style:none;
  font-family:var(--sans);font-size:.78rem;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;color:var(--brand);}
.cc-label::-webkit-details-marker{display:none;}
.cc-label::before{content:"\\275D";font-size:1.1rem;line-height:0;}
.cc-label::after{content:"\\25B8";margin-left:auto;font-size:.75rem;}
.citecard[open] .cc-label::after{content:"\\25BE";}
.citecard[open] .cc-label{margin-bottom:.9rem;}
.cc-body{}
.toolbar a.btn{text-decoration:none;}
/* "what is being replicated / drawn from" card — reuses the base .whatcard grid */
.whatcard{margin:1.4rem 0 1.6rem;}
.whatcard .drawn{background:var(--sunken);}
.whatcard .cardlabel{color:var(--brand);display:block;margin-bottom:.55rem;}
.whatpaper{font-family:var(--serif);font-size:1.05rem;line-height:1.35;margin:.2rem 0 .35rem;}
.whatpaper a{color:var(--ink);text-decoration:none;}
.whatpaper a:hover{text-decoration:underline;}
.whatcard .qlabel{font-size:1.12rem;}
.citetext{font-family:var(--mono);font-size:.84rem;line-height:1.55;background:var(--sunken);
  border-radius:8px;padding:.9rem 1rem;color:var(--ink);word-break:break-word;}
.copybtn{font-family:var(--sans);font-size:.8rem;font-weight:700;color:var(--accent);
  background:transparent;border:1.5px solid var(--accent);border-radius:999px;
  padding:.3rem .9rem;cursor:pointer;margin-top:.8rem;}
.copybtn:hover{background:var(--accent);color:#fff;}
.cc-note{font-family:var(--sans);font-size:.82rem;color:var(--muted);margin:.8rem 0 0;line-height:1.5;}
</style>"""


def render_synthesis(syn, style, audiences=()):
    rs, limbs = syn["rs"], syn["limbs"]
    name, _, _ = citation_parts(syn["uri"], syn["pub"], syn["a"])
    creator = one(syn["pub"], "creator") or ""
    created = (one(syn["pub"], "created") or "")[:10]
    parts_ = [w for w in re.split(r"[\s,]+", name or "") if w]
    initials = ((parts_[0][:1] + parts_[-1][:1]) if len(parts_) > 1
                else (parts_[0][:2] if parts_ else "?")).upper()

    paper = link_label(syn["paperDoi"]) if syn.get("paperDoi") else {"title": None, "sub": ""}
    deck = (f'<p class="deck">An independent replication &mdash; {len(limbs)} '
            f'{"limb" if len(limbs)==1 else "limbs"}, composed into one finding.</p>')

    # "What is being replicated, and from where" — the original claim stated in the
    # synthesis (verbatim, its first sentence) beside the source study resolved from
    # the paper DOI. Makes it unmistakable at the top that this is a replication.
    orig_claim = first_sentence(rs.get("synthesis") or "")
    doi = syn.get("paperDoi") or ""
    if paper.get("title"):
        src_bits = (f'<p class="whatpaper"><a href="{esc(doi)}">{esc(paper["title"])}</a></p>'
                    + (f'<p class="what">{esc(paper["sub"])}</p>' if paper.get("sub") else "")
                    + (f'<p class="srcline"><a href="{esc(doi)}">{esc(doi)}</a></p>' if doi else ""))
    elif doi:
        src_bits = f'<p class="srcline"><a href="{esc(doi)}">{esc(doi)}</a></p>'
    else:
        src_bits = '<p class="what">No source identifier in the record.</p>'
    whatcard_html = (
        '<div class="whatcard">'
        '<div><span class="cardlabel">What is being replicated</span>'
        + (f'<p class="qlabel">{esc(orig_claim)}</p>' if orig_claim else '')
        + '</div>'
        '<div class="drawn"><span class="cardlabel">Drawn from &mdash; the original study</span>'
        + src_bits + '</div></div>') if (orig_claim or doi) else ""

    views = [_limb_view(d) for d in limbs]
    tabbar_open, panels_close = tabs_wrap(
        audiences, [(v["vclass"], v["verdict"]) for v in views], syn.get("hero"))

    # hero: one coloured pill per limb — its CiTO relation and verdict. The pill
    # links to the CiTO citation nanopublication that signs the confirms/qualifies
    # relation (falls back to jumping to the limb if no CiTO nanopub is present).
    chips = "".join(
        f'<a href="{esc(v["cito_uri"] or ("#limb-%d" % i))}" class="verdict {v["vclass"]}" '
        f'title="{esc(v["relation"] or "Tested")} &mdash; the signed CiTO citation nanopublication">'
        f'<span class="dot"></span> {esc(v["relation"] or "Tested")}'
        f'{" &middot; " + esc(v["verdict"]) if v["verdict"] else ""}</a>'
        for i, v in enumerate(views, 1))

    topics_html = "".join(
        f'<a class="tag" href="{esc(u)}">{esc(term_label(u))}</a>' for u in syn.get("topics", []))
    topics_html = (f'<ul class="tags"><li class="tagslabel">Topics</li>{topics_html}</ul>'
                   if topics_html else "")

    hero = syn.get("hero")
    hero_html = (f'<figure class="fig wide"><img src="{esc(inline_figure(hero[0]))}" '
                 f'alt="Overview figure for the synthesis">'
                 f'<figcaption><strong>Overview.</strong> '
                 f'<a class="u" href="{esc(raw_to_blob(hero[0]))}">{esc(hero[1])}</a> &mdash; a figure from '
                 f'the replication repository, shared across both limbs.</figcaption></figure>'
                 if hero else "")

    # bottom line: the verdict pills (the at-a-glance index) + the record's own
    # first recommendation, verbatim — the payoff, in the first screen.
    key_rec = first_list_item(rs.get("recommendations") or "")
    bottomline_html = (f'<aside class="bottomline"><span class="bl-label">The bottom line</span>'
                       f'<div class="bl-chips">{chips}</div>'
                       + (f'<p class="bl-rec"><b>Recommendation:</b> {esc(key_rec)}</p>'
                          if key_rec else "")
                       + '</aside>') if (chips or key_rec) else ""

    # credit: an ORCID-aware byline
    if creator and "orcid.org" in creator:
        oid = creator.rstrip("/").rsplit("/", 1)[-1]
        orcid_html = (f'<span class="orcidline"><span class="oi"></span>'
                      f'<a href="{esc(creator)}">ORCID {esc(oid)}</a></span>')
    elif creator:
        orcid_html = f'<a href="{esc(creator)}">{esc(creator)}</a>'
    else:
        orcid_html = ""

    # citation: built from the synthesis nanopub's own metadata + its permanent URI
    cite_text = (f'{name}. ({created[:4] or "n.d."}). '
                 f'{rs.get("label") or "Research synthesis"} [Nanopublication]. {syn["uri"]}')
    cite_html = (f'<details class="citecard" id="cite"><summary class="cc-label">Cite this synthesis</summary>'
                 f'<div class="cc-body">'
                 f'<div class="citetext" id="citetext">{esc(cite_text)}</div>'
                 f'<button class="copybtn" type="button" data-copy="citetext">Copy citation</button>'
                 f'<p class="cc-note">The synthesis has a permanent identifier, '
                 f'<a class="u" href="{esc(syn["uri"])}">{esc(syn["uri"])}</a>, that always resolves to '
                 f'the signed record. Citing it credits the replication and its author.</p>'
                 f'</div></details>')
    platform_view_btn = platform_view_button(syn["uri"])

    # limb sections — one full-width block each, figure at the hero's width
    cards = ""
    n = len(views)
    for i, v in enumerate(views, 1):
        fig = ""
        if v.get("figure"):
            figname = v["figure"][1].rsplit("/", 1)[-1]
            fig = (f'<figure class="limbfig"><img src="{esc(inline_figure(v["figure"][0]))}" '
                   f'alt="Result figure for this replication">'
                   f'<figcaption><a class="u" href="{esc(raw_to_blob(v["figure"][0]))}">{esc(figname)}</a> '
                   f'&mdash; the figure named in this limb&rsquo;s outcome evidence.</figcaption></figure>')
        # each chip links to the nanopublication that ASSERTS it: validation status
        # and confidence live in the Outcome nanopub; the relation in the CiTO nanopub.
        ou, cu = v["outcome_uri"], v["cito_uri"]
        meta = ""
        if v["verdict"]:
            meta += (f'<a class="verdict {v["vclass"]}" href="{esc(ou)}" '
                     f'title="Validation status &mdash; from the signed Outcome nanopublication">'
                     f'<span class="dot"></span> {esc(v["verdict"])}</a>' if ou else
                     f'<span class="verdict {v["vclass"]}"><span class="dot"></span> {esc(v["verdict"])}</span>')
        if v["confidence"]:
            meta += (f'<a class="tag" href="{esc(ou)}" '
                     f'title="Confidence level &mdash; from the signed Outcome nanopublication">'
                     f'{esc(v["confidence"])}</a>' if ou else
                     f'<span class="tag">{esc(v["confidence"])}</span>')
        if v["relation"]:
            meta += (f'<a class="relpill" href="{esc(cu)}" '
                     f'title="CiTO relation &mdash; from the signed Citation nanopublication">'
                     f'{esc(v["relation"])}</a>' if cu else
                     f'<span class="relpill">{esc(v["relation"])}</span>')
        links = "".join(
            f'<a href="{esc(u)}">{esc(t)}</a>'
            for u, t in ((v["outcome_uri"], "Full replication chain →"),
                         (v["book"], "Jupyter Book"), (v["repo"], "Repository"),
                         (v["archive"], "Archived release")) if u)
        # tighten: a one-line lead, the full verbatim conclusion folded into <details>
        concl = v["conclusion"]
        lead = first_sentence(concl) if concl else ""
        lead_html = f'<p class="limblead">{esc(lead)}</p>' if lead else ""
        more_html = (f'<details class="limbmore"><summary>Full conclusion</summary>'
                     f'<div class="cbody">{prose_blocks(concl)}</div></details>'
                     if concl and len(concl.strip()) > len(lead) + 20 else "")
        cards += (f'<article class="limb {v["vclass"]}" id="limb-{i}">'
                  f'<div class="limbhead"><span class="limbindex">Replication {i} of {n}</span>'
                  f'<h3>{esc(v["heading"])}</h3></div>'
                  f'<div class="limbmeta">{meta}</div>'
                  f'{fig}'
                  f'{lead_html}'
                  f'{more_html}'
                  f'<div class="limblinks">{links}</div>'
                  f'</article>')

    # references: the synthesis nanopub, then each limb's chain nanopubs
    refs = (f'<li>{esc(name)}. ({esc(created[:4] or "n.d.")}). {esc(rs.get("label") or "Research synthesis")} '
            f'[Nanopublication]. <a class="u" href="{esc(syn["uri"])}">{esc(syn["uri"])}</a> '
            f'<span class="nptype">Research Synthesis</span></li>')
    per_limb = ""
    for i, (v, d) in enumerate(zip(views, limbs), 1):
        # what this replication cites — CiTO relation + the target's resolved title
        cites_li = "".join(
            f'<li><span class="relpill">{esc(rel_label(p_))}</span>'
            f'<span class="ctitle">{esc(link_label(o)["title"] or o)}</span>'
            f'<a class="cu" href="{esc(o)}">{esc(o)}</a></li>'
            for p_, o in d["cites"])
        cites_html = (f'<p class="subref">Cites the following</p>'
                      f'<ul class="creditlist citeslist">{cites_li}</ul>' if cites_li else "")
        # supporting sources declared on the AIDA (resolved to titles)
        sup_li = ""
        for s in many(d["a"].get("AIDA", {}), "obtainsSupportFrom"):
            ll = link_label(s)
            sup_li += (f'<li><span class="stitle">{esc(ll["title"] or s)}</span>'
                       f'<span class="smeta">{esc(ll["sub"])}</span>'
                       f'<a class="sdoi" href="{esc(s)}">{esc(s)}</a></li>')
        sup_html = (f'<p class="subref">Supported by</p><ul class="srcs">{sup_li}</ul>'
                    if sup_li else "")
        items = ""
        for kind, uri in d["order"]:
            p = d["root"]["pub"] if kind == "Question" and d["root"] else d["pub"].get(kind, {})
            g = d["root"]["a"] if kind == "Question" and d["root"] else d["a"].get(kind, {})
            n, y, t = citation_parts(uri, p, g)
            badge = ((" / ".join(term_label(x) for x in d["root"]["types"]) or d["root"]["kind"])
                     if kind == "Question" and d["root"] else kind)
            items += (f'<li>{esc(n)}. ({esc(y)}). {esc(t)} [Nanopublication]. '
                      f'<a class="u" href="{esc(uri)}">{esc(uri)}</a> '
                      f'<span class="nptype">{esc(badge)}</span></li>')
        per_limb += (f'<div class="refgroup {v["vclass"]}">'
                     f'<p class="refgroup-k">Replication {i} &middot; {esc(v["relation"] or "")}</p>'
                     f'<p class="refgroup-h">{esc(v["heading"])}</p>'
                     + cites_html
                     + f'<p class="subref">Nanopublications in this chain</p>'
                     + f'<ol class="bib">{items}</ol>'
                     + sup_html
                     + '</div>')

    def block(title, key):
        body = prose_blocks(rs.get(key) or "")
        return f'<h2 class="sec">{esc(title)}</h2>{body}' if body else ""

    total_np = 1 + sum(len(d["order"]) for d in limbs)

    return f"""<title>Research synthesis &mdash; generated</title>
{style}
{SYNTH_CSS}
<div class="toolbar"><div class="inner">
  <span class="brandmark"><span class="sq"></span> Science Live <span class="sub">&middot; research synthesis</span></span>
  <span class="tools">
    <a class="btn" href="#cite">&#10077; Cite</a>
    {platform_view_btn}
    <button class="btn" type="button" id="tt"><span id="tticon">&#9789;</span> <span id="ttlabel">Dark</span></button>
  </span></div></div>

{tabbar_open}
<article class="article">
  <header class="head">
    <div class="headtop">
      <p class="eyebrow">Independent replication &middot; research synthesis
        <span class="hint left"><button class="infobtn" type="button" aria-label="How this page is made">i</button>
        <span class="box" role="tooltip"><strong>How this page is made</strong>
        A synthesis composes {len(limbs)} independent replication {"limb" if len(limbs)==1 else "limbs"} into
        one finding. Each limb&rsquo;s facts are read from its own signed chain; the composed narrative,
        scope, limitations and recommendations are taken verbatim from the synthesis nanopublication.
        Absent fields are omitted rather than filled in.</span></span>
      </p>
    </div>
    <h1>{esc(rs.get("label") or "Research synthesis")}</h1>
    {deck}
    <div class="authorrow">
      <span class="avatar" aria-hidden="true">{esc(initials)}</span>
      <span class="who"><span class="name">{esc(name)}</span>
        <span class="meta">{orcid_html} &middot; published {esc(created)}</span></span>
    </div>
    {topics_html}
  </header>

  {whatcard_html}

  {cite_html}

  {bottomline_html}

  {hero_html}

  <div class="synthlead">{prose_blocks(rs.get("synthesis") or "")}</div>

  <h2 class="sec">The replication limbs</h2>
  <div class="limbwrap">{cards}</div>

  {block("Recommendations", "recommendations")}
  {block("Where this holds", "conditions")}
  {block("Limitations", "limitations")}

  <h2 class="sec">Responses</h2>
  <div class="empty"><strong>No approvals, disapprovals or comments yet.</strong><br>
    Anyone with an ORCID can approve, disapprove or comment on any nanopublication in this synthesis.</div>

  <section class="refs wide" id="refs">
    <h2>References &amp; citations</h2>
    <div class="refgroup accent"><p class="refgroup-k">Synthesis</p>
      <p class="refgroup-h">{esc(rs.get("label") or "Research synthesis")}</p>
      <ol class="bib">{refs}</ol></div>
    {per_limb}
    <p class="note" style="margin-top:.7rem;">Citations use the platform's rule: author from
      <span class="u">dct:creator</span>&rsquo;s <span class="u">foaf:name</span>, title from
      <span class="u">rdfs:label</span> in the publication info.</p>
  </section>

  <footer class="storyfoot wide">
    <span class="brandmark"><span class="sq"></span> Science Live</span>
    <span>Composed from {total_np} signed nanopublications across {len(limbs)} chains &middot; verdicts, responses and credits read live from the network.</span>
  </footer>
</article>
{panels_close}
<script>
(function(){{var r=document.documentElement,b=document.getElementById('tt'),
i=document.getElementById('tticon'),l=document.getElementById('ttlabel');
function cur(){{return r.getAttribute('data-theme')||(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');}}
function p(){{var d=cur()==='dark';i.innerHTML=d?'&#9788;':'&#9789;';l.textContent=d?'Light':'Dark';}}
b.addEventListener('click',function(){{r.setAttribute('data-theme',cur()==='dark'?'light':'dark');p();}});p();}})();
(function(){{
Array.prototype.forEach.call(document.querySelectorAll('.copybtn'),function(btn){{
  btn.addEventListener('click',function(){{
    var el=document.getElementById(btn.getAttribute('data-copy'));if(!el)return;
    var txt=el.textContent,ok=false;
    try{{if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(txt);ok=true;}}}}catch(e){{}}
    if(!ok){{try{{var rg=document.createRange();rg.selectNodeContents(el);var s=getSelection();
      s.removeAllRanges();s.addRange(rg);document.execCommand('copy');s.removeAllRanges();ok=true;}}catch(e){{}}}}
    var old=btn.textContent;btn.textContent=ok?'Copied':'Press Ctrl/Cmd+C';
    setTimeout(function(){{btn.textContent=old;}},1600);
  }});
}});
}})();
(function(){{document.addEventListener('click',function(e){{
  var a=e.target.closest?e.target.closest('a[href^="#"]'):null;if(!a)return;
  var el=document.getElementById(a.getAttribute('href').slice(1));
  if(el&&el.tagName==='DETAILS')el.open=true;
}});}})();
(function(){{
  var tabs=document.querySelectorAll('.tab'),panels=document.querySelectorAll('.tabpanel');
  if(!tabs.length)return;
  function show(id){{
    tabs.forEach(function(t){{t.classList.toggle('active',t.getAttribute('data-tab')===id);}});
    panels.forEach(function(p){{p.classList.toggle('active',p.getAttribute('data-panel')===id);}});
    try{{scrollTo({{top:0}});}}catch(e){{}}
  }}
  tabs.forEach(function(t){{t.addEventListener('click',function(){{show(t.getAttribute('data-tab'));}});}});
  document.addEventListener('click',function(e){{
    var g=e.target.closest&&e.target.closest('[data-goto]');
    if(g){{e.preventDefault();show(g.getAttribute('data-goto'));}}
  }});
}})();
</script>
"""


def load_style():
    """The page stylesheet, from the committed repo asset (self-contained: the
    display font is embedded, so the generated HTML needs no external request)."""
    css = (Path(__file__).resolve().parent / "story_assets" / "base.css").read_text()
    return "<style>\n" + css + "\n</style>"


def apex_from_published(repo_root):
    """The chain apex to render, read from ``nanopubs/PUBLISHED.md``: the Research
    Synthesis (step 08) if it was published, otherwise the Replication Outcome
    (step 05) — the apex of a single replication chain."""
    pub = Path(repo_root) / "nanopubs" / "PUBLISHED.md"
    if not pub.exists():
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_chain_draft import parse_published  # same PUBLISHED.md parser
    published = parse_published(pub.read_text())
    return published.get("08") or published.get("05")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("uri", nargs="?",
                   help="Chain apex nanopub URI. Default: read it from nanopubs/PUBLISHED.md "
                        "(the Research Synthesis if published, else the Replication Outcome).")
    p.add_argument("--repo-root", default=".", help="Repository root (default: cwd).")
    p.add_argument("-o", "--out", default=None,
                   help="Output HTML file (default: <repo-root>/blog/index.html).")
    p.add_argument("--audience", default=None,
                   help="Optional audience.json adding AI-enhanced tabs (schools, citizens, …). "
                        "Default: nanopubs/audience.json if it exists.")
    args = p.parse_args(argv)

    root = Path(args.repo_root).resolve()
    entry = args.uri or apex_from_published(root)
    if not entry:
        raise SystemExit("No chain apex URI given and none found in nanopubs/PUBLISHED.md. "
                         "Publish the chain first (Phase 5), or pass the URI explicitly.")
    out = Path(args.out) if args.out else (root / "blog" / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)

    audience_path = args.audience
    if not audience_path:
        default_aud = root / "nanopubs" / "audience.json"
        audience_path = str(default_aud) if default_aud.exists() else None
    # Prefer AI-summary nanopubs published on the network (signed, agent-attributed,
    # `schema:about` this apex) — the reader sees the on-network artefacts. Fall back
    # to a committed audience.json when none are published (or the network is down).
    audiences = fetch_published_summaries(entry)
    if audiences:
        print(f"  audiences: {len(audiences)} published summary nanopub(s) from the network")
    else:
        audiences = load_audiences(audience_path)
        if audiences:
            print(f"  audiences: {len(audiences)} from {audience_path} (no published summaries)")

    style = load_style()
    con = fetch_con(entry)
    if con.get("researchSynthesis"):
        syn = build_synthesis(entry, con)
        out.write_text(render_synthesis(syn, style, audiences))
        has_figure = bool(syn.get("hero")) or any(d.get("figure") for d in syn["limbs"])
        print(f"wrote {out}  [research synthesis, {len(syn['limbs'])} "
              f"{'limb' if len(syn['limbs']) == 1 else 'limbs'}]")
        for v in (_limb_view(d) for d in syn["limbs"]):
            print(f"    - {v['relation'] or '?'} / {v['verdict'] or '?'} / "
                  f"{v['confidence'] or '?'} | fig={bool(v['figure'])} | {v['heading'][:55]}")
    else:
        d = build(entry, con)
        out.write_text(render(d, style, audiences))
        has_figure = bool(d.get("figure"))
        print(f"wrote {out}  [replication chain]")
        print("  steps  :", [k for k, _ in d["order"]])
        print("  verdict:", term_label(one(d["a"].get("Outcome", {}), "hasValidationStatus")))
        print("  figure :", has_figure, "| book:", bool(d.get("book")))
    if not has_figure:
        print("No headline figure resolved from the repository — the page will have "
              "no hero image. Add one under figures/ (see figures/README.md).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
