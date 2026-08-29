#!/usr/bin/env python3
"""Normalize released target metadata to nominal A/B/C slot semantics.

The three fixed targets share one attack and scoring protocol.  Older release
artifacts carried a ``target_difficulty`` key and slot-specific ``target_role``
values inside JSON columns.  This migration removes the former and gives every
target the same neutral role while preserving candidate-level feasibility,
quality, and evidence annotations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


TARGET_COLUMNS = ("fixed_geo_targets", "attacked_target_metadata")
TARGET_CONFIGS = ("targets", "labels", "instances_manifest")
NOMINAL_ROLE = "nominal_fixed_target"


def decode(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def encode(value: Any, original: Any) -> Any:
    if isinstance(original, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def normalize_target(target: dict[str, Any]) -> bool:
    changed = target.pop("target_difficulty", None) is not None
    if target.get("target_role") != NOMINAL_ROLE:
        target["target_role"] = NOMINAL_ROLE
        changed = True
    return changed


def normalize_cell(value: Any) -> tuple[Any, bool]:
    if value is None:
        return value, False
    decoded = decode(value)
    changed = False
    if isinstance(decoded, list):
        for target in decoded:
            if not isinstance(target, dict):
                raise TypeError(f"Expected target mapping, got {type(target).__name__}")
            changed |= normalize_target(target)
    elif isinstance(decoded, dict):
        changed = normalize_target(decoded)
    else:
        raise TypeError(f"Expected target mapping or list, got {type(decoded).__name__}")
    return encode(decoded, value), changed


def read_columnwise(path: Path) -> pa.Table:
    """Read one column at a time to avoid nested-column decoder spikes."""
    parquet_file = pq.ParquetFile(path)
    arrays = [
        parquet_file.read(columns=[name], use_threads=False)[name]
        for name in parquet_file.schema_arrow.names
    ]
    return pa.Table.from_arrays(arrays, schema=parquet_file.schema_arrow)


def inspect_table(table: pa.Table) -> list[str]:
    errors: list[str] = []
    for column_name in TARGET_COLUMNS:
        if column_name not in table.column_names:
            continue
        for row_index, value in enumerate(table[column_name].to_pylist()):
            if value is None:
                continue
            decoded = decode(value)
            targets = decoded if isinstance(decoded, list) else [decoded]
            for target in targets:
                if "target_difficulty" in target:
                    errors.append(f"{column_name}[{row_index}] retains target_difficulty")
                if target.get("target_role") != NOMINAL_ROLE:
                    errors.append(f"{column_name}[{row_index}] has non-nominal target_role")
    return errors


def migrate_file(path: Path, *, check: bool) -> bool:
    table = read_columnwise(path)
    changed = False
    for column_name in TARGET_COLUMNS:
        if column_name not in table.column_names:
            continue
        original_values = table[column_name].to_pylist()
        normalized_values: list[Any] = []
        column_changed = False
        for value in original_values:
            normalized, value_changed = normalize_cell(value)
            normalized_values.append(normalized)
            column_changed |= value_changed
        if column_changed:
            changed = True
            index = table.schema.get_field_index(column_name)
            field = table.schema.field(index)
            table = table.set_column(index, field, pa.array(normalized_values, type=field.type))

    errors = inspect_table(table)
    if errors:
        raise AssertionError(f"{path}: {errors[0]}")
    if check or not changed:
        return changed

    temporary = path.with_suffix(".tmp.parquet")
    pq.write_table(table, temporary, compression="zstd")
    rewritten = read_columnwise(temporary)
    if rewritten.num_rows != table.num_rows or rewritten.schema != table.schema:
        temporary.unlink(missing_ok=True)
        raise AssertionError(f"Validation failed for rewritten {path}")
    errors = inspect_table(rewritten)
    if errors:
        temporary.unlink(missing_ok=True)
        raise AssertionError(f"{path}: {errors[0]}")
    temporary.replace(path)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        default=[Path("data"), Path("sample"), Path("diamond")],
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    changed_files: list[str] = []
    for root in args.roots:
        for config in TARGET_CONFIGS:
            for path in sorted((root / config).glob("*.parquet")):
                if migrate_file(path, check=args.check):
                    changed_files.append(str(path))
                    print(f"normalized {path}", flush=True)
    if args.check and changed_files:
        raise SystemExit(
            "Target metadata is not normalized in: " + ", ".join(changed_files)
        )
    print(
        "target metadata normalized"
        if changed_files
        else "target metadata already normalized"
    )


if __name__ == "__main__":
    main()
