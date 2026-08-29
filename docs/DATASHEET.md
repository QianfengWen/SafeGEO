# Datasheet for SafeGEO

This datasheet follows the structure proposed in *Datasheets for Datasets* (Gebru et al.).
It documents the motivation, composition, synthesis, preprocessing, intended uses,
distribution, and limitations of the SafeGEO dataset.

## Motivation

Generative Engine Optimization (GEO) lets content owners rewrite web content to increase
their visibility in generative systems. When a recommendation agent reads such documents,
seller-controlled sources can make a flawed product appear better supported than it is.
SafeGEO was created to measure this risk directly at the generation stage: it fixes the
candidate roster and retrieved source packet, then tests whether a model preserves
utility-aligned recommendations when one seller-controlled source is rewritten. It does not
evaluate live retrieval, crawling, source selection, tool use, or UI presentation.

The dataset supports two studies. The benchmark measures how far GEO attacks can move a
flawed target into the user's decision set across a wide attack library. The mitigation
study measures how much developer-side defenses reduce that effect on eight plausible
realistic GEO packages.

## Composition

### Instances

The dataset is built from 600 recommendation base cases, distributed evenly across 6 product
verticals (100 cases each): `ai_meeting_transcription`, `baby_monitor`, `carry_on_backpack`,
`home_air_purifier`, `noise_canceling_headphones`, and `office_chair`. A base case is a
single recommendation query with a roster of 18 to 22 candidate products, a fixed assignment
of three attack targets (slots A, B, and C), and the source corpus an agent would read.

Each base case is expanded into 68 instances:

- 22 attack packages applied to each of the 3 target slots (66 attacked instances), plus
- 2 controls (`original_no_geo_control` and `all_truthful_target_control`).

This produces 40,800 instances in total (600 base cases times 68). The attack library is
described in full in the [attack taxonomy](ATTACK_TAXONOMY.md): 7 primitives across 3
manipulation loci (content, epistemic, model-facing), composed into 7 atomic, 3 block, 4
block-combination, and 8 realistic packages. The package family is `realistic` throughout the
released `package_family` column as a stable identifier; it does not claim that the family is
representative of live-web attack prevalence.

### Semantics of the visible view

The visible inputs remove construction scaffolding while preserving the user's decision
semantics. The following properties hold of the model-facing data:

- Every visible query is the identifier-sanitized construction query. All decision-relevant
  hard constraints and soft preferences remain in the natural-language request; only the
  structured decomposition and construction metadata are hidden. An exact audit over all 600
  queries and 40,800 visible rows found zero request--label mismatches.
- Sources are longer and more ambiguous than a clean specification. Ground-truth evidence
  may be implicit, weak, embedded in surrounding text, or absent from the visible text
  entirely.
- Negative candidates may fail a hidden requirement or simply lack clear support, rather
  than being obviously wrong.
- Scaffolding artifacts are not visible: candidate cards, conflict logs, missing-information
  logs, extracted matrices, and agent notes are stripped from the model-facing view.
- Attack documents remain assertive. The GEO rewrites read as confident, well-formed
  sources, which is what makes them effective.

These transformations apply only to the visible inputs. The hidden labels preserve
the benchmark-reference evaluation, so scoring remains comparable across instances. The
per-instance `realism_adjustments` field in the `labels` config records which transformations
were applied.

### Configurations

The dataset is published as 10 Hugging Face Parquet configurations.

| Config | Rows | Contents |
|---|---|---|
| `visible` | 40,800 | Model-facing inputs (query, candidate roster, source documents). |
| `labels` | 40,800 | Hidden benchmark reference (package, attack vector, target mapping, evaluation keys). |
| `candidate_quality` | 11,974 | Per-candidate benchmark-reference judgments for utility and ranking metrics. |
| `source_annotations` | 21,513 | Per-source annotations for citation-validity scoring. |
| `geo_line_annotations` | 414,000 | Line-level misleading and refuting-line annotations. |
| `targets` | 600 | Fixed A/B/C target assignment per base case. |
| `instances_manifest` | 40,800 | Manifest mapping each instance to base case, package, and slot. |
| `quality_distributions` | 600 | Per-query candidate quality distribution. |
| `requirement_annotations` | 600 | Per-query requirement annotations. |
| `controlled_documents` | 41,400 | Full controlled-source corpus with hidden attack metadata. |

The `candidate_quality` config uses `benchmark_reference_utility` for the utility value consumed
by uNDCG@5 and regret scoring. The `controlled_documents` config carries a
`hidden_geo_document_metadata` field that
describes the attack behind each document. This is used only for analysis and scoring and is
never exposed to the model. Field-level column dictionaries for the `visible` and `labels`
configs are in `data/README.md`.

### Labeling and audit

Reference labels are produced by the synthesis pipeline rather than exhaustively annotated by
humans. Each instance
carries its attack package, the per-primitive attack vector, the active manipulation loci,
the mapping from target slots to controlled documents, the candidate-quality judgments needed
to compute utility, and line-level annotations marking misleading and refuting lines. These
labels define the benchmark reference used by the scorers; they are not claims of independently
verified real-world product truth.

