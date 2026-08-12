# Prior art

Assembled August 2026 from a web sweep of roughly fifteen query formulations. Verification status is marked per item and should be preserved when these move into a manuscript.

- `[fetched]` the page was retrieved and read
- `[snippet]` title and URL are real, details come from search-result summaries
- `[recall]` not verified in this sweep

**Headline: no published study estimates the female share of people visible in public space across places, from imagery.** What exists is demographics-from-cars, pedestrian counts with gender attempted only for cyclists, a large street-view-and-gender literature about perceived safety in which women are the raters rather than the subjects, and pedestrian attribute recognition as a pure computer-vision benchmark.

## Pre-emption sweep, August 2026

Ran to find the paper that scoops us. It does not appear to exist. Queries covered working-paper venues, Rahul Goel's recent output, the NUS Urban Analytics Lab, Alice Evans' own work, and Chinese-language sources. Four findings changed something.

**Nobody has taken the automated step to people.** Goel's group did scale up, in Kokka, Goel, Abbas, Nice, Martial, Labib, Ke, and coauthors, Vehicle detection from GSV imagery: predicting travel behaviour for cycling and motorcycling using computer vision, arXiv:2508.12794, 2025 `[fetched]`. Fine-tuned on six cities, 89% mean average precision, validated against survey and census mode share in 185 cities with predictions extended to 60 more. It detects **cycles and motorcycles only**, and the paper does not mention gender anywhere. The group with the strongest reason to move from vehicles to pedestrians, and the 2018 hand-coded gender pilot to build on, went the other way.

**The closest methodological ancestor is historical, and it should be cited.** Unveiling alternative quantitative narratives of gender and employment in Southern Europe from 19th- and 20th-century photographs: from pixels to socioeconomic insights using computer vision techniques. *The History of the Family*, 2026, doi:10.1080/1081602X.2026.2660747 `[snippet, Taylor & Francis returned 403]`. Builds the Photo-BALL database from a historical photo archive of Baix Llobregat county, Catalonia, 1870 to 2021: automatic segmentation of regions containing people, classification by **perceived sex and age**, then systematic contrast between census declarations of occupation and the activities visible in the photographs, to recover women's work that official documentation misses. Same three-step method as ours, applied to a different question, one county, and a curated archive rather than a sampling frame. It is a precedent for publishability, not a scoop. Get the author list and read it properly.

**Somebody has quantified the coverage bias we worry about.** Alpherts, T., Ghebreab, S., & van Noord, N. (2025). Artifacts of idiosyncracy in global street view data. arXiv:2505.11046 `[fetched]`. Shows that city idiosyncrasies such as layout bias street view data across 28 cities **even where coverage is dense**, proposes a method for evaluating those coverage distributions, and adds an Amsterdam case study with semi-structured interviews on how the collection process shapes which places get represented. This supports the within-cell identification argument directly, and it is the citation for why dense coverage is not the same as representative coverage.

**Multimodal models are already being used to code street imagery at multi-city scale, without gender.** Street View Sociability: interpretable analysis of urban social behavior across 15 cities. arXiv:2508.06342, 2025 `[fetched]`. 2,998 street view images, 15 cities, a multimodal large language model coding social interaction into Mehta's passive, fleeting, and enduring taxonomy, correlated with place attachment and sky, green, and water indices. No people detection, no demographics. Note the shape of it: about 3,000 images across 15 cities, and the abstract reports no validation against human labels. That is the failure mode our design exists to avoid.

Chinese-language search returned nothing counting pedestrian sex ratios. That literature runs to safety perception, streetscape aesthetics, street disorder measurement, age-friendliness, and women-friendly community design, including a Baidu street-view study of women's safety perception in Tianhe District, Guangzhou, published February 2026 `[snippet]`. Also found but not retrieved: Gender dynamics in urban space usage, a case study of Tebessa's historic city centre, Algeria, *Urban Science* 9(4):103, 2025 `[snippet, MDPI returned 403]`, apparently a single-city study of gender-specific pedestrian behaviour.

No public evidence that Alice Evans has a street-imagery project of her own.

## Still open

Whether the Maps Platform terms bar model inference as well as training (snippet-level only, and the highest-stakes unverified claim here). Whether the YFCC100M S3 bucket is currently serving objects. Author lists for the Photo-BALL paper and for several ScienceDirect items below, all of which returned 403. And the sweep searched the open web rather than SSRN, NBER, and the AEA registry directly, so a targeted search inside those catalogues would still be worth ten minutes.

## The anchors

