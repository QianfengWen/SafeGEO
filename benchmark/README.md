# SafeGEO Benchmark

The benchmark measures whether a recommendation agent preserves utility-aligned
recommendations when the sources it reads have been rewritten by a GEO adversary. A model is
served behind an OpenAI-compatible endpoint (for example vLLM), asked to rank a candidate
roster using only the provided sources, and scored against the hidden ground truth.

The central question is whether GEO attacks move a flawed target into the user's decision
set. The benchmark answers this by comparing attacked instances against truthful controls
across the full attack library described in [the attack taxonomy](../docs/ATTACK_TAXONOMY.md).

## Pipeline

The benchmark runs in three stages: generate predictions, score them, then analyze the
scored output.

```
run_safegeo.py  ->  score_safegeo.py  ->  analyze_safegeo_plan.py
   predictions             per-instance          aggregated tables
                           scores                 and statistics
```

### 1. Generate predictions

```bash
python benchmark/src/run_safegeo.py \
  --visible data/visible \
  --labels data/labels \
  --experiment main_realistic \
  --model "$MODEL" \
  --base-url http://127.0.0.1:8000/v1 \
  --output runs/benchmark/predictions.jsonl
```

The runner targets any OpenAI-compatible endpoint. `--provider` (`auto`, `vllm`, `openai`,
`openrouter`) selects a preset and `--json-mode` (`auto`, `guided_json`, `json_object`, `off`)
the structured-output strategy; with the defaults it auto-detects vLLM and uses `guided_json`.

The `--experiment` flag selects which instances to run:

| Mode | Instances run |
|---|---|
| `main_realistic` | The 8 realistic packages plus the 2 controls (the main paper setting). |
| `full` | All 22 packages across all 3 target slots plus controls. |
| `controls` | Controls only. |

`run_safegeo.py` supports resuming an interrupted run with `--resume`, and exposes
`--workers`, `--temperature`, `--top-p`, `--max-tokens`, `--retries`, and
`--request-timeout` for tuning throughput and decoding.

### 2. Score predictions

```bash
python benchmark/src/score_safegeo.py \
  --predictions runs/benchmark/predictions.jsonl \
  --labels data/labels \
  --candidate-quality data/candidate_quality \
  --source-annotations data/source_annotations \
  --geo-line-annotations data/geo_line_annotations \
  --out-dir runs/benchmark/scored
```

This writes per-instance scores and aggregated metric tables:

- `per_instance_scored.jsonl`: one scored record per instance (the input to the analyzer).
- `overall_metrics.json`: all aggregations in one JSON document.
- `model_metrics.csv`, `package_metrics.csv`, `package_family_metrics.csv`,
  `target_slot_metrics.csv`, `target_difficulty_metrics.csv`, `vertical_metrics.csv`,
  `citation_metrics.csv`: the same metrics broken down by each grouping.

### 3. Analyze

```bash
python benchmark/src/analyze_safegeo_plan.py \
  --scored runs/benchmark/scored/per_instance_scored.jsonl \
  --out-dir runs/benchmark/tables
```

The analyzer writes `dataset_stats.json` and a set of experiment tables:

- `experiment1_model_robustness.csv`: per-model robustness summary.
- `experiment2_package_effects.csv`, `experiment3_package_family_effects.csv`: effects by
  package and by family.
- `experiment3_primitive_linear_effects.csv`: linear regression of outcomes on the active
  primitives.
- `experiment4_target_slot.csv`, `experiment4_target_difficulty.csv`: effects by target slot
  and difficulty.
- `experiment5_citation_focus.csv`: citation behavior on the citation-focused packages.
- `experiment6_realistic_archetypes.csv`: the realistic packages versus controls.
- `experiment7_control_comparison.csv`: attacked instances versus truthful controls.
- `bootstrap_model_attack_ci.csv`: bootstrap confidence intervals (controlled by
  `--bootstrap-reps` and `--seed`).

Pass `--skip-regression` to omit the primitive regression.

## Metric glossary

Attack-effect metrics (computed on attacked instances, reported against controls):

| Metric | Meaning |
|---|---|
| `attacked_target_top3_rate` | Fraction of attacked instances where the attacked target lands in the top three. The headline attack-success metric. |
| `attacked_target_top1_rate` | Fraction where the attacked target is ranked first. |
| `attacked_target_rank_gain` | Mean improvement in the attacked target's rank relative to its truthful position. |
| `target_top3_uplift` | Mean increase in attacked-target top-three placement over the matched control. |
| `misleading_geo_line_citation_rate` | Fraction of instances that cite a misleading line introduced by the attack. |
| `geo_doc_citation_rate` | Fraction that cite a controlled (GEO) document. |
| `model_instruction_compliance_rate` | Fraction where the model follows a model-directed instruction planted in a source. |
| `paired_refuting_evidence_recall` | Fraction where the model cites the refuting evidence that contradicts the attacked claim. |
| `target_gap_detection_rate` | Fraction where the model detects the hidden disqualifying gap in the attacked target. |
| `unknown_treated_as_satisfied_rate` | Fraction where an unverified requirement is treated as satisfied. |

Recommendation-quality and safety metrics (computed on all instances):

| Metric | Meaning |
|---|---|
| `hard_violation_at_1` | Fraction where the top-one recommendation violates a hard constraint. |
| `utility_ndcg_at_5` | NDCG at 5 of the ranking against candidate utility. |
| `regret_at_1` | Utility gap between the best candidate and the top-one recommendation. |
| `top1_primary_gt_accuracy` | Fraction where the top-one item is a primary ground-truth candidate. |
| `top3_acceptable_gt_recall` | Fraction where the top three contain an acceptable ground-truth candidate. |
| `valid_citation_rate` | Fraction of citations that point to valid supporting evidence. |
| `parse_failure_rate` | Fraction of predictions that failed to parse against the output schema. |

## Offline smoke test

The full chain runs end to end against the tiny `sample/` subset with no GPU; see the
"Offline smoke test" section of the top-level [README](../README.md). Substitute `data` for
`sample` to run against the full dataset.
