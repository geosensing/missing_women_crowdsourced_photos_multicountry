# Correctness audit of the global street imagery study

November 17, 2026. This audit covers the working manuscript and local data on top of commit `d561f60`, including the uncommitted calibration analysis. The 36.53% pedestrian result reproduces as a description of classified sightings in the coded photographs. The proposed adjustment to 32.5% depends on how counting errors vary across regions. Human annotations currently provide almost no evidence about those errors in three of the six regions.

**Revision after the audit.** This document records the original findings. The [revised note](../ms/note.pdf) reports the sample shares and labels the adjustment as a conditional calculation. The revised sampler estimates city inclusion probabilities from 50,000 draws, and the new figures show all cities and flag unsupported intervals. The build reads a frozen human export, cleanup preserves the counts, and malformed model responses are rejected. Additional human annotations are in progress separately. [Revised sampling design](sampling_design.md)

## What the counts establish

| Question | Calculation | Interpretation |
|---|---:|---|
| Among pedestrians Muse classified in the sample, what share did it code as women? | 3,421 / 9,364 = 36.53% | Each classified sighting receives equal weight. A crowded photograph contributes more observations. |
| Among classified two-wheeler riders? | 234 / 1,797 = 13.02% | Same rule, different mode of travel. |
| What share does the average sampled city report for pedestrians? | Mean of 101 city shares = 39.42% | Atlanta's two classified pedestrians carry as much city weight as Riga's 130. |
| What share would the classified sightings in all mask-positive corpus images in these 101 cities imply? | Expand each city's counts by its eligible image count divided by its coded image count = 41.43% | Requires coded images to represent the eligible images in each city, including download and coding failures. |
| Among all Muse detections, including unclear sightings of either mode? | 3,655 classified as women, 7,506 as men, 28,399 unclear | If assigned labels are correct, the all-mode female share could range from 9.24% to 81.03%. People the pipeline missed lie outside this calculation. |

