# tests/test_mock.py
import json, importlib.util
from pathlib import Path
from safegeo.io import write_parquet

def _load(p):
    spec=importlib.util.spec_from_file_location("m", p); mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod); return mod
M=_load("scripts/make_mock_predictions.py")

def test_benchmark_mode(tmp_path: Path):
    write_parquet(tmp_path/"visible"/"test-0.parquet", [
        {"instance_id":"i1","query_id":"q1","vertical":"office_chair","split":"train",
         "candidate_roster":[{"candidate_id":"q1_ITEM1"},{"candidate_id":"q1_ITEM2"}]}])
    out=tmp_path/"preds.jsonl"
    M.run(mode="benchmark", source=tmp_path/"visible", out=out, model="mock")
    rows=[json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    assert rows[0]["instance_id"]=="i1"
    assert rows[0]["parsed"]["ranking_all_items"][0]=="q1_ITEM1"
    assert rows[0]["parsed"]["top_recommendations"][0]["item_id"]=="q1_ITEM1"
