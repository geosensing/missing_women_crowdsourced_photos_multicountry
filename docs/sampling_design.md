# City Sampling Design

Reproducible stratified sampling design for selecting **100 cities** from the Global Streetscapes corpus (`NUS-UAL/global-streetscapes`, 688 cities), enriched with official World Bank regions (`North America` + `Latin America & Caribbean` merged into `Americas`), GDP per capita PPP (`NY.GDP.PCAP.PP.CD`), and country population (`SP.POP.TOTL`).

**Target inference population:** Well-mapped global cities in Global Streetscapes (`img_count >= 400`), rather than an unweighted census of all world cities. All parameters, thresholds, and the random seed (`20261115`) live in [`config/sampling.json`](../config/sampling.json) (`version: 1.9.1`).

---

## Stage 1: Eligibility Gates

Inputs:
- `data/raw/cities688.csv` (from `NUS-UAL/global-streetscapes`)
- `data/raw/wb_countries.json` (official World Bank region classification per `iso3`)
- `data/raw/wb_gdp_pcap_pp.json` (World Bank `NY.GDP.PCAP.PP.CD`, most recent non-empty value per `iso3`, used as a national macro-context proxy rather than subnational city GDP)
- `data/raw/wb_pop_totl.json` (World Bank `SP.POP.TOTL`, most recent non-empty value per `iso3` and `WLD`, used for population-scaled country caps)

A city is eligible if it passes all three baseline gates:
1. `img_count >= 400` (`min_img_count = 400`)
2. Non-missing `population` (`require_population = true`)
3. Non-missing World Bank `gdp_pcap_pp` (`require_income = true`)

All 688 cities are logged in `outputs/city_eligibility.csv` with `eligible` (`1`/`0`) and `failed_gates`.

---

## Stage 2: Stratified Selection (100 Cities)

Among the **543 eligible cities**:
1. **Certainty anchors ($n = 2$):** **New Delhi** (`city_id = 1356215164`, `img_count = 1,371`) and **Faisalabad** (`city_id = 1586323916`, `img_count = 3,770`) are included with probability 1 (`inclusion_prob = 1.0`, `design_weight = 1.0`) as benchmark/regional anchors. *(Note: Mumbai, Bangalore, and Navi Mumbai are not in `cities688.csv`.)*
2. **Macro-regions (6 World Bank-derived regions):** `East Asia & Pacific`, `Europe & Central Asia`, `Middle East, North Africa, Afghanistan & Pakistan`, `South Asia`, `Sub-Saharan Africa`, and `Americas` (merging World Bank `North America` and `Latin America & Caribbean`).
3. **Within-region income split (`region_income_bin`):** Eligible cities are binned within each of the 6 regions using deterministic `(gdp_pcap_pp, city_id)` ordering into `Low` (below region median) and `High` (above region median), forming **12 strata** (`region | region_income_bin`).
4. **Two-stage allocation & $\sqrt{\text{population}}$-weighted draw:**
   - **Across regions:** The 99 non-anchor slots are allocated across the 6 regions via **Bankier square-root ($\sqrt{N_{\text{region}}}$) power allocation** (`region_allocation = "sqrt"`).
   - **Within regions:** Each region's quota is allocated proportionally across its `Low` and `High` strata via largest-remainder (`min_per_stratum = 0`).
   - **Weighted draw & country dispersion:** Within each stratum, cities are ordered by deterministic Efraimidis–Spirakis weighted `SHA-256` keys (`-ln(u) / sqrt(population)`) so larger, recognizable cities are favored without erasing mid-sized cities. Cities are drawn round-robin across strata in two passes: **Pass 1** prefers countries with `0` selected cities so far (`prefer_unrepresented_country = true`), and **Pass 2** fills remaining slots up to a population-scaled per-country cap `clamp(round(100 * country_pop / world_pop), 1, 8)`, with unconstrained fallback only when a stratum has no remaining under-cap candidates.
5. **Stratum metadata:** `outputs/selected_cities.csv` exports `stratum_eligible_n` ($N_h$), `stratum_selected_n` ($n_h$), `inclusion_prob` ($n_h / N_h$), and `design_weight` ($N_h / n_h$) alongside city `population` for unweighted and population-weighted sensitivity checks.

### Regional Funnel & Allocation Summary

| Region | Total | Eligible | Elig. Rate | Selected | Weight Range | Capped Images |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Europe & Central Asia** | 218 | 183 | 83.9% | 26 | 7.00 – 7.08 | 48,539 |
| **Americas** | 211 | 178 | 84.4% | 25 | 6.85 – 7.42 | 46,522 |
| **East Asia & Pacific** | 117 | 94 | 80.3% | 18 | 5.22 – 5.22 | 33,924 |
| **Sub-Saharan Africa** | 66 | 43 | 65.2% | 12 | 3.50 – 3.67 | 20,791 |
| **Middle East, North Africa, Afghanistan & Pakistan** | 34 | 27 | 79.4% | 10 | 2.60 – 2.80 | 17,575 |
| **South Asia** | 24 | 18 | 75.0% | 9* | 1.00 – 2.25 | 11,205 |
| **Total (incl. 18 ineligible territories)** | **688** | **543** | **78.9%** | **100** | **1.00 – 7.42** | **178,556** |

