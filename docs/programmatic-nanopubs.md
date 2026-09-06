# `docs/programmatic-nanopubs.md` — when to publish nanopubs at the TriG/CLI layer

**The default front-end for this template is the [Science Live platform](https://platform.sciencelive4all.org).** Drafts in `nanopubs/drafts/` get copy-pasted into the Science Live form and submitted by the user, producing nanopub URIs in the `https://w3id.org/sciencelive/np/...` namespace. That is the right path for the entire six-step FORRT chain (Quote → AIDA → Claim → Study → Outcome → CiTO Citation), plus the optional Research Software and Research Synthesis layers.

There are a small number of **operations Science Live doesn't expose**, and for those there is a lower layer: writing TriG files directly and signing them with the [nanopub Java CLI](https://github.com/Nanopublication/nanopub-java). That layer is what the Knowledge Pixels [`nanopub-agent-utilities`](https://github.com/knowledgepixels/nanopub-agent-utilities) Claude Code plugin automates.

## When the lower layer is needed

Reach for the `nanopub-agent-utilities` plugin **in addition to** Science Live (not instead of it) when:

- **Retracting** a previously-published nanopub. Retraction is not exposed in the Science Live UI; it requires the original signing key and the CLI's `retract` command.
- **Superseding** a previously-published nanopub. Same constraint as retraction — needs the original key.
- **Publishing many nanopubs programmatically.** A bulk batch driven by a script or registry, where the per-step UI flow becomes too slow to be practical.
- **Publishing a nanopub that doesn't fit any Science Live template.** E.g. an introduction nanopub for a software-agent identity, a nanopub index, a custom query template, a resource view.
- **Creating a software-agent identity** so the replication's pipeline can publish nanopubs autonomously (e.g. publishing run-level provenance for each Snakemake job). Agent identities have their own RSA keys and an introduction nanopub.

For the standard FORRT chain, you should not need any of this — the Science Live UI publishes all six steps. The lower layer is a power tool for the edge cases above.

There is one Science Live UI bug worth noting: the AIDA template has previously failed when both *Supported by datasets* and *Supported by other publications* groups are populated (see `docs/forrt-form-fields.md` § AIDA Sentence). If you hit it: omit one of the two groups and add it via supersede later (CLI-driven), or — strictly as a last resort if the chain is time-critical — publish that single AIDA via Nanodash. A Nanodash-published nanopub lives at `https://w3id.org/np/...` rather than `https://w3id.org/sciencelive/np/...`; both are valid and citable. Document the namespace difference in `nanopubs/PUBLISHED.md`.

## Installing nanopub-agent-utilities

`nanopub-agent-utilities` is published as a Claude Code plugin. To install:

```bash
# Clone the plugin
git clone https://github.com/knowledgepixels/nanopub-agent-utilities ~/.claude/plugins/nanopub-agent-utilities

# (Or wherever your Claude Code plugin directory is — see Claude Code docs)
```

The plugin installs three skills:

- **`/nanopub`** — create, sign, publish, query, or retract nanopublications. The flagship skill. Documents the full TriG → sign → publish → verify workflow.
- **`/modify-query-template`** — edit grlc query template nanopubs (the SPARQL endpoints that power the Nanopub Query API).
- **`/supersede-nanopub`** — supersede a published nanopub with an updated version, preserving the same signing key.

## Profile setup (one-off per laptop)

The plugin reads `~/.nanopub/profile.yaml` to know which ORCID and key to sign with. Create it once:

```yaml
# ~/.nanopub/profile.yaml
orcid_id: https://orcid.org/0000-0000-0000-0000
name: Your Name
```

Generate a personal RSA key pair:

```bash
mkdir -p ~/.nanopub
openssl genrsa -out ~/.nanopub/id_rsa 2048
openssl rsa -in ~/.nanopub/id_rsa -pubout -outform PEM -out ~/.nanopub/id_rsa.pub
```

**Never delete or alter key files in `~/.nanopub/`.** Losing the key means losing the ability to retract or supersede nanopubs published with that identity.

## Sandbox interaction

Note: this template's `.claude/settings.json` denies file writes outside the repo, including to `~/.nanopub/`. The CLI workflow needs `~/.nanopub/` access. To use the lower layer:

- **Option A** — disable the sandbox temporarily by editing `.claude/settings.json`'s `deny` list. Re-enable after you're done.
- **Option B** — run the CLI workflow outside Claude (in a regular shell), and only use Claude Code for drafting the TriG content. The plugin's skills can still be useful as drafting references even if signing/publishing happens in a separate shell.

For most replications, the SL UI is sufficient and the lower layer is unused. Reach for it only when the use case above applies.

## Mixing layers within a single chain

A FORRT chain that is published mostly via Science Live with one step issued at the CLI layer (e.g. a CLI-driven retraction + supersede after a bad first publication) is fine — the URIs from both namespaces (`w3id.org/sciencelive/np/…` from Science Live, `w3id.org/np/…` from CLI publication) are valid and citable. The chain still composes; the citation graph still resolves.

Record the namespace per step in `nanopubs/PUBLISHED.md` so downstream readers don't get confused. When you reference a non-Science-Live URI in a Jupyter Book embed or a public link, wrap it in the Science Live viewer:

```
https://platform.sciencelive4all.org/np/?uri=<full-non-SL-URI>
```

(Science Live URIs of the form `w3id.org/sciencelive/np/...` resolve directly through the same viewer and don't need the wrapper.)

## References

- [Science Live platform](https://platform.sciencelive4all.org) — the default front-end for this template.
- [nanopub-agent-utilities (GitHub)](https://github.com/knowledgepixels/nanopub-agent-utilities) — Claude Code plugin for the lower-layer operations.
- [nanopub-java CLI (GitHub)](https://github.com/Nanopublication/nanopub-java) — the underlying Java CLI used by the plugin.
- [Nanopub Query API](https://query.knowledgepixels.com/) — SPARQL endpoints for browsing the global nanopub network.
