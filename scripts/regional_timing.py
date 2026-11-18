"""Compare regional pedestrian shares under the same weekday and local-hour mix."""

from pathlib import Path

import numpy as np
import pandas as pd
from paper_tables import region_label, write_table


def regional_timing(frame, draws=4000):
    d = frame.loc[frame.n.gt(0) & frame.date.notna() & frame.hour.between(6, 21)].copy()
    d["block"] = ((d.hour - 6) // 4).astype(int)
    full = frame.groupby("region")[["women_count", "n"]].sum()
    rows = []
    moments = []
    # Demeaning within city eliminates its intercept before estimating the common time effects.
    design = pd.get_dummies(d[["weekday", "block"]].astype(str), drop_first=True, dtype=float)
    target = np.average(design, axis=0, weights=d.n)
    for (region, city), g in d.groupby(["region", "city_id"]):
        x = design.loc[g.index].to_numpy()
        y = 100 * (g.women_count / g.n).to_numpy()
        n = g.n.to_numpy()
        mix = np.average(x, axis=0, weights=n)
        centered = x - mix
        weighted = centered.T * n
        moments.append((weighted @ centered, weighted @ (y - np.average(y, weights=n)), mix))
        rows.append((region, city, n.sum(), g.women_count.sum()))
    cities = pd.DataFrame(rows, columns=["region", "city_id", "n", "women"])
    gram, score, mixes = (np.stack(a) for a in zip(*moments))
    regions = list(full.index)
    groups = [cities.index[cities.region.eq(region)].to_numpy() for region in regions]

    def estimate(indices):
        beta = np.linalg.solve(gram[indices].sum(axis=0), score[indices].sum(axis=0))
        values = []
        for group in groups:
            sampled = indices[np.isin(indices, group)]
            n = sizes[sampled]
            raw = 100 * women[sampled].sum() / n.sum()
            values.append(raw + (target - np.average(mixes[sampled], axis=0, weights=n)) @ beta)
        return values

    sizes, women = cities.n.to_numpy(), cities.women.to_numpy()
    adjusted = estimate(cities.index.to_numpy())
    rng = np.random.default_rng(20261118)
    bootstrap = np.asarray(
        [estimate(np.concatenate([rng.choice(g, len(g)) for g in groups])) for _ in range(draws)]
    )
    low, high = np.percentile(bootstrap, [2.5, 97.5], axis=0)
    window = cities.groupby("region")[["women", "n"]].sum()
    out = pd.DataFrame(
        {
            "full_pct": 100 * full.women_count / full.n,
            "window_pct": 100 * window.women / window.n,
            "adjusted_pct": adjusted,
            "low95": low,
            "high95": high,
            "sightings": window.n,
            "cities": cities.groupby("region").size(),
        }
    ).sort_values("full_pct", ascending=False)
    out.to_csv("outputs/region_timing_adjustment.csv")
    d.groupby(["region", "weekday", "block"]).n.sum().to_csv("outputs/region_timing_support.csv")
    table = pd.DataFrame(
        {
            "Region": out.index.map(region_label),
            "Sightings": out.sightings.map("{:,.0f}".format),
            "All hours": out.full_pct.map("{:.1f}".format),
            "6 a.m.–10 p.m.": out.window_pct.map("{:.1f}".format),
            "Adjusted [95% interval]": [
                f"{r.adjusted_pct:.1f} [{r.low95:.1f}, {r.high95:.1f}]" for r in out.itertuples()
            ],
        }
    )
    write_table(table, Path("tabs/tableB1_timing.tex"), "lrrrr")
    out["shift"] = out.adjusted_pct - out.window_pct
    Path("tabs/timing_macros.tex").write_text(
        rf"\newcommand{{\MaxTimingShift}}{{{out['shift'].abs().max():.1f}}}" + "\n"
    )
