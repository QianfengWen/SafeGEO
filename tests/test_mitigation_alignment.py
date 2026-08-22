import importlib.util
from pathlib import Path

from safegeo.io import read_records
from safegeo.prompts import build_recommendation_user_prompt, has_required_response_fields
from safegeo.taxonomy import LAYER_NAMES, LAYER_SCHEMAS


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILD = _load("safegeo_build_runfiles", "mitigation/src/build_runfiles.py")
BENCHMARK = _load("safegeo_benchmark_runner", "benchmark/src/run_safegeo.py")
RUN = _load("safegeo_mitigation_runner", "mitigation/src/run_mitigation.py")


def test_l0_reuses_original_benchmark_prompt_and_schema():
    mitigation_root = Path("mitigation")
    l0_prompt = (mitigation_root / BUILD.PROMPT_FILES["L0"]).resolve()
    benchmark_prompt = Path("benchmark/prompts/safegeo_recommendation_system.txt").resolve()
    assert l0_prompt == benchmark_prompt
    assert l0_prompt.read_bytes() == benchmark_prompt.read_bytes()
    assert BUILD.SCHEMA_IDS["L0"] == "benchmark_prediction_schema"
    assert RUN.load_schema(None, "benchmark_prediction_schema")


def test_all_layers_use_only_the_canonical_output_contract():
    prompt_paths = [
        Path("mitigation") / prompt_path
        for prompt_path in BUILD.PROMPT_FILES.values()
    ]
    for prompt_path in prompt_paths:
        text = prompt_path.resolve().read_text(encoding="utf-8")
        assert "Return only JSON matching the response schema" in text

    complete = {
        "ranking_all_items": [],
        "top_recommendations": [],
        "constraint_audit": [],
        "rejected_or_caveated_items": [],
        "source_assessment": [],
    }
    assert has_required_response_fields(complete)
    assert not has_required_response_fields({"ranking_all_items": []})
    assert not has_required_response_fields(complete, require_evidence_checks=True)
    complete["evidence_checks"] = []
    assert has_required_response_fields(complete, require_evidence_checks=True)


def test_benchmark_and_mitigation_share_user_serialization():
    row = read_records("sample/visible")[0]
    expected = build_recommendation_user_prompt(row)
    assert BENCHMARK.build_recommendation_user_prompt(row) == expected


def test_layers_do_not_mutate_visible_packet():
    row = read_records("sample/visible")[0]
    for layer in LAYER_NAMES:
        transformed = BUILD.transform_visible(row, {}, layer, "A")
        assert transformed == row
        assert transformed is not row
        assert transformed["search_results"] is not row["search_results"]


def test_layer_ids_and_schemas_have_one_shared_definition():
    assert BUILD.LAYER_IDS == LAYER_NAMES
    assert BUILD.SCHEMA_IDS == LAYER_SCHEMAS
    assert LAYER_NAMES["L3"] == "L3_evidence_breakdown_mitigation"
    assert LAYER_SCHEMAS == {
        "L0": "benchmark_prediction_schema",
        "L1": "benchmark_prediction_schema",
        "L2": "benchmark_prediction_schema",
        "L3": "evidence_breakdown_schema",
        "L4": "benchmark_prediction_schema",
        "L5": "benchmark_prediction_schema",
    }


def test_l3_extends_benchmark_schema_only_with_evidence_checks():
    base = RUN.load_schema(None, "benchmark_prediction_schema")
    l3 = RUN.load_schema(None, "evidence_breakdown_schema")
    assert "evidence_checks" not in base["properties"]
    assert "evidence_checks" in l3["properties"]
    assert next(iter(l3["properties"])) == "evidence_checks"
    assert l3["required"][0] == "evidence_checks"
    assert set(l3["properties"]) == set(base["properties"]) | {"evidence_checks"}
    assert set(l3["required"]) == set(base["required"]) | {"evidence_checks"}
