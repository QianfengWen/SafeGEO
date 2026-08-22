#!/usr/bin/env python3
"""Render model request payloads from mitigation runfiles.

This creates a JSONL with one request per run instance:
  {run_instance_id, layer_id, system_prompt, user_prompt, output_schema_id}

It does not call any model API.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Dict, Any

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "src"))
from safegeo.prompts import build_recommendation_user_prompt


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", type=Path, default=Path("mitigation"), help="Root of this mitigation package")
    ap.add_argument("--runfile", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    prompt_cache: Dict[str, str] = {}
    n = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.runfile.open("r", encoding="utf-8") as f, args.out.open("w", encoding="utf-8") as out:
        for line in f:
            if args.limit is not None and n >= args.limit:
                break
            row = json.loads(line)
            prompt_file = row["prompt_file"]
            if prompt_file not in prompt_cache:
                prompt_cache[prompt_file] = read(args.package_root / prompt_file)
            visible = row["visible_instance"]
            req = {
                "run_instance_id": row["run_instance_id"],
                "source_instance_id": row["source_instance_id"],
                "layer_id": row["layer_id"],
                "layer_name": row["layer_name"],
                "output_schema_id": row["output_schema_id"],
                "system_prompt": prompt_cache[prompt_file],
                # The user message is byte-for-byte the benchmark request for
                # the same visible row.  Layer differences live only in the
                # system prompt (and L3's evidence-check output schema).
                "user_prompt": build_recommendation_user_prompt(visible),
            }
            out.write(json.dumps(req, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} requests to {args.out}")

if __name__ == "__main__":
    main()
