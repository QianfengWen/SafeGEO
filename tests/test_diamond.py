import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq


def _rows(name: str, columns: list[str]):
    path = Path("diamond") / name / "test-00000-of-00001.parquet"
    return pq.read_table(path, columns=columns).to_pylist()


def test_diamond_manifest_and_row_counts():
    manifest = json.loads(Path("diamond/selection_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["base_case_ids"]) == 120
    assert manifest["target_slots"] == ["A"]
    assert manifest["attack_packages"] == [
        "selective_comparison_note",
        "false_fit_checklist",
        "citation_padded_note",
    ]
    assert manifest["row_counts"]["visible"] == 600
    assert manifest["row_counts"]["labels"] == 600
    assert manifest["row_counts"]["instances_manifest"] == 600


def test_diamond_is_balanced_and_has_three_attacks_plus_two_controls():
    labels = _rows("labels", ["base_case_id", "vertical", "package_id", "attacked_target_slot"])
    per_vertical = Counter({
        vertical: len({row["base_case_id"] for row in labels if row["vertical"] == vertical})
        for vertical in {row["vertical"] for row in labels}
    })
    assert set(per_vertical.values()) == {20}

    per_case = Counter(row["base_case_id"] for row in labels)
    assert set(per_case.values()) == {5}
    expected_packages = {
        "original_no_geo_control",
        "all_truthful_target_control",
        "selective_comparison_note",
        "false_fit_checklist",
        "citation_padded_note",
    }
    assert {row["package_id"] for row in labels} == expected_packages
    for row in labels:
        if row["package_id"] not in {
            "original_no_geo_control",
            "all_truthful_target_control",
        }:
            assert row["attacked_target_slot"] == "A"


def test_diamond_visible_and_label_ids_align():
    visible_ids = {row["instance_id"] for row in _rows("visible", ["instance_id"])}
    label_ids = {row["instance_id"] for row in _rows("labels", ["instance_id"])}
    assert visible_ids == label_ids


def test_diamond_target_a_is_a_hard_infeasible_negative():
    labels = _rows("labels", ["package_id", "fixed_geo_targets"])
    for row in labels:
        targets = row["fixed_geo_targets"]
        if isinstance(targets, str):
            targets = json.loads(targets)
        target_a = next(target for target in targets if target["target_slot"] == "A")
        assert target_a["quality_group"] == "hard_negative"
        assert target_a["hard_constraint_feasible"] is False
        assert target_a["failed_hard_constraints"]
        assert "benchmark_reference_utility" in target_a
        assert "verified_utility_score" not in target_a
