from pathlib import Path
from safegeo.io import read_records, write_parquet

def _norm(recs):
    return [{k: v for k, v in r.items() if v is not None} for r in recs]

def test_roundtrip_preserves_nested_and_empty(tmp_path: Path):
    records = [
        {"id": "a", "n": 1, "flag": True, "vec": {"P": 0, "A": 1},
         "mapping": {"A": {"doc": "SRC001"}}, "lines": [{"line_id": 1, "t": "x"}],
         "empty_dict": {}, "empty_list": []},
        {"id": "b", "n": None, "flag": False, "vec": {"P": 1, "A": 0},
         "mapping": {}, "lines": [], "note": "only-in-b"},
    ]
    p = tmp_path / "test-0.parquet"
    write_parquet(p, records)
    back = read_records(p)
    assert _norm(back) == _norm(records)
    # empty containers preserved exactly (not dropped, not null-filled)
    assert back[0]["empty_dict"] == {} and back[0]["empty_list"] == []
    assert back[1]["mapping"] == {}

def test_reads_directory_of_shards(tmp_path: Path):
    write_parquet(tmp_path / "test-0.parquet", [{"id": "a"}])
    write_parquet(tmp_path / "test-1.parquet", [{"id": "b"}])
    ids = sorted(r["id"] for r in read_records(tmp_path))
    assert ids == ["a", "b"]

def test_reads_jsonl(tmp_path: Path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"id": "a"}\n\n{"id": "b"}\n', encoding="utf-8")
    assert [r["id"] for r in read_records(p)] == ["a", "b"]
