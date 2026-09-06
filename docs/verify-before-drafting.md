# `docs/verify-before-drafting.md` — verify quotes, code, and execution before declaring a draft ready

Three rules, one principle: **don't write from memory; verify against the source.** Each rule below has an associated failure mode that has cost real time in past replications.

---

## Rule 1 — Verify quotes verbatim before drafting Quote-with-comment

When drafting the **Quoted Text** field of a Quote-with-comment nanopublication, the text MUST be verbatim from the cited source. Generating an "approximate" quote from memory of the paper is forbidden — even if the paraphrase is faithful in meaning, it is no longer a quote.

### Procedure

Before drafting Quote-with-comment text:

1. **Find the source PDF.** Should be in `paper/`. If it isn't, stop and ask the user for the PDF.
2. **Read it.** Open the file with `Read`. For papers >20 pages, page through systematically — abstract, introduction, the method or results section the claim lives in, conclusion.
3. **Copy the verbatim sentence.** Pick a sentence under the 500-character cap (for "Quote whole text" mode), or use the start/end-phrase span mode for longer quotes.
4. **Cross-check character count** against the 500-char limit.
5. **Only then draft the Quoted Text field.**

If the source is not accessible, **stop**. Tell the user, ask for the PDF or an open-access URL, and resume drafting only after verification.

### Failure mode

A previous replication (Wernberg et al. 2016, *Science*) drafted a quote from training-data memory:

> "An extreme marine heat wave in 2011 forced a reorganization of the temperate Australian kelp forest community to one dominated by tropical and subtropical species (i.e., regime shift), with degradation in ecosystem services."

This sentence does **not appear** in the paper. The actual abstract reads:

> "Following decades of ocean warming, extreme marine heatwaves forced a 100 km range contraction of extensive kelp forests, and saw temperate species replaced by seaweeds, invertebrates, corals and fishes characteristic of subtropical and tropical waters."

The user caught this with one question: *"from which file did you get the quote?"* — at which point the answer had to be "training data memory" (i.e. fabricated). Read the PDF first.

---

## Rule 2 — Verify code before drafting Replication Study and Outcome

Before drafting the **Methodology** or **Deviations** fields of a FORRT Replication Study, or the **conclusion / evidence** fields of an Outcome, read the actual code that ran the analysis. Don't infer the framework, library, or evaluation parameters from prior memory or from what feels "natural" given the paper.

### Procedure

1. **Read the main reproduction script** in `notebooks/` (typically `03_analysis.py` or whichever notebook produces the headline statistic).
2. **Read the config files** the script loads, if any.
3. **Read the actual numerical outputs** in `results/` (parquet/CSV/JSON files). Quote the numbers from there, not from memory.
4. **Only then write the Methodology and Deviations fields.**

The Quote / AIDA / Claim levels can be drafted from the paper alone, but the Study / Outcome levels are about *what the replication did*, so they must be grounded in *what the code actually does*.

### Failure mode

A previous replication (`fiesta-decrop-reproduction`) was about to claim "uses PyTorch" — pure extrapolation from "modern Python ML reproduction → probably PyTorch". The user caught it with one check: *"is it what we used in FIESTA?"* — at which point reading the code revealed the reproduction uses **TensorFlow 2.19 + Keras** via the authors' own `planktonclas` PyPI package. Same tools as the original paper, which makes the chain a **Reproduction Study** rather than a **Replication Study**, changing the Study Type dropdown selection from option 2 to option 1.

Other things that should be verified directly from code rather than guessed:

- Exact train/validation/test split sizes (paper Table N may differ from the released `test.txt`).
- Whether test-time augmentation was applied (often built into a library function, not always documented in the paper).
- Pretrained-weight provenance: exact released artefact or a near-equivalent retrained version.
- Hyperparameters (batch size, epochs, optimiser) when the script retrains rather than just evaluates.

---

## Rule 3 — Test code before claiming it's ready

When writing notebook or script code that uses unfamiliar APIs, **run it before saying it works** — and if you can't run it, say so explicitly.

### Procedure

- Try to run the code locally (`pixi install` then `pixi run python notebooks/01_data_download.py` — pixi reads `pixi.toml` and uses the lockfile to install a per-platform environment under `.pixi/`).
- If a needed dep is missing, say "I haven't run this — would need to add `X` to `pixi.toml`. Run it first?"
- **Never describe untested code as "works" or "ready"** — say "written, untested" or "written, runs in the Docker container per the API docs, not yet executed."
- This applies especially to code using libraries with version-specific APIs (h3 v3 vs v4, rhealpixdggs, dggrid4py, foscat versions).

### Failure mode

In a previous DGGS replication, code using `h3` and `rhealpixdggs` was written from API documentation alone, declared "ready to commit", and then the user asked: *"did you test it locally?"* — at which point the answer had to be "no". The code did happen to work, but the right protocol is to test first or be explicit that it is untested.

The cost of testing is small (one `pixi run` invocation). The cost of an incorrectly-claimed "works" is a debugging round-trip and credibility loss.

---

## Why this exists as a single doc

These three rules are versions of the same discipline: **the source of truth lives in the file system, not in conversation memory or prior knowledge.** When drafting nanopub content (which is the most authoritative public artefact this repo produces), shortcut around verification at your peril.

If you're tempted to skip verification because "I've worked on this all session, I know what's in there" — that is precisely the moment when verification is most likely to catch a slip.
