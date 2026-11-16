"""Generate publication figures, LaTeX tables, and macros for the global research note.

Reads outputs/muse_counts_round1.csv (or any --counts-csv), joins city metadata
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


def ratio_summary(df: pd.DataFrame, num_col: str, den_col: str, cluster_col: str) -> dict:
    """Ratio estimator sum(num)/sum(den) with cluster-robust linearized SE."""
    valid = df.dropna(subset=[num_col, den_col, cluster_col]).copy()
    num = valid[num_col].astype(float)
    den = valid[den_col].astype(float)
    tot_den = float(den.sum())
    if tot_den <= 0:
        return {"share": np.nan, "se": np.nan, "lower": np.nan, "upper": np.nan}
    share = float(num.sum() / tot_den)
    scores = (num - share * den).groupby(valid[cluster_col]).sum()
    n_c = len(scores)
    if n_c < 2:
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
    ax.set_yticklabels([f"{r['region']} (n={int(r['n_cities'])})" for _, r in df.iterrows()])
    ax.set_xlim(0, 0.58)
    ax.set_xlabel("Pedestrian female share (women / [women + men])")
    ax.text(global_share + 0.008, len(df) - 0.6, f"Global mean: {global_share*100:.1f}%", color=ACCENT, fontsize=7.5)
    ax.text(0.505, 0.15, "50% parity", color=TEXT_GRAY, fontsize=7.5)
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
    max_rows = max(int((df["region"] == r).sum()) for r in reg_order)
    ratios = [
        max(
            int((df["region"] == reg_order[r * ncols]).sum())
            if r * ncols < len(reg_order)
            else 0,
            int((df["region"] == reg_order[r * ncols + 1]).sum())
            if r * ncols + 1 < len(reg_order)
            else 0,
        )
        for r in range(nrows)
    ]

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(7.0, 8.8),
        sharex=True,
        gridspec_kw={"height_ratios": ratios, "hspace": 0.24, "wspace": 0.55},
    )
    axes_flat = axes.flatten()

    for ax, region in zip(axes_flat, reg_order):
        sub = df[df["region"] == region].sort_values("ped_share", ascending=True).reset_index(drop=True)
        y = np.arange(len(sub))
        ax.axvline(0.5, color=BAND_GRAY, linestyle="--", linewidth=0.9, zorder=1)
        ax.axvline(global_share, color=ACCENT, linestyle=":", linewidth=1.0, zorder=2)

        for idx, row in sub.iterrows():
            ax.plot([row["ped_lo"], row["ped_hi"]], [idx, idx], color="0.78", linewidth=0.6, zorder=2)
        ax.scatter(sub["ped_share"], y, color="0.12", s=9, zorder=3)

        ax.set_yticks(y)
        ax.set_yticklabels(
            [f"{r['city_ascii']} ({r['iso3']})" for _, r in sub.iterrows()],
            fontsize=5.6,
            color=TEXT_GRAY,
        )
        ax.tick_params(axis="y", length=0, pad=3)
        ax.spines["left"].set_visible(False)
        ax.set_ylim(-0.7, len(sub) - 0.3)
        ax.set_xlim(0, 1.0)
        ax.set_title(short_reg.get(region, region), loc="left", fontsize=7.5, fontweight="bold", pad=3)

    for ax in axes_flat[len(reg_order) :]:
        ax.set_visible(False)

    for ax in axes[-1, :]:
        ax.set_xlabel("Pedestrian female share (95% CI)", fontsize=7.5)
    fig.savefig(out_path)
    plt.close(fig)


def make_fig3_gdp(city_df: pd.DataFrame, out_path: Path) -> None:
    df = city_df.dropna(subset=["ped_share", "gdp_pcap_pp"]).copy()
    df = df[df["gdp_pcap_pp"] > 0]
    df["log_gdp"] = np.log10(df["gdp_pcap_pp"])

    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    ax.axhline(0.5, color=BAND_GRAY, linestyle="--", linewidth=1.0, zorder=1)
    ax.scatter(df["log_gdp"], df["ped_share"], color="0.25", alpha=0.75, s=18, zorder=3)

    if len(df) >= 5:
        w = np.maximum(1.0, df["ped_classified"].to_numpy(dtype=float))
        slope, intercept = np.polyfit(df["log_gdp"], df["ped_share"], 1, w=np.sqrt(w))
        xs = np.linspace(df["log_gdp"].min(), df["log_gdp"].max(), 100)
        ax.plot(xs, slope * xs + intercept, color=ACCENT, linewidth=1.4, zorder=4)

    ticks = [2000, 5000, 10000, 25000, 50000, 100000]
    ax.set_xticks([np.log10(t) for t in ticks])
    ax.set_xticklabels([f"${t//1000}k" for t in ticks])
    ax.set_ylim(0, 0.58)
    ax.set_xlabel("National GDP per capita, PPP (log scale)")
    ax.set_ylabel("Pedestrian female share")
    fig.savefig(out_path)
    plt.close(fig)


def make_fig4_modes(reg_df: pd.DataFrame, out_path: Path) -> None:
    df = reg_df.sort_values("ped_share", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    y = np.arange(len(df))
    ax.axvline(0.5, color=BAND_GRAY, linestyle="--", linewidth=1.0, zorder=1)
    for idx, row in df.iterrows():
        if pd.notna(row["tw_share"]):
            ax.plot([row["tw_share"], row["ped_share"]], [idx, idx], color="0.75", linewidth=1.0, zorder=2)
    ax.scatter(df["ped_share"], y, color="black", s=28, label="Pedestrians", zorder=4)
    ax.scatter(df["tw_share"], y, color=ACCENT, marker="s", s=24, label="Two-wheeler riders", zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(df["region"])
    ax.set_xlim(0, 0.58)
    ax.set_xlabel("Female share")
    ax.legend(frameon=False, loc="lower right", fontsize=7.5)
    fig.savefig(out_path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts-csv", type=Path, default=Path("outputs/muse_counts_round1.csv"))
    parser.add_argument("--images-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument("--cities-csv", type=Path, default=Path("outputs/selected_cities.csv"))
    parser.add_argument("--figs-dir", type=Path, default=Path("figs"))
    parser.add_argument("--tabs-dir", type=Path, default=Path("tabs"))
    args = parser.parse_args()

    apply_style()
    args.figs_dir.mkdir(parents=True, exist_ok=True)
    args.tabs_dir.mkdir(parents=True, exist_ok=True)

    counts = pd.read_csv(args.counts_csv)
    counts["uuid"] = counts["image"].str.replace(r"\.[^.]+$", "", regex=True)
    imgs = pd.read_csv(args.images_csv)[["uuid", "city_id", "city_ascii", "iso3", "region", "source"]]
    cities = pd.read_csv(args.cities_csv)[["city_id", "gdp_pcap_pp", "population", "design_weight"]]

    df = counts.merge(imgs, on="uuid", how="inner").merge(cities, on="city_id", how="left")
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
                "population": grp["population"].iloc[0],
                "design_weight": grp["design_weight"].iloc[0],
                "n_images": len(grp),
                "ped_classified": int(grp["ped_classified"].sum()),
                "ped_share": ped["share"],
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
    make_fig3_gdp(city_df, args.figs_dir / "fig3_gdp_vs_female_share.pdf")
    make_fig4_modes(reg_df, args.figs_dir / "fig4_pedestrian_vs_twowheeler.pdf")

    # Write LaTeX macros.
    macros = [
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
    ]
    (args.tabs_dir / "results_macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    # Write Table 1.
    lines = [
        "\\begin{table}[ht]",
        "\\centering",
        "\\caption{Pedestrian and two-wheeler female share by World Bank-derived region (Round 1).}",
        "\\label{tab:region_summary}",
        "\\begin{threeparttable}",
        "\\footnotesize",
        "\\begin{tabular}{@{}lrrrrrr@{}}",
        "\\toprule",
        "Region & Cities & Images & Pedestrians & Ped. Female Share [95\\% CI] & 2-Wh. Share & Unclear \\\\",
        "\\midrule",
    ]
    for _, r in reg_df.iterrows():
        reg_tex = str(r["region"]).replace("&", "\\&").replace(
            "Middle East, North Africa, Afghanistan \\& Pakistan", "MENA, Afg. \\& Pak."
        )
        tw_str = f"{r['tw_share']*100:.1f}\\%" if pd.notna(r["tw_share"]) else "--"
        lines.append(
            f"{reg_tex} & {int(r['n_cities'])} & {int(r['n_images']):,} & "
            f"{int(r['ped_classified']):,} & "
            f"{r['ped_share']*100:.1f}\\% [{r['ped_lo']*100:.1f}, {r['ped_hi']*100:.1f}] & "
            f"{tw_str} & {r['unclear_share']*100:.1f}\\% \\\\"
        )
    lines += [
        "\\midrule",
        f"Global (all regions) & {df['city_id'].nunique()} & {len(df):,} & "
        f"{int(df['ped_classified'].sum()):,} & "
        f"{global_ped['share']*100:.1f}\\% [{global_ped['lower']*100:.1f}, {global_ped['upper']*100:.1f}] & "
        f"{global_tw['share']*100:.1f}\\% & "
        f"{df['unclear_count'].sum() / max(1, df['all_detected'].sum()) * 100:.1f}\\% \\\\",
        "\\bottomrule",
        "\\end{tabular}",
        "\\begin{tablenotes}[flushleft]\\footnotesize",
        "\\item \\textit{Notes:} City-clustered 95\\% confidence intervals around ratio estimates. "
        "Pedestrian female share is $\\sum \\text{women} / \\sum (\\text{women} + \\text{men})$. "
        "Unclear share is unclear detections over all detected pedestrians and riders.",
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
    ]
    (args.tabs_dir / "table1_region_summary.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote figures to {args.figs_dir}/ and tables to {args.tabs_dir}/")


if __name__ == "__main__":
    main()
