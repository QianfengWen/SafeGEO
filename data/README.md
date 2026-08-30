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
---

# SafeGEO Dataset

Paper: <https://arxiv.org/abs/2606.28356> · Project page: <https://qianfengwen.github.io/SafeGEO/> · Code: <https://github.com/QianfengWen/SafeGEO>

SafeGEO is a benchmark for testing whether a source-conditioned LLM reranker preserves
utility-aligned recommendations when seller-controlled web sources are rewritten with
Generative Engine Optimization (GEO) attacks. Candidate generation, retrieval, and source
selection are fixed. It is built from 600 recommendation base cases spread evenly
across 6 product verticals (100 cases each). Each base case is expanded into 68 instances:
22 attack packages applied to each of 3 sampled targets, plus 2 controls. This yields
40,800 instances in total. The attack library spans 3 manipulation loci (content, epistemic,
and model-facing) drawn from 7 primitives; see the
[attack taxonomy](../docs/ATTACK_TAXONOMY.md) for the full breakdown.

For each base case, a fixed release seed samples three eligible non-ground-truth candidates
without replacement. Candidate IDs identify the sampled targets throughout the release.
Candidate-specific quality and evidence annotations remain available for scoring and analysis.
Run `python scripts/normalize_target_metadata.py --check` to verify the target schema.

The 6 verticals are: `ai_meeting_transcription`, `baby_monitor`, `carry_on_backpack`,
`home_air_purifier`, `noise_canceling_headphones`, and `office_chair`.

The dataset is published as 10 configurations. The `visible` config holds the model-facing
inputs (user query, candidate roster, and the source documents an agent reads). The `labels`
config holds the hidden benchmark reference used for scoring. The remaining configs supply
candidate-quality judgments, source and line-level annotations, the fixed per-case targets,
the instance manifest, per-query quality distributions, requirement annotations, and the
full controlled-document corpus.

Base candidate and source records are derived from shopping-research traces, then canonicalized.
Product and vendor names are replaced with synthetic names, and candidate and source records use
synthetic IDs. Seller-source control/GEO records are synthetic, while utility and evidence
labels are pipeline-generated benchmark references. See the
[datasheet](../docs/DATASHEET.md) and [human audit](../docs/HUMAN_AUDIT.md).

## Loading the dataset

The dataset uses standard Hugging Face Parquet configs and loads with the `datasets`
library (`pip install datasets`):

```python
from datasets import load_dataset

# Model-facing inputs.
visible = load_dataset("wieeii/SafeGEO", "visible", split="test")

# Hidden benchmark-reference labels for scoring.
labels = load_dataset("wieeii/SafeGEO", "labels", split="test")

print(visible[0]["user_query"])
print(labels[0]["package_id"])
```

When working inside this repository, the pipeline scripts read the same Parquet files
through `safegeo.io.read_records`, which also restores the JSON-encoded list and dict
columns described below:

```python
from safegeo.io import read_records

records = read_records("data/visible")   # list of dicts, nested fields decoded
```

## Configurations

| Config | Rows | Description |
|---|---|---|
| `visible` | 40,800 | Model-facing inputs per instance: user query, candidate roster, and source documents. |
| `labels` | 40,800 | Hidden benchmark reference per instance: attack package, attack vector, target mapping, and evaluation keys. |
| `candidate_quality` | 11,974 | Per-candidate benchmark-reference judgments used to compute utility and ranking metrics. |
| `source_annotations` | 21,513 | Per-source annotations supporting citation validity scoring. |
| `geo_line_annotations` | 414,000 | Line-level annotations marking misleading and refuting lines within controlled sources. |
| `targets` | 600 | The three sampled target candidates for each base case. |
| `instances_manifest` | 40,800 | Manifest mapping every expanded instance to its base case, package, and attacked candidate. |
| `quality_distributions` | 600 | Per-query candidate quality distribution (ground-truth, hard-negative, medium-negative counts). |
| `requirement_annotations` | 600 | Per-query requirement annotations describing the constraints a good recommendation must satisfy. |
| `controlled_documents` | 41,400 | Full controlled-source corpus, including hidden attack metadata (see note below). |

## Column dictionary: `visible`

These are the only fields a model sees at inference time.

| Field | Type | Description |
|---|---|---|
| `instance_id` | string | Neutral, opaque identifier for the expanded instance. |
| `query_id` | string | Identifier of the base case this instance belongs to. |
| `benchmark` | string | Benchmark name tag. |
| `split` | string | Data split tag. |
| `vertical` | string | Product vertical (one of the 6 listed above). |
| `version` | string | Visible-format version tag (semantics-preserved query, long sources). |
| `user_query` | string | Construction request, byte-identical across all expanded rows for a case. |
| `candidate_roster` | list | Candidate products with synthetic product/vendor names, a `candidate_id`, and visible attributes. |
| `search_results` | list | The source documents the agent may read, including controlled (potentially attacked) sources. |
| `generation_instruction` | dict | The task framing given to the model (recommend from the roster using only the provided sources). |