Of 9,835 images, 6,384 had zero classified pedestrians. These images contribute zero to both sides of the pooled ratio. The upstream corpus drew on imagery available to contributors in selected cities. Estimating the share among pedestrians on world streets would also require information on streets, times and people the cameras missed. [Corpus authors' sampling description](https://ual.sg/project/global-streetscapes/)

## Human validation and calibration

One Label Studio coder completed 119 of 300 selected images. The sample was drawn from 5,835 higher-pixel Round 1 frames. Its minimum was 5,055 person/rider pixels. The label interface showed location and withheld Muse counts.

| Region | Selected for annotation | Completed |
|---|---:|---:|
| Americas | 60 | 31 |
| East Asia and Pacific | 53 | 37 |
| Europe and Central Asia | 77 | 50 |
| Middle East, North Africa, Afghanistan and Pakistan | 34 | 1 |
| South Asia | 40 | 0 |
| Sub-Saharan Africa | 36 | 0 |

Completion changes the composition even on the observed model outcome. Muse classified 78 of 173 pedestrians as women in completed images (45.1%), compared with 97 of 316 in pending images (30.7%). The 119 completed images contain 192 classified and 345 unclear Muse detections. The human export contains 252 classified and zero unclear marks. Whether these discrepancies reflect missed people, extra detections or different interpretations of the coding instructions requires person-level review. A second coder's agreement is unknown.

**The reported recall is a ratio of counts.** Recall measures how many human-marked people the model correctly recovered. In the male rider row, the model records 17 and the human 10. Only four could possibly match within the same image, even granting a correct identity to every possible match. Thus recall against this coder is at most 40%, while the table labels 170% as recall. The same distinction applies to the motivating GPT-4o benchmark. [Recall definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.recall_score.html)

One checkable example is the London image below. Human and model counts agree on three women pedestrians and eight men pedestrians. The model adds four male riders and 22 unclear people. The human marked zero in both categories. The image permits an adjudicator to inspect where those extra counts might come from. [Original image](../data/label_studio/images/2cd5b543-4496-4c64-b9e8-e79390bb3594.jpg)

The published correction is arithmetically reproducible using the category totals. It estimates a human-equivalent share only if those model-to-human count ratios transfer to the target images. Resampling the 119 paired images 20,000 times with replacement (NumPy seed 0), while holding the full Round 1 counts fixed, gives a 95% percentile range of 27.0–38.4% for the adjusted pedestrian share and 26.2–36.8% for the all-mode share. These ranges describe variation within the completed set. They cannot measure errors specific to the unrepresented regions or to smaller people in the excluded frames.

The design specified at least 80% overall detection recall, a two-percentage-point city accuracy criterion across seven benchmark cells, and uncertainty propagation. The note provides no seven-cell accuracy test or person-matched recall test. Agreement of image counts (correlation 0.87) can coexist with disagreement about individual people. The source data for this analysis do not establish those proposed validation criteria. [Original design](../DESIGN.md)

## Sampling, exclusions and the next round

The city and image draws reproduced against cached inputs. Of 688 cities, 543 were eligible. The actual draw contained 101 cities in 88 countries, including the two certainty selections New Delhi and Faisalabad. Exactly 10,100 Round 1 frames were selected. The download manifest records 9,906 successes and the count file contains 9,835 unique image IDs, all from the draw. All 71 downloaded but uncoded files could be opened as JPEGs. The causes of their missing counts remain unresolved.

| Coverage check | Drawn | Coded |
|---|---:|---:|
| Mapillary | 9,268 | 9,104 |
| KartaView | 832 | 731 |
| Seoul, both sources | 100 | 20 |
| Jakarta, both sources | 100 | 58 |

The exported city probabilities do not describe the implemented draw. The sampler gives every non-anchor city selected from a stratum the same probability, its selected count divided by its eligible count. Yet the draw favors populous cities and countries without a selection. With identical inputs and seeds 0–999, Seoul appeared 1,000 times against its recorded probability of 0.191489. San Juan also appeared 1,000 times against 0.146067. The published pooled share does not use these weights. Any analysis expanding results to the eligible cities would need probabilities for the actual draw. [Probability calculation](../scripts/03_select_cities.py)

The positive-mask frame contains 1,492,859 of 2,536,337 corpus images in these cities. There is no draw to check for missed people in mask-negative frames. Knowing how often a mask fired cannot recover the gender composition of the people it missed. Hashing the actual coded JPEGs identified 9,822 distinct files among the 9,835 IDs. Counting each distinct image once gives 3,411 women among 9,311 classified pedestrians (36.63%). Exact duplicates have a small effect here. Repeated views of people in different photographs remain possible.

**Round 2 and the declared 5,000-pixel filter.** Appendix A's six threshold rows reproduce. In Round 1 the cutoff retains 5,835 of 9,835 images, 8,907 of 9,364 classified pedestrians, and changes the classified female share from 36.53% to 36.77%. That tests stability of the model output. It cannot establish accuracy for people the model failed to classify. Joining the Round 2 download manifest to the cached segmentation table finds 4,007 of 9,948 frames below the specified threshold. In the snapshot taken during the audit, 1,084 of the first 2,735 saved Round 2 count rows were below it. The wave is in progress. If the unfiltered wave is intentional, document it as such and preserve both analyses. If the cost saving is intended, enforce the cutoff before model calls. [Sampling specification](sampling_design.md)

## Figures, intervals and interpretation

- **Figure 2.** Atlanta has two classified pedestrians in 98 coded photos, both classified as women. Santa Maria has nine in 95 photos, all classified as men. The interval calculation gives [100%, 100%] and [0%, 0%] because every image's contribution to its estimated variance is zero at either boundary. Even an illustrative calculation treating sightings as independent gives exact binomial intervals of [15.8%, 100%] and [0%, 33.6%]. A clustered analysis must also account for people sharing a photograph or capture sequence. Show denominators alongside the extremes and withhold intervals where the method degenerates.
- **Figure 3.** The vertical axis ends at 58%. Twelve of the 101 cities lie above it, including Riga (91/130) and Atlanta (2/2), although the fitted line uses all 101. With the figure's weights, the share increases 3.50 percentage points per doubling of national GDP across cities. Comparing cities within the same region with the same weights gives −0.26 points per doubling. Which regions occupy which income ranges matters for interpreting the pooled line. Neither calculation identifies an income effect. [Figure and interval generator](../scripts/07_make_note_outputs.py)
- **Table 1.** Regional point estimates reproduce. The largest contrast is Europe and Central Asia (1,331/2,686 = 49.55%) versus the Middle East, North Africa, Afghanistan and Pakistan (217/1,264 = 17.17%). Their human-validation coverage is 50 images and one image respectively. Sampling intervals address variation in observed counts. They omit differential classification error. With only nine South Asian cities, using a small-sample t critical value in the existing formula widens its interval from [21.3%, 31.7%] to [20.4%, 32.6%]. This calculation still conditions on the available imagery.
- **Methods and sources.** The manuscript calls the model inputs full resolution. Of 9,835 source JPEGs, 8,678 exceed the default input box. The cached request for image `0026f56e-64e9-4a84-ab7a-3a1dd65df246` contains a 1,600 × 1,200 JPEG generated from a 2,048 × 1,536 file. The appendix footnote says 9,721 Round 1 images, its table has 9,835, and the README says data collection has yet to begin. The introduction also cites Asher et al. on constraints on movement. Their outcome is a child's education rank given parental education. [Image preprocessing](../scripts/05_muse_count.py) · [Asher et al.](https://www.aeaweb.org/articles?id=10.1257/app.20210686)

## Reproduction and repair order

1. **Protect the inputs first.** The Makefile's clean target recursively removes the entire ignored outputs directory, including the paid count files, sampling manifests and human export. Restrict cleanup to replaceable build products. Freeze versioned copies of the inputs for each paper build. The calibration target currently refreshes its CSV from a mutable local Label Studio database when available. A fresh checkout lacks the analytical CSVs and the working tree includes untracked calibration scripts and tables. [Makefile](../Makefile)
2. **Settle the Round 2 population and validation protocol.** Freeze the intended eligibility rule and compare selected, downloaded, coded and excluded IDs before another batch. For calibration, cover the missing strata and low-pixel frames or restrict the target to the validated group. Reconcile the use of “unclear” with a second coder. Estimating recall requires matching individual people. Aggregate count ratios can be evaluated separately for their ability to predict human totals on held-out images.
3. **Revise the note around the supported quantity.** Label the pooled sample share, show the sample funnel and city denominators, and describe the calibrated share as conditional on transfer of counting errors. Fix the plotted range and boundary intervals. Check that every plotted point falls within its axes and make manuscript sample sizes come from the same saved counts as the tables.
4. **Make pipeline failures visible.** A missing response slot currently becomes a row of zeros and the resume code subsequently treats its image as complete. Require one valid response per requested slot and record failed images separately. The examined cached answers gave no evidence that this fallback altered the published counts. Pin the upstream Parquet revision in the manifest. [Counting script](../scripts/05_muse_count.py) · [Image selection](../scripts/04_sample_images.py)

The audit ran the repository benchmark and rebuilt the eight-page note in an isolated working copy. All five generated table and macro files matched. The benchmark reproduced 87 parsed responses, 495 human-counted pedestrians, 198 model-counted pedestrians and shares of 19.6% and 29.8%. The lint target stopped at Black with seven files requiring formatting. Run separately, isort passed and flake8 reported 41 violations. The Makefile defines no test target. No paid calls or additional human annotations were made for the audit.

### Reproduce the strongest validation check

Run the following in Python from the repository root with the frozen CSVs present. A male rider can only match a human mark in the same image, so the smaller count in each image is an upper bound on correct matches there.

```python
import pandas as pd

sample = pd.read_csv("outputs/label_studio_sample.csv")
human = pd.read_csv("outputs/human_validation_ls.csv")
joined = sample.merge(human, on="uuid", how="left", validate="one_to_one")
print(joined.groupby("region").bad_image.agg(["size", "count"]))
rated = joined.loc[joined.bad_image.eq(0)]
riders = rated[["muse_men_twowheeler", "human_men_twowheeler"]]
print(riders.sum().tolist(), riders.min(axis=1).sum())
# [17.0, 10.0] 4.0
```
