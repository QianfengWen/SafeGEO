import json
from pathlib import Path

import pyarrow.parquet as pq


DATASET_ROOTS = [Path("data"), Path("sample"), Path("diamond")]


def _decode(value):
    return json.loads(value) if isinstance(value, str) else value


def test_candidate_utility_column_uses_camera_ready_name():
    for root in DATASET_ROOTS:
        path = next((root / "candidate_quality").glob("*.parquet"))
        names = pq.read_schema(path).names
        assert "benchmark_reference_utility" in names
        assert "pipeline_utility_score_original" in names
        assert "verified_utility_score" not in names
        assert "canonical_utility_score_original" not in names


def test_nested_target_records_use_benchmark_reference_terminology():
    for root in DATASET_ROOTS:
        for config in ("targets", "labels", "instances_manifest"):
            for path in sorted((root / config).glob("*.parquet")):
                rows = pq.read_table(path, columns=["fixed_geo_targets"]).to_pylist()
                for row in rows:
                    targets = _decode(row["fixed_geo_targets"])
                    if targets is None:
                        continue
                    for target in targets:
                        assert "benchmark_reference_utility" in target
                        assert "verified_utility_score" not in target
                        description = target.get("primary_exploitable_gap", {}).get("description", "")
                        assert "canonical truth" not in description.lower()
