# SafeGEO Aggregate Results

This directory contains the aggregate results reported in the camera-ready paper. It intentionally
does not include model-response traces, prediction dumps, or intermediate run records.

Files:

- [`deepseek_v4_flash_all22.csv`](deepseek_v4_flash_all22.csv): both controls and all 22 GEO
  variants on DeepSeek-V4-Flash.
- [`deepseek_v4_flash_mitigation.csv`](deepseek_v4_flash_mitigation.csv): the no-mitigation
  baseline and five intervention conditions averaged over eight realistic packages and three targets.
- [`deepseek_v4_flash_sensitivity.csv`](deepseek_v4_flash_sensitivity.csv): source-position and
  packet-depth sensitivity.
- [`paired_mechanism.csv`](paired_mechanism.csv): evidence, constraint-audit, and ranking-field
  associations from the paired response analysis.
- [`main_models_mitigation.csv`](main_models_mitigation.csv): aggregate mitigation results for
  the three main models.
- [`main_models_mitigation_by_package.csv`](main_models_mitigation_by_package.csv): Target@3
  reductions by model, strategy, and realistic package.
- [`main_models_evidence_breakdown_by_vertical.csv`](main_models_evidence_breakdown_by_vertical.csv):
  evidence-breakdown Target@3 reductions by model and vertical.
- [`../docs/HUMAN_AUDIT.md`](../docs/HUMAN_AUDIT.md): the 60-case human-audit agreement table.

All rate changes are percentage points. Attack deltas use the truthful-rewrite control;
mitigation deltas use the no-mitigation condition. Run
`python scripts/generate_mitigation_figures.py --output-dir <paper-figure-dir>` to regenerate the
paper figures with descriptive strategy labels. The paper contains confidence intervals,
definitions, and the full interpretation of each table.
