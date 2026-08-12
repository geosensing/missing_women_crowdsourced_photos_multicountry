"""Rebuild the GPT-4o-versus-human benchmark that motivates the research design.

Reads the frozen validation export from the sibling streetscope repository and
reports detection recall by sex and the resulting bias in the female share.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_INPUT = Path("../streetscope/data/mumbai/validation_results.csv")
DEFAULT_OUTPUT = Path("outputs/gpt4o_benchmark.csv")

AI_FIELDS = [
    "ai_men_count",
    "ai_women_count",
    "ai_men_twowheeler",
    "ai_women_twowheeler",
]


def load(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [column for column in AI_FIELDS if column not in frame.columns]
    if missing:
        raise ValueError(f"Export is missing expected columns: {missing}")
    return frame


def benchmark(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare human and model counts, dropping rows whose response never parsed.

    Unparsed responses are excluded rather than zero-filled: treating a parse
    failure as an observed count of zero would attribute a pipeline defect to
    the model and overstate the undercount.
    """
    unparsed = frame[AI_FIELDS].isna().any(axis=1)
    parsed = frame.loc[~unparsed].copy()
    parsed["human_pedestrians"] = parsed["men_count"] + parsed["women_count"]
    parsed["model_pedestrians"] = parsed["ai_men_count"] + parsed["ai_women_count"]

    rows = [
        {
            "group": "women pedestrians",
            "human": parsed["women_count"].sum(),
            "model": parsed["ai_women_count"].sum(),
        },
        {
            "group": "men pedestrians",
            "human": parsed["men_count"].sum(),
            "model": parsed["ai_men_count"].sum(),
        },
        {
            "group": "all pedestrians",
            "human": parsed["human_pedestrians"].sum(),
            "model": parsed["model_pedestrians"].sum(),
        },
    ]
    result = pd.DataFrame(rows)
    result["recall"] = result["model"] / result["human"]

    human_share = parsed["women_count"].sum() / parsed["human_pedestrians"].sum()
    model_share = parsed["ai_women_count"].sum() / parsed["model_pedestrians"].sum()
    result.attrs["n_rows_total"] = len(frame)
    result.attrs["n_rows_parsed"] = len(parsed)
    result.attrs["human_female_share"] = human_share
    result.attrs["model_female_share"] = model_share
    correlation = parsed["human_pedestrians"].corr(parsed["model_pedestrians"])
    result.attrs["image_correlation"] = correlation
    return result


def report(result: pd.DataFrame) -> str:
    lines = [
        f"images: {result.attrs['n_rows_parsed']} parsed "
        f"of {result.attrs['n_rows_total']} sampled",
        "",
        f"{'group':<20}{'human':>8}{'model':>8}{'recall':>9}",
    ]
    for _, row in result.iterrows():
        lines.append(
            f"{row['group']:<20}{row['human']:>8.0f}" f"{row['model']:>8.0f}{row['recall']:>9.2f}"
        )
    lines += [
        "",
        f"female share, human coders : {result.attrs['human_female_share']:.3f}",
        f"female share, GPT-4o       : {result.attrs['model_female_share']:.3f}",
        f"per-image count correlation: {result.attrs['image_correlation']:.3f}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = benchmark(load(args.input))
    print(report(result))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"\nwrote {args.output}")


if __name__ == "__main__":
    main()