Gebru, T., Krause, J., Wang, Y., Chen, D., Deng, J., Aiden, E. L., & Fei-Fei, L. (2017). Using deep learning and Google Street View to estimate the demographic makeup of neighborhoods across the United States. *PNAS* 114(50), 13108-13113. https://www.pnas.org/doi/10.1073/pnas.1700035114 `[snippet]`
About 50 million Street View images, 200 US cities, 3,068 ZIP codes, 39,286 precincts. Classifies **cars**, not people, into 2,657 make-model-year classes, then regresses ZIP-level income, race, education, and vote on fleet composition. Sedan-to-pickup ratio predicts precinct presidential vote at 88% and 82% accuracy. The design choice is the point: cars are large, unblurred, persistent, and taxonomized; pedestrians are none of those.

Goel, R., Garcia, L. M. T., Goodman, A., Johnson, R., Aldred, R., Murugesan, M., Brage, S., Bhalla, K., & Woodcock, J. (2018). Estimating city-level travel patterns using street imagery: a case study of using Google Street View in Britain. *PLoS ONE* 13(5), e0196521. https://pmc.ncbi.nlm.nih.gov/articles/PMC5931639/ `[fetched]`
68,000 archived Street View images, 2,000 per city across 34 British cities, 1,000 random locations per city, imagery from 2010 to 2012, coded by humans including MTurk into seven categories. Cycling correlates with 2011 census commute mode share at r between 0.87 and 0.92; **walking does not validate**. Gender attempted for cyclists only: determinable in **298 of 570 instances (52%)**. States that time of day and day of week are unavailable from the API, that most images are inter-peak, and that imagery is 43% summer and close to 0% winter. Read this first.

Follow-on: UChicago RCC feature on the Bhalla, Woodcock, and Murugesan worldwide transportation census. https://rcc.uchicago.edu/about-rcc/news-features/transforming-street-view-worldwide-transportation-census `[fetched]` Confirms an automated recognition module to scale beyond manual coding, and states explicitly that they could also collect data on the gender of cyclists. This is the closest group; check for unpublished gender work.

Männistö-Funk, T. The gender of walking: female pedestrians in street photographs 1890-1989. *Urban History*, published online 2019, issue 48(2) 2021, open access. doi:10.1017/S0963926819000981 `[resolved via Crossref]`
About 3,500 hand-coded street photographs of Turku, Finland across a century. Finds women were the largest continuous group of pedestrians throughout. The direct methodological ancestor of what we are automating, and it carries the archival-photo selection critique.

## Base layer

Hou, Y., Quintana, M., Khomiakov, M., Yap, W., Ouyang, J., Ito, K., Wang, Z., Zhao, T., & Biljecki, F. (2024). Global Streetscapes: a comprehensive dataset of 10 million street-level images across 688 cities for urban science and analytics. *ISPRS Journal of Photogrammetry and Remote Sensing* 215, 216-238. https://ual.sg/project/global-streetscapes/ · https://github.com/ualsg/global-streetscapes · https://huggingface.co/datasets/NUS-UAL/global-streetscapes `[fetched, repo]` `[snippet, author list]`
Ten million images, 688 cities, about 210 countries, from Mapillary and KartaView, CC BY-SA 4.0. 346 attributes; eight manually labeled including weather, lighting, view direction, panoramic status, quality, glare. Mask2Former instance segmentation and scene recognition precomputed, which gives person and rider masks for free. No pedestrian demographics. Imagery is roughly 6 TB; tabular data on Hugging Face.

Companion tooling: ZenSVI, an open-source package for acquisition, processing, and analysis of street-view imagery, arXiv:2412.18641, same lab. `[snippet]`

## Detection and gender classification

Arif, S. S., Shahrier, M. M., Haque, N., Raihan, M. A., & Hadiuzzaman, M. (2025). CNN-based framework for pedestrian age and gender classification using far-view surveillance in mixed-traffic intersections. arXiv:2511.22873; TRB 105th Annual Meeting poster. `[fetched]`
Three intersections in Dhaka. Six classes, male and female by adult, teen, child, from full-body cues with no faces at far view and low resolution. ResNet50 reaches **86.19%** gender accuracy; a lightweight custom CNN reaches 84.15%. Best existing evidence that body-only gender coding works in a South Asian street setting, and that the residual error will swamp small true differences without calibration.

