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
TEMPERATURE="${TEMPERATURE:-0}"
TOP_P="${TOP_P:-1}"
MAX_TOKENS="${MAX_TOKENS:-6144}"
mkdir -p "$OUT"
runner_args=(
  --visible data/visible
  --labels data/labels
  --experiment "$EXPERIMENT"
  --model "$MODEL"
  --provider "$PROVIDER"
  --json-mode "$JSON_MODE"
  --temperature "$TEMPERATURE"
  --top-p "$TOP_P"
  --max-tokens "$MAX_TOKENS"
  --output "$OUT/predictions.jsonl"
)
if [[ -n "${BASE_URL:-}" ]]; then runner_args+=(--base-url "$BASE_URL"); fi
if [[ -n "${API_KEY:-}" ]]; then runner_args+=(--api-key "$API_KEY"); fi
python benchmark/src/run_safegeo.py "${runner_args[@]}"
python benchmark/src/score_safegeo.py --predictions "$OUT/predictions.jsonl" --labels data/labels \
  --candidate-quality data/candidate_quality --source-annotations data/source_annotations \
  --geo-line-annotations data/geo_line_annotations --out-dir "$OUT/scored"
python benchmark/src/analyze_safegeo_plan.py --scored "$OUT/scored/per_instance_scored.jsonl" --out-dir "$OUT/tables"
echo "Done -> $OUT"
