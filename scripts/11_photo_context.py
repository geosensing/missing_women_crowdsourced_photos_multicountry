"""Join pinned Global Streetscapes metadata and describe the coded photographs."""

from pathlib import Path
from xml.etree import ElementTree

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
import statsmodels.formula.api as smf
from figstyle import ACCENT, apply_style
from huggingface_hub import hf_hub_download
from paper_tables import write_table
from regional_timing import regional_timing

matplotlib.use("Agg")

OUT = Path("outputs")
REV = "7bd2e7697a3cb5f74ff05bd718babdb927f8b60d"
CITIES = [("New Delhi", "delhi", 32643), ("London", "london", 32630)]


def metadata(name, ids, fields):
    path = hf_hub_download(
        "NUS-UAL/global-streetscapes",
        f"data/parquet/{name}.parquet",
        repo_type="dataset",
        revision=REV,
    )
    return pq.read_table(
        path, columns=["uuid", *fields], filters=[("uuid", "in", ids.tolist())]
    ).to_pandas()


def assemble():
    counts = pd.read_csv(OUT / "muse_counts_all.csv")
    counts["uuid"] = counts.image.str.removesuffix(".jpg")
    selected = pd.read_csv(OUT / "selected_images.csv")
    frame = counts.merge(selected, on="uuid", validate="1:1")
    assert len(frame) == len(counts)
    for name, fields in [
        ("metadata_common_attributes", ["lat", "lon", "year", "month", "day", "hour"]),
        ("osm", ["highway", "name", "snap_dist", "type_highway", "lanes", "maxspeed"]),
    ]:
        frame = frame.merge(
            metadata(name, frame.uuid, fields), on="uuid", how="left", validate="1:1"
        )
    frame["date"] = pd.to_datetime(frame[["year", "month", "day"]], errors="coerce")
    frame.loc[frame.year.eq(1970), ["date", "hour"]] = [pd.NaT, np.nan]
    frame["weekday"] = frame.date.dt.day_name()
    frame["n"] = frame.women_count + frame.men_count
    return frame


def compare(frame):
    d = frame.loc[frame.hour.between(6, 21) & frame.n.gt(0)].copy()
    d["share"] = 100 * d.women_count / d.n
    d["road"] = d.highway.fillna("unknown")
    rows = []
    for label, cutoff, extra in [
        ("primary", 18, ""),
        ("earlier evening", 17, ""),
        ("road, source and year adjusted", 18, " + C(road) + C(source) + C(year)"),
    ]:
        d["evening"] = d.hour.ge(cutoff).astype(int)
        fit = smf.wls(
            "share ~ evening + C(weekday, Treatment('Monday')) + C(city_id)" + extra, d, weights=d.n
        ).fit(cov_type="cluster", cov_kwds={"groups": d.city_id}, use_t=True)
        for term in fit.params.index:
            if term == "evening" or term.startswith("C(weekday"):
                low, high = fit.conf_int().loc[term]
                rows.append((label, term, fit.params[term], low, high))
        if label == "primary":
            terms = [i for i, t in enumerate(fit.params.index) if t.startswith("C(weekday")]
            print("Weekday joint p", fit.f_test(np.eye(len(fit.params))[terms]).pvalue)
            print(
                d.groupby("evening").agg(
                    photos=("uuid", "size"),
                    sightings=("n", "sum"),
                    women=("women_count", "sum"),
                    cities=("city_id", "nunique"),
                )
            )
            print("Cities with both", d.groupby("city_id").evening.nunique().eq(2).sum())
    estimates = pd.DataFrame(rows, columns=["model", "term", "points", "lower95", "upper95"])
    estimates.to_csv(OUT / "capture_time_regression.csv", index=False)
    return estimates


