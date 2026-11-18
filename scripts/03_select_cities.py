"""Select cities from Global Streetscapes and estimate their inclusion probabilities."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_CONFIG = Path("config/sampling.json")
DEFAULT_CITIES = Path("data/raw/cities688.csv")
DEFAULT_WB_GDP = Path("data/raw/wb_gdp_pcap_pp.json")
DEFAULT_WB_POP = Path("data/raw/wb_pop_totl.json")
DEFAULT_WB_COUNTRIES = Path("data/raw/wb_countries.json")
DEFAULT_ELIGIBILITY_OUT = Path("outputs/city_eligibility.csv")
DEFAULT_SELECTED_OUT = Path("outputs/selected_cities.csv")
DEFAULT_MANIFEST_OUT = Path("outputs/sampling_manifest.json")


def file_digest(path: Path) -> dict[str, int | str]:
    """Return byte size and SHA-256 hex digest for a file."""
    data = path.read_bytes()
    return {
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def load_wb_indicator(path: Path) -> dict[str, tuple[float, str]]:
    """Load World Bank v2 indicator JSON keyed by ISO3 code -> (value, year)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload[1]
    out: dict[str, tuple[float, str]] = {}
    for item in records:
        iso3 = item.get("countryiso3code")
        val = item.get("value")
        year = str(item.get("date", ""))
        if iso3 and val is not None:
            out[iso3] = (float(val), year)
    return out


