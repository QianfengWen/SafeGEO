#!/usr/bin/env python3
"""Align every model-visible query with its identifier-sanitized construction query.

The visible request preserves all decision-relevant requirements and preferences;
structured annotations remain hidden. The command can materialize this invariant
or check it without writing.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq


VISIBLE_VERSION = "source_only_semantics_preserved_query_complex_sources"
VISIBLE_FORMAT = "source_only_semantics_preserved_query_long_sources"


def query_map(dataset_root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for shard in sorted((dataset_root / "targets").glob("*.parquet")):
        for row in pq.read_table(shard, columns=["query_id", "user_query"]).to_pylist():
            mapping[str(row["query_id"])] = str(row["user_query"])
    if not mapping:
        raise ValueError(f"No target queries found under {dataset_root / 'targets'}")
    return mapping


def atomic_write(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        pq.write_table(table, tmp_path, compression="zstd")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def replace_column(table: pa.Table, name: str, values: list[str]) -> pa.Table:
    index = table.schema.get_field_index(name)
    if index < 0:
        raise KeyError(f"Missing required column: {name}")
    return table.set_column(index, name, pa.array(values, type=pa.string()))


def align_visible(dataset_root: Path, mapping: dict[str, str], *, check: bool) -> tuple[int, int]:
    rows = mismatches = 0
    for shard in sorted((dataset_root / "visible").glob("*.parquet")):
        table = pq.read_table(shard)
        query_ids = [str(value) for value in table.column("query_id").to_pylist()]
        expected = [mapping[query_id] for query_id in query_ids]
        current = table.column("user_query").to_pylist()
        mismatches += sum(actual != wanted for actual, wanted in zip(current, expected))
        rows += table.num_rows
        if not check:
            table = replace_column(table, "user_query", expected)
            table = replace_column(table, "version", [VISIBLE_VERSION] * table.num_rows)
            atomic_write(table, shard)
    return rows, mismatches


def align_labels(dataset_root: Path, *, check: bool) -> int:
    rows = 0
    for shard in sorted((dataset_root / "labels").glob("*.parquet")):
        table = pq.read_table(shard)
        rows += table.num_rows
        adjustments: list[str] = []
        for raw in table.column("realism_adjustments").to_pylist():
            record = json.loads(raw)
            record.pop("visible_query_deexplicitized", None)
            record.pop("direct_requirement_language_softened", None)
            record["visible_query_semantics_preserved"] = True
            record["identifier_sanitization_only"] = True
            adjustments.append(json.dumps(record, ensure_ascii=False))
        if not check:
            table = replace_column(table, "visible_format", [VISIBLE_FORMAT] * table.num_rows)
            table = replace_column(table, "realism_adjustments", adjustments)
            atomic_write(table, shard)
    return rows


def validate(dataset_root: Path, mapping: dict[str, str]) -> dict[str, int]:
    total = mismatches = 0
    for shard in sorted((dataset_root / "visible").glob("*.parquet")):
        table = pq.read_table(shard, columns=["query_id", "user_query"])
        for row in table.to_pylist():
            total += 1
            mismatches += int(str(row["user_query"]) != mapping[str(row["query_id"])])
    return {
        "visible_rows": total,
        "unique_construction_queries": len(mapping),
        "request_label_mismatches": mismatches,
    }


def main() -> None:
    # Keep Parquet migration deterministic and lightweight on CI/laptops.
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path, help="Dataset roots, e.g. data sample")
    parser.add_argument("--check", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    reports = {}
    for root in args.roots:
        mapping = query_map(root)
        visible_rows, before = align_visible(root, mapping, check=args.check)
        label_rows = align_labels(root, check=args.check)
        report = validate(root, mapping) if args.check else {
            **validate(root, mapping),
            "mismatches_replaced": before,
        }
        report["label_rows"] = label_rows
        if visible_rows != report["visible_rows"]:
            raise AssertionError("Visible row count changed during alignment")
        reports[str(root)] = report
    print(json.dumps(reports, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
