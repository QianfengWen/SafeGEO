---
license: cc-by-4.0
task_categories: [text-ranking, text-retrieval]
language: [en]
tags: [generative-engine-optimization, geo, recommendation, recommendation-agents, llm-safety, adversarial, red-teaming, retrieval-augmented-generation, agents, benchmark]
pretty_name: SafeGEO
size_categories: [100K<n<1M]
configs:
  - config_name: visible
    data_files: [{split: test, path: visible/test-*.parquet}]
  - config_name: labels
    data_files: [{split: test, path: labels/test-*.parquet}]
  - config_name: candidate_quality
    data_files: [{split: test, path: candidate_quality/test-*.parquet}]
  - config_name: source_annotations
    data_files: [{split: test, path: source_annotations/test-*.parquet}]
  - config_name: geo_line_annotations
    data_files: [{split: test, path: geo_line_annotations/test-*.parquet}]
  - config_name: targets
    data_files: [{split: test, path: targets/test-*.parquet}]
  - config_name: instances_manifest
    data_files: [{split: test, path: instances_manifest/test-*.parquet}]
  - config_name: quality_distributions
    data_files: [{split: test, path: quality_distributions/test-*.parquet}]
  - config_name: requirement_annotations
    data_files: [{split: test, path: requirement_annotations/test-*.parquet}]
  - config_name: controlled_documents
    data_files: [{split: test, path: controlled_documents/test-*.parquet}]
  - config_name: diamond_visible
    data_files: [{split: test, path: diamond/visible/test-*.parquet}]
  - config_name: diamond_labels
    data_files: [{split: test, path: diamond/labels/test-*.parquet}]
  - config_name: diamond_candidate_quality
    data_files: [{split: test, path: diamond/candidate_quality/test-*.parquet}]
  - config_name: diamond_source_annotations
    data_files: [{split: test, path: diamond/source_annotations/test-*.parquet}]
  - config_name: diamond_geo_line_annotations
    data_files: [{split: test, path: diamond/geo_line_annotations/test-*.parquet}]
  - config_name: diamond_targets
    data_files: [{split: test, path: diamond/targets/test-*.parquet}]
  - config_name: diamond_instances_manifest
    data_files: [{split: test, path: diamond/instances_manifest/test-*.parquet}]
  - config_name: diamond_quality_distributions
    data_files: [{split: test, path: diamond/quality_distributions/test-*.parquet}]
  - config_name: diamond_requirement_annotations
    data_files: [{split: test, path: diamond/requirement_annotations/test-*.parquet}]
  - config_name: diamond_controlled_documents
    data_files: [{split: test, path: diamond/controlled_documents/test-*.parquet}]
---

# SafeGEO Dataset

Paper: <https://arxiv.org/abs/2606.28356> · Project page: <https://qianfengwen.github.io/SafeGEO/> · Code: <https://github.com/QianfengWen/SafeGEO>

SafeGEO tests whether recommendation agents preserve utility-aligned decisions
when seller-controlled web sources are rewritten with Generative Engine
Optimization (GEO) attacks. The full benchmark contains 600 recommendation base
cases across six product verticals. Each case is expanded into 68 instances: 22
attack packages applied separately to three fixed targets, plus two controls,
for 40,800 instances total.

Target A/B/C are nominal identifiers. They do not encode difficulty, and all
three targets use the same attack-generation, scoring, and reporting protocol.
Candidate-specific feasibility, quality, and evidence annotations remain
available for analysis. Nested target records use the shared role
`nominal_fixed_target` and contain no target-difficulty field.

The attack library spans three manipulation loci (content, epistemic, and
model-facing) and seven primitives. Full construction and schema documentation
is available in the [GitHub data guide](https://github.com/QianfengWen/SafeGEO/blob/main/data/README.md),
[attack taxonomy](https://github.com/QianfengWen/SafeGEO/blob/main/docs/ATTACK_TAXONOMY.md),
and [datasheet](https://github.com/QianfengWen/SafeGEO/blob/main/docs/DATASHEET.md).

## SafeGEO Diamond

SafeGEO Diamond is a 600-instance screening subset for inexpensive iteration.
It contains 120 deterministic, vertical-balanced base cases (20 per vertical),
with one target per case balanced across A/B/C (40 cases per target ID). Each
case includes three high-effect realistic attack packages and both controls.
Attack selection makes Diamond a biased screening set; use the complete
benchmark for population-level reporting. The exact cases, target assignments,
and row counts are recorded in
[`diamond/selection_manifest.json`](https://huggingface.co/datasets/wieeii/SafeGEO/blob/main/diamond/selection_manifest.json).

## Loading

```python
from datasets import load_dataset

# Full benchmark model inputs and hidden scoring labels.
visible = load_dataset("wieeii/SafeGEO", "visible", split="test")
labels = load_dataset("wieeii/SafeGEO", "labels", split="test")

# Fast Diamond screening inputs and labels.
diamond_visible = load_dataset("wieeii/SafeGEO", "diamond_visible", split="test")
diamond_labels = load_dataset("wieeii/SafeGEO", "diamond_labels", split="test")
```

The full dataset and Diamond each expose the same ten logical configs:

| Full config | Diamond config | Description |
|---|---|---|
| `visible` | `diamond_visible` | Model-facing query, candidate roster, and source packet. |
| `labels` | `diamond_labels` | Hidden package, target, and scoring metadata. |
| `candidate_quality` | `diamond_candidate_quality` | Candidate-level benchmark-reference quality annotations. |
| `source_annotations` | `diamond_source_annotations` | Source annotations for citation-validity scoring. |
| `geo_line_annotations` | `diamond_geo_line_annotations` | Misleading and refuting controlled-source lines. |
| `targets` | `diamond_targets` | Fixed nominal A/B/C targets by base case. |
| `instances_manifest` | `diamond_instances_manifest` | Expanded-instance mapping. |
| `quality_distributions` | `diamond_quality_distributions` | Per-query candidate-quality distributions. |
| `requirement_annotations` | `diamond_requirement_annotations` | Query requirements used by the benchmark reference. |
| `controlled_documents` | `diamond_controlled_documents` | Full controlled-source corpus and hidden attack metadata. |

The full `visible`, `labels`, and `instances_manifest` configs contain 40,800
rows. The corresponding Diamond configs contain 600 rows. Other config counts
follow their base-case, candidate, source, or document granularity.

## Visibility and storage

Only `visible` / `diamond_visible` fields are model inputs. Attack design,
target identity, package IDs, and benchmark-reference annotations are hidden
from evaluated models. Records are stored as Parquet; nested lists and mappings
are JSON-encoded strings and can be decoded with `json.loads`, or loaded through
`safegeo.io.read_records` from the GitHub repository.

## License

The dataset is released under CC-BY-4.0. Code and scoring utilities are released
separately under Apache-2.0 in the GitHub repository.

## Citation

```bibtex
@article{wen2026safegeo,
  title   = {SafeGEO: Understanding Generative Engine Optimization Risks in Recommendation Agents},
  author  = {Wen, Qianfeng and Liu, Yifan Simon and Liu, Xin and Jiao, Difan and Yang, Blair and Wu, Junda and Tang, Zhenwei},
  journal = {arXiv preprint arXiv:2606.28356},
  year    = {2026}
}
```
