# Women in public space, measured from photographs

## Research design

The hard part of this study is not getting the pictures. It is that the model doing the counting is wrong in a way that looks exactly like the answer. We ran GPT-4o over 100 street images that human coders had already counted. It found 40% of the people, and its recall differed by sex: 61% of the women, 35% of the men. A true female share of 19.6% came back as 29.8%. That error, ten points, is larger than the whole spread we are trying to measure across cities, which runs from about 18% to 27%.

So the design below is organized around calibration rather than collection. Everything else is cheap.

## What we already have

Three instruments have measured the same quantity in Indian cities, and they agree.

| Instrument | Places | Sightings | Female share of pedestrians |
|---|---|---|---|
| Wearable camera on sampled routes, human-coded (`streetscope`) | Mumbai, Navi Mumbai, Bangalore, Delhi | 22,848 | 19.1 / 18.1 / 27.4 / 19.8% |
| Street View at sampled road midpoints, human-coded (`missing_women_gsview`) | Delhi, Mumbai, Navi Mumbai | 4,737 | 20.0 / 20.5 / 24.8% |
| Distributed photographers plus MTurk, 2016 to 2017 (`geosensing/women-count`) | Delhi | 1,958 photos | about 18.5% |

Three methods, a decade apart, land on roughly one in five. The two recent instruments share no code, no imagery, and no annotators, and their Delhi estimates differ by 0.2 percentage points.

The interesting number is what survives the obvious explanation. Scaling each city's residential sex ratio by the mobility rates in the 2019 Time Use Survey, women who never left home account for most of the shortfall, and women who left home but made fewer trips account for a little more. About 23% of the gap remains (`streetscope/supplementary/mobility_accounting.md`). Those are women who left the house, made their trips, and are still not standing on a road. A time-use survey cannot see them. That residual is the quantity the imagery uniquely provides, and measuring it somewhere other than India is what this study is for.

## What the literature has and has not done

Nobody has published a cross-place estimate of the female share of people visible in public space. The nearest work does something adjacent on purpose. Gebru and coauthors inferred neighborhood demographics across 200 American cities from 50 million Street View images by classifying cars, not people (PNAS 2017). Cars are large, unblurred, persistent, and come with a canonical taxonomy; pedestrians have none of those properties.

The one real precedent is a cautionary one. Goel and coauthors hand-coded 68,000 Street View images across 34 British cities (PLoS ONE 2018). Cycling volumes validated against the census at r between 0.87 and 0.92. Walking did not validate. They attempted gender for cyclists only, the easiest case, and could determine it in 298 of 570 instances, or 52%. They also state that time of day and day of week are unavailable from the Street View API, and that their imagery was 43% summer and almost no winter.

Three lessons follow. Walking is the hard signal. Gender is undeterminable about half the time at this resolution. The temporal confound is documented rather than hypothetical.

A large literature does connect gender and street view, but it studies women as raters of perceived safety rather than as subjects, and it does not help us.

Two findings from a pre-emption sweep sharpen the position. Goel's group did automate their pilot, across 185 cities with 89% mean average precision, but they detect cycles and motorcycles and never mention gender (arXiv:2508.12794, 2025). The group with the strongest reason to move from vehicles to pedestrians went the other way, which is a fact about how hard the pedestrian problem is, not an oversight.

And the closest methodological ancestor is historical. The Photo-BALL project segments people out of a photographic archive of one Catalan county covering 1870 to 2021, classifies them by perceived sex and age, and contrasts the result against census declarations of occupation to recover women's work that the official record misses (*The History of the Family*, 2026). Same three steps as ours, on a curated archive rather than a sampling frame, and in one county. It establishes that the method is publishable, and it leaves the cross-place present-day question open.

## Architecture: detect, then classify

The GPT-4o failure has a known cause. Counting is the documented weak point of vision language models (arXiv:2401.17600), while attribute recognition on a single crop is a strength: a fine-tuned PaliGemma reaches 95.8% gender accuracy on FairFace, and GPT-4o handles multi-person attribute extraction well when prompted for it (arXiv:2410.24148). Asking one model to do both puts it where it is weakest.

So we separate the stages. A detector finds people. Small distant pedestrians are exactly the regime the recent detectors target. A classifier or vision language model then codes apparent gender on each crop above a pixel-height threshold, with an explicit undeterminable category. Refusing to guess is a feature, and Goel's 52% determinability is the number to beat.

Faces are unavailable and that is structural, not incidental. Google blurs more than 89% of faces by design (Frome et al., ICCV 2009) and Mapillary claims more than 99%. Every face-based gender classifier is therefore out, including the commercial systems audited in Gender Shades. Body, clothing, and posture cues are all we have. That is what the working precedent uses: a plain ResNet50 on far-view crops from Dhaka intersections reaches 86.2% gender accuracy with no faces (arXiv:2511.22873).

