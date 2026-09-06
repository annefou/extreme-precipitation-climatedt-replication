# Domain flavours

A domain flavour is a `DOMAIN.md` file tailored to one research field. It encodes:

- The default tooling stack (which libraries to reach for first).
- Field-specific conventions that, if violated, break downstream interop.
- Style and write-up rules specific to the field.

The active flavour for a given replication is whatever lives at the repository root as `DOMAIN.md`. To swap flavours, copy a file from this directory over `DOMAIN.md`.

## Available flavours

- **`biodiversity-earth-observation.md`** — biological diversity + remote sensing / climate data. Defaults: HEALPix NESTED, GBIF download DOIs, Copernicus services, `xarray` / `healpy` / `pygbif` / `cartopy`. (This is also what ships at the root as the default `DOMAIN.md`.)

## Writing a new flavour

1. Copy `_template.md` to `<your-domain>.md`.
2. Fill in the three required sections: default tooling stack, domain conventions, style conventions.
3. Test it: clone the template into a new repo, copy your flavour over `DOMAIN.md`, and run a dry replication. The flavour is correct when Claude makes domain-appropriate suggestions without prompting.
4. Open a PR against `forrt-replication-template` to contribute the flavour back.

## Contract for a flavour file

A good flavour file is short (~150-300 lines) and load-bearing. Each rule should answer: *"if a Claude session in this domain violated this rule, what would go wrong?"* If you can't articulate a concrete failure mode, the rule is style — move it to `USER_PREFERENCES.md` instead.

Examples of load-bearing domain rules:

- **Genomics**: "Reference genome version is metadata, not implementation. Always pin GRCh38 vs GRCh37 explicitly in `CITATION.cff`."
- **Social science**: "Never share raw participant data; share derived datasets only. The Replication Study Methodology field must list the de-identification step."
- **Materials science**: "Compositions are reported in atomic %, not weight %, in nanopub Outcomes — the units are silently confusable."
- **Bioacoustics**: "Spectrograms are reproducible only with full STFT parameters (window, hop, fmin, fmax). The Methodology field must list all four."