AlDahoul, N., Tan, M. J. T., Kasireddy, H. R., & Zaki, Y. (2024). Exploring vision language models for facial attribute recognition: emotion, race, gender, and age. arXiv:2410.24148. `[fetched]`
Tests GPT-4o, GPT-4o-mini, Gemini 1.5 Flash and Pro, LLaVA-NeXT, PaliGemma, Florence-2 on FairFace, AffectNet, UTKFace. Fine-tuned PaliGemma reaches **95.8%** gender accuracy. Notes GPT-4o is good at multi-person attribute extraction from a single image. Also documents refusal behavior: GPT-4o and Gemini 1.5 initially refused race prompts, and Gemini 1.5 Pro kept refusing.

Good at captioning, bad at counting: benchmarking GPT-4V on Earth observation data. arXiv:2401.17600. `[snippet]`
The specific weakness that bit us, since our estimand is a count ratio. Mitigation: detect with a detector, classify on crops.

Buolamwini, J., & Gebru, T. (2018). Gender Shades: intersectional accuracy disparities in commercial gender classification. *PMLR* 81, 77-91. https://proceedings.mlr.press/v81/buolamwini18a.html `[snippet]`
Up to **34.7%** error for darker-skinned women against **0.8%** for lighter-skinned men. Benchmark datasets 79.6% and 86.2% lighter-skinned. Face-based, so it transfers to our setting by analogy rather than directly, but the structural lesson holds: error is worst exactly where the count matters and is correlated with the grouping variable.

Frome, A., Cheung, G., Abdulkader, A., Zennaro, M., Wu, B., Bissacco, A., Adam, H., Neven, H., & Vincent, L. (2009). Large-scale privacy protection in Google Street View. *ICCV*. https://research.google.com/archive/papers/cbprivacy_iccv09.pdf `[snippet]`
Blurs more than **89%** of faces and 94 to 96% of plates. Mapillary claims more than 99% `[snippet]`. Face-based gender classifiers are therefore structurally unusable on street-level imagery.

Detectors current as of 2026: RF-DETR (Apache 2.0, first real-time model past 60 mAP on COCO) and YOLO26 (NMS-free, with small-target-aware label assignment, which is the relevant property for distant pedestrians). arXiv:2601.12882, arXiv:2605.24831. `[snippet]`

Pedestrian attribute recognition benchmarks, all carrying a binary gender attribute: PETA (19,000 images, identity leakage), RAP (41,585 samples, one shopping mall), PA-100K (100,000 images, 598 scenes, leakage fixed), Market-1501 attributes, WIDER Attribute. `[snippet]` Current SOTA is VLM-PAR, a SigLIP 2 based model, arXiv:2512.22217 `[fetched]`. **All of these are British surveillance, Chinese mall, and campus crops.** Adequate for model selection, useless as ground truth for cross-country calibration.

**Nothing found on gender-classifier accuracy as a function of national dress or veiling.** Searched for; appears not to exist. Treat as an open research question.

## Measurement error and the correction frame

Fatehkia, M., Kashyap, R., & Weber, I. (2018). Using Facebook ad data to track the global digital gender gap. *World Development* 107, 189-209. https://www.sciencedirect.com/science/article/pii/S0305750X18300883 `[snippet]`

Zagheni, E., and coauthors (2018). Analyzing gender inequality through large-scale Facebook advertising data. *PNAS*. https://www.pnas.org/doi/abs/10.1073/pnas.1717781115 `[snippet]`

Kashyap, R., and coauthors. Monitoring global digital gender inequality using the online populations of Facebook and Google. Data2X. `[snippet]`

These establish the template: regress a biased digital indicator on survey ground truth where both exist, then predict out of sample.

Guilbeault, D., Delecourt, S., Hull, T., Srinivasa Desikan, B., Chu, M., & Nadler, E. (2024). Online images amplify gender bias. *Nature* 626, 1049-1055. https://www.nature.com/articles/s41586-024-07068-x `[snippet]`
3,495 social categories, more than a million images. Underrepresentation of women is substantially worse in images than in text. A direct warning against reading any image corpus as a population sample.

## Capture and coverage bias

Quantifying seasonal bias in street view imagery for urban form assessment: a global analysis of 40 cities. *Computers, Environment and Urban Systems*, 2025. https://www.sciencedirect.com/science/article/pii/S0198971525000559 `[snippet, authors missing]`
54% mean absolute percentage error on the Green View Index; bias correlates with climate.

Coverage and bias of street view imagery in mapping the urban environment. *Computers, Environment and Urban Systems*, 2025. arXiv:2409.15386 `[snippet, authors missing]`
Street-view imagery over-represents non-residential buildings; recommends 50 to 60 meter sampling intervals.

Fine-timestamped street view imagery reveals patterns of pedestrian dynamics associated with urban functional characteristics. *Cities*, 2025. https://www.sciencedirect.com/science/article/abs/pii/S0264275125008182 `[snippet, authors missing]`
Built specifically to escape the daily-resolution temporal limitation. Get the author list.