Two annotators who were not involved in dataset construction independently audited 60
vertical-stratified cases, including 180 hard requirements, 540 candidate--requirement pairs,
180 candidate pairs, and 600 line--claim pairs. Inter-annotator exact agreement was 100.0% for
hard-requirement extraction, 76.7% for candidate hard status, 78.1% for pairwise utility
ordering, 91.7% for the top candidate, 83.3% for evidence relation, 80.3% for truth status,
and 88.9% for utility validity. Full aggregate definitions and model--human agreement are in
[the human-audit report](HUMAN_AUDIT.md).

## Collection and synthesis process

SafeGEO is a hybrid, controlled artifact. Base candidates and source records are derived from
production shopping-research traces, then canonicalized and de-identified. The seller-source
control and GEO records are synthetic, and utility/evidence reference labels are generated by
the annotation pipeline. `benchmark/config/synthesis_config.yaml` fixes design parameters,
including:

- 600 base cases, with 18 to 22 candidates per query and 2 to 3 ground-truth candidates per
  query.
- Three eligible non-ground-truth targets per base case, fixed as nominal slots A/B/C. Slots are
  evaluated symmetrically and do not encode difficulty; candidate-specific constraint and evidence
  properties remain in the hidden reference annotations. No primary or acceptable ground-truth
  candidate is used as an attack target.
- A source budget per case (catalog entries, opened evidence chunks, and the number of
  controlled target sources, chunks, and lines per chunk).
- Visible sanitization rules that neutralize instance and document identifiers and remove
  attack vectors, package ids, and internal source flags without removing user requirements.

The released records are de-identified and contain no intended personal or human-subject data.
The repository does not redistribute raw proprietary webpages.

## Preprocessing, cleaning, and labeling

The released data was converted once from source JSONL into the Parquet dataset. Conversion
performed two operations:

- **Storage encoding.** Scalar fields become native Parquet columns (directly queryable in
  standard tooling). List- and dict-valued fields are JSON-encoded into string columns, with
  the set of JSON-encoded columns recorded in the Parquet file metadata. The
  `safegeo.io.read_records` loader restores these columns to native Python objects, giving a
  byte-faithful round-trip.
- **Request alignment.** Every visible `user_query` is the identifier-sanitized construction
  query. The exact check over 600 cases and 40,800 expanded rows is implemented in
  `scripts/audit_camera_ready_claims.py`.
- **Reference terminology.** Public utility fields use `benchmark_reference_utility`. The
  released data and scorers use this field directly.

A tiny `sample/` subset (2 base cases per vertical) is derived by `scripts/build_sample.py`
for offline smoke tests that need no GPU.

## Uses

The dataset is intended for:

- Benchmarking the robustness of recommendation agents to GEO attacks: measuring how much
  attacks raise attacked-target top-three placement and hard-constraint-violating top-one
  recommendations relative to truthful controls.
- Studying agent-side mitigations: measuring how developer-side defenses (defensive
  prompting, rationale elicitation, evidence breakdowns, context balancing, and instruction
  filtering) reduce attack effectiveness on the realistic packages.

The dataset should not be used to develop or improve GEO attacks against deployed systems.
Because the released artifact is canonicalized/de-identified and confined to consumer product recommendation, results
should not be read as measurements of any specific real-world product, brand, or marketplace.

The repository also publishes **SafeGEO Diamond**, a 600-instance, vertical-balanced screening
split. Diamond deliberately uses the three realistic packages with the highest DeepSeek-V4-Flash
Target@3 values and therefore is a hard stress set, not an unbiased estimator of full-SafeGEO
performance.

## Distribution and license

The dataset is released under the Creative Commons Attribution 4.0 International license
(CC-BY-4.0); see `DATA_LICENSE`. The accompanying code is released under the Apache License
2.0; see `LICENSE`.

## Limitations

- Controlled seller-source rewrites use fixed text templates and do not reproduce the full
  diversity, layout, ratings, images, structured metadata, or noise of real webpages.
- Coverage is limited to 6 consumer product verticals and to text-only sources. Other
  domains, modalities, and recommendation settings are out of scope.
- The evaluation fixes retrieval and source selection and measures only source-conditioned
  LLM reranking/generation; it is not an end-to-end deployed recommendation-agent benchmark.
- The attack library is broad but not exhaustive; it captures the manipulation loci and
  primitives defined in the taxonomy rather than every conceivable GEO technique.
- The mitigation study is a focused stress test (all three targets, the 8 realistic
  packages, 14,400 instances per layer). It is not a complete factorial over all 22 attacks.
- Quality judgments and line-level annotations are pipeline-generated. The 60-case human audit
  improves confidence but is not exhaustive, and utility ordering shows more disagreement than
  hard-requirement extraction.
