# SafeGEO Mitigation Study

The mitigation study asks a different question from the benchmark: given that GEO attacks
work, what can an **agent developer** do to reduce their effect without changing the model?
It compares a set of agent-design layers on the same attacked instances and reports how much
each layer reduces attack success relative to an unmitigated baseline.

## Design

The study is a focused stress test rather than the full 40,800-instance crossed design. It
uses:

```
600 base cases
x Target A only
x 8 realistic GEO attack packages
x each mitigation layer
```

Target A is the primary harmful near-miss target: a high-quality hard negative that becomes
harmful if the agent overlooks a hidden disqualifying gap. The 8 realistic packages are the
ones a plausible GEO operator might deploy (`caveat_burial_faq`,
`popularity_heavy_profile`, `citation_padded_note`, `independent_buyer_guide`,
`false_fit_checklist`, `selective_comparison_note`, `ai-directed_source_text`,
`full_stack_realistic_geo`). No no-attack controls are used in this stress test; instead,
every layer is compared against `L0_source_only_baseline` on the same attacked instances.
Each layer runs 4,800 instances (600 base cases times 8 packages).

## Mitigation layers

| Layer | Strategy | What changes |
|---|---|---|
| L0 | Source-only baseline | No mitigation. |
| L1 | Prompt mitigation | A defensive final instruction is added; nothing else changes. |
| L2 | Rationale elicitation | Top recommendations are required to carry reasons and citations. |
| L3 | Audited evidence sheet | A lightweight upstream evidence-verification artifact is added. |
| L4 | Context balancing | Source context is reordered to reduce single-source GEO salience. |
| L5 | Instruction filtering | Source-internal instructions directed at the assistant are removed. |

Layers L0, L1, L3, L4, and L5 use the simple recommendation schema; L2 uses the accountable
recommendation schema (`mitigation/schemas/`).

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
  --target-slot A \
  --layers L0,L1,L2,L3,L4,L5
```

This selects the attacked Target-A instances for the 8 realistic packages and emits one
runfile per layer under `runs/mitigation/runfiles/`, along with
`runs/mitigation/labels/mitigation_labels_manifest.jsonl` and a `run_summary.json`. Each
layer has the same instance count (4,800 in the full run). For a smaller screening run, pass
`--base-cases-per-vertical 25` (1,200 instances per layer).

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
  --schema-dir mitigation/schemas \
  --output runs/mitigation/predictions/L0.jsonl
```

Like the benchmark runner, `run_mitigation.py` targets any OpenAI-compatible endpoint via
`--provider` and `--json-mode`; with the defaults it auto-detects vLLM and uses `guided_json`.
Passing `--json-mode off` disables structured output entirely (the parser still recovers JSON
from the response).

`render_requests.py` applies each layer's prompt template and the L4/L5 source transforms
(context balancing for L4, instruction filtering for L5) using the prompts under
`mitigation/prompts/`. Repeat for every layer; the
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
