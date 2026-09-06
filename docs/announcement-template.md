# `docs/announcement-template.md` — drafting the launch post

When a replication is complete (Phase 5 finished, FAIR4RS checklist green, nanopub chain published), the natural next step is a public announcement. This doc is the structural template for that post — typically a LinkedIn or Bluesky thread, sometimes also a blog post.

## Lead with vision, not result

The strongest framing for a research-software / Open-Science announcement is **vision-first**: lead with a forward-looking question about how research practice should evolve, then use this replication as the worked example.

Result-first framings ("we replicated X with stronger effect") and method-first framings ("here's the 9-nanopub recipe") consistently underperform vision-first framings on engagement and on connecting with people who care about Open Science as a movement, not just this specific paper.

## Structural template

Five-part structure:

### 1. Hook with a forward-looking question

Acknowledge what's already in place (Carpentries, CodeRefinery, FAIR4RS) — never dismiss the legacy. Frame the question as "what comes next?", not "what was wrong?".

### 2. Argue the principle

State the position. Atomic claims. Machine-readable provenance. Do-one-thing-well. Replicability as the floor, not the ceiling. Keep it to 2-3 short paragraphs.

### 3. The worked example as the payoff

Drop in the specific replication once the principle is set up. Reader sees it as proof of concept, not self-promotion. Single concrete number from the Outcome:

> *"We tested the claim on independent data: the effect replicates with X — sign and significance match the original."*

### 4. The chain steps inline

List the FORRT chain at a glance:

> *Quote → AIDA → FORRT Claim → Replication Study → Replication Outcome → CiTO Citation. Each step is a separate, atomic, signed nanopub. The full chain is at <Jupyter Book URL>.*

This shows the granularity without requiring the reader to click anything.

### 5. Close with a question

Domain-specific, not generic. Invites engagement from people thinking about the same problem.

## What to avoid

- ❌ Marketing-fluff openings ("excited to announce…", "thrilled to share…").
- ❌ Result hyping that overpromises ("this proves X is universally true").
- ❌ Tagging the original paper authors directly. They'll find it via citation pipelines if it's notable; tagging looks like trying to attract their notice rather than letting the work speak.
- ❌ Dense hashtag walls. About 5 well-targeted tags, maximum.
- ❌ Tacking the Jupyter Book / Zenodo links at the very bottom as a footer. Integrate them into the argument.
- ❌ Bot signatures (`🤖 Generated with Claude Code`). The post is from the human; co-authoring belongs in commits, not on social.

## Posting account

If you're posting on behalf of an organisation (e.g. a "Science Live" or "FAIR4RS" account), match the post to the audience the account speaks to. Personal-account posts can be more stylised; org-account posts should connect this replication to the broader purpose the account exists for.

## Length

Aim for the post to be readable in under 90 seconds — typically 200-350 words on LinkedIn, threaded if longer. Bluesky/Mastodon variants compress to a 3-5-post thread; the structural template above shrinks naturally.

## Template skeleton

```markdown
**[Forward-looking hook — one or two sentences naming the practice change you see coming.]**

[2-3 paragraph principle argument — what's the new floor, why does it matter, what makes it different from what's already in place.]

We tested it on the [paper] claim that [headline]. [Single concrete number from the Outcome.] [One sentence on why this domain matters.]

The chain runs:
🔗 Quote → AIDA → FORRT Claim → Replication Study → Replication Outcome → CiTO Citation
🔗 [Jupyter Book URL]
🔗 [Zenodo concept DOI]

[Domain-specific question to close.]

#OpenScience #FAIR4RS #FORRT #[your-domain-tag] #[one-more]
```

## Cross-references

- `DOMAIN.md` § Vision-piece framing for advocacy posts (current domain's framing rule).
- `docs/cicd-conventions.md` § Release notes are Zenodo descriptions (similar discipline applied to release bodies).
