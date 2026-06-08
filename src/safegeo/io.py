"""Parquet-aware, fidelity-preserving record I/O for the SafeGEO release.

Records are plain dicts. Scalar fields become native Parquet columns (queryable
in the HF viewer); list/dict fields are JSON-encoded into string columns. The set
of JSON-encoded columns is stored in the Parquet file-schema metadata under
`safegeo_json_columns`, so read_records restores records faithfully.

Fidelity contract: read_records(write_parquet(R)) equals R after dropping keys
whose value is None (the pipeline reads optional fields via .get(...)). Empty
dicts/lists and present scalars are preserved exactly.

Also reads plain .jsonl and .jsonl.gz (runtime prediction files).
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

META_KEY = b"safegeo_json_columns"


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    # For gzip inputs, fully stream-decompress to a temporary plain-text file in
    # bounded (1 MB) chunks *before* parsing any records. The inputs are
    # single-member, valid gzip files, but iterating records directly off a live
    # gzip read-buffer intermittently raises a BadGzipFile/CRC error mid-stream on
    # large files in this environment (a non-deterministic Python-gzip streaming
    # flake). Draining the whole stream up front via copyfileobj verifies the CRC
    # eagerly, so a bad read fails loudly here rather than silently truncating.
    # The decompressed bytes are byte-identical to the original; this changes only
    # how the file is read. The plain-.jsonl path is unchanged.
    if path.suffix == ".gz":
        tmp = tempfile.NamedTemporaryFile(prefix="safegeo_io_", suffix=".jsonl", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            with gzip.open(path, "rb") as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            with open(tmp_path, "rt", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    else:
        with open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _read_parquet_file(path: Path) -> list[dict[str, Any]]:
    table = pq.read_table(path)
    meta = table.schema.metadata or {}
    json_cols = set(json.loads(meta[META_KEY].decode())) if META_KEY in meta else set()
    columns = {name: table.column(name).to_pylist() for name in table.column_names}
    records: list[dict[str, Any]] = []
    for i in range(table.num_rows):
        rec: dict[str, Any] = {}
        for name, values in columns.items():
            val = values[i]
            if name in json_cols:
                if val is None:
                    continue  # key was absent in original record
                rec[name] = json.loads(val)
            else:
                if val is None:
                    continue  # absent or None-valued scalar; pipeline treats alike
                rec[name] = val
        records.append(rec)
    return records


def read_records(path: str | Path) -> list[dict[str, Any]]:
    """Read records from a Parquet file, a directory of Parquet shards, or JSONL(.gz)."""
    path = Path(path)
    if path.is_dir():
        out: list[dict[str, Any]] = []
        for shard in sorted(path.glob("*.parquet")):
            out.extend(_read_parquet_file(shard))
        return out
    if path.suffix == ".parquet":
        return _read_parquet_file(path)
    return list(_iter_jsonl(path))


def iter_records(path: str | Path) -> Iterable[dict[str, Any]]:
    """Streaming iteration for JSONL(.gz); Parquet is read fully then yielded."""
    path = Path(path)
    if not path.is_dir() and path.suffix in (".jsonl", ".gz"):
        yield from _iter_jsonl(path)
    else:
        yield from read_records(path)


def write_parquet(path: str | Path, records: list[dict[str, Any]], *, compression: str = "zstd") -> int:
    """Write records to Parquet with fidelity-preserving column handling.

    A column is JSON-encoded (string) if any record has a list/dict value for it;
    otherwise it stays a native scalar column. JSON columns store json.dumps(value)
    when the key is present (including None/empty) and null when the key is absent.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns: list[str] = []
    for rec in records:
        for k in rec:
            if k not in columns:
                columns.append(k)
    json_cols = [
        name for name in columns
        if any(isinstance(rec.get(name), (list, dict)) for rec in records)
    ]
    arrays = {}
    for name in columns:
        if name in json_cols:
            col = [json.dumps(rec[name], ensure_ascii=False) if name in rec else None for rec in records]
            arrays[name] = pa.array(col, type=pa.string())
        else:
            arrays[name] = pa.array([rec.get(name) for rec in records])
    table = pa.table(arrays).replace_schema_metadata({META_KEY.decode(): json.dumps(json_cols)})
    pq.write_table(table, path, compression=compression)
    return len(records)
