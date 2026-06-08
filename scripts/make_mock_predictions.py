#!/usr/bin/env python3
"""Generate schema-valid mock predictions so scoring/analysis run without a GPU.

benchmark mode: reads a `visible` config (Parquet dir/file) and emits the
prediction-schema JSON the SafeGEO scorer expects, ranking candidates in roster
order. mitigation mode: reads a mitigation runfile and emits per-run-instance
predictions in the accountable/simple schema shape.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from safegeo.io import read_records


def _roster_ids(rec):
    return [c.get("candidate_id") for c in rec.get("candidate_roster", []) if c.get("candidate_id")]


def run(mode: str, source: Path, out: Path, model: str) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        if mode == "benchmark":
            for rec in read_records(source):
                ids = _roster_ids(rec)
                top = [{"item_id": x, "rank": i + 1, "rationale": "mock", "citations": []}
                       for i, x in enumerate(ids[:3])]
                parsed = {"ranking_all_items": ids, "top_recommendations": top,
                          "constraint_audit": [], "rejected_or_caveated_items": [],
                          "source_assessment": []}
                fh.write(json.dumps({
                    "instance_id": rec["instance_id"], "query_id": rec.get("query_id"),
                    "vertical": rec.get("vertical"), "split": rec.get("split"),
                    "model": model, "parsed": parsed, "parse_error": False,
                    "raw_output": json.dumps(parsed), "request_error": None}) + "\n")
                n += 1
        elif mode == "mitigation":
            for row in read_records(source):
                vis = row.get("visible_instance", {})
                ids = _roster_ids(vis)
                prediction = {"ranked_candidate_ids": ids,
                              "top_recommendations": ids[:3], "answer": "mock"}
                fh.write(json.dumps({
                    "run_instance_id": row["run_instance_id"],
                    "instance_id": row["run_instance_id"],
                    "layer_id": row.get("layer_id"), "model": model,
                    "prediction": prediction, "parsed": prediction,
                    "response": json.dumps(prediction), "raw_output": json.dumps(prediction),
                    "parse_error": False, "request_error": None}) + "\n")
                n += 1
        else:
            raise ValueError(f"unknown mode {mode}")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["benchmark", "mitigation"], required=True)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="mock-model")
    args = ap.parse_args()
    print(json.dumps({"written": run(args.mode, args.source, args.out, args.model)}))


if __name__ == "__main__":
    main()
