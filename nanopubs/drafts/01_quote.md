# 01 — Quote-with-comment (paper-rooted chains)

> Run the pre-flight checklist in `docs/forrt-form-fields.md` § Pre-flight checklist before drafting.
>
> If this is a question-rooted chain, use `01_pico.md` or `01_pcc.md` instead — see `docs/chain-decision-tree.md`.
>
> **After choosing the chain shape, delete the two step-1 alternates you aren't using.** Once you've decided this chain is paper-rooted and keep `01_quote.md`, run:
> ```bash
> rm nanopubs/drafts/01_pico.md nanopubs/drafts/01_pcc.md
> ```

**Form heading:** *"Annotate a paper quotation — Annotating a paper quotation with personal interpretation"*

## Field-by-field draft

<!-- field: paper -->
### Cited DOI (text input, required)

Format: starts with `10.` — bare DOI, **NOT** `https://doi.org/...` form.

```
10.1002/joc.8393
```

### Quote mode (radio button)

- [x] **Quote whole text (less than 500 characters)**
- [ ] Quote start/end *(use this if the quote exceeds 500 chars)*

<!-- field: quotation -->
### The exact quotation from the paper (max. 500 characters) (textarea, required)

Verbatim from the paper PDF in `paper/`. Character-for-character. ≤ 500 chars in whole-text mode.

> _Read the PDF first. Don't paraphrase from memory. See `docs/verify-before-drafting.md`._

Verified with `verify_quote` against `paper/hundhausen-2024.pdf`: **`normalized`**, page 13
(Conclusions), transforms `collapse-whitespace`, `join-hyphenated-linebreaks`,
`typographic-punctuation`. The same claim as phrased in the *abstract* does NOT verify —
that page's text layer inserts spaces inside words ("CP en semble", "largest c hanges") —
so the Conclusions wording is used.

```
The CP simulations project climate change signals of extreme precipitation intensities of up to 6 or 8.5% increase per K GW depending on the ensemble member. Events with short duration and long RPs are expected to change the most.
```

Character count: 230 / 500.

<!-- field: quotation-end -->
### End of quotation (optional - use when quoting beginning and end of a longer passage, max. 500 characters) (textarea, optional)

Only when quoting the beginning *and* end of a longer passage — set the mode above to
**Quote start/end**, put the opening phrase under the previous heading and the closing
phrase here. Leave empty for a single short quote.

```

```

<!-- field: comment -->
### Our interpretation and explanation of why this quotation is relevant (max. 800 characters) (textarea, required)

Why this quote matters and what the replication tests. Connect the paper's claim to the work this repo does. Don't repeat the quote.

> **Anne's wording**, tightened while reviewing the chain in the publishing
> wizard and back-ported here on 2026-09-07. `chain-draft.json` is GENERATED from
> this file by `pixi run build-chain-draft`, so an edit made only there is lost
> on the next rebuild — this draft is the source of truth.

```
The magnitude (6 or 8.5% per K) is specific to a COSMO-CLM ensemble over Germany and could only be re-measured elsewhere, not tested. The second sentence proposes a STRUCTURE: intensification is greatest for short durations and long return periods. This thermodynamic hypothesis should hold across domains and models if real, making it reusable and adaptation-relevant, since urban drainage is designed around such events.
```

Character count: 669 / 800.

## Publication note

After publishing, paste the resulting URI into `nanopubs/PUBLISHED.md` step 01.
