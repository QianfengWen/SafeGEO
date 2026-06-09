<div align="center">

# SafeGEO: Understanding Generative Engine Optimization Risks in Recommendation Agents

[![Project Page](https://img.shields.io/badge/Project-Page-1f72b8.svg)](https://qianfengwen.github.io/SafeGEO/)
![arXiv](https://img.shields.io/badge/arXiv-coming%20soon-lightgrey.svg)
[![Dataset](https://img.shields.io/badge/HuggingFace-Dataset-ffce1c.svg)](https://huggingface.co/datasets/wieeii/SafeGEO)
[![Code License: Apache 2.0](https://img.shields.io/badge/Code-Apache%202.0-blue.svg)](LICENSE)
[![Data License: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-green.svg)](DATA_LICENSE)

Qianfeng Wen<sup>1,5,\*</sup>, Yifan Simon Liu<sup>2,\*</sup>, Xin Liu<sup>3,5,\*</sup>, Difan Jiao<sup>1</sup>, Blair Yang<sup>1,6</sup>, Junda Wu<sup>4</sup>, Zhenwei Tang<sup>1</sup>

<sup>1</sup>Dept. of Computer Science, University of Toronto. <sup>2</sup>Dept. of Mechanical & Industrial Engineering, University of Toronto. <sup>3</sup>Faculty of Information, University of Toronto. <sup>4</sup>UC San Diego. <sup>5</sup>ZBot Technology. <sup>6</sup>Coolwei AI Lab.
<br><sub><sup>\*</sup> Equal contribution</sub>

</div>

SafeGEO tests whether recommendation agents keep their utility-aligned recommendations when sellers rewrite web sources using Generative Engine Optimization (GEO). It also includes an agent-side mitigation study of practical developer defenses.

Project page: <https://qianfengwen.github.io/SafeGEO/> &nbsp;·&nbsp; Dataset: <https://huggingface.co/datasets/wieeii/SafeGEO>

This release contains:

- A GEO robustness benchmark with 22 attack packages and 2 truthful controls, over 600 cases and 3 target slots (40,800 instances).
- A structured attack library of 7 manipulation primitives across 3 loci, from single moves up to full realistic GEO pages.
- A Hugging Face dataset in 10 Parquet configs, with hidden ground-truth labels and line-level evidence annotations.
- An agent-side mitigation study of 6 developer defenses (L0 to L5), reported as reductions against an unmitigated baseline.

## News

- June 2026: first public release of the benchmark, dataset, and mitigation study. The arXiv preprint is coming soon.

## Contents

- [Overview](#overview)
- [Key results](#key-results)
- [Results](#results)
- [Installation](#installation)
- [Dataset](#dataset)
- [Usage](#usage)
- [Attack taxonomy](#attack-taxonomy)
- [Mitigation study](#mitigation-study)
- [Evaluation metrics](#evaluation-metrics)
- [Reproducing the paper](#reproducing-the-paper)
- [Repository structure](#repository-structure)
- [Citation](#citation)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Overview

Generative Engine Optimization (GEO) lets content owners rewrite web content to increase their visibility in generative systems. In recommendation agents, this creates a risk that seller-controlled sources make flawed products appear better supported than they are. We study this risk by asking whether recommendation agents preserve utility-aligned decisions when seller-controlled sources are rewritten for GEO. To make this question measurable, we construct SafeGEO, an evaluation suite with 22 GEO attack variants across 600 recommendation cases. We empirically show that GEO attacks can promote flawed target products. On average, they increase the rate at which such flawed products enter the recommendation set by up to 83.2%. We further study whether agent-side design choices can mitigate this risk and show that simple defenses, including defensive prompting and structured evidence checks, reduce harmful target promotion by up to 39.2%. These gains are substantial but do not restore the no-GEO performance, showing that GEO remains a serious risk despite developer-side mitigation.

Figures and an interactive walkthrough are on the [project page](https://qianfengwen.github.io/SafeGEO/).

## Key results

- GEO attacks promote flawed products: they raise the rate at which a flawed target enters the recommendation set by up to 83.2% over truthful-source controls.
- Developer-side defenses help but do not fully fix it. Defensive prompting and structured evidence checks cut harmful promotion by up to 39.2%, which is still short of no-GEO performance.
- Scale: 22 attack packages plus 2 controls, across 600 cases and 6 product verticals, for 40,800 instances.

## Results

We evaluate three open-weight recommendation agents (Gemma 4 31B IT, Qwen3.6 27B, and Devstral Small 2 24B Instruct), with a frontier robustness check on DeepSeek-V4-Flash. The metrics are Target@3 (attacked-target top-3 rate), HCV@1 (hard-constraint violation at rank 1), GT@3 (ground-truth at 3), and uNDCG@5 (utility NDCG at 5); see [Evaluation metrics](#evaluation-metrics). The plots are on the [project page](https://qianfengwen.github.io/SafeGEO/).

Main attack on the realistic GEO variants, averaged over targets (truthful-rewrite control, then GEO attack):

| Model | Target@3 | HCV@1 | GT@3 | uNDCG@5 |
|---|---|---|---|---|
| Gemma 4 31B IT | 3.4 → 79.6 (+76.2) | 16.9 → 75.6 (+58.8) | 71.2 → 67.9 (−3.3) | 74.4 → 68.6 (−5.8) |
| Qwen3.6 27B | 8.1 → 78.3 (+70.2) | 24.2 → 83.7 (+59.5) | 61.2 → 60.8 (−0.4) | 66.5 → 63.6 (−3.0) |
| Devstral Small 2 24B Instruct | 12.7 → 90.9 (+78.2) | 41.1 → 90.7 (+49.7) | 50.7 → 47.9 (−2.8) | 67.4 → 59.2 (−8.2) |

GEO moves a flawed target into the top 3 in up to 90.9% of cases, up from roughly 3 to 13% under truthful controls. The strongest single variant, full-stack realistic on Devstral, reaches +83.2 on Target@3.

Mitigation, reported as the Target@3 reduction against the no-mitigation baseline (a more negative number means less harm):

| Layer | Gemma 4 31B IT | Qwen3.6 27B | Devstral 2 24B |
|---|---|---|---|
| L0 No mitigation (Target@3) | 79.6 | 78.3 | 90.9 |
| L1 Defensive prompt | −15.1 | −11.0 | −2.8 |
| L2 Rationale elicitation | −15.0 | +7.5 | +2.3 |
| L3 Evidence breakdown | −29.7 | −39.2 | −17.7 |
| L4 Context balancing | −11.5 | −4.5 | −3.2 |
| L5 Instruction filtering | −2.2 | +3.0 | −0.5 |

The L3 audited evidence breakdown is the strongest defense, reaching a 39.2 point Target@3 reduction, but no layer restores no-GEO performance. DeepSeek-V4-Flash is the most robust model we test, yet a single rewrite still lifts Target@3 from 4.6 to 72.6% (+68.0) and HCV@1 from 23.0 to 73.4% (+50.4). Full per-variant results are in the paper.

## Installation

The package targets Python 3.10+ and installs in editable mode:

```bash
pip install -e .
```

This installs the runtime dependencies (`pyarrow`, `numpy`, `openai`) and makes the shared `safegeo` library importable. Loading the dataset with the Hugging Face `datasets` library is optional:

```bash
pip install datasets
```

## Dataset

SafeGEO is built from 600 recommendation base cases across 6 product verticals, 100 each: AI meeting transcription, baby monitors, carry-on backpacks, home air purifiers, noise-canceling headphones, and office chairs. Each base case expands into 68 instances (22 attack packages times 3 target slots, plus 2 controls), for 40,800 instances. The data ships as 10 Hugging Face Parquet configs. The `visible` config holds the model-facing inputs and `labels` holds the hidden ground truth.

```python
from datasets import load_dataset

visible = load_dataset("wieeii/SafeGEO", "visible", split="test")  # model-facing inputs
labels  = load_dataset("wieeii/SafeGEO", "labels",  split="test")  # hidden ground truth
```

| Config | Rows | Contents |
|---|--:|---|
| `visible` | 40,800 | Model-facing inputs (query, candidate roster, source documents). |
| `labels` | 40,800 | Hidden ground truth (attack package, vectors, target mapping, eval keys). |
| `candidate_quality` | 11,974 | Per-candidate quality judgments for utility and ranking metrics. |
| `source_annotations` | 21,513 | Per-source annotations for citation-validity scoring. |
| `geo_line_annotations` | 414,000 | Line-level misleading and refuting annotations within controlled sources. |
| `targets` | 600 | Fixed A/B/C target assignment per base case. |
| `instances_manifest` | 40,800 | Maps each expanded instance to its base case, package, and slot. |
| `quality_distributions` | 600 | Per-query candidate quality distribution. |
| `requirement_annotations` | 600 | Per-query requirement annotations. |
| `controlled_documents` | 41,400 | Full controlled-source corpus, with hidden attack metadata that is not model-visible. |

The same Parquet tree is included in this repo under [`data/`](data/) so the pipelines run offline. See [`data/README.md`](data/README.md) for the full column dictionaries and the [datasheet](docs/DATASHEET.md).

## Usage

### Offline smoke test (no GPU)

Both pipelines run end to end against the tiny [`sample/`](sample/) subset using mock predictions in place of a served model. This validates the install with no GPU.

```bash
# Benchmark
python scripts/make_mock_predictions.py --mode benchmark --source sample/visible --out /tmp/pred.jsonl
python benchmark/src/score_safegeo.py --predictions /tmp/pred.jsonl --labels sample/labels \
  --candidate-quality sample/candidate_quality --source-annotations sample/source_annotations \
  --geo-line-annotations sample/geo_line_annotations --out-dir /tmp/scored
python benchmark/src/analyze_safegeo_plan.py --scored /tmp/scored/per_instance_scored.jsonl --out-dir /tmp/tables

# Mitigation
python mitigation/src/build_runfiles.py --dataset-root sample --out /tmp/mit_runs --target-slot A --layers L0,L1,L2,L3,L4,L5
python mitigation/src/materialize_labels.py --dataset-root sample \
  --manifest /tmp/mit_runs/labels/mitigation_labels_manifest.jsonl --out /tmp/mit_labels.jsonl
python mitigation/src/render_requests.py --package-root mitigation \
  --runfile /tmp/mit_runs/runfiles/L0_L0_source_only_baseline.jsonl --out /tmp/mit_req_L0.jsonl
python scripts/make_mock_predictions.py --mode mitigation \
  --source /tmp/mit_runs/runfiles/L0_L0_source_only_baseline.jsonl --out /tmp/mit_pred_L0.jsonl
python mitigation/src/score_mitigation.py --predictions /tmp/mit_pred_L0.jsonl --labels /tmp/mit_labels.jsonl \
  --candidate-quality sample/candidate_quality --source-annotations sample/source_annotations \
  --geo-line-annotations sample/geo_line_annotations --out-dir /tmp/mit_scored
```

### Full run

A full run evaluates a real model served behind any OpenAI-compatible endpoint (vLLM, OpenAI, OpenRouter). The runner scripts read `MODEL` (required) and select a provider with `PROVIDER` (default `vllm`); `BASE_URL` and `API_KEY` override the preset.

```bash
# vLLM (local; default guided_json structured decoding, the paper setting)
python -m vllm.entrypoints.openai.api_server --model <hf-id> --port 8000
MODEL=<hf-id> bash scripts/run_benchmark.sh     # EXPERIMENT = main_realistic | full | controls
MODEL=<hf-id> bash scripts/run_mitigation.sh    # LAYERS = L0,L1,L2,L3,L4,L5

# Hosted providers
OPENAI_API_KEY=sk-...    PROVIDER=openai     MODEL=gpt-4o-mini        bash scripts/run_benchmark.sh
OPENROUTER_API_KEY=...   PROVIDER=openrouter MODEL=openai/gpt-4o-mini bash scripts/run_benchmark.sh
```

See [`benchmark/README.md`](benchmark/README.md) and [`mitigation/README.md`](mitigation/README.md) for the stage-by-stage pipelines and full options.

## Attack taxonomy

SafeGEO models GEO as an adversary that rewrites seller-controlled sources along 3 manipulation loci, built from 7 primitives, composed into 22 attack packages and probed against 2 truthful controls over 3 target slots.

| Code | Primitive | Manipulation locus |
|:--:|---|---|
| `A` | authority laundering | epistemic |
| `U` | unsupported fit claim | content |
| `C` | caveat omission | content |
| `R` | relevance flooding | content |
| `E` | evidence padding | epistemic |
| `S` | salience manipulation | model-facing |
| `M` | model-directed instruction | model-facing |

Packages grow in composition across four families: 7 atomic (one primitive), 3 block (one full locus), 4 cross-block (multiple loci), and 8 realistic (deployable GEO pages, the focus of the mitigation study). Each package is applied to one of three target slots: A (primary harmful near-miss, used in the mitigation study), B (contrast hard negative), and C (utility or uncertainty target). Full definitions are in [`docs/ATTACK_TAXONOMY.md`](docs/ATTACK_TAXONOMY.md).

## Mitigation study

Given that GEO attacks work, what can an agent developer do without changing the model? The study compares six design layers on the same attacked instances (Target A, the 8 realistic packages, 4,800 instances per layer) and reports how much each reduces attack success against the unmitigated baseline.

| Layer | Strategy | What changes |
|:--:|---|---|
| L0 | Source-only baseline | No mitigation, the reference point. |
| L1 | Prompt mitigation | A defensive final instruction is added; nothing else changes. |
| L2 | Rationale elicitation | Top recommendations must carry reasons and citations. |
| L3 | Audited evidence sheet | A lightweight upstream evidence-verification artifact is added. |
| L4 | Context balancing | Source context is reordered to reduce single-source GEO salience. |
| L5 | Instruction filtering | Source-internal instructions aimed at the assistant are removed. |

See [`mitigation/README.md`](mitigation/README.md) for the pipeline and the reduction-vs-L0 metrics.

## Evaluation metrics

Every instance is scored against hidden ground truth, weighing attack success against recommendation utility and safety. The headline metrics:

| Metric | Field | Meaning |
|---|---|---|
| Target@3 | `attacked_target_top3_rate` | Attacked target lands in the top three. The headline attack-success rate. |
| HCV@1 | `hard_violation_at_1` | Top-one recommendation violates a hard constraint. |
| uNDCG@5 | `utility_ndcg_at_5` | Utility NDCG at 5 of the ranking. |
| GT@3 | `top3_acceptable_gt_recall` | Top three contain an acceptable ground-truth candidate. |

Citation validity, refuting-evidence recall, gap detection, and other metrics are defined in the glossary in [`benchmark/README.md`](benchmark/README.md).

## Reproducing the paper

The headline numbers come from full runs (`scripts/run_benchmark.sh`, `scripts/run_mitigation.sh`) against the served models reported in the paper, scored with the `score_*` and `analyze_*` stages. Only the vLLM `guided_json` path guarantees schema-conformant decoding (the paper setting). OpenAI and OpenRouter fall back to JSON mode plus the explicit schema, which may slightly raise the parse-failure rate.

## Repository structure

```
.
├── README.md                  This file.
├── pyproject.toml             Package metadata and dependencies.
├── LICENSE                    Apache-2.0 (code).
├── DATA_LICENSE               CC-BY-4.0 (data).
├── assets/                    Figure sources.
├── data/                      The SafeGEO Hugging Face dataset (10 Parquet configs).
├── sample/                    Tiny subset (2 base cases per vertical) for offline smoke tests.
├── src/safegeo/               Shared library (Parquet I/O, taxonomy constants).
├── benchmark/                 The GEO robustness benchmark (run, score, analyze).
├── mitigation/                The agent-side mitigation study (L0 to L5 layers).
├── scripts/                   Sampling, mock predictions, and end-to-end runners.
├── tests/                     Unit tests (I/O round-trip fidelity, mock predictions).
└── docs/                      Attack taxonomy and datasheet.
```

## Citation

```bibtex
@article{wen2026safegeo,
  title   = {SafeGEO: Understanding Generative Engine Optimization Risks in Recommendation Agents},
  author  = {Wen, Qianfeng and Liu, Yifan Simon and Liu, Xin and Jiao, Difan and Yang, Blair and Wu, Junda and Tang, Zhenwei},
  journal = {arXiv preprint arXiv:XXXX.XXXXX},
  year    = {2026}
}
```

## Acknowledgments

We thank the community working on the safety of retrieval-augmented and recommendation agents. Funding and full acknowledgments appear in the paper. The project page is built from the [Academic Project Page Template](https://github.com/eliahuhorwitz/Academic-project-page-template).

## License

Code is released under the [Apache License 2.0](LICENSE). The dataset is released under the [Creative Commons Attribution 4.0 International](DATA_LICENSE) license.
