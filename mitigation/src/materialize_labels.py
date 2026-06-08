#!/usr/bin/env python3
"""Materialize full SafeGEO labels for mitigation run instances.

The mitigation label manifest is intentionally lightweight. This script copies
the corresponding source-only label for each run instance and gives it the
expanded run_instance_id so the main SafeGEO scorer can compute quality metrics
by mitigation layer.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Iterable

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "src"))
from safegeo.io import read_records

LAYER_NAMES = {
    "L0": "L0_source_only_baseline",
    "L1": "L1_prompt_mitigation",
    "L2": "L2_rationale_elicitation_mitigation",
    "L3": "L3_audited_evidence_sheet_mitigation",
    "L4": "L4_context_balancing_mitigation",
    "L5": "L5_instruction_filtering_mitigation",
}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("data"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source_labels = {str(r["instance_id"]): r for r in read_records(args.dataset_root / "labels")}
    if not source_labels:
        raise SystemExit(f"No labels found under {args.dataset_root / 'labels'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with args.out.open("w", encoding="utf-8") as out:
        for manifest in iter_jsonl(args.manifest):
            source_id = str(manifest["source_instance_id"])
            original = source_labels.get(source_id)
            if original is None:
                raise KeyError(f"Missing source label for {source_id}")
            row = copy.deepcopy(original)
            layer_id = str(manifest["layer_id"])
            row["instance_id"] = manifest["run_instance_id"]
            row["source_instance_id"] = source_id
            row["mitigation_layer_id"] = layer_id
            row["mitigation_layer_name"] = LAYER_NAMES.get(layer_id, manifest.get("layer_name"))
            row["mitigation_target_slot"] = manifest.get("target_slot")
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print(json.dumps({"out": str(args.out), "n": n}, indent=2))


if __name__ == "__main__":
    main()
