# SafeGEO Diamond

SafeGEO Diamond is a fast, high-difficulty screening split with 600 expanded instances: 120
base cases (20 per product vertical), hard-infeasible target A, the three most harmful plausible
realistic packages on DeepSeek-V4-Flash, and both controls (the unmodified source and the
truthful target-source rewrite).

The selected attacks are `selective_comparison_note`, `false_fit_checklist`, and
`citation_padded_note`. Base cases are selected independently of model outcomes by a fixed,
vertical-stratified hash. The exact IDs and row counts are recorded in
`selection_manifest.json`.

Diamond is 68 times smaller than the 40,800-instance diagnostic benchmark and 26 times smaller
than the 15,600-instance realistic-package evaluation. It supports rapid robustness screening and model
iteration. Its attacks are selected for high attack success, so population-level reporting
should use the complete benchmark.

Diamond inherits the full dataset's CC BY 4.0 license in `DATA_LICENSE`.

Run it with the ordinary benchmark pipeline:

```bash
python benchmark/src/run_safegeo.py \
  --visible diamond/visible \
  --labels diamond/labels \
  --experiment full \
  --model "$MODEL" \
  --base-url http://127.0.0.1:8000/v1 \
  --output runs/diamond/predictions.jsonl

python benchmark/src/score_safegeo.py \
  --predictions runs/diamond/predictions.jsonl \
  --labels diamond/labels \
  --candidate-quality diamond/candidate_quality \
  --source-annotations diamond/source_annotations \
  --geo-line-annotations diamond/geo_line_annotations \
  --out-dir runs/diamond/scored
```

Rebuild the split deterministically with:

```bash
python scripts/build_diamond.py --data-root data --out diamond
```