One operational note. Vision language models sometimes refuse demographic prompts, and one of the Gemini models in the study above refused persistently. If refusal rates vary with what is in the image, that is non-random missingness in the outcome. Log refusals as data.

## Do not build a Mapillary collector

Global Streetscapes already did it (Hou et al., *ISPRS Journal of Photogrammetry and Remote Sensing* 215, 2024). Ten million street-level images across 688 cities and about 210 countries, sourced from Mapillary and KartaView, released under CC BY-SA 4.0, with 346 attributes including hand-labeled weather, lighting, view direction, and image quality, and with Mask2Former instance segmentation already computed. The segmentation hands us person masks for free, which is the detection stage.

That covers city sampling, temporal metadata, licensing, and detection, in a form we can redistribute. Its weakness is the one Mapillary always has: coverage is contributor-driven and skews arterial, and in a thinly covered country a few thousand images can come from a handful of contributors, which is close to n = 1 at the camera level.

Licensing is also why we are not using Google. Street View policies prohibit pre-fetching, storing, and caching imagery, allowing only panorama IDs to be kept, and the Maps Platform terms appear to bar using Maps content to train, test, or validate models. Mapillary's terms run the other way: imagery is CC BY-SA 4.0, and commercial users may use the service for the improvement, training, and development of algorithms and datasets. Free, licensed, and explicit.

If direct API work is needed, note that since 16 January 2026 Mapillary constrains bounding-box queries to under 0.01 degrees square, which changes how a city gets enumerated.

## Three arms, three estimands

The three sources answer different questions, and treating them as three measurements of one thing would be a mistake.

### Mapillary: presence, and its change

The estimand is the person-weighted share of classified pedestrian sightings coded as women, in spatial cell k at time t, which is the same estimand as the existing Indian work:

    p(k,t) = sum of women sightings / sum of all pedestrian sightings

Bin images into cells of about 50 meters, keep cells imaged in two or more distinct years, and estimate change with cell fixed effects. Levels across countries are contaminated by coverage, capture process, and place-varying classifier error. Change at a fixed location differences most of that away.

The threat is that the capture process changes within a cell. A hobbyist cyclist at 3pm on a Sunday in 2016 and a mapping van at 9am on a Tuesday in 2023 produce a difference that is not a change in who is on the street. Mapillary carries what we need to condition on this: capture timestamps at second resolution, which Street View does not provide at all, plus creator ID, camera make and model, compass angle, and sequence ID. The identifying comparison is therefore within cell, within hour band and day type, and where possible within creator or camera class. That belongs in the design, not in a robustness appendix.

The cost of skipping it is known. Seasonal capture bias alone produces 54% mean absolute percentage error on the Green View Index across 40 cities (*Computers, Environment and Urban Systems*, 2025), and street-view sampling over-represents non-residential space, which is itself gendered. Alpherts and coauthors go further and show that city layout biases street-view coverage across 28 cities even where coverage is dense, so a high image count is not evidence of a representative sample (arXiv:2505.11046).

### Flickr and YFCC100M: representation, not presence

A Flickr photo is a chosen scene, and the photographer is the sampling mechanism. The honest estimand is the share of people appearing in publicly posted geotagged street photographs who are coded as women. That measures visual representation and who is deemed photographable. It is worth measuring as itself, and the design should not launder it into a measure of presence.

Two constraints. The corpus holds 99.2 million photos, about 49 million geotagged, and stops in 2014, so this arm is historical and bounded. And Guilbeault and coauthors find that the underrepresentation of women is substantially worse in images than in text across 3,495 social categories (*Nature* 626, 2024), which is a direct warning against reading any image corpus as a population sample.

The minimum defensible version restricts to outdoor street scenes, compares within place and within photographer, and reports how the photographer population itself shifts between the early-adopter era and the smartphone era, since that shift is the main rival explanation for any trend.

### Yelp: who eats out

Two measurements from one dataset, sharing no failure mode, which is the point of including it.

The photo route codes the share of people who are women in restaurant interior photos. Expect it to be weak. The open dataset holds 200,100 photos across 11 North American metros, labeled only food, drink, menu, inside, or outside, and interior photos are mostly decor. People photograph their plate, not strangers.

The name route is better identified. Yelp user records carry first names, so we can infer gender with tools we already maintain (`naampy`, `ethnicolr`, `parsernaam`) and estimate the female share of reviewers by restaurant, cuisine, price tier, and hour. Where the two routes agree, the measure is credible. Where they diverge, the divergence is informative.

The American Time Use Survey reports eating-out episodes by sex, so this arm has a probability-sample benchmark.