ROAD_LABELS = {
    "motorway": "Motorway or trunk",
    "trunk": "Motorway or trunk",
    "primary": "Primary",
    "secondary": "Secondary",
    "tertiary": "Tertiary",
    "residential": "Residential",
    "service": "Service",
    "footway": "Footway",
    "pedestrian": "Pedestrian street",
    "cycleway": "Cycleway",
}


def road_classes(highway):
    return (
        highway.str.replace(r"_link$", "", regex=True)
        .map(ROAD_LABELS)
        .fillna("Other or mixed")
        .mask(highway.isna(), "Unmatched")
    )


def road_table(frame):
    regions = {
        "Europe & Central Asia": r"Europe \&\\Central Asia",
        "East Asia & Pacific": r"East Asia\\\& Pacific",
        "Americas": "Americas",
        "Sub-Saharan Africa": r"Sub-Saharan\\Africa",
        "South Asia": r"South\\Asia",
        "Middle East, North Africa, Afghanistan & Pakistan": r"MENA, Afg.\\\& Pak.",
    }
    if set(frame.region.unique()) != set(regions):
        raise ValueError("Check the region labels before generating the appendix")
    road = road_classes(frame.highway)
    counts = pd.crosstab(road.mask(frame.highway.isna(), "Unmatched"), frame.region)
    counts = counts.reindex(
        index=[*dict.fromkeys(ROAD_LABELS.values()), "Other or mixed", "Unmatched"],
        columns=list(regions),
        fill_value=0,
    )
    counts["All"] = counts.sum(axis=1)
    if counts["All"].sum() != len(frame):
        raise ValueError("Road table does not account for every coded photo")
    counts.to_csv(OUT / "road_type_by_region_counts.csv")
    shares = 100 * counts / counts.sum()
    table = shares.map("{:.1f}".format)
    table.loc["Photos"] = counts.sum().map("{:,}".format)
    table.columns = [r"\shortstack{" + label + "}" for label in [*regions.values(), "All"]]
    write_table(
        table.rename_axis("Street type").reset_index(),
        Path("tabs/tableB1_road_types.tex"),
        "lrrrrrrr",
        escape=False,
    )