## Benchmarks and validation targets

Goel, R. (2022). Gender gap in mobility outside home in urban India. arXiv:2208.08990. `[fetched]`
2019 India Time Use Survey, nationally representative, 30-minute diary intervals. **53% of urban women reported not going out of home on the diary day, against 14% of men.** Female mobility falls sharply at the transition to adulthood; marriage, household size, infant care, low income, and low education all reduce it. Already used in `streetscope/supplementary/mobility_accounting.md`.

Gehl Institute Public Life Data Protocol. https://github.com/gehl-institute/pldp `[snippet]`
Open specification for public-life observation built with Gehl, Copenhagen, San Francisco, and Seattle DOT. More than 80 coded attributes of who occupies space, including gender and age, with explicit guidance on observing the same place across days, times, and weather. Data from more than 250 cities.

Safetipin. https://safetipin.com/ `[fetched]`
Nine-parameter night-time urban safety audit collected from a windshield-mounted phone, with more than 35,000 audit points in Delhi since 2013, plus Bogota and Nairobi under a UN-Habitat partnership. Founding paper: Viswanath, K., & Basu, A. (2015). SafetiPin: an innovative mobile app to collect data on women's safety in Indian cities. *Gender & Development* 23(1), doi:10.1080/13552074.2015.1013669 `[resolved via Crossref]`. An earlier draft of this file gave the venue as *Environment and Urbanization*, which was wrong.
**Two caveats.** The gender parameter is an ordinal 0 to 3 rating of the diversity of women and children among people present, not a count, so it correlates with our estimand rather than measuring it. And the data is not public: aggregate PDF reports and their feature-extraction code (https://github.com/SafetiPin-App/SafetiPin_ML) are open, the audit points are shared with city governments and partners and viewable in the app. Access requires asking.

Other time-use benchmarks: OECD Time Use Database (30 countries), the Multinational Time Use Study, Eurostat HETUS. `[snippet]`

There is no international index of women's share of people in public space. The nearest institutional constructs are UN-Habitat's Women's Safety Audit, which originates with METRAC in Toronto in 1989, and the UNDP Gender Social Norms Index, which is attitudinal rather than behavioral.

## Data availability

**Mapillary** `[fetched, terms page, last updated 15 February 2024]`. Free. Imagery is CC BY-SA 4.0 by default, with some content CC BY-NC-SA, so check per image. Terms explicitly permit use for the improvement, training, and development of algorithms, datasets, and technologies. Bulk scraping outside the API is prohibited. Attribution required on display. Since **16 January 2026**, bounding-box queries to `/images` and `/map_features` must be under 0.01 degrees square; use `mapillary-python-sdk` `[snippet, verify against live docs]`. Faces and plates auto-blurred.

**YFCC100M** `[snippet]`. Alive as the Multimedia Commons AWS Open Data dataset, `s3://multimedia-commons/`. 99,171,688 images and 787,479 videos, 2004 to 2014, about 49 million geotagged. Metadata is a single bzip2 file of about 15 GB. Per-photo Creative Commons licenses vary, including NC and ND. **Not verified that the bucket is currently serving.** Note the ethics literature on repurposing CC-licensed Flickr faces for biometrics (Harvey, Creative Commons Biometrics).

**Yelp Open Dataset** `[fetched]`. Downloadable. 6,990,280 reviews, 150,346 businesses, **200,100 photos**, 11 metropolitan areas, all United States and Canada. JSON archive 4.35 GB compressed; photos 7.45 GB compressed. Photo labels are food, drink, menu, inside, outside, with no person label. The web page says educational use and points at general Yelp terms; the bundled `Dataset_User_Agreement.pdf` is the binding document and historically requires non-commercial academic use and prohibits redistribution `[recall]`. Read it.

**Google Street View** `[fetched, pricing and policies]` `[snippet, service terms]`. Static Street View is 5.60 dollars per 1,000 in the 100,001 to 500,000 band, falling to 0.53 per 1,000 above 5 million, with 10,000 free events per month since the March 2025 pricing change. **Street View metadata is unlimited and free**, which is the endpoint to use for coverage and date discovery. Policies prohibit pre-fetching, indexing, storing, and caching, with panorama IDs the sole exception, and attribution is mandatory on display. Service terms appear to include a no-scraping clause and a prohibition on using Maps content to train, test, validate, or fine-tune models `[snippet only, verify]`. One million images runs about 5,000 to 6,000 dollars. Mapillary is zero.