def load_wb_regions(path: Path, merge_americas: bool = False) -> dict[str, str]:
    """Load official World Bank region names keyed by ISO3 code."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    regions: dict[str, str] = {}
    for item in payload[1]:
        iso3 = item.get("id")
        reg = (item.get("region") or {}).get("value", "").strip()
        if iso3 and reg and reg != "Aggregates":
            if merge_americas and reg in {"North America", "Latin America & Caribbean"}:
                reg = "Americas"
            regions[iso3] = reg
    return regions


def load_cities(
    cities_path: Path,
    gdp_by_iso3: dict[str, tuple[float, str]],
    pop_by_iso3: dict[str, tuple[float, str]],
    region_by_iso3: dict[str, str],
) -> list[dict]:
    """Load cities688.csv and enrich each row with World Bank metadata."""
    with cities_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    enriched: list[dict] = []
    for row in rows:
        iso3 = row["iso3"]
        gdp_val, gdp_year = gdp_by_iso3.get(iso3, (None, ""))
        c_pop_val, _ = pop_by_iso3.get(iso3, (None, ""))
        pop_val = float(row["population"]) if row["population"] else None
        enriched.append(
            {
                **row,
                "region": region_by_iso3.get(iso3, row["continent"]),
                "population_num": pop_val,
                "gdp_pcap_pp": gdp_val,
                "gdp_year": gdp_year,
                "country_pop": c_pop_val,
                "img_count_num": int(row["img_count"]),
            }
        )
    return enriched


def assign_quantiles(eligible: list[dict], value_key: str, out_col: str, labels: list[str]) -> None:
    """Assign equal-count quantile labels in place using deterministic tie-breaking."""
    ordered = sorted(eligible, key=lambda r: (r[value_key], r["city_id"]))
    n = len(ordered)
    n_bins = len(labels)
    for idx, row in enumerate(ordered):
        q = min(n_bins - 1, (idx * n_bins) // n)
        row[out_col] = labels[q]


def deterministic_rank(seed: int, stratum: str, city_id: str, weight: float = 1.0) -> float:
    """Compute a deterministic Efraimidis-Spirakis sort key (smaller = higher priority)."""
    payload = f"{seed}:{stratum}:{city_id}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    u = (int(digest[:16], 16) + 0.5) / (2**64)
    return -math.log(u) / max(weight, 1e-9)


def allocate_quotas(
    stratum_sizes: dict[str, int],
    n_sample: int,
    min_per_stratum: int = 0,
    power: float = 1.0,
) -> dict[str, int]:
    """Allocate n_sample slots across groups via largest-remainder with optional power."""
    if n_sample <= 0 or not stratum_sizes:
        return {k: 0 for k in stratum_sizes}

    total_eligible = sum(stratum_sizes.values())
    if n_sample >= total_eligible:
        return dict(stratum_sizes)

    quotas = {k: 0 for k in stratum_sizes}
    if min_per_stratum > 0 and n_sample >= len(stratum_sizes) * min_per_stratum:
        for k in quotas:
            quotas[k] = min(min_per_stratum, stratum_sizes[k])
    remaining = n_sample - sum(quotas.values())

    if remaining > 0:
        capacity = {k: stratum_sizes[k] - quotas[k] for k in stratum_sizes}
        weights = {k: (capacity[k] ** power if capacity[k] > 0 else 0.0) for k in stratum_sizes}
        weight_total = sum(weights.values())
        exact = {k: (weights[k] / weight_total) * remaining for k in stratum_sizes}
        floors = {k: min(capacity[k], math.floor(exact[k])) for k in stratum_sizes}
        for k, add in floors.items():
            quotas[k] += add
        leftover = remaining - sum(floors.values())
        remainders = sorted(
            stratum_sizes.keys(),
            key=lambda k: (-(exact[k] - floors[k]), k),
        )
        for k in remainders:
            if leftover == 0:
                break
            if quotas[k] < stratum_sizes[k]:
                quotas[k] += 1
                leftover -= 1

    return quotas


def draw_cities(rows: list[dict], config: dict, world_pop: float) -> tuple[list[dict], list[dict]]:
    """Evaluate eligibility, bin quantiles, and run deterministic stratified selection."""
    seed = int(config["seed"])
    gates = config["eligibility_gates"]
    strat_cfg = config["stratification"]
    alloc_cfg = config["within_city_allocation"]
    anchors = set(config["certainty_anchors"])

    eligibility_rows: list[dict] = []
    eligible_non_anchor: list[dict] = []
    selected: list[dict] = []

    for row in rows:
        failures: list[str] = []
        if row["img_count_num"] < gates["min_img_count"]:
            failures.append("min_img_count")
        if gates["require_population"] and row["population_num"] is None:
            failures.append("missing_population")
        if gates["require_income"] and row["gdp_pcap_pp"] is None:
            failures.append("missing_income")

        passed = len(failures) == 0
        is_anchor = row["city_ascii"] in anchors

        record = {
            "city_id": row["city_id"],
            "city_ascii": row["city_ascii"],
            "country": row["country"],
            "iso3": row["iso3"],
            "continent": row["continent"],
            "region": row["region"],
            "population": "" if row["population_num"] is None else f"{row['population_num']:.0f}",
            "gdp_pcap_pp": "" if row["gdp_pcap_pp"] is None else f"{row['gdp_pcap_pp']:.2f}",
            "gdp_year": row["gdp_year"],
            "img_count": str(row["img_count_num"]),
            "region_income_bin": "",
            "eligible": "1" if passed else "0",
            "is_anchor": "1" if is_anchor else "0",
            "failed_gates": ";".join(failures),
            "_pop": row["population_num"],
            "_gdp": row["gdp_pcap_pp"],
        }
        eligibility_rows.append(record)

        if is_anchor and not passed:
            raise ValueError(f"Certainty anchor '{row['city_ascii']}' failed gates: {failures}")

    region_col = strat_cfg["region_col"]
    income_scope = strat_cfg.get("income_quantile_scope", "within_region")
    eligible_all = [r for r in eligibility_rows if r["eligible"] == "1"]

    by_region: dict[str, list[dict]] = defaultdict(list)
    for record in eligible_all:
        by_region[record[region_col]].append(record)

    if income_scope == "global":
        assign_quantiles(eligible_all, "_gdp", "region_income_bin", strat_cfg["income_labels"])
    elif income_scope == "within_region":
        for region_rows in by_region.values():
            assign_quantiles(region_rows, "_gdp", "region_income_bin", strat_cfg["income_labels"])
    else:
        raise ValueError(f"Unsupported income_quantile_scope: {income_scope}")

    for record in eligible_all:
        if record["is_anchor"] == "1":
            selected.append(
                {
                    **record,
                    "selection_type": "certainty_anchor",
                    "stratum": f"{record[region_col]}|{record['region_income_bin']}",
                    "stratum_eligible_n": "1",
                    "stratum_selected_n": "1",
                }
            )
        else:
            eligible_non_anchor.append(record)

    remaining_slots = strat_cfg["target_total_cities"] - len(selected)
    if remaining_slots < 0:
        raise ValueError("More certainty anchors than target_total_cities")

    by_stratum: dict[str, list[dict]] = defaultdict(list)
    region_by_stratum: dict[str, str] = {}
    for record in eligible_non_anchor:
        stratum = f"{record[region_col]}|{record['region_income_bin']}"
        by_stratum[stratum].append(record)
        region_by_stratum[stratum] = record[region_col]

    region_power = 0.5 if strat_cfg.get("region_allocation", "proportional") == "sqrt" else 1.0
    region_sizes: dict[str, int] = defaultdict(int)
    for stratum, members in by_stratum.items():
        region_sizes[region_by_stratum[stratum]] += len(members)
    region_quotas = allocate_quotas(dict(region_sizes), remaining_slots, power=region_power)

    quotas: dict[str, int] = {}
    min_per_stratum = int(strat_cfg.get("min_per_stratum", 0))
    for region, r_quota in sorted(region_quotas.items()):
        r_strata = {
            s: len(members) for s, members in by_stratum.items() if region_by_stratum[s] == region
        }
        quotas.update(allocate_quotas(r_strata, r_quota, min_per_stratum=min_per_stratum))

    # Draw round-robin across strata so per-country caps do not starve later strata.
    cap_mode = strat_cfg.get("country_cap_mode", "pop_proportional")
    cap_min = int(strat_cfg.get("country_cap_min", 1))
    cap_max = int(strat_cfg.get("country_cap_max", 8))
    total_target = int(strat_cfg["target_total_cities"])

    country_pop_by_iso3: dict[str, float] = {}
    for row in rows:
        if row["country_pop"] is not None:
            country_pop_by_iso3[row["iso3"]] = row["country_pop"]

    def country_cap(iso3: str) -> int:
        if cap_mode == "pop_proportional" and iso3 in country_pop_by_iso3 and world_pop > 0:
            raw = round(total_target * (country_pop_by_iso3[iso3] / world_pop))
            return max(cap_min, min(cap_max, raw))
        return cap_max

    country_counts: dict[str, int] = defaultdict(int)
    for row in selected:
        country_counts[row["iso3"]] += 1

    weighting = strat_cfg.get("within_stratum_weighting", "sqrt_population")

    def city_weight(record: dict) -> float:
        pop = max(1.0, record["_pop"] or 1.0)
        if weighting == "sqrt_population":
            return math.sqrt(pop)
        if weighting == "population":
            return pop
        return 1.0

    ranked = {
        stratum: sorted(
            by_stratum[stratum],
            key=lambda r: deterministic_rank(seed, stratum, r["city_id"], city_weight(r)),
        )
        for stratum in sorted(by_stratum.keys())
    }
    picked_ids: set[str] = set()
    stratum_picks: dict[str, list[dict]] = defaultdict(list)

    prefer_unrep = bool(strat_cfg.get("prefer_unrepresented_country", False))
    passes = [True, False] if prefer_unrep else [False]
    for only_unrepresented in passes:
        made_progress = True
        while made_progress:
            made_progress = False
            for stratum in sorted(ranked.keys()):
                if len(stratum_picks[stratum]) >= quotas[stratum]:
                    continue
                for candidate in ranked[stratum]:
                    cid = candidate["city_id"]
                    if cid in picked_ids:
                        continue
                    c_count = country_counts[candidate["iso3"]]
                    if only_unrepresented and c_count > 0:
                        continue
                    if c_count >= country_cap(candidate["iso3"]):
                        continue
                    stratum_picks[stratum].append(candidate)
                    picked_ids.add(cid)
                    country_counts[candidate["iso3"]] += 1
                    made_progress = True
                    break

    # Fallback: fill any remaining quota if country cap left a stratum short.
    for stratum in sorted(ranked.keys()):
        for candidate in ranked[stratum]:
            if len(stratum_picks[stratum]) >= quotas[stratum]:
                break
            cid = candidate["city_id"]
            if cid not in picked_ids:
                stratum_picks[stratum].append(candidate)
                picked_ids.add(cid)
                country_counts[candidate["iso3"]] += 1

    for stratum in sorted(stratum_picks.keys()):
        n_h = len(stratum_picks[stratum])
        if n_h == 0:
            continue
        big_n_h = len(by_stratum[stratum])
        for chosen in stratum_picks[stratum]:
            selected.append(
                {
                    **chosen,
                    "selection_type": "stratified",
                    "stratum": stratum,
                    "stratum_eligible_n": str(big_n_h),
                    "stratum_selected_n": str(n_h),
                }
            )

    per_city_cap = min(
        alloc_cfg["target_images_per_city"],
        alloc_cfg["max_total_inference_images"] // max(1, len(selected)),
    )
    cal_imgs = alloc_cfg["calibration_images_per_city"]

    for row in selected:
        allocated = min(per_city_cap, int(row["img_count"]))
        person_imgs = round(allocated * alloc_cfg["person_mask_share"])
        audit_imgs = allocated - person_imgs
        row["alloc_inference_images"] = str(allocated)
        row["alloc_person_mask_images"] = str(person_imgs)
        row["alloc_zero_mask_audit_images"] = str(audit_imgs)
        row["alloc_calibration_images"] = str(cal_imgs)

    # Strip internal numeric helpers before writing CSVs.
    for collection in (eligibility_rows, selected):
        for row in collection:
            row.pop("_pop", None)
            row.pop("_gdp", None)

    return eligibility_rows, selected


def estimate_probabilities(
    rows: list[dict], config: dict, world_pop: float, eligibility: list[dict], selected: list[dict]
) -> dict:
    """Replay the full draw because ranks and country caps couple the strata."""
    draws = int(config["probability_simulation"]["draws"])
    first_seed = int(config["probability_simulation"]["first_seed"])
    if draws < 2 or first_seed <= config["seed"] < first_seed + draws:
        raise ValueError("Use at least two replay seeds distinct from the observed draw.")
    hits = Counter()
    for seed in range(first_seed, first_seed + draws):
        _, sample = draw_cities(rows, {**config, "seed": seed}, world_pop)
        ids = {r["city_id"] for r in sample}
        if len(ids) != len(selected):
            raise ValueError(f"Unexpected number of distinct cities in replay {seed}.")
        hits.update(ids)

    by_id = {}
    for row in eligibility:
        count = hits[row["city_id"]]
        probability = count / draws
        method = "monte_carlo"
        if row["eligible"] == "0":
            method = "ineligible"
            if count:
                raise ValueError(f"Ineligible city {row['city_id']} selected in replays.")
        elif row["is_anchor"] == "1":
            method = "certainty_anchor"
            if count != draws:
                raise ValueError(f"Anchor {row['city_id']} absent from a replay.")
        # The plug-in SE degenerates at the simulation boundaries. Report
        # the one-sided 95% binomial bound for these cases in the manifest.
        if method != "monte_carlo":
            se = 0.0
        elif 0 < count < draws:
            se = math.sqrt(probability * (1 - probability) / draws)
        else:
            se = None
        fields = {
            "probability_method": method,
            "simulation_hits": count,
            "simulation_draws": draws,
            "inclusion_prob": f"{probability:.8f}",
            "inclusion_prob_mc_se": "" if se is None else f"{se:.8f}",
            "design_weight": f"{draws / count:.8f}" if count else "",
        }
        row.update(fields)
        by_id[row["city_id"]] = fields
    for row in selected:
        fields = by_id[row["city_id"]]
        if fields["simulation_hits"] == 0:
            raise ValueError(f"Increase replay count to estimate a weight for {row['city_ascii']}.")
        row.update(fields)
    return {
        "draws": draws,
        "first_seed": first_seed,
        "last_seed": first_seed + draws - 1,
        "eligible_cities_with_zero_hits": sum(
            r["eligible"] == "1" and not r["simulation_hits"] for r in eligibility
        ),
        "minimum_hits_among_selected": min(r["simulation_hits"] for r in selected),
        "maximum_possible_mc_se": 0.5 / math.sqrt(draws),
        "one_sided_95_upper_bound_after_zero_hits": -math.expm1(math.log(0.05) / draws),
        "one_sided_95_lower_bound_after_all_hits": math.exp(math.log(0.05) / draws),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write a list of uniform dicts to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cities", type=Path, default=DEFAULT_CITIES)
    parser.add_argument("--wb-gdp", type=Path, default=DEFAULT_WB_GDP)
    parser.add_argument("--wb-pop", type=Path, default=DEFAULT_WB_POP)
    parser.add_argument("--wb-countries", type=Path, default=DEFAULT_WB_COUNTRIES)
    parser.add_argument("--eligibility-out", type=Path, default=DEFAULT_ELIGIBILITY_OUT)
    parser.add_argument("--selected-out", type=Path, default=DEFAULT_SELECTED_OUT)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    gdp_by_iso3 = load_wb_indicator(args.wb_gdp)
    pop_by_iso3 = load_wb_indicator(args.wb_pop)
    merge_americas = bool(config["stratification"].get("merge_americas", False))
    region_by_iso3 = load_wb_regions(args.wb_countries, merge_americas=merge_americas)
    world_pop = pop_by_iso3["WLD"][0]
    rows = load_cities(args.cities, gdp_by_iso3, pop_by_iso3, region_by_iso3)

    eligibility_rows, selected = draw_cities(rows, config, world_pop)
    _, selected_verify = draw_cities(rows, config, world_pop)
    if [r["city_id"] for r in selected] != [r["city_id"] for r in selected_verify]:
        raise AssertionError("Reproducibility check failed: draws did not match")

    diagnostics = estimate_probabilities(rows, config, world_pop, eligibility_rows, selected)
    write_csv(args.eligibility_out, eligibility_rows)
    write_csv(args.selected_out, selected)

    manifest = {
        "seed": config["seed"],
        "config_version": config["version"],
        "probability_simulation": diagnostics,
        "inputs": {
            "config": file_digest(args.config),
            "cities688": file_digest(args.cities),
            "wb_gdp_pcap_pp": file_digest(args.wb_gdp),
            "wb_pop_totl": file_digest(args.wb_pop),
            "wb_countries": file_digest(args.wb_countries),
        },
        "counts": {
            "total_cities": len(rows),
            "eligible_cities": sum(1 for r in eligibility_rows if r["eligible"] == "1"),
            "selected_cities": len(selected),
            "populated_strata": len({r["stratum"] for r in selected}),
            "total_inference_images_capped": sum(
                int(r["alloc_inference_images"]) for r in selected
            ),
            "total_calibration_images": sum(int(r["alloc_calibration_images"]) for r in selected),
        },
        "outputs": {
            "city_eligibility": file_digest(args.eligibility_out),
            "selected_cities": file_digest(args.selected_out),
        },
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(
        f"Seed {config['seed']}: {manifest['counts']['eligible_cities']}/"
        f"{manifest['counts']['total_cities']} eligible, "
        f"{manifest['counts']['selected_cities']} selected across "
        f"{manifest['counts']['populated_strata']} strata"
    )
    print(f"Wrote {args.eligibility_out}, {args.selected_out}, and {args.manifest_out}")


if __name__ == "__main__":
    main()
