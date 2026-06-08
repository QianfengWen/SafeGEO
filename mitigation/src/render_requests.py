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


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fmt_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def render_user(template: str, visible: Dict[str, Any]) -> str:
    audited = ""
    if "audited_evidence_sheet" in visible:
        audited = "\n# Audited evidence sheet\n\n" + fmt_json(visible["audited_evidence_sheet"])
    return (template
        .replace("{{user_query}}", str(visible.get("user_query", "")))
        .replace("{{candidate_roster_json}}", fmt_json(visible.get("candidate_roster", [])))
        .replace("{{search_results_json}}", fmt_json(visible.get("search_results", [])))
        .replace("{{audited_evidence_sheet_section}}", audited)
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", type=Path, default=Path("mitigation"), help="Root of this mitigation package")
    ap.add_argument("--runfile", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    user_template = read(args.package_root / "prompts" / "user_template.md")
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
                "user_prompt": render_user(user_template, visible),
            }
            out.write(json.dumps(req, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} requests to {args.out}")

if __name__ == "__main__":
    main()