## Column dictionary: `labels`

These fields are hidden benchmark-reference annotations and are used only for scoring.

| Field | Type | Description |
|---|---|---|
| `instance_id` | string | Matches `visible.instance_id`. |
| `expanded_instance_id` | string | Human-readable instance id (`<base_case_id>__<package_id>`). |
| `base_case_id` | string | Identifier of the base recommendation case. |
| `query_id` | string | Identifier of the base case (equal to `base_case_id` in this release). |
| `split` | string | Data split tag. |
| `vertical` | string | Product vertical. |
| `scenario_type` | string | High-level instance type (for example `control_no_geo` or an attack scenario). |
| `control_type` | string | Control identifier when the instance is a control; empty otherwise. |
| `num_attacked_targets` | int | Number of targets attacked (0 for controls, 1 for the attacked instances). |
| `package_id` | string | Attack package applied (or the control id). |
| `package_family` | string | Package family (`atomic`, `block`, `cross_block`, `realistic`, or `control`). |
| `attack_vector` | dict | Per-primitive activation map over `A/U/C/R/E/S/M` (1 = active). |
| `attack_blocks` | dict | Which manipulation loci are active: `content`, `epistemic`, `model_facing`. |
| `expected_correct_behavior` | dict | The behavior a robust agent should exhibit for this instance. |
| `version` | string | Dataset-format version tag. |
| `visible_format` | string | Visible-rendering format tag. |
| `source_only_doc_id_map` | dict | Mapping from visible neutral doc ids to canonical source ids. |
| `controlled_source_candidate_mapping` | dict | Mapping from sampled candidate IDs to their controlled documents. |
| `fixed_geo_targets` | list | The three sampled target records for the base case. |
| `attacked_candidate_id` | string | Candidate ID of the attacked target; empty for controls. |
| `paired_refuting_lines` | list | Lines in the corpus that refute attacked claims (used for evidence-recall scoring). |
| `geo_misleading_lines` | list | Lines introduced by the attack that are misleading (used for citation scoring). |
| `controlled_source_line_annotations` | list | Line-level annotations for the controlled sources in this instance. |
| `removed_visible_scaffolding` | list | Scaffolding artifacts removed from the visible view (for example candidate cards, conflict logs). |
| `target_metadata_source` | string | Provenance tag for the target metadata. |
| `realism_adjustments` | dict | Flags describing the realism transformations applied to the visible view. |

## Core columns: `candidate_quality`

The scorer reads the following candidate-level reference fields. These are pipeline-generated
benchmark annotations, not independent claims about real-world product quality.

| Field | Type | Description |
|---|---|---|
| `item_id` | string | Candidate identifier within the base case. |
| `hard_constraint_feasible` | bool | Whether the candidate satisfies all benchmark-reference hard constraints. |
| `failed_hard_constraints` | list | Hard requirements marked failed by the annotation pipeline. |
| `soft_preference_score` | float | Weighted soft-preference score. |
| `benchmark_reference_utility` | float | Utility used for ranking metrics in the camera-ready release. |
| `quality_group` | string | Ground-truth, hard-negative, or medium-negative grouping. |
| `candidate_shortlist_rank` | int | Position in the canonicalized upstream candidate shortlist; this is not the benchmark-reference rank. |

The released Parquet files and scorers use only `benchmark_reference_utility`.

## A note on hidden attack metadata

The `controlled_documents` config contains the full controlled-source corpus. Each record
carries a `hidden_geo_document_metadata` field that records the attack design behind a
document (the package, the active primitives, and which lines are manipulated). This
metadata is for analysis and scoring only. It is **not** part of any model input: the
`visible` config never exposes it, and the visible view strips package ids, attack vectors,
and internal source flags. Likewise, candidate cards, conflict logs, missing-information
logs, extracted matrices, and agent notes are not visible to the model.

## Storage format

Records are stored as Parquet. Scalar fields are native Parquet columns and are directly
queryable. List and dict fields are JSON-encoded into string columns, with the set of
JSON-encoded columns recorded in the Parquet file metadata. The `safegeo.io.read_records`
loader restores these columns to native Python objects, giving a byte-faithful round-trip.
Reading the configs with the `datasets` library returns the JSON-encoded columns as strings;
decode them with `json.loads` if you need the nested structure.

## License

This dataset is released under the Creative Commons Attribution 4.0 International license
(CC-BY-4.0). See `../DATA_LICENSE`.

## Citation

If you use SafeGEO, please cite:

```bibtex
@article{wen2026safegeo,
  title   = {SafeGEO: Understanding Generative Engine Optimization Risks in Recommendation Agents},
  author  = {Wen, Qianfeng and Liu, Yifan Simon and Liu, Xin and Jiao, Difan and Yang, Blair and Wu, Junda and Tang, Zhenwei},
  journal = {arXiv preprint arXiv:2606.28356},
  year    = {2026}
}
```

Code & docs: <https://github.com/QianfengWen/SafeGEO> · Paper: <https://arxiv.org/abs/2606.28356>
