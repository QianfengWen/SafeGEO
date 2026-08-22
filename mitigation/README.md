# SafeGEO Mitigation Study

The mitigation study compares lightweight prompt/input-level interventions on matched attacked
instances. The model, query, candidate roster, source packet, order, lines, and decoding settings
remain fixed across conditions.

## Design

The study is a focused stress test rather than the full 40,800-instance crossed design. It
uses:

```
600 base cases
x 3 target slots (A, B, C)
x 8 realistic GEO packages
x each mitigation layer
```

The three fixed targets are non-ground-truth candidates drawn from complementary hard-negative
and medium/uncertainty strata. The 8 realistic packages are coherent synthetic seller-source templates
(`caveat_burial_faq`,
`popularity_heavy_profile`, `citation_padded_note`, `independent_buyer_guide`,
`false_fit_checklist`, `selective_comparison_note`, `ai-directed_source_text`,
`full_stack_realistic_geo`). No no-attack controls are used in this stress test; instead,
every layer is compared against `L0_source_only_baseline` on the same attacked instances.
The `realistic` family, `L0_source_only_baseline`, and
`L2_rationale_elicitation_mitigation` strings are retained as stable artifact identifiers;
the L2 camera-ready display name is **Rationale emphasis**. Each layer runs 14,400 instances
(600 base cases times 3 targets times 8 packages).

## Mitigation layers

| Layer | Strategy | What changes |
|---|---|---|
| L0 | No mitigation | Exact benchmark system prompt, user-message serialization, output schema, and visible packet. |
| L1 | Defensive prompt | A defensive system instruction is added; nothing else changes. |
| L2 | Rationale emphasis | The output instruction for the benchmark's existing rationale and citation fields is tightened. |
| L3 | Evidence breakdown | The model generates candidate-level evidence checks from the visible packet before ranking; no external sheet or hidden label is supplied. |
| L4 | Context balancing | The model is instructed to balance source use; the source packet and order remain unchanged. |
| L5 | Instruction filtering | The model is instructed to ignore source-internal directives; no source line is deleted or replaced. |

L0, L1, L2, L4, and L5 use the exact benchmark prediction schema. L3 extends that schema only
with a required `evidence_checks` field. All conditions use the same decoding settings.

## Pipeline

The study runs in five stages.

```
build_runfiles.py -> materialize_labels.py -> render_requests.py -> run_mitigation.py -> score_mitigation.py
   per-layer            full scoring             model requests        predictions             layer metrics and
   runfiles             labels                                                                  reductions vs L0
```

### 1. Build runfiles

```bash
python mitigation/src/build_runfiles.py \
  --dataset-root data \
  --out runs/mitigation \
  --layers L0,L1,L2,L3,L4,L5
```

This selects all three attacked target slots for the 8 realistic packages and emits one
runfile per layer under `runs/mitigation/runfiles/`, along with
`runs/mitigation/labels/mitigation_labels_manifest.jsonl` and a `run_summary.json`. Each
layer has the same instance count (14,400 in the full run). For a smaller screening run, pass
`--base-cases-per-vertical 25` (3,600 instances per layer).

### 2. Materialize labels

```bash
python mitigation/src/materialize_labels.py \
  --dataset-root data \
  --manifest runs/mitigation/labels/mitigation_labels_manifest.jsonl \
  --out runs/mitigation/labels/full_labels.jsonl
```

This expands the manifest into the full per-instance labels the scorer needs.

### 3. Render requests, then run the model

Render the prompt batch for a layer, then send it to the served model:

```bash
python mitigation/src/render_requests.py \
  --package-root mitigation \
  --runfile runs/mitigation/runfiles/L0_L0_source_only_baseline.jsonl \
  --out runs/mitigation/requests/L0.jsonl

python mitigation/src/run_mitigation.py \
  --requests runs/mitigation/requests/L0.jsonl \
  --model "$MODEL" \
  --base-url http://127.0.0.1:8000/v1 \
  --output runs/mitigation/predictions/L0.jsonl
```

Like the benchmark runner, `run_mitigation.py` targets any OpenAI-compatible endpoint via
`--provider` and `--json-mode`; with the defaults it auto-detects vLLM and uses `guided_json`.
Passing `--json-mode off` disables structured output entirely (the parser still recovers JSON
from the response).

`render_requests.py` uses the shared benchmark user-prompt builder for every layer and applies
the selected system instruction. L0 reads the benchmark system-prompt file directly, making
the complete no-mitigation request byte-identical to the benchmark request. The other layers
retain that visible packet. Repeat for every layer; the
[run_mitigation.sh](../scripts/run_mitigation.sh) script loops over all runfiles
automatically.

### 4. Score

```bash
python mitigation/src/score_mitigation.py \
  --predictions runs/mitigation/predictions/*.jsonl \
  --labels runs/mitigation/labels/full_labels.jsonl \
  --candidate-quality data/candidate_quality \
  --source-annotations data/source_annotations \
  --geo-line-annotations data/geo_line_annotations \
  --out-dir runs/mitigation/scored
```

This writes per-instance scores and the layer comparison tables:

- `per_instance_scored.jsonl`, `overall_metrics.json`.
- `mitigation_layer_metrics.csv`: attack-effect and quality metrics for each layer.
- `mitigation_layer_package_metrics.csv`, `mitigation_layer_vertical_metrics.csv`: the same
  metrics broken down by package and by vertical.
- `mitigation_reductions_vs_L0.csv`: for each layer, the reduction in each attack metric
  relative to L0.

The same full SafeGEO scorer used by the benchmark is applied here, so the layer metrics use
the candidate-quality and line-level annotations and are directly comparable to the benchmark
results.

## Reduction-vs-L0 metrics

`mitigation_reductions_vs_L0.csv` reports, per layer and model:

- For each attack metric (for example `attacked_target_top3_rate`, `hard_violation_at_1`,
  `misleading_geo_line_citation_rate`): an absolute `<metric>_reduction_vs_L0` (L0 minus the
  layer, so positive means the layer reduced the attack) and a
  `<metric>_relative_reduction_vs_L0` (the same as a fraction of the L0 value).
- For each quality metric (for example `utility_ndcg_at_5`, `top3_acceptable_gt_recall`): a
  `<metric>_delta_vs_L0` showing the change relative to L0, so a developer can see whether a
  defense traded away recommendation quality.

A positive top-three reduction means the layer kept the attacked target out of the user's
decision set more often than the unmitigated baseline did. See the
[benchmark metric glossary](../benchmark/README.md) for the definition of each metric.

## Offline smoke test

The full chain runs end to end against the tiny `sample/` subset with no GPU; see the
"Offline smoke test" section of the top-level [README](../README.md). Substitute `data` for
`sample` to run against the full dataset.

Camera-ready defaults are temperature 0, top-p 1, and a 6,144-token output cap for the three
main models. Published aggregate mitigation tables are in [`results/`](../results/); model
responses and prediction traces are not distributed.
