#!/usr/bin/env bash
set -euo pipefail
# End-to-end SafeGEO benchmark against any OpenAI-compatible endpoint (vLLM, OpenAI, OpenRouter, ...).
# PROVIDER selects the preset (vllm default); BASE_URL/API_KEY override it when set. For OpenAI/
# OpenRouter the runner reads the key from OPENAI_API_KEY/OPENROUTER_API_KEY, so API_KEY is optional.
MODEL="${MODEL:?set MODEL to the served model id}"
PROVIDER="${PROVIDER:-vllm}"
JSON_MODE="${JSON_MODE:-auto}"
EXPERIMENT="${EXPERIMENT:-main_realistic}"   # main_realistic | full | controls
OUT="${OUT:-runs/benchmark}"
mkdir -p "$OUT"
python benchmark/src/run_safegeo.py --visible data/visible --labels data/labels \
  --experiment "$EXPERIMENT" --model "$MODEL" --provider "$PROVIDER" --json-mode "$JSON_MODE" \
  ${BASE_URL:+--base-url "$BASE_URL"} ${API_KEY:+--api-key "$API_KEY"} --output "$OUT/predictions.jsonl"
python benchmark/src/score_safegeo.py --predictions "$OUT/predictions.jsonl" --labels data/labels \
  --candidate-quality data/candidate_quality --source-annotations data/source_annotations \
  --geo-line-annotations data/geo_line_annotations --out-dir "$OUT/scored"
python benchmark/src/analyze_safegeo_plan.py --scored "$OUT/scored/per_instance_scored.jsonl" --out-dir "$OUT/tables"
echo "Done -> $OUT"
