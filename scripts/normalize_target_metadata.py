#!/usr/bin/env python3
"""Migrate released artifacts to candidate-ID-based target metadata.

Each case contains three targets sampled without replacement and held fixed for
paired evaluation. Candidate IDs already identify those targets, so the public
schema does not need a second slot label. This migration removes slot, role,
and difficulty fields; converts source mappings to candidate-keyed mappings;
and keeps all candidate-specific quality and evidence annotations.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


CONFIGS = (
    "targets",
    "labels",
    "instances_manifest",
    "geo_line_annotations",
    "controlled_documents",
)
LEGACY_SLOTS = ("A", "B", "C")
REMOVED_KEYS = {"target_slot", "target_role", "target_difficulty"}
COLUMN_RENAMES = {
    "controlled_source_slot_mapping": "controlled_source_candidate_mapping",
    "controlled_source_slots": "controlled_sources",
    "target_slot": "candidate_id",
}
DROPPED_COLUMNS = {"attacked_target_slot", "target_role", "target_difficulty"}
LEGACY_ID_RE = re.compile(r"__(?:TARGET|target)_[ABC]__")


def decode(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def read_columnwise(path: Path) -> pa.Table:
    """Read one column at a time to bound nested-column decoder memory."""
    parquet_file = pq.ParquetFile(path)
    arrays = [
        parquet_file.read(columns=[name], use_threads=False)[name]
        for name in parquet_file.schema_arrow.names
    ]
    return pa.Table.from_arrays(arrays, schema=parquet_file.schema_arrow)


def json_columns(schema: pa.Schema) -> set[str]:
    metadata = schema.metadata or {}
    raw = metadata.get(b"safegeo_json_columns")
    return set(json.loads(raw.decode())) if raw else set()


def load_candidate_maps(root: Path) -> dict[str, dict[str, str]]:
    """Recover the legacy slot-to-candidate map before dropping slot fields.

    The list-order fallback makes the migration idempotent and also supports a
    partially migrated checkout.
    """
    maps: dict[str, dict[str, str]] = {}
    for path in sorted((root / "targets").glob("*.parquet")):
        table = read_columnwise(path)
        base_ids = table["base_case_id"].to_pylist()
        target_cells = table["fixed_geo_targets"].to_pylist()
        for base_case_id, cell in zip(base_ids, target_cells):
            targets = decode(cell) or []
            if len(targets) != 3:
                raise AssertionError(f"{root}: {base_case_id} has {len(targets)} targets")
            mapping: dict[str, str] = {}
            for index, target in enumerate(targets):
                slot = str(target.get("target_slot") or LEGACY_SLOTS[index])
                mapping[slot] = str(target["candidate_id"])
            if set(mapping) != set(LEGACY_SLOTS) or len(set(mapping.values())) != 3:
                raise AssertionError(f"{root}: invalid target mapping for {base_case_id}")
            maps[str(base_case_id)] = mapping
    return maps


def candidate_token(candidate_id: str) -> str:
    return candidate_id.rsplit("_", 1)[-1]


def replace_legacy_identifiers(value: str, candidate_map: dict[str, str]) -> str:
    updated = value.replace("controlled_target_slot", "controlled_target_source")
    for slot, candidate_id in candidate_map.items():
        token = candidate_token(candidate_id)
        updated = updated.replace(f"__TARGET_{slot}__", f"__TARGET_{token}__")
        updated = updated.replace(f"__target_{slot}__", f"__target_{token}__")
        if ".example/" in updated:
            updated = updated.replace(f"-{slot.lower()}-", f"-{token.lower()}-")
    return updated


def normalize_value(value: Any, candidate_map: dict[str, str]) -> Any:
    if isinstance(value, str):
        return replace_legacy_identifiers(value, candidate_map)
    if isinstance(value, list):
        return [normalize_value(item, candidate_map) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if key in REMOVED_KEYS:
                continue
            new_key = replace_legacy_identifiers(str(key), candidate_map)
            normalized[new_key] = normalize_value(child, candidate_map)
        return normalized
    return value


def transform_record(
    record: dict[str, Any],
    candidate_maps: dict[str, dict[str, str]],
) -> dict[str, Any]:
    base_case_id = record.get("base_case_id") or record.get("query_id")
    hidden = record.get("hidden_geo_document_metadata")
    if base_case_id is None and isinstance(hidden, dict):
        base_case_id = hidden.get("base_case_id") or hidden.get("query_id")
    candidate_map = candidate_maps.get(str(base_case_id), {})

    transformed = dict(record)
    legacy_target_slot = transformed.pop("target_slot", None)
    if legacy_target_slot is not None:
        transformed["candidate_id"] = candidate_map[str(legacy_target_slot)]

    transformed.pop("attacked_target_slot", None)
    transformed.pop("target_role", None)
    transformed.pop("target_difficulty", None)

    old_mapping = transformed.pop("controlled_source_slot_mapping", None)
    if old_mapping is not None:
        transformed["controlled_source_candidate_mapping"] = {
            candidate_map[str(slot)]: mapping
            for slot, mapping in (old_mapping or {}).items()
        }

    old_sources = transformed.pop("controlled_source_slots", None)
    if old_sources is not None:
        transformed["controlled_sources"] = {
            candidate_map[str(slot)]: source
            for slot, source in (old_sources or {}).items()
        }

    if "target_metadata_source" in transformed:
        transformed["target_metadata_source"] = "targets"

    transformed = normalize_value(transformed, candidate_map)

    targets = transformed.get("fixed_geo_targets") or []
    if targets:
        candidate_ids = [str(target["candidate_id"]) for target in targets]
        if len(candidate_ids) != 3 or len(set(candidate_ids)) != 3:
            raise AssertionError(f"{base_case_id}: expected three unique sampled targets")
    attacked_candidate_id = transformed.get("attacked_candidate_id")
    if attacked_candidate_id is not None and targets:
        if str(attacked_candidate_id) not in {str(target["candidate_id"]) for target in targets}:
            raise AssertionError(f"{base_case_id}: attacked candidate is not a sampled target")
    return transformed


def find_forbidden(value: Any, path: str = "") -> str | None:
    if isinstance(value, str):
        if LEGACY_ID_RE.search(value):
            return f"{path} contains a legacy target-slot identifier"
        return None
    if isinstance(value, list):
        for index, child in enumerate(value):
            error = find_forbidden(child, f"{path}[{index}]")
            if error:
                return error
        return None
    if isinstance(value, dict):
        for key, child in value.items():
            if key in REMOVED_KEYS or key in {
                "attacked_target_slot",
                "controlled_source_slot_mapping",
                "controlled_source_slots",
            }:
                return f"{path}.{key} retains a legacy target field"
            error = find_forbidden(child, f"{path}.{key}")
            if error:
                return error
    return None


def output_columns(schema: pa.Schema) -> list[tuple[str, str, pa.Field]]:
    columns: list[tuple[str, str, pa.Field]] = []
    for field in schema:
        old_name = field.name
        if old_name in DROPPED_COLUMNS:
            continue
        new_name = COLUMN_RENAMES.get(old_name, old_name)
        columns.append(
            (
                old_name,
                new_name,
                pa.field(new_name, field.type, field.nullable, field.metadata),
            )
        )
    return columns


def migrate_file(
    path: Path,
    candidate_maps: dict[str, dict[str, str]],
    *,
    check: bool,
) -> bool:
    parquet_file = pq.ParquetFile(path)
    source_schema = parquet_file.schema_arrow
    old_json_columns = json_columns(source_schema)
    column_specs = output_columns(source_schema)
    fields = [field for _old_name, _new_name, field in column_specs]
    metadata = dict(source_schema.metadata or {})
    updated_json_columns = [
        COLUMN_RENAMES.get(name, name)
        for name in old_json_columns
        if name not in DROPPED_COLUMNS
    ]
    if updated_json_columns:
        metadata[b"safegeo_json_columns"] = json.dumps(sorted(updated_json_columns)).encode()
    migrated_schema = pa.schema(fields, metadata=metadata)

    changed = False
    row_offset = 0
    temporary = path.with_suffix(".candidate-id.tmp.parquet")
    writer = None if check else pq.ParquetWriter(temporary, migrated_schema, compression="zstd")
    try:
        for batch in parquet_file.iter_batches(batch_size=8192, use_threads=False):
            batch_table = pa.Table.from_batches([batch])
            source_values = {
                name: batch_table[name].to_pylist()
                for name in source_schema.names
            }
            output_values = {new_name: [] for _old_name, new_name, _field in column_specs}
            for local_index in range(batch_table.num_rows):
                record: dict[str, Any] = {}
                for name in source_schema.names:
                    value = source_values[name][local_index]
                    record[name] = (
                        decode(value)
                        if name in old_json_columns and value is not None
                        else value
                    )
                transformed = transform_record(record, candidate_maps)
                changed |= transformed != record
                error = find_forbidden(transformed, f"row[{row_offset + local_index}]")
                if error:
                    raise AssertionError(f"{path}: {error}")
                for old_name, new_name, _field in column_specs:
                    value = transformed.get(new_name)
                    if old_name in old_json_columns and value is not None:
                        value = json.dumps(
                            value,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    output_values[new_name].append(value)
            if writer is not None:
                arrays = [
                    pa.array(output_values[new_name], type=field.type)
                    for _old_name, new_name, field in column_specs
                ]
                writer.write_table(pa.Table.from_arrays(arrays, schema=migrated_schema))
            row_offset += batch_table.num_rows
    finally:
        if writer is not None:
            writer.close()

    if check:
        return changed
    if not changed:
        temporary.unlink(missing_ok=True)
        return False
    rewritten = pq.ParquetFile(temporary)
    if rewritten.metadata.num_rows != parquet_file.metadata.num_rows or rewritten.schema_arrow != migrated_schema:
        temporary.unlink(missing_ok=True)
        raise AssertionError(f"Validation failed for rewritten {path}")
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
    maps_by_root = {root: load_candidate_maps(root) for root in args.roots}
    changed_files: list[str] = []
    for root in args.roots:
        for config in CONFIGS:
            for path in sorted((root / config).glob("*.parquet")):
                if migrate_file(path, maps_by_root[root], check=args.check):
                    changed_files.append(str(path))
                    print(f"normalized {path}", flush=True)
    if args.check and changed_files:
        raise SystemExit("Legacy target fields remain in: " + ", ".join(changed_files))
    print("target metadata normalized" if changed_files else "target metadata already normalized")


if __name__ == "__main__":
    main()
