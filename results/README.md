# SafeGEO Aggregate Results

This directory contains the aggregate results reported in the camera-ready paper. It intentionally
does not include model-response traces, prediction dumps, or intermediate run records.

Files:

- [`deepseek_v4_flash_all22.csv`](deepseek_v4_flash_all22.csv): both controls and all 22 GEO
  variants on DeepSeek-V4-Flash.
- [`deepseek_v4_flash_mitigation.csv`](deepseek_v4_flash_mitigation.csv): L0--L5 averaged over
  eight plausible synthetic archetypes and three targets.
- [`deepseek_v4_flash_sensitivity.csv`](deepseek_v4_flash_sensitivity.csv): source-position and
  packet-depth sensitivity.
- [`paired_mechanism.csv`](paired_mechanism.csv): evidence, constraint-audit, and ranking-field
  associations from the paired response analysis.
- [`../docs/HUMAN_AUDIT.md`](../docs/HUMAN_AUDIT.md): the 60-case human-audit agreement table.

All rate changes are percentage points. Attack deltas use the truthful-rewrite control;
mitigation deltas use L0. The paper contains confidence intervals, definitions, and the full
interpretation of each table.
