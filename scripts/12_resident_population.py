"""Pair city population records with pedestrian sightings near the reference year."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WINDOW = 2


def main():
    photos = pd.read_csv(ROOT / "outputs/coded_photo_place_metadata.csv")
    cities = pd.read_csv(ROOT / "outputs/selected_cities.csv")[["city_id", "city_ascii", "iso3"]]
    records = pd.read_csv(ROOT / "docs/city_population_records.csv")
    if photos.uuid.duplicated().any() or cities.city_id.duplicated().any():
        raise ValueError("Duplicate photo or city identifier")
    if not (photos.women_count + photos.men_count).eq(photos.n).all():
        raise ValueError("Classified pedestrian counts disagree")
    median = photos.groupby("city_id").year.median().rename("median_photo_year")
    records = records.join(median, on="city_id")
    records["distance"] = (records.Year - records.median_photo_year).abs()
    records = records.loc[records.distance <= WINDOW].sort_values(
        ["distance", "Record Type", "Year", "Source Year"], ascending=[True, True, True, False]
    )
    selected = records.drop_duplicates("city_id")
    if not selected[["Female", "Male", "Total"]].gt(0).all().all():
        raise ValueError("Missing or nonpositive population")
    # Published totals can differ slightly because of confidentiality rounding.
    if (selected.Female + selected.Male - selected.Total).abs().gt(5).any():
        raise ValueError("Population counts disagree with the separately reported total")
    selected = selected.assign(resident_pct=100 * selected.Female / selected.Total)
    matched = photos.merge(selected[["city_id", "Year"]], on="city_id", validate="many_to_one")
    window = matched.loc[(matched.year - matched.Year).abs() <= WINDOW]
    counts = window.groupby("city_id").agg(
        photo_start=("year", "min"),
        photo_end=("year", "max"),
        photos=("uuid", "size"),
        sightings=("n", "sum"),
        women=("women_count", "sum"),
    )
    result = cities.merge(selected, how="left", on=["city_id", "city_ascii"], validate="one_to_one")
    result = result.join(counts, on="city_id").sort_values("city_ascii")
    result["photo_pct"] = 100 * result.women / result.sightings.where(result.sightings > 0)
    result["gap_pp"] = result.photo_pct - result.resident_pct
    result.to_csv(ROOT / "outputs/city_resident_comparison.csv", index=False)
    table = result.dropna(subset=["Year"]).copy()
    table["Photo years"] = [
        str(int(a)) if a == b else f"{int(a)}–{int(b)}"
        for a, b in zip(table.photo_start, table.photo_end)
    ]
    table["City"] = table.city_ascii.replace({"Dubai": "Dubai (emirate)"})
    for label, col in [("Pop. year", "Year"), ("Sightings", "sightings")]:
        table[label] = table[col].astype(int)
    for label, col in [("Population", "resident_pct"), ("Photographs", "photo_pct")]:
        table[label] = table[col].map(lambda n: f"{n:.1f}" if pd.notna(n) else "—")
    table[["City", "Pop. year", "Photo years", "Sightings", "Population", "Photographs"]].to_latex(
        ROOT / "tabs/tableD1_residents.tex",
        index=False,
        escape=True,
        longtable=True,
        column_format="@{}lrrrrr@{}",
        caption=(
            "Female share of the population and share of classified pedestrians "
            "coded as women (percent)."
        ),
        label="tab:residents",
    )


if __name__ == "__main__":
    main()
