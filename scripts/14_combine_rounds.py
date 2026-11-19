"""Combine the three coded samples after checking each against the original draw."""

from pathlib import Path

import pandas as pd


def main():
    output = Path("outputs")
    selected = pd.read_csv(output / "selected_images.csv").set_index("uuid", verify_integrity=True)
    frames = []
    for wave in range(1, 4):
        expected = selected.index[selected.rank_in_city.between(100 * wave - 99, 100 * wave)]
        manifest = pd.read_csv(output / f"download_manifest_round{wave}.csv").set_index(
            "uuid", verify_integrity=True
        )
        if set(expected) != set(manifest.index):
            raise ValueError(f"Manifest differs from selected ranks in round {wave}")
        counts = pd.read_csv(output / f"muse_counts_round{wave}.csv", dtype=str)
        ids = counts.image.map(lambda name: Path(name).stem)
        downloaded = manifest.index[manifest.status.isin(["ok", "cached"])]
        if ids.duplicated().any() or not ids.isin(downloaded).all():
            raise ValueError(f"Duplicate image or missing download in round {wave}")
        frames.append(counts)
    pooled = pd.concat(frames, ignore_index=True)
    pooled.to_csv(output / "muse_counts_all.csv", index=False)


if __name__ == "__main__":
    main()