Two limits to state up front. Eleven metros in the United States and Canada means no cross-country design is possible here, so this is a method demonstration. And the dataset ships a user agreement restricting it to educational use and prohibiting redistribution, which we should read rather than infer.

## The calibration model

Treat the classifier as a noisy instrument and estimate its error rates separately in every place, from human-coded subsamples. Two stages, both shown to be real by the GPT-4o run.

Detection: the probability that a person of each sex who is present gets counted at all. GPT-4o managed 0.61 for women and 0.35 for men, and that asymmetry alone moved the share by ten points.

Classification: given detection, the probability that a woman is coded a woman and a man a man, plus the rate at which the coder declines to say.

The observed share is a known function of the truth given those rates, so we invert it and propagate the uncertainty in the rates, which is Rogan-Gladen with a detection stage added.

The statistical template exists. The Facebook advertising literature on the digital gender gap (Fatehkia, Kashyap, and Weber, *World Development* 107, 2018; Zagheni and coauthors, PNAS 2018) regresses a biased digital indicator on survey ground truth where both exist and predicts out of sample. That is the right frame for the cross-country correction.

One more thing belongs here, and it may be the most publishable part of the study. No paper appears to measure gender-classifier accuracy as a function of national dress or veiling. A thobe and an abaya are both long robes to a model trained on PETA, RAP, and PA-100K, all of which are British surveillance footage and Chinese mall and campus crops. Differential accuracy by country would produce exactly the cross-country pattern we are trying to measure, as pure artifact. Gender Shades established the general shape of this failure, with error rates up to 34.7% for darker-skinned women against 0.8% for lighter-skinned men, but nobody has done it for dress. This is at once the first referee objection and a contribution. Build the per-country calibration sets so that quantifying it falls out of the design.

Check also whether undeterminability is itself gendered. Loose clothing and distance both raise it, and both are distributed non-randomly. Goel's 48% undeterminable rate is not missing at random.

## External validation

Beyond the two instruments we own:

The 2019 India Time Use Survey found that 53% of urban women reported not leaving home on the diary day, against 14% of men (Goel 2022, arXiv:2208.08990). We already use this in the accounting; it is the natural benchmark for any Indian imagery estimate. The OECD Time Use Database, MTUS, and Eurostat HETUS cover other countries.

The Gehl Institute Public Life Data Protocol is an open specification for public-life observation with more than 80 coded attributes including gender, with explicit guidance on observing the same place at different times, days, and weather. Data exists from more than 250 cities. It is the manual solution to the time-of-day confound, and a ready-made instrument if we extend the field arm.

Safetipin has more than 35,000 audit points in Delhi since 2013, plus Bogota and Nairobi, collected at night from a windshield-mounted phone. Two caveats. Their gender parameter is an ordinal 0 to 3 rating of the diversity of women and children among people present, not a headcount, so it correlates with our estimand rather than measuring it. And the data is not public: aggregate reports and their feature-extraction code are, the audit points are shared with city governments and partners. Access means a conversation.

State the estimand mismatch explicitly, because a referee will find it. Time-use surveys measure person-hours out of home. Imagery measures person-instances visible in public at capture moments, weighted by dwell time and by how street-facing the activity is. A woman who drives to a mall contributes far less to the imagery estimand than to the survey estimand.

## Two assets we already own that change the pilot

Both are in the `geosensing` organisation, and neither has been used for what it is now worth.

`women-count` is 1,958 head-height phone photographs of Delhi, taken between 12 November 2016 and 11 January 2017 between 10:00 and 19:00, with 5,874 MTurk assignments coding 32,675 people, of whom 18.5% are women. Two properties nothing else in the collection has. The capture time is known from EXIF, which Street View never gives us. And every photo was coded three times independently, so **human disagreement is estimable**. That matters more than it sounds: human disagreement is the ceiling on what we can fairly demand of a model, and without it the two-point tolerance in the pilot below is a number we chose rather than a number we derived. Compute it first, then set the criterion.

`streetsense` holds 7,923 Street View panorama identifiers with capture dates, sampled with `geo-sampling` in 2017 and 2018: Bangkok 999, Dhaka 246, Jakarta 978, Lagos 872, and Wayne County Michigan 4,828. All returned status OK. They were coded by MTurk for road condition, litter, and sidewalks, and never for people.

That is a documented sampling frame in five non-Indian places spanning most of the range we care about, and panorama identifiers are the one artifact Google's policy permits storing indefinitely, so the frame itself is clean. Re-pulling imagery against those identifiers is the restricted act, not holding them. If we did, we would get a cross-country pilot at zero sampling cost and an eight-year within-location panel, which is the only route to the headline design that does not depend on Mapillary happening to have repeat coverage.

