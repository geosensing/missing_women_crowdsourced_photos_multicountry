# City and image sampling design

The study describes people a vision model could classify in sampled ground-level photographs. Its city frame consists of the 688 cities in Global Streetscapes. The available photographs depend on which places, dates, and viewpoints contributors recorded within the source collection’s tiles. The pooled share gives each classified pedestrian sighting equal weight. Representing another population requires specifying which cities, photographs or people should count, and accounting for selection and missing observations.

## Selecting cities

The frozen city list supplies city population and image counts. World Bank records supply national GDP per capita at purchasing power parity, national population and region. A city qualified with at least 400 corpus images, a recorded population and a recorded national GDP figure. Of 688 cities, 543 qualified. The selection includes 101 cities in 88 countries. New Delhi and Faisalabad entered with certainty as benchmarks. The published seed is 20261115. [Sampling configuration](../config/sampling.json)

| Region | Cities in frame | Eligible | Selected | Ranked inference pool (up to 500 per city) |
|---|---:|---:|---:|---:|
| Americas | 211 | 178 | 25 | 11,754 |
| East Asia & Pacific | 117 | 94 | 18 | 9,000 |
| Europe & Central Asia | 218 | 183 | 26 | 12,100 |
| Middle East, North Africa, Afghanistan & Pakistan | 34 | 27 | 11 | 5,178 |
| South Asia | 24 | 18 | 9 | 4,087 |
| Sub-Saharan Africa | 66 | 43 | 12 | 5,835 |
| No World Bank region | 18 | 0 | 0 | 0 |
| **Total** | **688** | **543** | **101** | **47,954** |

North America and Latin America & the Caribbean form the Americas group. Within each region, eligible cities are sorted by national GDP per capita and city ID, then split into two halves by rank. The ID breaks ties when cities in the same country span the midpoint. This occurs in India, Italy and Japan. An income half describes its rank among regional peers and can include cities with the same national GDP as cities in the other half.

After setting aside the anchors, the sampler allocates 99 slots to regions in proportion to the square root of their eligible non-anchor count. It divides each regional quota between the income halves in proportion to their size, with largest-remainder rounding. Within each region–income cell the city priority is `−log(U) / sqrt(city population)`, where the first 64 bits of a hash of the seed, cell and city ID determine `U`. A smaller value receives higher priority.

Cells take turns selecting cities. The first pass gives preference to countries that have yet to contribute a city. The second pass fills remaining slots under a country cap of `round(101 × country population / world population)`, bounded between one and eight. If a quota still has empty slots, the remaining cities fill it in priority order. Both passes include anchors when counting how many cities a country has contributed. [Selection implementation](../scripts/03_select_cities.py)

### Computing the city weights

The code repeats the complete city draw using 50,000 additional seeds, 0 through 49,999. A city's estimated inclusion probability is the fraction of those draws that selected it. Its estimated design weight is the reciprocal. Both CSVs report the hit count, number of replays, inclusion probability, simulation standard error and weight. The full eligibility file includes every city, so analysts can check support across the frame. The selected-city file also reports the number of eligible and selected non-anchor cities in each cell, with a separate one-city cell size for each anchor. Replaying complex sampling designs is a standard way to estimate inclusion probabilities. [Monte Carlo sampling weights](https://doi.org/10.1093/biomet/93.2.269)

The two anchors have exact probability one and the ineligible cities have exact probability zero. For other cities, an observed frequency of zero or one can reflect simulation error. A city with zero hits has no estimated inverse weight. At either boundary, the manifest reports a one-sided 95% binomial bound and the CSV leaves the simulation standard error blank. For intermediate probabilities the standard error is `sqrt(p × (1 − p) / 50000)`. These measures describe simulation precision. They do not quantify uncertainty in the gender counts. A design-weighted estimate targeting all eligible cities requires positive inclusion probability for every eligible city and appropriate treatment of the second-stage image selection.

In the East Asia & Pacific high-income cell, Seoul appeared in all 50,000 draws, Tokyo appeared in 29,583 (estimated probability 0.59166, weight 1.69), and Oshu appeared in 2,211 (0.04422, weight 22.61). Every eligible city appeared at least once. The least frequently drawn eligible city, Kawamata, appeared 58 times. Among the 101 cities in the observed sample, the smallest count was 1,004 for Fleury-les-Aubrais (0.02008, simulation standard error 0.00063, weight 49.80).

## Selecting images

From the pinned Global Streetscapes city metadata we identified 2,536,337 unique image IDs in the selected cities. The instance mask detected a person, bicyclist, motorcyclist or other rider in 1,492,859 images. The remaining images include 1,043,468 with observed zero counts and 10 without a complete mask record. The per-city mask rate divides positive masks by images with observed counts. The number of people and their gender composition in mask-negative or unmeasured images remain unknown. [Image selection implementation](../scripts/04_sample_images.py)

Within each city, the draw orders positive-mask image IDs by the SHA-256 hash of the seed, city ID and image UUID. The inference draw takes the first 500, or all available images in a smaller pool. The first 100 per city form Round 1. A separate calibration reserve contains 9,939 images, with 1,300 shared with inference in cities with small pools. There are 56,593 distinct IDs across inference and the reserve. The later Label Studio validation exercise used a separate sample of Round 1 images.

| Stage | Round 1 images |
|---|---:|
| Drawn | 10,100 |
| Downloaded | 9,906 |
| Coded | 9,835 |

The Round 1 draw includes 9,268 Mapillary and 832 KartaView IDs. Coded coverage varies across cities, including 20 of 100 drawn in Seoul and 58 of 100 in Jakarta. An image ID denotes a corpus record. Some records have byte-identical photographs.

The third batch used ranks 201 through 300. Across the three batches, 29,659 image IDs were selected, 29,081 downloads succeeded, and 28,794 yielded counts.

### Round 2 and the pixel cutoff

The second wave in the image manifest consists of ranks 101 through 500, with 37,854 image IDs. The Round 2 download manifest used for the audit contains the 9,948 available IDs at ranks 101 through 200. Of those, 9,740 downloads succeeded and 4,007 IDs fall below 5,000 person/rider pixels. This batch used the positive-instance rule throughout. A threshold of 5,000 pixels was a proposed cost-saving restriction.

In Round 1, applying that cutoff after coding retains 5,835 of 9,835 images and 8,907 of 9,364 classified pedestrian sightings. The classified female share rises from 36.53% to 36.77%. This comparison tests sensitivity of model counts to the cutoff. Accuracy for people the model missed requires independent annotation. [Threshold results](../tabs/tableA1_pixel_threshold.tex)

## Reproduction

With the four frozen files under `data/raw/`, run the city draw and then the image draw from the repository root.

```sh
make sample
make sample-images
```

The city draw reads `cities688.csv`, `wb_countries.json`, `wb_gdp_pcap_pp.json` and `wb_pop_totl.json`. It writes `outputs/city_eligibility.csv`, `outputs/selected_cities.csv` and `outputs/sampling_manifest.json`. The image draw uses the pinned revision of `simplemaps.parquet` and `instances.parquet` from the corpus. It writes `outputs/selected_images.csv`, `outputs/city_image_summary.csv` and `outputs/image_sampling_manifest.json`. The manifests record output hashes and the inputs used for each stage.
