import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq


def _rows(name: str, columns: list[str]):
    path = Path("diamond") / name / "test-00000-of-00001.parquet"
    return pq.read_table(path, columns=columns).to_pylist()


def test_diamond_manifest_and_row_counts():
    manifest = json.loads(Path("diamond/selection_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.1"
    assert len(manifest["base_case_ids"]) == 120
    assert manifest["target_slots"] == ["A", "B", "C"]
    assert manifest["target_selection_strategy"] == "balanced_round_robin_one_per_base_case"
    assert manifest["target_slot_case_counts"] == {"A": 40, "B": 40, "C": 40}
    assert "difficulty" not in manifest["selection_bias_notice"].lower()
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
    attacked = [
        row
        for row in labels
        if row["package_id"]
        not in {"original_no_geo_control", "all_truthful_target_control"}
    ]
    selected_slot_by_case = {}
    for row in attacked:
        selected_slot_by_case.setdefault(row["base_case_id"], row["attacked_target_slot"])
        assert row["attacked_target_slot"] == selected_slot_by_case[row["base_case_id"]]
    assert Counter(selected_slot_by_case.values()) == {"A": 40, "B": 40, "C": 40}
    assert Counter(row["attacked_target_slot"] for row in attacked) == {
        "A": 120,
        "B": 120,
        "C": 120,
    }


def test_diamond_visible_and_label_ids_align():
    visible_ids = {row["instance_id"] for row in _rows("visible", ["instance_id"])}
    label_ids = {row["instance_id"] for row in _rows("labels", ["instance_id"])}
    assert visible_ids == label_ids


def test_diamond_selected_targets_are_present_and_scored_uniformly():
    labels = _rows("labels", ["package_id", "attacked_target_slot", "fixed_geo_targets"])
    for row in labels:
        if row["package_id"] in {
            "original_no_geo_control",
            "all_truthful_target_control",
        }:
            continue
        targets = row["fixed_geo_targets"]
        if isinstance(targets, str):
            targets = json.loads(targets)
        selected = next(
            target for target in targets if target["target_slot"] == row["attacked_target_slot"]
        )
        assert selected["target_slot"] in {"A", "B", "C"}
        assert "benchmark_reference_utility" in selected
        assert "verified_utility_score" not in selected
