# Missing women, globally

Measuring the female share of people visible in public space, from photographs, across places and over time.

This repository holds the research design. No data has been collected yet.

## Why the design looks the way it does

We ran GPT-4o over 100 street images that human coders had already counted. It found 40% of the people, and its recall differed by sex: 61% of women, 35% of men. A true female share of 19.6% came back as 29.8%. That ten-point error is larger than the entire spread across the cities we are trying to compare, which runs from about 18% to 27%.

Rebuild that table:

```bash
make benchmark
```

It reads the frozen validation export from the sibling `streetscope` checkout and makes no API calls.

```
images: 87 parsed of 100 sampled

group                  human   model   recall
women pedestrians         97      59     0.61
men pedestrians          398     139     0.35
all pedestrians          495     198     0.40

female share, human coders : 0.196
female share, GPT-4o       : 0.298
per-image count correlation: 0.696
```

## Contents

| Path | What it is |
|---|---|
| `DESIGN.md` | The research design. Start here. |
| `docs/literature_review.md` | Comparison table: data, n, unit, coder, sex coded, validation |
| `docs/prior-art.md` | Full sweep and data-availability review, with per-item verification status |
| `docs/refs.bib` | Bibliography, resolved from Crossref and DataCite by `make bib` |
| `scripts/01_gpt4o_benchmark.py` | Rebuilds the benchmark above from frozen inputs |
| `scripts/02_build_bibliography.py` | Resolves every citation from its identifier; nothing typed by hand |

## Related repositories

Expected as siblings of this directory.

| Repository | What it contributes |
|---|---|
| `streetscope` | Wearable-camera study, four Indian cities, 22,848 human-coded pedestrian sightings |
| `missing_women_gsview` | Street View study, three Indian cities, 4,737 human-coded sightings |
| `geo_sampling` | Road-network sampling frame, on PyPI as `geo-sampling` |
| `geosensing/women-count` | The 2016 Delhi precursor |

## Requirements

Python 3.11 or later and pandas. A sibling `streetscope` checkout for the benchmark.

## License

MIT
