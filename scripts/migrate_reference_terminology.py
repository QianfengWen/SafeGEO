#!/usr/bin/env python3
"""Align released Parquet terminology with the camera-ready paper.

The original artifact used ``verified_utility_score`` for a pipeline-generated
benchmark label. The camera-ready release calls this quantity
``benchmark_reference_utility`` and reserves verification language for evidence
relations. This migration updates the public column, nested target records, and
the corresponding explanatory text without changing numeric values.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


COLUMN_RENAMES = {
    "verified_utility_score": "benchmark_reference_utility",
    "canonical_utility_score_original": "pipeline_utility_score_original",
}

KEY_RENAMES = {
    "verified_utility_score": "benchmark_reference_utility",
    "canonical_utility_score_original": "pipeline_utility_score_original",
}

TEXT_REPLACEMENTS = {
    "under canonical truth": "under the benchmark-reference annotations",
    "under the canonical truth": "under the benchmark-reference annotations",
    "verified utility score": "benchmark-reference utility",
    "verified utility": "benchmark-reference utility",
}


def transform(value: Any) -> Any:
    if isinstance(value, dict):
        return {KEY_RENAMES.get(str(key), str(key)): transform(item) for key, item in value.items()}
    if isinstance(value, list):
        return [transform(item) for item in value]
    if isinstance(value, str):
        result = value
        for old, new in TEXT_REPLACEMENTS.items():
            result = result.replace(old, new)
        return result
    return value


def transform_json_cell(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if not stripped.startswith(("{", "[")):
        return transform(value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return transform(value)
    return json.dumps(transform(parsed), ensure_ascii=False)


def atomic_write(table: pa.Table, path: Path) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        pq.write_table(table, temp_path, compression="zstd")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def migrate_file(path: Path, *, check: bool) -> dict[str, int]:
    table = pq.read_table(path)
    original_names = list(table.column_names)
    renamed_names = [COLUMN_RENAMES.get(name, name) for name in original_names]
    renamed_columns = sum(a != b for a, b in zip(original_names, renamed_names))

    changed_cells = 0
    arrays: list[pa.Array | pa.ChunkedArray] = []
    for name in original_names:
        column = table[name]
        if pa.types.is_string(column.type) or pa.types.is_large_string(column.type):
            before = column.to_pylist()
            after = [transform_json_cell(value) for value in before]
            changed_cells += sum(old != new for old, new in zip(before, after))
            arrays.append(pa.array(after, type=column.type))
        else:
            arrays.append(column)

    migrated = pa.Table.from_arrays(arrays, names=renamed_names)
    migrated = migrated.replace_schema_metadata(table.schema.metadata)
    if (renamed_columns or changed_cells) and not check:
        atomic_write(migrated, path)
    return {
        "rows": table.num_rows,
        "renamed_columns": renamed_columns,
        "changed_cells": changed_cells,
    }


def audit_root(root: Path) -> dict[str, int]:
    old_columns = old_nested_keys = old_phrases = rows = 0
    for path in sorted(root.glob("*/*.parquet")):
        table = pq.read_table(path)
        rows += table.num_rows
        old_columns += sum(name in COLUMN_RENAMES for name in table.column_names)
        for name in table.column_names:
            column = table[name]
            if not (pa.types.is_string(column.type) or pa.types.is_large_string(column.type)):
                continue
            for value in column.to_pylist():
                if not isinstance(value, str):
                    continue
                old_nested_keys += value.count('"verified_utility_score"')
                old_nested_keys += value.count('"canonical_utility_score_original"')
                lowered = value.lower()
                old_phrases += lowered.count("canonical truth")
                old_phrases += lowered.count("verified utility")
    return {
        "rows_scanned": rows,
        "old_columns": old_columns,
        "old_nested_keys": old_nested_keys,
        "old_phrases": old_phrases,
    }


def main() -> None:
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path, help="Dataset roots, e.g. data sample")
    parser.add_argument("--check", action="store_true", help="Audit without writing")
    args = parser.parse_args()

    report: dict[str, Any] = {}
    for root in args.roots:
        file_report = {}
        for path in sorted(root.glob("*/*.parquet")):
            result = migrate_file(path, check=args.check)
            if result["renamed_columns"] or result["changed_cells"]:
                file_report[str(path.relative_to(root))] = result
        report[str(root)] = {
            "files": file_report,
            "audit": audit_root(root),
        }
    print(json.dumps(report, indent=2, sort_keys=True))

    failures = [
        root
        for root, result in report.items()
        if result["audit"]["old_columns"]
        or result["audit"]["old_nested_keys"]
        or result["audit"]["old_phrases"]
    ]
    if failures:
        raise SystemExit(f"Legacy reference terminology remains under: {', '.join(failures)}")


if __name__ == "__main__":
    main()
