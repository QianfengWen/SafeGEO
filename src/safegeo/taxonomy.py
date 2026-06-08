"""Shared SafeGEO taxonomy constants."""
from __future__ import annotations

CONTROL_PACKAGES = {"original_no_geo_control", "all_truthful_target_control"}

REALISTIC_PACKAGES = [
    "caveat_burial_faq", "popularity_heavy_profile", "citation_padded_note",
    "independent_buyer_guide", "false_fit_checklist", "selective_comparison_note",
    "ai-directed_source_text", "full_stack_realistic_geo",
]

CITATION_FOCUS_PACKAGES = {
    "A_only_geo", "U_only_geo", "C_only_geo", "E_only_geo", "M_only_geo",
    "false_fit_checklist", "selective_comparison_note", "ai-directed_source_text",
    "full_stack_realistic_geo",
}

ATTACK_VECTOR_KEYS = ("A", "U", "C", "R", "E", "S", "M")

PRIMITIVES = {
    "A": "authority_laundering", "U": "unsupported_fit_claim",
    "C": "caveat_omission", "R": "relevance_flooding",
    "E": "evidence_padding", "S": "salience_manipulation",
    "M": "model_directed_instruction",
}

LAYER_NAMES = {
    "L0": "L0_source_only_baseline", "L1": "L1_prompt_mitigation",
    "L2": "L2_rationale_elicitation_mitigation", "L3": "L3_audited_evidence_sheet_mitigation",
    "L4": "L4_context_balancing_mitigation", "L5": "L5_instruction_filtering_mitigation",
}

LAYER_SCHEMAS = {
    "L0": "simple_recommendation_schema", "L1": "simple_recommendation_schema",
    "L2": "accountable_recommendation_schema", "L3": "simple_recommendation_schema",
    "L4": "simple_recommendation_schema", "L5": "simple_recommendation_schema",
}