*\*Includes certainty anchor New Delhi (`design_weight = 1.0`). Sample spans **87 countries** across **12 strata** (median city population: `1,126,534`).*

---

## Stage 3: Within-City Allocation (Person-Filtered)

Executed by `scripts/04_sample_images.py` (`make sample-images`), which caches only the Parquet tables `simplemaps.parquet` and `instances.parquet` from `NUS-UAL/global-streetscapes` (~732 MB total, avoiding the ~6 TB image corpus):

- **Person-mask filter (`person_mask_filter = true`):** Restricts the within-city frame to images with at least one precomputed Mask2Former `Person`, `Bicyclist`, `Motorcyclist`, or `Other-Rider` instance (`1,489,150` of `2,532,567` corpus images across the 100 cities). Per-city `total_corpus_images`, `images_with_people`, and `person_mask_rate` are logged in `outputs/city_image_summary.csv` so unconditional street-level rates can be recovered if needed.
- **Inference sample (two-wave):** Up to `500` person-containing images per city, sorted deterministically by `SHA-256(f"{seed}:img:{city_id}:{uuid}")` (**`47,454`** images across 100 cities):
  - **Round 1 (`wave = "round1"`, `rank_in_city <= 100`):** Exact **`100`** images per city (**`10,000`** total: `9,175` Mapillary, `825` KartaView) for initial full-res (`1×1`) Muse counting, plots, and analysis (~$3).
  - **Round 2 (`wave = "round2"`, `rank_in_city = 101..500`):** Remaining **`37,454`** images, ready to run without altering Round 1 once the pipeline is validated.
- **Human calibration sample:** Up to `100` person-containing images per city (**`9,839`** total; disjoint from inference when a city has `> 500` person-containing images), yielding **`55,993` unique sampled images** in `outputs/selected_images.csv`.

### Empirical Pixel-Area Threshold & Bias Check (Round 1 Validation)

In Round 1 (`9,721` coded images across all 100 cities), filtering only on Mask2Former `instances >= 1` still admitted images where pedestrians were small, distant silhouettes (`72.3%` of all detections fell into `unclear_count`). Joining Round 1 counts against `data/parquet/segmentation.parquet` (`Person + Bicyclist + Motorcyclist + Other-Rider` pixel counts) shows that images with `< 5,000` person/rider pixels (`41.0%` of Round 1 images) contributed only **`4.9%`** of sex-classified pedestrians (`454 / 9,212`), and filtering to **`pix >= 5,000`** introduces virtually no compositional bias globally or within any region:

| Region | All `Person >= 1` (`pix >= 0`) | `pix >= 5,000` | Difference |
| :--- | :---: | :---: | :---: |
| **Europe & Central Asia** | 49.50% (`n = 2,677`) | 49.25% (`n = 2,605`) | −0.24 pp |
| **East Asia & Pacific** | 43.54% (`n = 1,254`) | 44.22% (`n = 1,203`) | +0.68 pp |
| **Americas** | 40.08% (`n = 1,300`) | 40.28% (`n = 1,194`) | +0.21 pp |
| **Sub-Saharan Africa** | 30.51% (`n = 1,180`) | 30.65% (`n = 1,080`) | +0.14 pp |
| **South Asia** | 26.49% (`n = 1,676`) | 26.57% (`n = 1,652`) | +0.08 pp |
| **MENA, Afg. & Pak.** | 18.40% (`n = 1,125`) | 18.65% (`n = 1,024`) | +0.25 pp |
| **Global** | **36.94%** (`n = 9,212`) | **37.19%** (`n = 8,758`) | **+0.25 pp** |

Accordingly, `pix >= 5,000` is an empirically validated filter for Round 2: it cuts image volume and API cost by **41%** while retaining **95.1%** of sex-classified pedestrians and preserving regional female shares within `±0.7 pp`.

---

## Reproducibility Protocol

Run Stage 1–2 offline from frozen inputs, and Stage 3 from Hugging Face Parquet metadata:

```bash
make sample
make sample-images
```

`scripts/03_select_cities.py` re-derives the city draw from `seed = 20261115`, asserts an exact match, and writes `outputs/city_eligibility.csv`, `outputs/selected_cities.csv`, and `outputs/sampling_manifest.json`. `scripts/04_sample_images.py` writes `outputs/selected_images.csv`, `outputs/city_image_summary.csv`, and `outputs/image_sampling_manifest.json` (with byte counts and SHA-256 hashes of all inputs and outputs).
