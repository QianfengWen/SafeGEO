#!/usr/bin/env python3
"""Build SafeGEO mitigation runfiles.

This script reads a SafeGEO Parquet dataset and constructs layer-specific
runfiles for the mitigation experiment:

  600 base cases × 3 sampled targets × 8 realistic packages ×
  L0–L5 conditions.

It does not include no-GEO or all-truthful controls. Mitigation is measured by
comparing each layer against L0 on the same attacked instances.

Example:
  python mitigation/src/build_runfiles.py \
    --dataset-root data \
    --out runs/mitigation_all_targets_realistic \
    --layers L0,L1,L2,L3,L4,L5

Screening:
  python mitigation/src/build_runfiles.py \
    --dataset-root data \
    --out runs/screening \
    --base-cases-per-vertical 25
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "src"))
from safegeo.io import read_records
from safegeo.taxonomy import (
    LAYER_NAMES as _LAYER_NAMES,
    LAYER_SCHEMAS as _LAYER_SCHEMAS,
    REALISTIC_PACKAGES,
)

LAYER_IDS = dict(_LAYER_NAMES)

PROMPT_FILES = {
    # L0 intentionally points to the benchmark prompt itself.  It must not be a
    # paraphrased copy: L0 is the original benchmark request with no mitigation.
    "L0": "../benchmark/prompts/safegeo_recommendation_system.txt",
    "L1": "prompts/layers/L1_prompt_mitigation.md",
    "L2": "prompts/layers/L2_rationale_elicitation_mitigation.md",
    "L3": "prompts/layers/L3_evidence_breakdown_mitigation.md",
    "L4": "prompts/layers/L4_context_balancing_mitigation.md",
    "L5": "prompts/layers/L5_instruction_filtering_mitigation.md",
}

SCHEMA_IDS = dict(_LAYER_SCHEMAS)


def load_dataset(dataset_root: Path):
    visible = {r["instance_id"]: r for r in read_records(dataset_root / "visible")}
    labels = read_records(dataset_root / "labels")
    return visible, labels


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def stable_hash(s: str, seed: str = "safegeo") -> str:
    return hashlib.sha256((seed + "::" + s).encode("utf-8")).hexdigest()


def choose_base_cases(labels: List[Dict[str, Any]], per_vertical: Optional[int], seed: str) -> Optional[set[str]]:
    if per_vertical is None:
        return None
    by_vertical: Dict[str, set[str]] = {}
    for lab in labels:
        by_vertical.setdefault(lab["vertical"], set()).add(lab["base_case_id"])
    selected: set[str] = set()
    for vertical, ids in by_vertical.items():
        ordered = sorted(ids, key=lambda x: stable_hash(x, seed=seed))
        selected.update(ordered[:per_vertical])
    return selected


def get_target_info(label: Dict[str, Any], candidate_id: str) -> Optional[Dict[str, Any]]:
    for t in label.get("fixed_geo_targets", []):
        if t.get("candidate_id") == candidate_id:
            return t
    return None


def transform_visible(row: Dict[str, Any], label: Dict[str, Any], layer: str) -> Dict[str, Any]:
    """Return an independent copy of the shared visible packet for a condition.

    L1--L5 vary their system instructions. L3 adds a response field, while L4
    and L5 leave document order and source lines intact.
    """
    del label
    if layer not in LAYER_IDS:
        raise ValueError(f"Unknown layer: {layer}")
    return copy.deepcopy(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", type=Path, default=Path("data"), help="Root of the SafeGEO Parquet dataset (the data/ dir)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--layers", default="L0,L1,L2,L3,L4,L5")
    ap.add_argument("--base-cases-per-vertical", type=int, default=None, help="Use for screening, e.g. 25")
    ap.add_argument("--seed", default="safegeo-mitigation")
    args = ap.parse_args()

    layers = [x.strip() for x in args.layers.split(",") if x.strip()]
    for layer in layers:
        if layer not in LAYER_IDS:
            raise ValueError(f"Invalid layer {layer}; choose from {sorted(LAYER_IDS)}")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "runfiles").mkdir(exist_ok=True)
    (args.out / "labels").mkdir(exist_ok=True)

    visible_index, all_labels = load_dataset(args.dataset_root)
    all_selected_labels: List[Dict[str, Any]] = [
        lab for lab in all_labels
        if lab.get("attacked_candidate_id")
        and lab.get("num_attacked_targets") == 1
        and lab.get("package_id") in REALISTIC_PACKAGES
    ]

    selected_base_cases = choose_base_cases(all_selected_labels, args.base_cases_per_vertical, args.seed)
    if selected_base_cases is not None:
        all_selected_labels = [lab for lab in all_selected_labels if lab["base_case_id"] in selected_base_cases]

    # Sort for deterministic output.
    all_selected_labels.sort(key=lambda x: (x["vertical"], x["base_case_id"], x["package_id"], x["instance_id"]))

    counts_by_layer = {layer: 0 for layer in layers}
    package_counts: Dict[str, int] = {}
    vertical_counts: Dict[str, int] = {}

    writers = {}
    try:
        for layer in layers:
            path = args.out / "runfiles" / f"{layer}_{LAYER_IDS[layer]}.jsonl"
            writers[layer] = path.open("w", encoding="utf-8")

        label_path = args.out / "labels" / "mitigation_labels_manifest.jsonl"
        with label_path.open("w", encoding="utf-8") as lfout:
            for lab in all_selected_labels:
                vertical = lab["vertical"]
                visible = visible_index.get(lab["instance_id"])
                if visible is None:
                    raise KeyError(f"Missing visible row for {lab['instance_id']} in {vertical}")

                package_id = lab["package_id"]
                package_counts[package_id] = package_counts.get(package_id, 0) + 1
                vertical_counts[vertical] = vertical_counts.get(vertical, 0) + 1

                attacked_candidate_id = str(lab["attacked_candidate_id"])
                target = get_target_info(lab, attacked_candidate_id) or {}
                label_record = {
                    "source_instance_id": lab["instance_id"],
                    "expanded_instance_id": lab.get("expanded_instance_id"),
                    "base_case_id": lab.get("base_case_id"),
                    "query_id": lab.get("query_id"),
                    "split": lab.get("split"),
                    "vertical": vertical,
                    "attacked_candidate_id": attacked_candidate_id,
                    "package_id": package_id,
                    "package_family": lab.get("package_family"),
                    "attack_vector": lab.get("attack_vector"),
                    "attack_blocks": lab.get("attack_blocks"),
                    "target_metadata": target,
                    "paired_refuting_lines": lab.get("paired_refuting_lines", []),
                    "geo_misleading_lines": lab.get("geo_misleading_lines", []),
                    "controlled_source_candidate_mapping": lab.get("controlled_source_candidate_mapping", {}),
                    "expected_correct_behavior": lab.get("expected_correct_behavior", {})
                }

                for layer in layers:
                    run_instance_id = f"{lab['instance_id']}__{layer}"
                    transformed = transform_visible(visible, lab, layer)
                    row = {
                        "run_instance_id": run_instance_id,
                        "source_instance_id": lab["instance_id"],
                        "layer_id": layer,
                        "layer_name": LAYER_IDS[layer],
                        "prompt_file": PROMPT_FILES[layer],
                        "output_schema_id": SCHEMA_IDS[layer],
                        "visible_instance": transformed,
                    }
                    writers[layer].write(json.dumps(row, ensure_ascii=False) + "\n")
                    counts_by_layer[layer] += 1

                    lfout.write(json.dumps({"run_instance_id": run_instance_id, "layer_id": layer, **label_record}, ensure_ascii=False) + "\n")
    finally:
        for f in writers.values():
            f.close()

    summary = {
        "dataset_root": str(args.dataset_root),
        "layers": layers,
        "realistic_packages": REALISTIC_PACKAGES,
        "base_cases_per_vertical": args.base_cases_per_vertical,
        "unique_base_cases": len({lab["base_case_id"] for lab in all_selected_labels}),
        "selected_attack_instances_before_layer_expansion": len(all_selected_labels),
        "counts_by_layer": counts_by_layer,
        "package_counts_before_layer_expansion": package_counts,
        "vertical_counts_before_layer_expansion": vertical_counts,
        "labels_manifest": "labels/mitigation_labels_manifest.jsonl",
    }
    (args.out / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
