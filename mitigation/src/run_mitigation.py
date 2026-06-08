#!/usr/bin/env python3
"""Run SafeGEO mitigation requests against a vLLM OpenAI endpoint."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Please run this inside the vLLM/OpenAI-client environment.") from exc

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "src"))
from safegeo.io import iter_records
from safegeo.serving import infer_provider, resolve_endpoint, resolve_mode, structured_kwargs, default_headers


def iter_jsonl(path):
    return iter_records(path)


def read_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rid = row.get("run_instance_id") or row.get("instance_id")
            if rid:
                done.add(str(rid))
    return done


def select_rows(path: Path, limit: int | None, start: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(iter_jsonl(path)):
        if idx < start:
            continue
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:].strip()
    if stripped.startswith("```"):
        stripped = stripped[3:].strip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].strip()
    try:
        obj = json.loads(stripped)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    for match in re.finditer(r"\{", stripped):
        start = match.start()
        depth = 0
        in_str = False
        esc = False
        for idx in range(start, len(stripped)):
            ch = stripped[idx]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : idx + 1]
                    try:
                        obj = json.loads(candidate)
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        break
    return None


def is_schema_like(obj: dict[str, Any] | None) -> bool:
    return isinstance(obj, dict) and (
        "ranked_candidate_ids" in obj
        or "ranking_all_items" in obj
        or "top_recommendations" in obj
    )


def load_schema(schema_dir: Path, schema_id: str) -> dict[str, Any]:
    path = schema_dir / f"{schema_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing schema for {schema_id}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_one(
    client: OpenAI,
    row: dict[str, Any],
    model: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    retries: int,
    schema_dir: Path | None,
    mode: str,
) -> dict[str, Any]:
    raw = ""
    parsed: dict[str, Any] | None = None
    error: str | None = None
    started = time.time()
    messages = [
        {"role": "system", "content": row["system_prompt"]},
        {"role": "user", "content": row["user_prompt"]},
    ]
    schema = load_schema(schema_dir, str(row["output_schema_id"])) if (mode == "guided_json" and schema_dir is not None) else None
    struct = structured_kwargs(mode, schema)

    for attempt in range(1, retries + 2):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            }
            kwargs.update(struct)
            response = client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content or ""
            parsed = extract_json_object(raw)
            error = None
            break
        except Exception as exc:  # noqa: BLE001 - preserve backend errors in output rows.
            error = repr(exc)
            if attempt <= retries:
                time.sleep(min(30, 2**attempt))

    ok = is_schema_like(parsed)
    rid = str(row["run_instance_id"])
    return {
        "run_instance_id": rid,
        "instance_id": rid,
        "source_instance_id": row.get("source_instance_id"),
        "layer_id": row.get("layer_id"),
        "layer_name": row.get("layer_name"),
        "output_schema_id": row.get("output_schema_id"),
        "model": model,
        "parsed": parsed if ok else None,
        "prediction": parsed if ok else None,
        "response": raw,
        "raw_output": raw,
        "parse_error": not ok,
        "request_error": error,
        "latency_s": round(time.time() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--provider", choices=["auto", "vllm", "openai", "openrouter"], default="auto")
    parser.add_argument("--json-mode", choices=["auto", "guided_json", "json_object", "off"], default="auto")
    parser.add_argument("--schema-dir", type=Path, default=Path("schemas"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--request-timeout", type=float, default=900.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    rows = select_rows(args.requests, limit=args.limit, start=args.start)
    if args.resume:
        done_ids = read_done_ids(args.output)
        rows = [row for row in rows if str(row["run_instance_id"]) not in done_ids]
    else:
        done_ids = set()
        if args.output.exists():
            args.output.unlink()

    provider = infer_provider(args.base_url) if args.provider == "auto" else args.provider
    base_url, api_key = resolve_endpoint(provider, args.base_url, args.api_key)
    mode = resolve_mode(args.json_mode, provider)
    schema_dir = args.schema_dir if mode == "guided_json" else None
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=args.request_timeout, default_headers=default_headers(provider))
    print(f"provider={provider} json_mode={mode} base_url={base_url} model={args.model}", file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    file_mode = "a" if args.resume and args.output.exists() else "w"
    total = len(rows) + len(done_ids)
    completed = len(done_ids)
    failures = 0
    workers = max(1, args.workers)

    with args.output.open(file_mode, encoding="utf-8") as handle:
        def write_result(result: dict[str, Any]) -> None:
            nonlocal completed, failures
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.flush()
            completed += 1
            if result.get("request_error") or result.get("parse_error"):
                failures += 1
            if completed % 25 == 0 or completed == total:
                print(
                    f"Wrote {completed}/{total} mitigation predictions ({failures} parse/request issues)",
                    file=sys.stderr,
                    flush=True,
                )

        if workers == 1:
            for row in rows:
                write_result(
                    run_one(
                        client,
                        row,
                        args.model,
                        args.temperature,
                        args.top_p,
                        args.max_tokens,
                        args.retries,
                        schema_dir,
                        mode,
                    )
                )
        elif rows:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(
                        run_one,
                        client,
                        row,
                        args.model,
                        args.temperature,
                        args.top_p,
                        args.max_tokens,
                        args.retries,
                        schema_dir,
                        mode,
                    )
                    for row in rows
                ]
                for future in as_completed(futures):
                    write_result(future.result())

    print(json.dumps({"output": str(args.output), "total": total, "new": len(rows), "skipped": len(done_ids)}, indent=2))


if __name__ == "__main__":
    main()
