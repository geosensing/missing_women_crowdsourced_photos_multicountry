# Missing women, globally

A vision model counted pedestrians and two-wheeler riders in ground-level photographs from 101 cities. The [research note](ms/note.pdf) reports how often it classified them as women, how the results vary across cities, and how its counts compare with a human coder's. See the [sampling design](docs/sampling_design.md) for the selection rules.

## Why the design looks the way it does

In an earlier study in Mumbai, human coders counted 495 pedestrians in the 87 photographs for which GPT-4o returned usable counts. GPT-4o counted 198. Its count of women was 61% of the human count, while its count of men was 35% of the human count. That difference raised the estimated share of women from 19.6% to 29.8%.

Rebuild that table:

```bash
make benchmark
```

It reads the frozen validation export from the sibling `streetscope` checkout and makes no API calls.

```
images: 87 parsed of 100 sampled

group                  human   model  model/human
women pedestrians         97      59         0.61
men pedestrians          398     139         0.35
all pedestrians          495     198         0.40

female share, human coders : 0.196
female share, GPT-4o       : 0.298
per-image count correlation: 0.696
```

## Contents

| Path | What it is |
|---|---|
| `DESIGN.md` | The research design. Start here. |
| `config/sampling.json` | Fixed seed, eligibility gates, strata, and budget caps for city sampling |
| `docs/sampling_design.md` | Two-stage stratified sampling specification and reproducibility protocol |
| `docs/literature_review.md` | Comparison table: data, n, unit, coder, sex coded, validation |
| `docs/prior-art.md` | Full sweep and data-availability review, with per-item verification status |
| `docs/refs.bib` | Bibliography, resolved from Crossref and DataCite by `make bib` |
| `scripts/01_gpt4o_benchmark.py` | Rebuilds the benchmark above from frozen inputs |
| `scripts/02_build_bibliography.py` | Resolves every citation from its identifier; including manually documented sources |
| `scripts/03_select_cities.py` | Runs Stage-1 eligibility gates and deterministic seeded city draw |
| `scripts/04_sample_images.py` | Streams Parquet metadata from Hugging Face to draw person-containing images |

## From a photograph to an appendix estimate

1. Global Streetscapes retrieved contributor photographs from the Mapillary and KartaView map tile containing each city’s SimpleMaps reference coordinate. These images include squares, streets, and paths. We draw cities within region and national income groups. In each city, use the Global Streetscapes pedestrian and rider detections to identify eligible photos, then randomly draw up to 200 for the main sample. The selection file stores the photo identifier, city, region, and sampling wave.
2. Retrieve each selected image and send it to Muse. The saved counts give apparent women and men on foot, apparent women and men on two-wheelers, and a separate count of people the model could not classify. A photo can have zero classified pedestrians.
3. Join the saved counts to the selection file by photo identifier. For Appendices B and C, join the local calendar fields and OpenStreetMap road class from the pinned Global Streetscapes release by that same identifier. Each join keeps one row per coded photo.
4. For Table B1, count photos by road class within each region and divide by all coded photos in that region. Figure B1 maps each coded photo location in New Delhi and London. Table B2 compares the photo shares with the share of street length inside those map areas. For Figure C1, keep photos with a valid local date taken from 6 a.m. to before 10 p.m. and at least one classified pedestrian. Derive weekday from the local year, month, and day, and discard 1970 placeholder dates. Model the fraction coded as women using weekday, evening, and a separate baseline for each city. Weight each photo by its number of classified pedestrians and cluster uncertainty by city.

Run `python3 scripts/11_photo_context.py` to regenerate the sample and pedestrian comparisons from saved counts. The underlying regional counts and model estimates are in `outputs/road_type_by_region_counts.csv` and `outputs/capture_time_regression.csv`. The script uses matplotlib, pandas, numpy, statsmodels, pyarrow, requests, huggingface_hub, geopandas, shapely, and pyproj. The paper build runs it automatically. Table C1 uses city baselines and a shared weekday and local-time distribution to compare regions. `outputs/region_timing_adjustment.csv` gives observed and timing-adjusted shares and `outputs/region_timing_support.csv` gives the sighting counts by region, day, and time block. Appendix C also pools the within-city residential minus primary differences, weighting by the number of sightings available on both street types. City totals, weights, and leave-one-city-out estimates are in `outputs/residential_primary_support.csv`.

## Related repositories

Expected as siblings of this directory.

| Repository | What it contributes |
|---|---|
| `streetscope` | Wearable-camera study, four Indian cities, 22,848 human-coded pedestrian sightings |
| `missing_women_gsview` | Street View study, three Indian cities, 4,737 human-coded sightings |
| `geo_sampling` | Road-network sampling frame, on PyPI as `geo-sampling` |
| `geosensing/women-count` | The 2016 Delhi precursor |

## Requirements

The benchmark uses Python and pandas and reads its input from the sibling `streetscope` checkout. To rebuild the paper from the saved counts and human annotations, run `make note` with the local sampling files in `outputs/`, the Global Streetscapes segmentation metadata, uv, Python with pyarrow and huggingface_hub, and a LaTeX installation with latexmk. All six numbered tables use pandas’ LaTeX exporter through `scripts/paper_tables.py` (with Jinja2). Their analysis scripts write the cells, and the manuscript supplies captions and notes. The published PDF and generated tables are included here.

## License

MIT

Appendix D compares the resident population with classified pedestrian sightings near the population reference year. Run `python3 scripts/12_resident_population.py` after the photo-context script. It writes Table D1 and `outputs/city_resident_comparison.csv`, which retains all 101 selected cities, including unmatched cities and cities with zero classified sightings.

The [frozen population records](docs/city_population_records.csv) preserve the source city name, boundary type, reference and publication years, count type, male and female counts, independently published total, and available sex-specific footnotes. For the [UN city series](https://data.un.org/legacy/Data.aspx?d=POP&f=tableCode%3A240), the source files are the [archived export and footnote tables](https://github.com/datasets/population-city/tree/46308b15a9de69949438b731acaa58530674c6ea/data). Cities were matched by country and city name, including local names such as Praha and Wien. We retained final, complete records labeled city proper, total area, and de jure (residence-based), pairing sex counts with the same release's all-person total. The extract includes eligible years within two years of the city's median coded-photo year. The analysis picks the nearest year, breaking ties in favor of a census, then the earlier year. Source notes retain exceptions to internationally comparable geography and coverage.

Two additional records use local sources. The [Dubai 2018 bulletin](https://www.dsc.gov.ae/Publication/Population%20Bulletin%20Emirate%20of%20Dubai%202018.pdf), Table 1, counts usual residents of the emirate, including expatriate workers. Table 2 separately estimates the daytime population. The [Greater London count](https://www.nomisweb.co.uk/datasets/c2021ts008) comes from Census 2021 table TS008, geography E12000007, all usual residents. Blank population fields mean no benchmark matched under this search. They do not establish that a local statistical office lacks suitable data.
