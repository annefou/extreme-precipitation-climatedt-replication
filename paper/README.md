# `paper/` — drop the source paper PDF here

Place the PDF of the paper you are replicating in this directory. The paper-analyst agent (`/agent paper-analyst`) reads it from here.

Naming convention: `{first-author}-{year}.pdf` (e.g. `soroye-2020.pdf`). One PDF per replication; if you are replicating multiple papers, add additional files and reference all of them in `index.md`.

If the paper is open access via DOI, you can also use `WebFetch` against the publisher's landing page — but a local PDF is more reliable and works offline.

## Why this matters

The Quote-with-comment nanopublication step requires **verbatim** text from the paper. Drafting from memory or paraphrase is forbidden — see `docs/verify-before-drafting.md`. A local PDF is the source of truth.
