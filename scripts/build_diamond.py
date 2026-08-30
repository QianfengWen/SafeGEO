#!/usr/bin/env python3
"""Build the published SafeGEO Diamond screening subset.

The subset uses a deterministic, vertical-balanced base-case sample and the
three highest-Target@3 realistic packages on the held-out DeepSeek-V4-Flash
robustness check. Each selected case contributes one of its three sampled
targets, chosen with a fixed seed. Diamond is a fast screening set; the full
benchmark supports population-level averages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_key(value: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}::{value}".encode("utf-8")).hexdigest()


def write_table(root: Path, name: str, table: pa.Table) -> int:
    out = root / name / "test-00000-of-00001.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out, compression="zstd")
    return table.num_rows


def parse_json_cell(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def select_base_cases(data_root: Path, count: int, seed: str) -> tuple[list[str], list[str]]:
    targets = []
    for shard in sorted((data_root / "targets").glob("*.parquet")):
        targets.extend(
            pq.read_table(shard, columns=["base_case_id", "query_id", "vertical"]).to_pylist()
        )
    by_vertical: dict[str, list[dict[str, str]]] = {}
    for row in targets:
        by_vertical.setdefault(str(row["vertical"]), []).append(row)

    base_ids: list[str] = []
    query_ids: list[str] = []
    for vertical, rows in sorted(by_vertical.items()):
        ordered = sorted(rows, key=lambda row: stable_key(str(row["base_case_id"]), seed))
        if len(ordered) < count:
            raise ValueError(f"{vertical} has only {len(ordered)} cases; requested {count}")
        chosen = ordered[:count]
        base_ids.extend(str(row["base_case_id"]) for row in chosen)
        query_ids.extend(str(row["query_id"]) for row in chosen)
    return sorted(base_ids), sorted(query_ids)


def load_sampled_targets(data_root: Path) -> dict[str, list[str]]:
    sampled: dict[str, list[str]] = {}
    for shard in sorted((data_root / "targets").glob("*.parquet")):
        rows = pq.read_table(shard, columns=["base_case_id", "fixed_geo_targets"]).to_pylist()
        for row in rows:
            targets = parse_json_cell(row["fixed_geo_targets"]) or []
            candidate_ids = [str(target["candidate_id"]) for target in targets]
            if len(candidate_ids) != 3 or len(set(candidate_ids)) != 3:
                raise AssertionError(
                    f"{row['base_case_id']} does not contain three unique sampled targets"
                )
            sampled[str(row["base_case_id"])] = candidate_ids
    return sampled


def filtered_table(root: Path, name: str, key_columns: list[str], keep) -> pa.Table:
    """Filter Parquet in small record batches to keep nested packets bounded."""
    selected: list[pa.Table] = []
    schema = None
    for shard in sorted((root / name).glob("*.parquet")):
        parquet_file = pq.ParquetFile(shard)
        schema = parquet_file.schema_arrow
        for batch in parquet_file.iter_batches(batch_size=256, use_threads=False):
            batch_table = pa.Table.from_batches([batch])
            key_rows = batch_table.select(key_columns).to_pylist()
            mask = pa.array([bool(keep(row)) for row in key_rows], type=pa.bool_())
            piece = batch_table.filter(mask)
            if piece.num_rows:
                selected.append(piece)
    if selected:
        return pa.concat_tables(selected)
    if schema is None:
        raise ValueError(f"No Parquet shards found for {name}")
    return pa.Table.from_batches([], schema=schema)


def main() -> None:
    # The nested source packets are large after decompression; a single-threaded
    # streaming build is faster and more predictable on laptop/CI environments.
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--config", type=Path, default=Path("benchmark/config/diamond.json"))
    parser.add_argument("--out", type=Path, default=Path("diamond"))
    args = parser.parse_args()

    config = load_json(args.config)
    base_ids, query_ids = select_base_cases(
        args.data_root,
        int(config["base_cases_per_vertical"]),
        str(config["selection_seed"]),
    )

    base_set = set(base_ids)
    query_set = set(query_ids)
    attack_set = set(config["attack_packages"])
    control_set = set(config["controls"])
    if config.get("target_selection_strategy") != "fixed_seed_one_per_base_case":
        raise ValueError("Unsupported Diamond target_selection_strategy")
    sampled_targets = load_sampled_targets(args.data_root)
    target_candidate_by_case = {
        base_case_id: min(
            sampled_targets[base_case_id],
            key=lambda candidate_id: stable_key(
                candidate_id,
                f"{config['selection_seed']}:target",
            ),
        )
        for base_case_id in base_ids
    }
    selected_labels = filtered_table(
        args.data_root,
        "labels",
        ["base_case_id", "package_id", "attacked_candidate_id"],
        lambda row: str(row.get("base_case_id")) in base_set
        and (
            str(row.get("package_id")) in control_set
            or (
                str(row.get("package_id")) in attack_set
                and str(row.get("attacked_candidate_id"))
                == target_candidate_by_case[str(row.get("base_case_id"))]
            )
        ),
    )
    label_rows = selected_labels.to_pylist()
    instance_ids = sorted(str(row["instance_id"]) for row in label_rows)
    expanded_ids = sorted(str(row["expanded_instance_id"]) for row in label_rows)
    instance_set = set(instance_ids)
    expanded_set = set(expanded_ids)

    controlled_doc_ids: set[str] = set()
    for row in label_rows:
        mapping = parse_json_cell(row.get("controlled_source_candidate_mapping")) or {}
        for source_record in mapping.values():
            doc_id = source_record.get("original_doc_id")
            if doc_id:
                controlled_doc_ids.add(str(doc_id))

    args.out.mkdir(parents=True, exist_ok=True)
    counts = {"labels": write_table(args.out, "labels", selected_labels)}
    counts["visible"] = write_table(
        args.out,
        "visible",
        filtered_table(
            args.data_root,
            "visible",
            ["instance_id"],
            lambda row: str(row.get("instance_id")) in instance_set,
        ),
    )
    counts["instances_manifest"] = write_table(
        args.out,
        "instances_manifest",
        filtered_table(
            args.data_root,
            "instances_manifest",
            ["expanded_instance_id"],
            lambda row: str(row.get("expanded_instance_id")) in expanded_set,
        ),
    )

    for name in ("candidate_quality", "source_annotations", "targets", "quality_distributions", "requirement_annotations"):
        counts[name] = write_table(
            args.out,
            name,
            filtered_table(
                args.data_root,
                name,
                ["query_id"],
                lambda row: str(row.get("query_id")) in query_set,
            ),
        )

    counts["geo_line_annotations"] = write_table(
        args.out,
        "geo_line_annotations",
        filtered_table(
            args.data_root,
            "geo_line_annotations",
            ["doc_id"],
            lambda row: str(row.get("doc_id")) in controlled_doc_ids,
        ),
    )
    counts["controlled_documents"] = write_table(
        args.out,
        "controlled_documents",
        filtered_table(
            args.data_root,
            "controlled_documents",
            ["doc_id"],
            lambda row: str(row.get("doc_id")) in controlled_doc_ids,
        ),
    )

    expected = int(config["expected_counts"]["visible_instances"])
    if counts["visible"] != expected or counts["labels"] != expected:
        raise AssertionError(f"Expected {expected} Diamond instances, got {counts}")
    if counts["instances_manifest"] != expected:
        raise AssertionError("Diamond manifest does not match selected labels")

    manifest = {
        "name": config["name"],
        "version": config["version"],
        "selection_seed": config["selection_seed"],
        "base_case_ids": base_ids,
        "query_ids": query_ids,
        "attack_packages": config["attack_packages"],
        "controls": config["controls"],
        "target_selection_strategy": config["target_selection_strategy"],
        "target_candidate_by_base_case": target_candidate_by_case,
        "row_counts": counts,
        "selection_bias_notice": config["purpose"],
    }
    (args.out / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
