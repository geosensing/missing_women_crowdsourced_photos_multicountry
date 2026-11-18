"""Booktabs tables for the manuscript. Captions and explanatory notes live in note.tex."""

from pathlib import Path

import pandas as pd


def write_table(frame: pd.DataFrame, path: Path, alignment: str, *, escape: bool = True) -> None:
    frame.to_latex(
        path,
        index=False,
        escape=escape,
        column_format=f"@{{}}{alignment}@{{}}",
        multicolumn_format="c",
        na_rep="—",
    )


def region_label(region: str) -> str:
    if region == "Middle East, North Africa, Afghanistan & Pakistan":
        return "MENA, Afg. & Pak."
    return region