def time_figure(estimates):
    apply_style()
    primary = estimates.loc[estimates.model.eq("primary")].copy()
    primary.index = primary.term.str.extract(r"\[T\.(\w+)\]", expand=False).fillna("Evening")
    order = ["Evening", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    primary = primary.loc[order]
    fig, ax = plt.subplots(figsize=(6.1, 2.85))
    y = [7.5, 5, 4, 3, 2, 1, 0]
    ax.axvline(0, color="0.6", linewidth=0.8, linestyle="--")
    ax.errorbar(
        primary.points,
        y,
        xerr=[primary.points - primary.lower95, primary.upper95 - primary.points],
        fmt="o",
        color=ACCENT,
        ecolor="0.4",
        linewidth=1.2,
        markersize=4,
    )
    ax.set_yticks(y, ["Evening vs. daytime", *order[1:]])
    ax.text(
        0,
        6.1,
        "Day of week relative to Monday",
        transform=ax.get_yaxis_transform(),
        weight="bold",
        size=8,
    )
    ax.set_xlabel("Difference in share coded as women (percentage points)")
    ax.set_ylim(-0.6, 8.1)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    fig.savefig("figs/figC1_capture_time.pdf")
    plt.close(fig)


def street_lines(stem, project):

    bounds = {"delhi": (77.187, 28.611, 77.215, 28.635), "london": (-0.135, 51.493, -0.107, 51.511)}
    w, s, e, n = bounds[stem]
    boxes = (
        [(w, s, e, n)]
        if stem == "delhi"
        else [
            (x0, y0, x1, y1)
            for x0, x1 in [(w, (w + e) / 2), ((w + e) / 2, e)]
            for y0, y1 in [(s, (s + n) / 2), ((s + n) / 2, n)]
        ]
    )
    nodes, ways = {}, {}
    for index, box in enumerate(boxes):
        suffix = "" if len(boxes) == 1 else str(index)
        path = Path(f"data/raw/{stem}{suffix}_streets.osm")
        if not path.exists():
            response = requests.get(
                "https://api.openstreetmap.org/api/0.6/map",
                params={"bbox": ",".join(map(str, box))},
                timeout=90,
            )
            response.raise_for_status()
            path.write_bytes(response.content)
        for element in ElementTree.parse(path).getroot():
            key = element.get("id")
            tags = {t.get("k"): t.get("v") for t in element.findall("tag")}
            if element.tag == "node":
                nodes[key] = project.transform(float(element.get("lon")), float(element.get("lat")))
            if element.tag == "way":
                ways[key] = (tags, [nd.get("ref") for nd in element.findall("nd")])
    from shapely.geometry import LineString

    records = [
        (tags["highway"], LineString([nodes[k] for k in refs]))
        for tags, refs in ways.values()
        if "highway" in tags
        and tags.get("area") != "yes"
        and tags["highway"]
        not in {
            "construction",
            "proposed",
            "abandoned",
            "razed",
            "platform",
            "rest_area",
            "services",
        }
    ]
    return records


def road_contrast(frame):
    """Pool same-city residential minus primary differences by their overlap in sightings."""
    road = frame.highway.replace("primary_link", "primary")
    counts = frame.loc[road.isin(["primary", "residential"])].pivot_table(
        index="city_id", columns=road, values=["women_count", "n"], aggfunc="sum", fill_value=0
    )
    n = counts["n"]
    paired = n.min(axis=1).gt(0)
    n = n.loc[paired]
    share = 100 * counts["women_count"].loc[paired] / n
    difference = share.residential - share.primary
    weight = n.primary * n.residential / n.sum(axis=1)
    contribution = weight * difference
    estimate = contribution.sum() / weight.sum()
    rng = np.random.default_rng(20261118)
    draws = rng.integers(len(n), size=(10000, len(n)))
    boot = contribution.to_numpy()[draws].sum(axis=1) / weight.to_numpy()[draws].sum(axis=1)
    lower, upper = np.percentile(boot, [2.5, 97.5])
    omit_one = (contribution.sum() - contribution) / (weight.sum() - weight)
    substantial = n.min(axis=1).ge(10)
    check = np.average(difference[substantial], weights=weight[substantial])
    n.assign(difference_pp=difference, weight=weight, omit_one_pp=omit_one).to_csv(
        OUT / "residential_primary_support.csv"
    )
    daytime = frame.date.notna() & frame.hour.between(6, 17)
    evening = frame.date.notna() & frame.hour.between(18, 21)
    valid = frame.date.notna() & frame.hour.between(0, 23)
    values = {
        "RoadPairedCities": len(n),
        "RoadPrimaryN": int(n.primary.sum()),
        "RoadResidentialN": int(n.residential.sum()),
        "RoadDifference": f"{estimate:.1f}",
        "RoadLower": f"{lower:.1f}",
        "RoadUpper": f"{upper:.1f}",
        "RoadCheckCities": int(substantial.sum()),
        "RoadCheckDifference": f"{check:.1f}",
        "DaytimePhotos": int(daytime.sum()),
        "EveningPhotos": int(evening.sum()),
        "OvernightPhotos": int((valid & ~daytime & ~evening).sum()),
        "NoTimePhotos": int((~valid).sum()),
    }
    Path("tabs/photo_context_macros.tex").write_text(
        "".join(
            (
                rf"\newcommand{{\{key}}}{{{value:,}}}" + "\n"
                if isinstance(value, int)
                else rf"\newcommand{{\{key}}}{{{value}}}" + "\n"
            )
            for key, value in values.items()
        )
    )
    print("Leave-one-city-out range (points)", omit_one.min(), omit_one.max())


def maps(frame):
    import geopandas as gpd
    from pyproj import Transformer
    from shapely.geometry import box

    benchmark = []
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 4.25))
    for ax, (city, stem, utm) in zip(axes, CITIES):
        photos = frame.loc[frame.city_ascii.eq(city)]
        projection = Transformer.from_crs(4326, utm, always_xy=True)
        x, y = projection.transform(photos.lon, photos.lat)
        if not np.isfinite([x, y]).all():
            raise ValueError(f"Missing photo location in {city}")
        cx, cy = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
        width = max(np.ptp(x), np.ptp(y)) + 150
        area = box(cx - width / 2, cy - width / 2, cx + width / 2, cy + width / 2)
        roads = gpd.GeoDataFrame(
            street_lines(stem, projection),
            columns=["highway", "geometry"],
            geometry="geometry",
            crs=utm,
        )
        roads = gpd.clip(roads, area, keep_geom_type=True)
        length = roads.geometry.length.groupby(road_classes(roads.highway)).sum() / 1000
        numbers = road_classes(photos.highway).value_counts()
        bench = pd.concat([length.rename("km"), numbers.rename("photos")], axis=1).fillna(0)
        bench["km_pct"] = 100 * bench.km / bench.km.sum()
        bench["photo_pct"] = 100 * bench.photos / len(photos)
        benchmark.append(bench.assign(city=city))
        roads.plot(ax=ax, color="#c9cdce", linewidth=0.48, zorder=0)
        ax.set(
            xlim=(cx - width / 2, cx + width / 2),
            ylim=(cy - width / 2, cy + width / 2),
            aspect="equal",
        )
        ax.scatter(x, y, s=9, c=ACCENT, alpha=0.75, linewidths=0)
        left, bottom = cx - width * 0.46, cy - width * 0.46
        ax.plot([left, left + 500], [bottom, bottom], color="black", linewidth=1.8)
        ax.text(
            left,
            bottom + 35,
            "500 m",
            size=8,
            bbox=dict(facecolor="white", edgecolor="none", pad=1),
        )
        ax.set_axis_off()
        ax.set_title(f"{city} ({len(photos)} photos)", loc="left", size=12)
    stats = pd.concat(benchmark).rename_axis("street_type").reset_index()
    stats.to_csv(OUT / "map_area_road_mix.csv", index=False)
    comparisons = stats.set_index(["city", "street_type"])
    macros = []
    for prefix, key in [
        ("DelhiResidential", ("New Delhi", "Residential")),
        ("LondonFootway", ("London", "Footway")),
    ]:
        row = comparisons.loc[key]
        for suffix, value in [("Photos", row.photo_pct), ("Length", row.km_pct)]:
            macros.append(rf"\newcommand{{\{prefix}{suffix}}}{{{value:.1f}}}")
    Path("tabs/network_share_macros.tex").write_text("\n".join(macros) + "\n")

    classes = [*dict.fromkeys(ROAD_LABELS.values()), "Other or mixed", "Unmatched"]
    columns = {("", "Street type"): [*classes, "Photographs", "Mapped kilometers"]}
    for city, _, _ in CITIES:
        area = (
            stats.loc[stats.city.eq(city)].set_index("street_type").reindex(classes, fill_value=0)
        )
        photo_pct = area.photo_pct.map("{:.1f}".format)
        km_pct = area.km_pct.map("{:.1f}".format)
        km_pct.loc["Unmatched"] = "—"
        columns[(city + " map area", "Photos (%)")] = [*photo_pct, f"{area.photos.sum():.0f}", ""]
        columns[(city + " map area", "Length (%)")] = [*km_pct, "", f"{area.km.sum():.1f}"]
    write_table(pd.DataFrame(columns), Path("tabs/tableB2_network.tex"), "lrrrr")
    fig.tight_layout(pad=0.3)
    fig.savefig("figs/figB1_photo_locations.pdf")
    plt.close(fig)


if __name__ == "__main__":
    data = assemble()
    regional_timing(data)
    road_table(data)
    road_contrast(data)
    time_figure(compare(data))
    maps(data)
