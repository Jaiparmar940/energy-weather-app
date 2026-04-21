from pathlib import Path

import pandas as pd

from dc_region_scoring import assign_data_center_likelihood, default_pjm_scoring_config


ROOT = Path(__file__).resolve().parents[1]


def main():
    nodes_path = ROOT / "data" / "samples" / "pjm_nodes_synthetic.csv"
    ts_path = ROOT / "data" / "samples" / "pjm_timeseries_synthetic.csv"

    nodes = pd.read_csv(nodes_path)
    nodes = nodes.rename(columns={"latitude": "lat", "longitude": "lon"})

    config = default_pjm_scoring_config()

    geo_only = assign_data_center_likelihood(nodes, config)
    geo_plus_behavior = assign_data_center_likelihood(nodes, config, pd.read_csv(ts_path))

    print("\n=== Geography-only scoring ===")
    print(
        geo_only[
            [
                "node_id",
                "zone",
                "data_center_likelihood_score",
                "confidence_score",
                "classification_label",
                "matched_region",
            ]
        ].head(10)
    )

    print("\n=== Geography + time-series scoring ===")
    print(
        geo_plus_behavior[
            [
                "node_id",
                "zone",
                "data_center_likelihood_score",
                "confidence_score",
                "classification_label",
                "matched_region",
            ]
        ].head(10)
    )


if __name__ == "__main__":
    main()
