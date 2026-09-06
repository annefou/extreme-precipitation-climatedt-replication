# 01 — PICO Research Question (question-rooted chains, comparative)

> Use this draft instead of `01_quote.md` if your chain is question-rooted with a clear comparator (X vs Y). For descriptive/scoping question-rooted chains, use `01_pcc.md`. See `docs/chain-decision-tree.md`.
>
> Run the pre-flight checklist in `docs/forrt-form-fields.md` § Pre-flight checklist before drafting.
>
> **After choosing the chain shape, delete the two step-1 alternates you aren't using.** Once you've decided this chain is question-rooted-comparative and keep `01_pico.md`, run:
> ```bash
> rm nanopubs/drafts/01_quote.md nanopubs/drafts/01_pcc.md
> ```

**Form heading:** *"PICO Research Question — Define a research question using the PICO framework (Population, Intervention, Comparator, Outcome)"*

## Field-by-field draft

<!-- field: pico -->
### Short ID used as URI suffix (text input, required)

Slug becomes part of the nanopub URI. Use kebab-case.

```

```

<!-- field: label -->
### Label for the research question (text input, required)

10-200 characters. Length-bounded.

```

```

<!-- field: description -->
### Description of the research question (textarea, required)

One coherent sentence/paragraph that names P, I, C, O inline.

```

```

<!-- field: type -->
### Question Type (dropdown, required)

- [ ] causation research question - (Does factor X cause outcome Y?)
- [ ] descriptive research question - (What are the characteristics of X?)
- [ ] effectiveness research question - (Does approach X work better than Y?)
- [ ] experience research question - (How do people experience phenomenon X?)
- [ ] prediction research question - (What outcomes can we expect from X?)

<!-- field: populationDescription -->
### Description of the population (textarea, required)

Who/what is being studied. Discipline-level concept — not implementation. See `docs/pico-study-outcome-levels.md`.

```

```

<!-- field: interventionGroupDescription -->
### Description of the intervention group (textarea, required)

The intervention or exposure being examined. Discipline-level concept.

```

```

<!-- field: comparatorGroupDescription -->
### Description of the comparator group (textarea, required)

The comparison or control condition. Discipline-level concept.

```

```

<!-- field: outcomeGroupDescription -->
### Description of the outcome group (textarea, required)

What outcomes are being measured. The kind of measurement, not the value.

```

```

## Publication note

After publishing, paste the resulting URI into `nanopubs/PUBLISHED.md` step 01.
