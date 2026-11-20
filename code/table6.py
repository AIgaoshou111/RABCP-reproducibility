"""Assemble Table 6 from the matching stationary and change cohorts."""

import argparse
import csv
from pathlib import Path


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results/manuscript_tables",
    )
    root = parser.parse_args().source
    output = {}
    for r in read(root / "component_control_summary.csv"):
        output.setdefault(r["condition"], {})[r["method"]] = float(r["MAE"])
    for r in read(root / "model_misspecification_summary.csv"):
        if r["method"] == "weighted_bae_imperfect_flag":
            output[r["condition"]]["window5"] = float(r["mean_mae_after_10"])
    for r in read(root / "recovery_corrected_summary.csv"):
        if r["method"] == "weighted_bae_forget_0.05":
            output[r["condition"]]["window5"] = float(r["post_change_MAE"])
    print("condition,weighted_mean,weighted_filter_window1,weighted_filter_window5")
    for c in (
        "symmetric_mixed",
        "asymmetric_high",
        "heavy_tail_bursts",
        "persistent_late_bias",
        "abrupt_up",
        "abrupt_down",
    ):
        print(
            c,
            *(
                f"{output[c][m]:.4f}"
                for m in ("weighted_mean", "weighted_filter_window1", "window5")
            ),
            sep=",",
        )
