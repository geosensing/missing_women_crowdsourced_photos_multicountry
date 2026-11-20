"""Generate publication figures, LaTeX tables, and macros for the global research note.

Reads Round 1 counts, joins city metadata
from outputs/selected_cities.csv and image metadata from outputs/selected_images.csv,
computes cluster-robust ratio SEs (clustered by city/image), and writes:
  - tabs/results_macros.tex
  - tabs/table1_region_summary.tex
  - figs/fig1_region_summary.pdf
  - figs/fig2_city_distribution.pdf
  - figs/fig3_gdp_vs_female_share.pdf
  - figs/fig4_pedestrian_vs_twowheeler.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from figstyle import ACCENT, BAND_GRAY, BAR_GRAY, TEXT_GRAY, apply_style
from matplotlib.ticker import PercentFormatter
from paper_tables import region_label, write_table


def ratio_summary(df: pd.DataFrame, num_col: str, den_col: str, cluster_col: str) -> dict:
    """Ratio estimator sum(num)/sum(den) with cluster-robust linearized SE."""
    num = df[num_col].astype(float)
    den = df[den_col].astype(float)
    tot_den = float(den.sum())
    if tot_den <= 0:
        return {"share": np.nan, "se": np.nan, "lower": np.nan, "upper": np.nan}
    share = float(num.sum() / tot_den)
    scores = (num - share * den).groupby(df[cluster_col]).sum()
    n_c = len(scores)
    # At a boundary every cluster residual is zero, whatever the sample size.
    if n_c < 2 or share in (0.0, 1.0):
        return {"share": share, "se": np.nan, "lower": np.nan, "upper": np.nan}
    se = float(np.sqrt((n_c / (n_c - 1)) * np.sum(scores.to_numpy() ** 2)) / tot_den)
    return {
        "share": share,
        "se": se,
        "lower": max(0.0, share - 1.96 * se),
        "upper": min(1.0, share + 1.96 * se),
    }


def make_fig1_region(reg_df: pd.DataFrame, global_share: float, out_path: Path) -> None:
    df = reg_df.sort_values("ped_share", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    y = np.arange(len(df))
    ax.axvline(0.5, color=BAND_GRAY, linestyle="--", linewidth=1.0, zorder=1)
    ax.axvline(global_share, color=ACCENT, linestyle=":", linewidth=1.1, zorder=2)

    for idx, row in df.iterrows():
        ax.plot([row["ped_lo"], row["ped_hi"]], [idx, idx], color=BAR_GRAY, linewidth=1.4, zorder=3)
    ax.scatter(df["ped_share"], y, color="black", s=28, zorder=4)

    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['region']} ({int(r['n_cities'])} cities)" for _, r in df.iterrows()])
    ax.set_xlim(left=0)
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlabel("Women among classified pedestrians")
    ax.plot([], [], color=ACCENT, linestyle=":", label=f"All sampled cities ({global_share:.1%})")
    ax.plot([], [], color=BAND_GRAY, linestyle="--", label="Parity (50%)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
    fig.savefig(out_path)
    plt.close(fig)


def make_fig2_cities(city_df: pd.DataFrame, global_share: float, out_path: Path) -> None:
    """Healy/Wickham-style faceted Cleveland dot plot: all cities by region, no left spine."""
    df = city_df.dropna(subset=["ped_share"]).copy()
    reg_order = (
        df.groupby("region")["ped_share"].median().sort_values(ascending=False).index.tolist()
    )
    short_reg = {
        "Middle East, North Africa, Afghanistan & Pakistan": "MENA, Afg. & Pak.",
    }
    ncols = 2
    nrows = int(np.ceil(len(reg_order) / ncols))
    ratios = [
        max(
            int((df["region"] == reg_order[r * ncols]).sum()) if r * ncols < len(reg_order) else 0,
            (
                int((df["region"] == reg_order[r * ncols + 1]).sum())
                if r * ncols + 1 < len(reg_order)
                else 0
            ),
        )
        for r in range(nrows)
    ]

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(8.0, 8.8),
        sharex=True,
        squeeze=False,
        gridspec_kw={"height_ratios": ratios, "hspace": 0.24, "wspace": 0.55},
    )
    axes_flat = axes.flatten()

    for ax, region in zip(axes_flat, reg_order):
        sub = (
            df[df["region"] == region]
            .sort_values("ped_share", ascending=True)
            .reset_index(drop=True)
        )
        y = np.arange(len(sub))
        ax.axvline(0.5, color=BAND_GRAY, linestyle="--", linewidth=0.9, zorder=1)
        ax.axvline(global_share, color=ACCENT, linestyle=":", linewidth=1.0, zorder=2)

        for idx, row in sub.iterrows():
            ax.plot(
                [row["ped_lo"], row["ped_hi"]], [idx, idx], color="0.78", linewidth=0.6, zorder=2
            )
        has_interval = sub["ped_lo"].notna()
        ax.scatter(sub.loc[has_interval, "ped_share"], y[has_interval], color="0.12", s=9, zorder=3)
        ax.scatter(
            sub.loc[~has_interval, "ped_share"],
            y[~has_interval],
            facecolors="white",
            edgecolors="0.12",
            s=12,
            zorder=3,
        )

        ax.set_yticks(y)
        ax.set_yticklabels(
            [
                f"{r['city_ascii']} ({r['iso3']}, n={r['ped_classified']:,})"
                for _, r in sub.iterrows()
            ],
            fontsize=5.6,
            color=TEXT_GRAY,
        )
        ax.tick_params(axis="y", length=0, pad=3)
        ax.spines["left"].set_visible(False)
        ax.set_ylim(-0.7, len(sub) - 0.3)
        ax.set_xlim(-0.025, 1.025)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_title(
            short_reg.get(region, region), loc="left", fontsize=7.5, fontweight="bold", pad=3
        )

    n_regions = len(reg_order)
    for ax in axes_flat[n_regions:]:
        ax.set_visible(False)

    for ax in axes[-1, :]:
        ax.set_xlabel("Women among classified pedestrians", fontsize=7.5)
    fig.savefig(out_path)
    plt.close(fig)


def make_fig3_gdp(city_df: pd.DataFrame, out_path: Path) -> tuple[float, float]:
    """Return between-city and within-region slopes in share units per GDP doubling."""
    df = city_df.dropna(subset=["ped_share", "gdp_pcap_pp"]).copy()
    if (df["gdp_pcap_pp"] <= 0).any():
        raise ValueError("Log GDP requires positive GDP per capita")
    df["log_gdp"] = np.log2(df["gdp_pcap_pp"])

    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    ax.axhline(0.5, color=BAND_GRAY, linestyle="--", linewidth=1.0, zorder=1)
    ax.scatter(df["log_gdp"], df["ped_share"], color="0.25", alpha=0.75, s=18, zorder=3)

    w = df["ped_classified"]
    slope, intercept = np.polyfit(df["log_gdp"], df["ped_share"], 1, w=np.sqrt(w))
    xs = np.linspace(df["log_gdp"].min(), df["log_gdp"].max(), 100)
    ax.plot(xs, slope * xs + intercept, color=ACCENT, linewidth=1.4, zorder=4)
    region_weight = w.groupby(df["region"]).transform("sum")
    dx = df["log_gdp"] - (df["log_gdp"] * w).groupby(df["region"]).transform("sum") / region_weight
    dy = (
        df["ped_share"]
        - (df["ped_share"] * w).groupby(df["region"]).transform("sum") / region_weight
    )
    within_slope = (w * dx * dy).sum() / (w * dx**2).sum()

    ticks = [2000, 5000, 10000, 25000, 50000, 100000]
    ax.set_xticks([np.log2(t) for t in ticks])
    ax.set_xticklabels([f"${t//1000}k" for t in ticks])
    ax.set_ylim(-0.03, 1.03)
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlabel("National GDP per capita, PPP (log scale)")
    ax.set_ylabel("Women among classified pedestrians")
    fig.savefig(out_path)
    plt.close(fig)
    return slope, within_slope


def make_fig4_modes(reg_df: pd.DataFrame, out_path: Path) -> None:
    df = reg_df.sort_values("ped_share", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    y = np.arange(len(df))
    ax.axvline(0.5, color=BAND_GRAY, linestyle="--", linewidth=1.0, zorder=1)
    for idx, row in df.iterrows():
        if pd.notna(row["tw_share"]):
            ax.plot(
                [row["tw_share"], row["ped_share"]],
                [idx, idx],
                color="0.75",
                linewidth=1.0,
                zorder=2,
            )
    ax.scatter(df["ped_share"], y, color="black", s=28, label="Pedestrians", zorder=4)
    ax.scatter(
        df["tw_share"], y, color=ACCENT, marker="s", s=24, label="Two-wheeler riders", zorder=4
    )
    ax.set_yticks(y)
    ax.set_yticklabels(df["region"])
    ax.set_xlim(left=0)
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlabel("Women among classified sightings")
    ax.legend(frameon=False, loc="lower right", fontsize=7.5)
    fig.savefig(out_path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts-csv", type=Path, default=Path("outputs/muse_counts_all.csv"))
    parser.add_argument("--images-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument("--cities-csv", type=Path, default=Path("outputs/selected_cities.csv"))
    parser.add_argument(
        "--eligibility-csv", type=Path, default=Path("outputs/city_eligibility.csv")
    )
    parser.add_argument(
        "--downloads-csv",
        type=Path,
        nargs="+",
        default=[
            Path("outputs/download_manifest_round1.csv"),
            Path("outputs/download_manifest_round2.csv"),
            Path("outputs/download_manifest_round3.csv"),
        ],
    )
    parser.add_argument("--figs-dir", type=Path, default=Path("figs"))
    parser.add_argument("--tabs-dir", type=Path, default=Path("tabs"))
    args = parser.parse_args()

    apply_style()
    args.figs_dir.mkdir(parents=True, exist_ok=True)
    args.tabs_dir.mkdir(parents=True, exist_ok=True)

    counts = pd.read_csv(args.counts_csv)
    counts["uuid"] = counts["image"].str.replace(r"\.[^.]+$", "", regex=True)
    images = pd.read_csv(args.images_csv, usecols=["uuid", "city_id", "wave"])
    downloads = pd.concat(
        [pd.read_csv(p, usecols=["uuid", "status"]) for p in args.downloads_csv],
        ignore_index=True,
    )
    if downloads["uuid"].duplicated().any():
        raise ValueError("Download manifests contain duplicate UUIDs")
    drawn = images.loc[images["uuid"].isin(downloads["uuid"]), ["uuid", "city_id"]]
    if set(downloads["uuid"]) != set(drawn["uuid"]):
        raise ValueError("Download manifests do not match selected images")
    downloaded = downloads.loc[downloads["status"].isin(["cached", "ok"]), "uuid"]
    if not counts["uuid"].isin(downloaded).all():
        raise ValueError("A coded image has no successful download")

    cities = pd.read_csv(
        args.cities_csv,
        usecols=["city_id", "city_ascii", "iso3", "region", "stratum", "gdp_pcap_pp"],
    )
    eligibility = pd.read_csv(args.eligibility_csv, usecols=["city_id", "eligible"])
    if (
        eligibility["city_id"].duplicated().any()
        or not cities["city_id"]
        .isin(eligibility.loc[eligibility["eligible"] == 1, "city_id"])
        .all()
    ):
        raise ValueError("City selection is inconsistent with the eligibility file")
    df = counts.merge(drawn, on="uuid", how="left", validate="one_to_one").merge(
        cities, on="city_id", how="left", validate="many_to_one"
    )
    count_cols = ["women_count", "men_count", "women_twowheeler", "men_twowheeler", "unclear_count"]
    if df[[*count_cols, *cities.columns]].isna().any().any():
        raise ValueError("A coded image is missing counts or selected-city metadata")
    if ((df[count_cols] < 0) | (df[count_cols] % 1 != 0)).any().any():
        raise ValueError("Sightings must be nonnegative integer counts")
    df["ped_classified"] = df["women_count"] + df["men_count"]
    df["tw_classified"] = df["women_twowheeler"] + df["men_twowheeler"]
    df["all_women"] = df["women_count"] + df["women_twowheeler"]
    df["all_classified"] = df["ped_classified"] + df["tw_classified"]
    df["all_detected"] = df["all_classified"] + df["unclear_count"]

    # City-level summaries (clustered by image within city).
    city_rows = []
    for cid, grp in df.groupby("city_id"):
        ped = ratio_summary(grp, "women_count", "ped_classified", "uuid")
        tw = ratio_summary(grp, "women_twowheeler", "tw_classified", "uuid")
        city_rows.append(
            {
                "city_id": cid,
                "city_ascii": grp["city_ascii"].iloc[0],
                "iso3": grp["iso3"].iloc[0],
                "region": grp["region"].iloc[0],
                "gdp_pcap_pp": grp["gdp_pcap_pp"].iloc[0],
                "n_images": len(grp),
                "ped_classified": int(grp["ped_classified"].sum()),
                "ped_share": ped["share"],
                "ped_se": ped["se"],
                "ped_lo": ped["lower"],
                "ped_hi": ped["upper"],
                "tw_share": tw["share"],
            }
        )
    city_df = pd.DataFrame(city_rows)

    # Region-level summaries (clustered by city).
    reg_rows = []
    for region, grp in df.groupby("region"):
        ped = ratio_summary(grp, "women_count", "ped_classified", "city_id")
        allm = ratio_summary(grp, "all_women", "all_classified", "city_id")
        tw = ratio_summary(grp, "women_twowheeler", "tw_classified", "city_id")
        unclear_share = grp["unclear_count"].sum() / max(1, grp["all_detected"].sum())
        reg_rows.append(
            {
                "region": region,
                "n_cities": grp["city_id"].nunique(),
                "n_images": len(grp),
                "ped_classified": int(grp["ped_classified"].sum()),
                "ped_share": ped["share"],
                "ped_lo": ped["lower"],
                "ped_hi": ped["upper"],
                "all_share": allm["share"],
                "tw_share": tw["share"],
                "unclear_share": float(unclear_share),
            }
        )
    reg_df = pd.DataFrame(reg_rows).sort_values("ped_share", ascending=False)
    global_ped = ratio_summary(df, "women_count", "ped_classified", "city_id")
    global_all = ratio_summary(df, "all_women", "all_classified", "city_id")
    global_tw = ratio_summary(df, "women_twowheeler", "tw_classified", "city_id")

    make_fig1_region(reg_df, global_ped["share"], args.figs_dir / "fig1_region_summary.pdf")
    make_fig2_cities(city_df, global_ped["share"], args.figs_dir / "fig2_city_distribution.pdf")
    slope, within_slope = make_fig3_gdp(city_df, args.figs_dir / "fig3_gdp_vs_female_share.pdf")
    make_fig4_modes(reg_df, args.figs_dir / "fig4_pedestrian_vs_twowheeler.pdf")

    # Write LaTeX macros.
    unclear_share = df["unclear_count"].sum() / df["all_detected"].sum()
    highest_city = city_df.loc[city_df["ped_share"].idxmax()]
    # New Delhi entered the draw by design for comparison with the Delhi field studies.
    delhi = city_df.set_index("city_id").loc[1356215164]
    delhi_women = df.loc[df["city_id"].eq(1356215164), "women_count"].sum()
    india_df = df[df["iso3"] == "IND"]
    india_ped = ratio_summary(india_df, "women_count", "ped_classified", "city_id")
    regional_shares = reg_df.set_index("region")["ped_share"]
    mena = regional_shares["Middle East, North Africa, Afghanistan & Pakistan"]
    eca = regional_shares["Europe & Central Asia"]
    sa_row = reg_df.loc[reg_df["region"] == "South Asia"].iloc[0]
    macros = [
        f"\\newcommand{{\\DelhiWomen}}{{{delhi_women:,}}}",
        f"\\newcommand{{\\DelhiPedestrians}}{{{delhi['ped_classified']:,}}}",
        f"\\newcommand{{\\DelhiShare}}{{{100 * delhi['ped_share']:.1f}}}",
        f"\\newcommand{{\\DelhiSE}}{{{100 * delhi['ped_se']:.1f}}}",
        f"\\newcommand{{\\DelhiLo}}{{{100 * delhi['ped_lo']:.1f}}}",
        f"\\newcommand{{\\DelhiHi}}{{{100 * delhi['ped_hi']:.1f}}}",
        f"\\newcommand{{\\MaxCityPedCount}}{{{highest_city['ped_classified']:,}}}",
        f"\\newcommand{{\\IncomeSlope}}{{\\ensuremath{{{100 * slope:+.1f}}}}}",
        f"\\newcommand{{\\WithinRegionIncomeSlope}}{{\\ensuremath{{{100 * within_slope:+.1f}}}}}",
        f"\\newcommand{{\\TotalRegions}}{{{len(reg_df):,}}}",
        f"\\newcommand{{\\DrawnImages}}{{{len(drawn):,}}}",
        f"\\newcommand{{\\DownloadedImages}}{{{len(downloaded):,}}}",
        f"\\newcommand{{\\EligibleCities}}{{{eligibility['eligible'].eq(1).sum():,}}}",
        f"\\newcommand{{\\CorpusCities}}{{{len(eligibility):,}}}",
        f"\\newcommand{{\\TotalStrata}}{{{cities['stratum'].nunique():,}}}",
        f"\\newcommand{{\\WomenPedestrians}}{{{df['women_count'].sum():,}}}",
        f"\\newcommand{{\\UnclearShare}}{{{100 * unclear_share:.1f}}}",
        f"\\newcommand{{\\MENAPedShare}}{{{100 * mena:.1f}}}",
        f"\\newcommand{{\\ECAPedShare}}{{{100 * eca:.1f}}}",
        f"\\newcommand{{\\TotalCities}}{{{df['city_id'].nunique():,}}}",
        f"\\newcommand{{\\TotalCountries}}{{{df['iso3'].nunique():,}}}",
        f"\\newcommand{{\\TotalImages}}{{{len(df):,}}}",
        f"\\newcommand{{\\TotalPedestrians}}{{{int(df['ped_classified'].sum()):,}}}",
        f"\\newcommand{{\\TotalRiders}}{{{int(df['tw_classified'].sum()):,}}}",
        f"\\newcommand{{\\TotalUnclear}}{{{int(df['unclear_count'].sum()):,}}}",
        f"\\newcommand{{\\GlobalPedShare}}{{{global_ped['share']*100:.1f}}}",
        f"\\newcommand{{\\GlobalPedCILo}}{{{global_ped['lower']*100:.1f}}}",
        f"\\newcommand{{\\GlobalPedCIHi}}{{{global_ped['upper']*100:.1f}}}",
        f"\\newcommand{{\\GlobalAllShare}}{{{global_all['share']*100:.1f}}}",
        f"\\newcommand{{\\GlobalTWShare}}{{{global_tw['share']*100:.1f}}}",
        f"\\newcommand{{\\MinCityPedShare}}{{{city_df['ped_share'].min()*100:.1f}}}",
        f"\\newcommand{{\\MaxCityPedShare}}{{{city_df['ped_share'].max()*100:.1f}}}",
        f"\\newcommand{{\\IndiaCities}}{{{india_df['city_id'].nunique():,}}}",
        f"\\newcommand{{\\IndiaImages}}{{{len(india_df):,}}}",
        f"\\newcommand{{\\IndiaPedShare}}{{{india_ped['share']*100:.1f}}}",
        f"\\newcommand{{\\IndiaPedCILo}}{{{india_ped['lower']*100:.1f}}}",
        f"\\newcommand{{\\IndiaPedCIHi}}{{{india_ped['upper']*100:.1f}}}",
        f"\\newcommand{{\\SouthAsiaPedShare}}{{{sa_row['ped_share']*100:.1f}}}",
        f"\\newcommand{{\\SouthAsiaPedCILo}}{{{sa_row['ped_lo']*100:.1f}}}",
        f"\\newcommand{{\\SouthAsiaPedCIHi}}{{{sa_row['ped_hi']*100:.1f}}}",
    ]
    (args.tabs_dir / "results_macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    summary = pd.concat(
        [
            reg_df,
            pd.DataFrame(
                [
                    {
                        "region": "All sampled cities",
                        "n_cities": df.city_id.nunique(),
                        "n_images": len(df),
                        "ped_classified": df.ped_classified.sum(),
                        "ped_share": global_ped["share"],
                        "ped_lo": global_ped["lower"],
                        "ped_hi": global_ped["upper"],
                        "tw_share": global_tw["share"],
                        "unclear_share": unclear_share,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    table = pd.DataFrame(
        {
            "Region": summary.region.map(region_label),
            "Cities": summary.n_cities,
            "Images": summary.n_images.map("{:,}".format),
            "Pedestrians": summary.ped_classified.map("{:,.0f}".format),
            "Women [95% CI]": [
                f"{r.ped_share:.1%} [{100*r.ped_lo:.1f}, {100*r.ped_hi:.1f}]"
                for r in summary.itertuples()
            ],
            "Women riders": summary.tw_share.map(
                lambda share: f"{share:.1%}" if pd.notna(share) else "—"
            ),
            "Unclear": summary.unclear_share.map("{:.1%}".format),
        }
    )
    write_table(table, args.tabs_dir / "table1_region_summary.tex", "lrrrrrr")
    print(f"Wrote figures to {args.figs_dir}/ and tables to {args.tabs_dir}/")


if __name__ == "__main__":
    main()
