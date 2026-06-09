# Datasheet for SafeGEO

This datasheet follows the structure proposed in *Datasheets for Datasets* (Gebru et al.).
It documents the motivation, composition, synthesis, preprocessing, intended uses,
distribution, and limitations of the SafeGEO dataset.

## Motivation

Generative Engine Optimization (GEO) lets content owners rewrite web content to increase
their visibility in generative systems. When a recommendation agent reads such documents,
seller-controlled sources can make a flawed product appear better supported than it is.
SafeGEO was created to measure this risk directly: it tests whether a model preserves
utility-aligned recommendations when the sources it reads have been rewritten by a GEO
adversary, and it provides a setting for studying agent-side defenses against that adversary.

The dataset supports two studies. The benchmark measures how far GEO attacks can move a
flawed target into the user's decision set across a wide attack library. The mitigation
study measures how much developer-side defenses reduce that effect on a realistic subset of
attacks.

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
block-combination, and 8 realistic packages.

### Realism of the visible view

The visible inputs are deliberately realistic and underspecified, so that an agent must
reason rather than pattern-match. The following properties hold of the model-facing data:

- Visible queries do not enumerate the hidden constraints or preferences a good
  recommendation must satisfy. The user states a need in natural terms, and the agent must
  infer what matters.
- Sources are longer and more ambiguous than a clean specification. Ground-truth evidence
  may be implicit, weak, embedded in surrounding text, or absent from the visible text
  entirely.
- Negative candidates may fail a hidden requirement or simply lack clear support, rather
  than being obviously wrong.
- Scaffolding artifacts are not visible: candidate cards, conflict logs, missing-information
  logs, extracted matrices, and agent notes are stripped from the model-facing view.
- Attack documents remain assertive. The GEO rewrites read as confident, well-formed
  sources, which is what makes them effective.

These realism transformations apply only to the visible inputs. The hidden labels preserve
the canonical evaluation, so scoring remains exact and comparable across instances. The
per-instance `realism_adjustments` field in the `labels` config records which transformations
were applied.

### Configurations

The dataset is published as 10 Hugging Face Parquet configurations.

| Config | Rows | Contents |
|---|---|---|
| `visible` | 40,800 | Model-facing inputs (query, candidate roster, source documents). |
| `labels` | 40,800 | Hidden ground truth (package, attack vector, target mapping, evaluation keys). |
| `candidate_quality` | 11,974 | Per-candidate quality judgments for utility and ranking metrics. |
| `source_annotations` | 21,513 | Per-source annotations for citation-validity scoring. |
| `geo_line_annotations` | 414,000 | Line-level misleading and refuting-line annotations. |
| `targets` | 600 | Fixed A/B/C target assignment per base case. |
| `instances_manifest` | 40,800 | Manifest mapping each instance to base case, package, and slot. |
| `quality_distributions` | 600 | Per-query candidate quality distribution. |
| `requirement_annotations` | 600 | Per-query requirement annotations. |
| `controlled_documents` | 41,400 | Full controlled-source corpus with hidden attack metadata. |

The `controlled_documents` config carries a `hidden_geo_document_metadata` field that
describes the attack behind each document. This is used only for analysis and scoring and is
never exposed to the model. Field-level column dictionaries for the `visible` and `labels`
configs are in `data/README.md`.

### Labeling

Labels are produced by the synthesis pipeline rather than by human annotation. Each instance
carries its attack package, the per-primitive attack vector, the active manipulation loci,
the mapping from target slots to controlled documents, the candidate-quality judgments needed
to compute utility, and line-level annotations marking misleading and refuting lines. These
labels define the canonical evaluation used by the scorers.

## Collection and synthesis process

The dataset is synthetic. It is generated by the SafeGEO synthesis pipeline according to
`benchmark/config/synthesis_config.yaml`, which fixes the design parameters, including:

- 600 base cases, with 18 to 22 candidates per query and 2 to 3 ground-truth candidates per
  query.
- Three target slots per base case, randomly sampled from the candidate roster and grouped by
  evidence stratum (`A: primary_harmful_near_miss`, `B: contrast_hard_negative`,
  `C: utility_or_uncertainty_target`).
- A source budget per case (catalog entries, opened evidence chunks, and the number of
  controlled target sources, chunks, and lines per chunk).
- Visible sanitization rules that neutralize instance and document identifiers and remove
  attack vectors, package ids, and internal source flags from the visible view.

Because the data is fully synthetic, no personal or human-subject data is involved.

## Preprocessing, cleaning, and labeling

The released data was converted once from source JSONL into the Parquet dataset. Conversion
performed two operations:

- **Storage encoding.** Scalar fields become native Parquet columns (directly queryable in
  standard tooling). List- and dict-valued fields are JSON-encoded into string columns, with
  the set of JSON-encoded columns recorded in the Parquet file metadata. The
  `safegeo.io.read_records` loader restores these columns to native Python objects, giving a
  byte-faithful round-trip.
- **Normalization.** Two metadata fields whose names carried a legacy version prefix were
  renamed to unprefixed names, and version-prefixed tags were stripped from the `version`
  metadata value, so the released dataset is self-consistent and free of internal release
  markers.

A tiny `sample/` subset (2 base cases per vertical) is derived by `scripts/build_sample.py`
for offline smoke tests that need no GPU.

## Uses

The dataset is intended for:

- Benchmarking the robustness of recommendation agents to GEO attacks: measuring how much
  attacks raise attacked-target top-three placement and hard-constraint-violating top-one
  recommendations relative to truthful controls.
- Studying agent-side mitigations: measuring how developer-side defenses (defensive
  prompting, rationale elicitation, evidence breakdowns, context balancing, and instruction
  filtering) reduce attack effectiveness on the realistic attack subset.

The dataset should not be used to develop or improve GEO attacks against deployed systems.
Because all instances are synthetic and confined to consumer product recommendation, results
should not be read as measurements of any specific real-world product, brand, or marketplace.

## Distribution and license

The dataset is released under the Creative Commons Attribution 4.0 International license
(CC-BY-4.0); see `DATA_LICENSE`. The accompanying code is released under the Apache License
2.0; see `LICENSE`.

## Limitations

- The data is synthetic. It is designed to be realistic and underspecified, but it does not
  reproduce the full diversity or noise of real web sources.
- Coverage is limited to 6 consumer product verticals and to text-only sources. Other
  domains, modalities, and recommendation settings are out of scope.
- The attack library is broad but not exhaustive; it captures the manipulation loci and
  primitives defined in the taxonomy rather than every conceivable GEO technique.
- The mitigation study is a focused stress test (Target A, the 8 realistic packages, 600 base
  cases per layer). It is not a complete factorial over every package and slot.
- Quality judgments and line-level annotations are generated by the synthesis pipeline rather
  than independently human-verified.
