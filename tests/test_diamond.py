import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq


def _rows(name: str, columns: list[str]):
    path = Path("diamond") / name / "test-00000-of-00001.parquet"
    return pq.read_table(path, columns=columns).to_pylist()


def test_diamond_manifest_and_row_counts():
    manifest = json.loads(Path("diamond/selection_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "1.2"
    assert len(manifest["base_case_ids"]) == 120
    assert manifest["target_selection_strategy"] == "fixed_seed_one_per_base_case"
    assert len(manifest["target_candidate_by_base_case"]) == 120
    assert set(manifest["target_candidate_by_base_case"]) == set(manifest["base_case_ids"])
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
    labels = _rows("labels", ["base_case_id", "vertical", "package_id", "attacked_candidate_id"])
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
    selected_candidate_by_case = {}
    for row in attacked:
        selected_candidate_by_case.setdefault(row["base_case_id"], row["attacked_candidate_id"])
        assert row["attacked_candidate_id"] == selected_candidate_by_case[row["base_case_id"]]
    assert len(selected_candidate_by_case) == 120
    assert set(Counter(row["attacked_candidate_id"] for row in attacked).values()) == {3}


def test_diamond_visible_and_label_ids_align():
    visible_ids = {row["instance_id"] for row in _rows("visible", ["instance_id"])}
    label_ids = {row["instance_id"] for row in _rows("labels", ["instance_id"])}
    assert visible_ids == label_ids


def test_diamond_selected_targets_are_present_and_scored_uniformly():
    labels = _rows("labels", ["package_id", "attacked_candidate_id", "fixed_geo_targets"])
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
            target for target in targets if target["candidate_id"] == row["attacked_candidate_id"]
        )
        assert "target_slot" not in selected
        assert "target_role" not in selected
        assert "benchmark_reference_utility" in selected
        assert "verified_utility_score" not in selected
