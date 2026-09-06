# figures/

Commit the image that represents your replication here.

One of these images becomes the illustration on your replication's **story page**
— the readable, blog-style page the Science Live platform generates from your
published FORRT chain. Which one is picked:

- a filename containing `main`, `result`, `headline` or `hero` wins;
- otherwise the alphabetically first image in this directory;
- `.png`, `.jpg`, `.jpeg`, `.webp` and `.svg` all count.

So `main_result.png` is the safe name when you have several.

## It has to be committed

This is the part that catches people out. Analysis scripts usually write their
plots to `results/`, which this repo git-ignores along with the other run
artefacts — so the figure exists on the machine that ran the experiment, the
author sees it every day, and the published story page has no image at all.

`results/` is for run output. `figures/` is for the curated figure you want
people to see. Copy or save it here, and commit it.

`scripts/build_chain_draft.py` prints a warning when this directory holds no
image, so you find out while you can still fix it rather than after publishing.

## What makes a good one

The story page is read by people deciding whether your replication is worth
their attention, so the figure should answer the question the replication asked
— typically your result against the original's, with the uncertainty that
decides whether they agree. A figure that shows only your own numbers makes the
reader do the comparison themselves.
