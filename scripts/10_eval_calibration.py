"""Compare human and Muse counts on paired images and rebuild Table 2.

The default build reads the frozen human CSV. Use --refresh-human to replace it
with the latest non-cancelled annotations from the specified Label Studio project.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
from paper_tables import write_table

DEFAULT_DB = Path.home() / "Library/Application Support/label-studio/label_studio.sqlite3"
LABELS = {
    "Woman pedestrian": "women_count",
    "Man pedestrian": "men_count",
    "Woman two-wheeler": "women_twowheeler",
    "Man two-wheeler": "men_twowheeler",
    "Unclear person": "unclear_count",
}
COUNTS = list(LABELS.values())
SPARSE_REGIONS = {
    "Middle East, North Africa, Afghanistan & Pakistan",
    "South Asia",
    "Sub-Saharan Africa",
}


def read_annotations(db_path: Path, project_title: str) -> pd.DataFrame:
    """Read the latest non-cancelled annotation for each task UUID."""
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        projects = con.execute("SELECT id FROM project WHERE title=?", (project_title,)).fetchall()
        if len(projects) != 1:
            raise ValueError(f"Expected one project named {project_title!r}, found {len(projects)}")
        rows = con.execute(
            """
            SELECT t.data, tc.result
            FROM task_completion tc
            JOIN task t ON t.id = tc.task_id
            WHERE tc.project_id = ? AND tc.was_cancelled = 0
            ORDER BY tc.id ASC
            """,
            projects[0],
        ).fetchall()
    if not rows:
        raise ValueError(f"No completed annotations in {project_title!r}")

    latest = {}
    for data_json, result_json in rows:
        uuid = json.loads(data_json)["uuid"]
        counts: Counter[str] = Counter()
        bad = False
        for item in json.loads(result_json):
            values = item["value"]
            for label in values.get("keypointlabels", []):
                counts[LABELS[label]] += 1
            bad |= "Bad / unusable image" in values.get("choices", [])
        latest[uuid] = {
            "uuid": uuid,
            **{f"human_{key}": counts[key] for key in COUNTS},
            "bad_image": int(bad),
        }
    return pd.DataFrame(latest.values()).sort_values("uuid")


def check_counts(frame: pd.DataFrame, key: str, prefix: str) -> None:
    if frame[key].isna().any() or frame[key].duplicated().any():
        raise ValueError(f"Missing or duplicate {key} in {prefix or 'Round 1'} counts")
    values = frame[[prefix + column for column in COUNTS]]
    if values.isna().any().any() or (values < 0).any().any() or (values % 1 != 0).any().any():
        raise ValueError(f"Expected complete nonnegative integer counts for {prefix or 'Round 1'}")


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else math.nan


def scenario_share(women: int, men: int, women_ratio: float, men_ratio: float) -> float:
    """Female share if the validation count ratios apply to every Round 1 image."""
    if not (women_ratio > 0 and men_ratio > 0 and women + men > 0):
        return math.nan
    return 100 * (women / women_ratio) / (women / women_ratio + men / men_ratio)


def fmt(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}" if math.isfinite(value) else "---"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-human", action="store_true")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--project", default="missing_women_300")
    parser.add_argument("--human-csv", type=Path, default=Path("outputs/human_validation_ls.csv"))
    parser.add_argument("--sample-csv", type=Path, default=Path("outputs/label_studio_sample.csv"))
    parser.add_argument("--round1-csv", type=Path, default=Path("outputs/muse_counts_all.csv"))
    parser.add_argument("--tabs-dir", type=Path, default=Path("tabs"))
    args = parser.parse_args()

    human = (
        read_annotations(args.db, args.project)
        if args.refresh_human
        else pd.read_csv(args.human_csv)
    )
    sample = pd.read_csv(args.sample_csv)
    round_one = pd.read_csv(args.round1_csv)
    round_one["uuid"] = round_one["image"].map(lambda image: Path(image).stem)
    check_counts(human, "uuid", "human_")
    check_counts(sample, "uuid", "muse_")
    check_counts(round_one, "uuid", "")
    if not human["bad_image"].isin([0, 1]).all():
        raise ValueError("Expected a zero or one bad_image flag for every annotation")
    if not human["uuid"].isin(sample["uuid"]).all():
        raise ValueError("Annotated UUID absent from the validation manifest")
    original = round_one.set_index("uuid")[COUNTS].reindex(sample["uuid"])
    stored = sample.set_index("uuid")[["muse_" + k for k in COUNTS]]
    if not (original.to_numpy() == stored.to_numpy()).all():
        raise ValueError("Validation manifest has missing or mismatched Round 1 model counts")
    if sample["region"].isna().any():
        raise ValueError("Validation manifest contains missing regions")
    paired = human.merge(sample, on="uuid", validate="one_to_one")
    valid = paired.loc[paired["bad_image"].eq(0)]
    if valid.empty:
        raise ValueError("No usable paired images")

    modes = {
        "Pedestrians": ("women_count", "men_count"),
        "Two-wheeler riders": ("women_twowheeler", "men_twowheeler"),
    }
    table_rows = []
    macros = {
        "CalSelectedImages": f"{len(sample):,}",
        "CalRatedImages": f"{len(human):,}",
        "CalImages": f"{len(valid):,}",
        "CalBadImages": f"{int(paired.bad_image.sum()):,}",
        "CalSparseRegionImages": f"{valid.region.isin(SPARSE_REGIONS).sum():,}",
        "CalHumanUnclear": f"{valid.human_unclear_count.sum():,.0f}",
        "CalMuseUnclear": f"{valid.muse_unclear_count.sum():,.0f}",
    }
    totals = {}
    for mode, (women, men) in modes.items():
        totals[mode] = [
            int(valid[prefix + col].sum()) for prefix in ("human_", "muse_") for col in (women, men)
        ]
    totals["Both modes"] = [sum(counts) for counts in zip(*totals.values())]

    for mode, (hw, hm, mw, mm) in totals.items():
        rw, rm = ratio(mw, hw), ratio(mm, hm)
        table_rows.extend(
            [
                (mode, "Women", f"{hw:,}", f"{mw:,}", fmt(rw)),
                ("", "Men", f"{hm:,}", f"{mm:,}", fmt(rm)),
            ]
        )
        if mode in ("Both modes", "Pedestrians"):
            all_modes = mode == "Both modes"
            label = "All" if all_modes else "Ped"
            macros[f"Cal{label}RatioW"] = fmt(rw)
            macros[f"Cal{label}RatioM"] = fmt(rm)
            women = round_one["women_count"].sum()
            men = round_one["men_count"].sum()
            if all_modes:
                macros["CalAllHumanShare"] = fmt(100 * ratio(hw, hw + hm), 1)
                macros["CalAllMuseShare"] = fmt(100 * ratio(mw, mw + mm), 1)
                women += round_one["women_twowheeler"].sum()
                men += round_one["men_twowheeler"].sum()
            macros[f"Global{label}CorrShare"] = fmt(scenario_share(women, men, rw, rm), 1)
    h, m = (valid[[p + k for k in COUNTS[:-1]]].sum(axis=1) for p in ("human_", "muse_"))
    macros["CalCorrAll"] = fmt(h.corr(m) if h.nunique() > 1 and m.nunique() > 1 else math.nan)
    unclear_ratio = fmt(ratio(valid.muse_unclear_count.sum(), valid.human_unclear_count.sum()))
    table_rows.append(
        (
            "Both modes",
            "Unclear",
            macros["CalHumanUnclear"],
            macros["CalMuseUnclear"],
            unclear_ratio,
        )
    )
    table = pd.DataFrame(
        table_rows, columns=["Travel mode", "Classification", "Human", "Muse", "Muse/human"]
    )
    args.tabs_dir.mkdir(parents=True, exist_ok=True)
    macro_text = "\n".join(rf"\newcommand{{\{key}}}{{{value}}}" for key, value in macros.items())
    (args.tabs_dir / "calibration_macros.tex").write_text(macro_text + "\n", encoding="utf-8")
    write_table(table, args.tabs_dir / "table2_calibration.tex", "llrrr")
    if args.refresh_human:
        args.human_csv.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", dir=args.human_csv.parent, delete=False) as temp:
            human.to_csv(temp, index=False)
        Path(temp.name).replace(args.human_csv)
    print(f"Wrote validation table for {len(valid)} of {len(sample)} selected images")


if __name__ == "__main__":
    main()