That requires reopening the decision to drop Street View. It is the first open question below, and this is what puts weight behind it.

## Proof of concept

The point of running a proof of concept here is that we can grade it against a number fixed before it runs. Delhi and Mumbai already have a female pedestrian share near 19% to 20%, measured twice by instruments sharing nothing. If a Mapillary pipeline lands there, the source, the model, the estimator, and the sampling frame are vindicated at once. If it lands at 30%, we know before spending anything.

### Stage one: benchmark the instrument

Roughly one day and twenty dollars, using imagery already on disk: 1,942 human-coded Street View views covering 4,737 sightings, and 3,287 human-coded wearable-camera frames covering 22,848 sightings across four cities.

Replace the existing validation script with a shared, model-agnostic annotator: a detector for the count and a classifier on crops for the gender, structured output against a schema rather than a regular expression (13 of 100 responses failed to parse last time), the same taxonomy the human coders used so the comparison is like for like, an explicit undeterminable class and a pixel-height threshold, at least three classifier options and three repeats per image so that model choice and run-to-run variance are visible, refusals logged, and all the labeled images rather than a hundred.

Success criteria, fixed in advance:

1. Corrected city-level female share within 2 percentage points of the human estimate in all seven city-by-instrument cells.
2. The ordering across cities, with Bangalore highest, preserved.
3. Before correction, detection recall of at least 0.8 overall, with the women-to-men recall ratio between 0.9 and 1.1, so that the correction is an adjustment rather than the load-bearing element.
4. The undeterminable rate reported and tested for association with sex.
5. Cost per image low enough that 200,000 images stays under 500 dollars.

A model returning plausible counts uncorrelated with the truth image by image could still match the aggregates and pass the first two criteria. So report per-image correlation and the confusion structure alongside the aggregates, and look at a contact sheet stratified by human count before believing any of it.

### Stage two: one arm, end to end

Two or three days. Mapillary only, Delhi and Mumbai only, because those are the cities with two independent human-coded estimates to grade against. Pull the Global Streetscapes slice for those cities, apply the stage-one annotator and correction, and compute the share with the clustered estimator we already use.

The criterion: the corrected estimate falls within the union of the two existing 95% intervals in both cities, or the discrepancy gets traced to a named mechanism such as capture hour, road-class mix, or creator composition, rather than left as a gap.

Either way, stage two tells us how often Mapillary timestamps are present and trustworthy, how concentrated creators are, and whether hour of day is usable. Those facts decide whether the identification strategy for the Mapillary arm exists at all.

Out of scope for both stages: the Flickr and Yelp arms, anywhere outside Delhi and Mumbai, and any claim about levels or trends.

### After that

A coverage census, which is free and takes a day, gates the city list: cells with imagery in two or more years, images per cell per year, hour distribution, creator concentration, camera mix. Cities enter on the census rather than on interest. The census is a result in its own right, since coverage in the earlier Street View work ranged from 24.6% of sampled roads in Dhaka to 99.9% in Bangkok.

## Reproducibility

Model annotation breaks the usual recipe, because the annotator is a remote service that can change or disappear. Three requirements follow.

Archive the raw model responses, not just the parsed counts. Pin the model snapshot, set temperature to zero, and store full request and response payloads, so the analysis replays without the API. This is the only way a result stays reproducible after a model is retired.

Report model nondeterminism as a quantity. Spread across repeats is a component of measurement error and belongs in the intervals.

Cache the raw source responses too: Mapillary metadata, Yelp records, YFCC rows. Store the payloads, not only the derived tables.

The rest we already do. Every input recorded in a manifest with byte counts and SHA-256 hashes. Every sampling stage re-derived from its recorded seed and asserted to match. Published numbers rebuilt offline from frozen inputs by a single command, with no API calls. Licensing determined per source and written down before collection rather than after.

The known local failure mode is provenance. The first Street View round lost the provenance of its 4,500-location subsample and its Overpass query timestamp, and its README now has to call the cross-city contrasts descriptive as a result.

## Open decisions

1. Street View is out as a collection source, on licensing. The 7,923 stored panorama identifiers in `streetsense` make that decision expensive: they buy five non-Indian places and an eight-year panel. Do we reopen it?
2. How many places, and who codes the per-place calibration samples? This is the real budget line, and it is annotation, not compute.
3. When do we approach Safetipin, before or after the proof of concept?

## References

`docs/literature_review.md` has the comparison table: data, sample size, unit, coder, whether sex was coded, and what each study validated against. `docs/prior-art.md` has the full sweep with per-item verification status. `docs/refs.bib` is built by `make bib` from resolved identifiers, with `docs/reference_validation.csv` recording what each one returned.
