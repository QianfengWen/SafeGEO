import importlib.util
from pathlib import Path

import pytest


def _load(path: str):
    module_path = Path(path)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "module_path",
    ["benchmark/src/score_safegeo.py", "mitigation/src/score_mitigation.py"],
)
def test_unverified_requirement_is_evidence_based_not_slot_based(module_path: str):
    scorer = _load(module_path)
    without_refutation = {
        "target_slot": "A",
        "primary_exploitable_gap": {"paired_refuting_lines": []},
    }
    with_refutation = {
        "target_slot": "C",
        "primary_exploitable_gap": {
            "paired_refuting_lines": [{"doc_id": "SRC001", "line_id": 2}]
        },
    }

    assert scorer.target_has_unverified_requirement(without_refutation)
    assert not scorer.target_has_unverified_requirement(with_refutation)
    assert not scorer.target_has_unverified_requirement(None)
