# Literature review

Bibliography keys refer to `refs.bib`, which is built by `make bib` from `references.json`. Every entry there is resolved from Crossref or DataCite rather than typed, and `reference_validation.csv` records what each identifier actually returned. Two errors were caught that way: a title search for Gender Shades matched a different 2021 paper, and the Safetipin founding paper is in *Gender & Development*, not *Environment and Urbanization*.

Closeness is scored 1 to 5 against our design, where 5 would mean the study has already been done.

## Studies that measure people, or their absence, from images

| Study | Data | n | Unit | Coder | Sex coded | Validated against | Close |
|---|---|---|---|---|---|---|:-:|
| `photoball2026` Pujadas-Mora & Molina Rodríguez, *History of the Family* | Historical photo archive, Baix Llobregat, Catalonia, 1870 to 2021 | not stated in abstract | Person in photo | Segmentation plus classifier | Yes, perceived sex and age | Census and population registers | 4 |
| `goel2018streetimagery` Goel et al., *PLoS ONE* | Google Street View, 34 British cities, 2010 to 2012 | 68,000 images, 2,000 per city | Image | Human, partly MTurk | Cyclists only; determinable in 298 of 570 | 2011 census commute mode share (cycling r = 0.87 to 0.92; walking failed) | 4 |
| `turku2021walking` Männistö-Funk, *Urban History* | Street photographs of Turku, Finland, 1890 to 1989 | about 3,500 photographs | Person in photo | Human | Yes | None external | 3 |
| `gebru2017cars` Gebru et al., *PNAS* | Google Street View, 200 US cities | 50M images, 3,068 ZIP codes | Vehicle | Detector plus fine-grained classifier | No, cars not people | ACS demographics and precinct vote (88% / 82%) | 3 |
| `kokka2025vehicles` Kokka, Goel, Abbas, Nice, Martial, Labib, Ke, Schönlieb & Woodcock, arXiv | Google Street View, 185 cities plus 60 predicted | not stated | Vehicle | Detector, 89% mAP, fine-tuned on 6 cities | No, and gender is never mentioned | Survey and census mode share | 3 |
| `elrod2025sociability` Elrod, Flanigan & Bergés, ACM BuildSys | Global Streetscapes, 15 cities | 2,998 images, 200 sampled per city | Image | GPT-4o-mini, structured prompt | No | **None.** Authors call it a proof of concept | 3 |
| `arif2025pedestrian` Arif et al., arXiv and TRB | Far-view CCTV, 3 Dhaka intersections | not stated | Person crop | ResNet50, no faces | Yes, 6 classes by sex and age | Manual labels, 86.2% accuracy | 2 |

## Our own instruments, for comparison

| Instrument | Data | n | Coder | Redundancy | Female share |
|---|---|---|---|---|---|
| `streetscope` | Wearable GoPro on sampled routes, 4 Indian cities, 2025 to 2026 | 3,287 frames, 22,848 sightings | Human, Label Studio | Single | 18.1 to 27.4% |
| `missing_women_gsview` | Street View at sampled OSM road midpoints, 3 Indian cities | 1,942 views, 4,737 sightings | Human, Label Studio | 5 of 1,942 double-coded | 20.0 to 24.8% |
| `geosensing/women-count` | Head-height phone photos, Delhi, Nov 2016 to Jan 2017, hours 10:00 to 19:00 | 1,958 photos, 196 locations, 32,675 people coded | MTurk | **3 assignments per photo** | 18.5% |
| `geosensing/streetsense` | Street View, Bangkok, Dhaka, Jakarta, Lagos, Wayne County MI, 2017 to 2018 | 7,923 panoramas with ids and capture dates | MTurk, road condition only | Varies | Not coded for people |

The three Indian estimates of the female share agree to within about two points across a decade and three unrelated methods. That agreement is the anchor the new work is graded against.

## What the field has established that constrains us

**Counting is where models fail, attribute recognition is where they work.** `vlmcounting2024` benchmarks GPT-4V and finds counting the weak point. `aldahoul2025vlmfaces` gets 95.8% gender accuracy from a fine-tuned VLM on face crops and notes competent multi-person attribute extraction, and also documents outright refusals on demographic prompts, with one Gemini model refusing persistently. Together these say: detect with a detector, classify on crops, and log refusals as data.

**Faces are unavailable by design.** `frome2009blurring` reports Google blurring more than 89% of faces; Mapillary claims more than 99%. Every face-based classifier is therefore out, including everything audited in `buolamwini2018gendershades`, whose lesson still transfers: error rates were up to 34.7% for darker-skinned women against 0.8% for lighter-skinned men, which is error correlated with the very variable being estimated.

**Body-based benchmarks are out of distribution for most of the world.** `liu2017pa100k` and its siblings PETA and RAP are British surveillance and Chinese mall and campus crops. `vlmpar2025` is the current state of the art on them. They are fine for model selection and useless as ground truth for cross-country calibration.

**No one has measured classifier accuracy against national dress.** Searched for, not found. A thobe and an abaya are both long robes to these models, and differential accuracy by country would manufacture exactly the cross-country pattern we want to measure.

**Coverage is biased even where it is dense.** `alpherts2025idiosyncracy` shows city layout biases street view coverage across 28 cities regardless of density, with Amsterdam interviews on how the collection process shapes representation. `svicoverage2025` finds over-representation of non-residential space and recommends 50 to 60 metre sampling intervals. `seasonalbias2025` finds 54% mean absolute percentage error on the Green View Index from capture season alone across 40 cities.

**Time of day is the confound and only some sources carry it.** `goel2018streetimagery` states that Street View exposes neither time of day nor day of week, and that its imagery was 43% summer and almost no winter. `finetimestamp2025` exists specifically to escape that limit. Mapillary carries second-resolution capture timestamps; our own `women-count` photos carry EXIF times spanning 10:00 to 19:00.

**Image corpora understate women more than text does.** `guilbeault2024images`, across 3,495 social categories and more than a million images. A standing warning against reading any image collection as a population sample.

## The correction template

`fatehkia2018facebook` and `zagheni2018facebook` build country-level gender indicators from a badly biased digital source by regressing it on survey ground truth where both exist and predicting out of sample. That is the frame for our per-place calibration, with the addition of a detection stage that their setting does not have.

## Benchmarks outside imagery

`goel2022mobility` reports from the 2019 India Time Use Survey that 53% of urban women did not leave home on the diary day against 14% of men. `viswanath2015safetipin` founds the Safetipin audit, whose gender parameter is an ordinal 0 to 3 rating of the diversity of women and children present rather than a headcount, and whose point data is not public.

## Infrastructure

`hou2024globalstreetscapes` is the proposed base layer: 10 million Mapillary and KartaView images, 688 cities, CC BY-SA, with Mask2Former person masks precomputed. `kashyap2025zensvi` is its tooling companion. `thomee2016yfcc100m` is the Flickr corpus, 99.2 million photos ending in 2014.
