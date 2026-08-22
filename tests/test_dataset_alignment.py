from pathlib import Path

import pyarrow.parquet as pq


def _query_map(root: Path) -> dict[str, str]:
    result = {}
    for shard in sorted((root / "targets").glob("*.parquet")):
        for row in pq.read_table(shard, columns=["query_id", "user_query"]).to_pylist():
            result[str(row["query_id"])] = str(row["user_query"])
    return result


def test_sample_visible_queries_preserve_construction_request():
    root = Path("sample")
    expected = _query_map(root)
    seen = set()
    for shard in sorted((root / "visible").glob("*.parquet")):
        rows = pq.read_table(shard, columns=["query_id", "user_query", "version"]).to_pylist()
        for row in rows:
            query_id = str(row["query_id"])
            seen.add(query_id)
            assert row["user_query"] == expected[query_id]
            assert row["version"] == "source_only_semantics_preserved_query_complex_sources"
    assert seen == set(expected)


def test_full_query_audit_report_records_zero_mismatch():
    report = __import__("json").loads(
        Path("benchmark/config/source_only_validation_report.json").read_text(encoding="utf-8")
    )
    audit = report["query_semantics_audit"]
    assert audit["matched_queries"] == 600
    assert audit["mismatched_queries"] == 0
    assert audit["matched_visible_rows"] == 40_800
    assert audit["mismatched_visible_rows"] == 0

