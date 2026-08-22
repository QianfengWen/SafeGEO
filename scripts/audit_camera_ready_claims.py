#!/usr/bin/env python3
"""Check the release invariants cited in the SafeGEO camera-ready paper."""
from __future__ import annotations

from collections import Counter
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]


def decode(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def parquet_rows(root: Path, columns: list[str]):
    for path in sorted(root.glob("*.parquet")):
        yield from pq.read_table(path, columns=columns).to_pylist()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_queries() -> dict[str, int]:
    target_queries = {
        str(row["query_id"]): str(row["user_query"])
        for row in parquet_rows(ROOT / "data/targets", ["query_id", "user_query"])
    }
    visible_rows = mismatches = 0
    visible_query_ids: set[str] = set()
    for row in parquet_rows(ROOT / "data/visible", ["query_id", "user_query"]):
        query_id = str(row["query_id"])
        visible_query_ids.add(query_id)
        visible_rows += 1
        mismatches += str(row["user_query"]) != target_queries[query_id]
    assert len(target_queries) == 600
    assert visible_query_ids == set(target_queries)
    assert visible_rows == 40_800
    assert mismatches == 0
    return {
        "base_queries": len(target_queries),
        "expanded_rows": visible_rows,
        "exact_mismatches": mismatches,
    }


def audit_targets() -> dict[str, Any]:
    targets = []
    for row in parquet_rows(ROOT / "data/targets", ["fixed_geo_targets"]):
        targets.extend(decode(row["fixed_geo_targets"]))
    roles = Counter(target["target_role"] for target in targets)
    hard_infeasible = sum(not target["hard_constraint_feasible"] for target in targets)

    # ``candidate_shortlist_rank`` records the upstream shortlist position, not
    # the reference ordering used in the paper. Reconstruct that ordering from
    # the released scoring fields: hard-feasible items first, then descending
    # benchmark-reference utility, with item id as a deterministic tie-break.
    quality_by_query: dict[str, list[dict[str, Any]]] = {}
    for row in parquet_rows(
        ROOT / "data/candidate_quality",
        ["query_id", "item_id", "hard_constraint_feasible", "benchmark_reference_utility"],
    ):
        quality_by_query.setdefault(str(row["query_id"]), []).append(row)
    reference_ranks: dict[tuple[str, str], int] = {}
    for query_id, candidates in quality_by_query.items():
        ordered = sorted(
            candidates,
            key=lambda row: (
                -int(bool(row["hard_constraint_feasible"])),
                -float(row["benchmark_reference_utility"]),
                str(row["item_id"]),
            ),
        )
        reference_ranks.update(
            ((query_id, str(row["item_id"])), rank)
            for rank, row in enumerate(ordered, start=1)
        )
    top_five = sum(
        reference_ranks[(str(target["query_id"]), str(target["candidate_id"]))] <= 5
        for target in targets
    )
    assert len(targets) == 1_800
    assert hard_infeasible == 1_754
    assert len(targets) - hard_infeasible == 46
    assert top_five == 46
    assert set(roles.values()) == {600}
    assert all("benchmark_reference_utility" in target for target in targets)
    return {
        "targets": len(targets),
        "hard_infeasible": hard_infeasible,
        "feasible_lower_utility": len(targets) - hard_infeasible,
        "reference_top_five": top_five,
        "roles": dict(sorted(roles.items())),
    }


def audit_diamond() -> dict[str, Any]:
    rows = list(
        parquet_rows(
            ROOT / "diamond/labels",
            ["base_case_id", "vertical", "package_id", "fixed_geo_targets"],
        )
    )
    base_cases = {str(row["base_case_id"]) for row in rows}
    per_vertical = Counter()
    for vertical in {str(row["vertical"]) for row in rows}:
        per_vertical[vertical] = len(
            {str(row["base_case_id"]) for row in rows if str(row["vertical"]) == vertical}
        )
    packages = Counter(str(row["package_id"]) for row in rows)
    for row in rows:
        targets = decode(row["fixed_geo_targets"])
        target_a = next(target for target in targets if target["target_slot"] == "A")
        assert target_a["quality_group"] == "hard_negative"
        assert target_a["hard_constraint_feasible"] is False
    assert len(rows) == 600
    assert len(base_cases) == 120
    assert set(per_vertical.values()) == {20}
    assert sorted(packages.values()) == [120] * 5
    return {
        "instances": len(rows),
        "base_cases": len(base_cases),
        "base_cases_per_vertical": dict(sorted(per_vertical.items())),
        "conditions": dict(sorted(packages.items())),
    }


def audit_mitigation() -> dict[str, Any]:
    build = load_module("safegeo_build_runfiles_audit", ROOT / "mitigation/src/build_runfiles.py")
    benchmark_prompt = ROOT / "benchmark/prompts/safegeo_recommendation_system.txt"
    l0_prompt = (ROOT / "mitigation" / build.PROMPT_FILES["L0"]).resolve()
    assert l0_prompt == benchmark_prompt.resolve()
    assert l0_prompt.read_bytes() == benchmark_prompt.read_bytes()

    baseline = benchmark_prompt.read_text(encoding="utf-8").strip()
    for layer in ("L1", "L2", "L3", "L4", "L5"):
        path = ROOT / "mitigation" / build.PROMPT_FILES[layer]
        assert path.read_text(encoding="utf-8").strip().startswith(baseline)

    sample_path = next((ROOT / "sample/visible").glob("*.parquet"))
    sample = pq.read_table(sample_path).slice(0, 1).to_pylist()[0]
    for layer in build.LAYER_IDS:
        transformed = build.transform_visible(sample, {}, layer, "A")
        assert transformed == sample
        assert transformed is not sample
    return {
        "l0_is_benchmark_prompt": True,
        "shared_visible_packet": True,
        "layers": list(build.LAYER_IDS),
        "l3_schema": build.SCHEMA_IDS["L3"],
    }


def audit_results() -> dict[str, Any]:
    expected = {
        "deepseek_v4_flash_all22.csv": 24,
        "deepseek_v4_flash_mitigation.csv": 6,
        "deepseek_v4_flash_sensitivity.csv": 6,
        "paired_mechanism.csv": 4,
    }
    tables: dict[str, list[dict[str, str]]] = {}
    for name, expected_rows in expected.items():
        with (ROOT / "results" / name).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        tables[name] = rows
        assert len(rows) == expected_rows

    all22 = {row["package_id"]: row for row in tables["deepseek_v4_flash_all22.csv"]}
    truthful = all22["all_truthful_target_control"]
    strongest = all22["selective_comparison_note"]
    assert tuple(map(float, (truthful["target_at_3"], truthful["hcv_at_1"]))) == (4.6, 23.0)
    assert tuple(
        map(
            float,
            (
                strongest["target_at_3"],
                strongest["target_delta_pp"],
                strongest["hcv_at_1"],
                strongest["hcv_delta_pp"],
                strongest["undcg_at_5"],
            ),
        )
    ) == (82.3, 77.7, 81.8, 58.8, 65.4)
    realistic = [row for row in all22.values() if row["family"] == "realistic"]
    assert len(realistic) == 8
    realistic_average = {
        key: round(sum(float(row[key]) for row in realistic) / len(realistic), 1)
        for key in ("target_at_3", "hcv_at_1", "gt_at_3", "undcg_at_5")
    }
    assert realistic_average == {
        "target_at_3": 72.6,
        "hcv_at_1": 73.4,
        "gt_at_3": 57.7,
        "undcg_at_5": 66.9,
    }

    mitigation = {
        row["layer"]: row for row in tables["deepseek_v4_flash_mitigation.csv"]
    }
    assert tuple(map(float, (mitigation["L3"]["target_at_3"], mitigation["L3"]["target_delta_vs_l0_pp"], mitigation["L3"]["hcv_at_1"], mitigation["L3"]["hcv_delta_vs_l0_pp"]))) == (46.8, -25.8, 54.8, -18.6)
    assert tuple(map(float, (mitigation["L4"]["gt_at_3"], mitigation["L4"]["undcg_at_5"]))) == (57.2, 69.0)

    mechanism = {
        row["transition"]: row for row in tables["paired_mechanism.csv"]
    }
    assert tuple(map(int, (mechanism["evidence_shift_to_target_gap_shift"]["group_a_count"], mechanism["evidence_shift_to_target_gap_shift"]["group_a_total"], mechanism["evidence_shift_to_target_gap_shift"]["group_b_count"], mechanism["evidence_shift_to_target_gap_shift"]["group_b_total"]))) == (4441, 8203, 203, 3010)
    assert tuple(map(float, (mechanism["full_path_share_of_observed_entries"]["difference_or_coverage_percent"], mechanism["full_path_share_of_observed_entries"]["ci_low"], mechanism["full_path_share_of_observed_entries"]["ci_high"]))) == (49.7, 47.9, 51.6)

    return {
        "rows": {name: len(rows) for name, rows in tables.items()},
        "realistic_average": realistic_average,
        "strongest_realistic_package": strongest["display_name"],
        "deepseek_l3_target_reduction_pp": float(
            mitigation["L3"]["target_delta_vs_l0_pp"]
        ),
        "paired_mechanism_entry_coverage": float(
            mechanism["full_path_share_of_observed_entries"][
                "difference_or_coverage_percent"
            ]
        ),
    }


def main() -> None:
    report = {
        "queries": audit_queries(),
        "targets": audit_targets(),
        "diamond": audit_diamond(),
        "mitigation": audit_mitigation(),
        "aggregate_results": audit_results(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
