"""Small designs with known probabilities for the constrained city sampler."""

import json
import runpy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sampler = runpy.run_path(str(ROOT / "scripts/03_select_cities.py"))


class CityWeightTest(unittest.TestCase):
    def test_one_seat_after_certainty_anchor(self):
        config = json.loads((ROOT / "config/sampling.json").read_text())
        config["certainty_anchors"] = ["Anchor"]
        config["stratification"].update(target_total_cities=2, income_labels=["All"])
        config["probability_simulation"]["draws"] = 4000
        rows = []
        for city, country, population in [
            ("Anchor", "A", 1),
            ("Same country", "A", 1000),
            ("Small", "B", 1),
            ("Large", "C", 4),
        ]:
            rows.append(
                dict(
                    city_id=city,
                    city_ascii=city,
                    country=country,
                    iso3=country,
                    region="Region",
                    continent="Continent",
                    img_count_num=500,
                    gdp_pcap_pp=1000,
                    gdp_year="2025",
                    population_num=population,
                    country_pop=10000,
                )
            )
        eligible, selected = sampler["draw_cities"](rows, config, 30000)
        sampler["estimate_probabilities"](rows, config, 30000, eligible, selected)
        estimates = {r["city_ascii"]: r for r in eligible}
        self.assertEqual(estimates["Anchor"]["simulation_hits"], 4000)
        self.assertEqual(estimates["Same country"]["simulation_hits"], 0)
        self.assertEqual(estimates["Same country"]["design_weight"], "")
        # A single open seat favors the two remaining cities in ratio sqrt(4):sqrt(1).
        for city, probability in [("Large", 2 / 3), ("Small", 1 / 3)]:
            self.assertAlmostEqual(
                float(estimates[city]["inclusion_prob"]), probability, delta=0.03
            )
        for city in selected:
            estimate = estimates[city["city_ascii"]]
            self.assertEqual(city["design_weight"], estimate["design_weight"])
            self.assertAlmostEqual(float(city["design_weight"]), 1 / float(city["inclusion_prob"]))
