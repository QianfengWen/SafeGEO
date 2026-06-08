import json
from pathlib import Path

from safegeo.taxonomy import (
    ATTACK_VECTOR_KEYS,
    LAYER_NAMES,
    PRIMITIVES,
    REALISTIC_PACKAGES,
)


def test_new_attack_taxonomy_terms_and_realistic_packages():
    assert ATTACK_VECTOR_KEYS == ("A", "U", "C", "R", "E", "S", "M")
    assert PRIMITIVES == {
        "A": "authority_laundering",
        "U": "unsupported_fit_claim",
        "C": "caveat_omission",
        "R": "relevance_flooding",
        "E": "evidence_padding",
        "S": "salience_manipulation",
        "M": "model_directed_instruction",
    }
    assert REALISTIC_PACKAGES == [
        "caveat_burial_faq",
        "popularity_heavy_profile",
        "citation_padded_note",
        "independent_buyer_guide",
        "false_fit_checklist",
        "selective_comparison_note",
        "ai-directed_source_text",
        "full_stack_realistic_geo",
    ]


def test_attack_schema_uses_new_primitive_codes_and_package_ids():
    schema = json.loads(Path("benchmark/config/attack_package_schema.json").read_text())
    packages = {pkg["package_id"]: pkg for pkg in schema["attack_packages"]}

    assert schema["primitive_definitions"] == PRIMITIVES
    assert set(packages) == {
        "A_only_geo",
        "U_only_geo",
        "C_only_geo",
        "R_only_geo",
        "E_only_geo",
        "S_only_geo",
        "M_only_geo",
        "content_bundle_geo",
        "epistemic_bundle_geo",
        "model_facing_bundle_geo",
        "content_epistemic_geo",
        "content_model_facing_geo",
        "epistemic_model_facing_geo",
        "full_stack_diagnostic_geo",
        *REALISTIC_PACKAGES,
    }
    assert packages["content_bundle_geo"]["active_primitives"] == ["U", "C", "R"]
    assert packages["epistemic_bundle_geo"]["active_primitives"] == ["A", "E"]
    assert packages["full_stack_realistic_geo"]["active_primitives"] == ["A", "U", "C", "R", "E", "S", "M"]


def test_mitigation_layer_names_use_new_terms():
    assert LAYER_NAMES["L2"] == "L2_rationale_elicitation_mitigation"
    assert LAYER_NAMES["L4"] == "L4_context_balancing_mitigation"
    assert LAYER_NAMES["L5"] == "L5_instruction_filtering_mitigation"
