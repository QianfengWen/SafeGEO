#!/usr/bin/env bash
set -euo pipefail
# End-to-end SafeGEO mitigation study against any OpenAI-compatible endpoint (vLLM, OpenAI, OpenRouter, ...).
# PROVIDER selects the preset (vllm default); BASE_URL/API_KEY override it when set. For OpenAI/
# OpenRouter the runner reads the key from OPENAI_API_KEY/OPENROUTER_API_KEY, so API_KEY is optional.
MODEL="${MODEL:?set MODEL to the served model id}"
PROVIDER="${PROVIDER:-vllm}"
JSON_MODE="${JSON_MODE:-auto}"
OUT="${OUT:-runs/mitigation}"
LAYERS="${LAYERS:-L0,L1,L2,L3,L4,L5}"
TARGET_SLOTS="${TARGET_SLOTS:-A,B,C}"
TEMPERATURE="${TEMPERATURE:-0}"
TOP_P="${TOP_P:-1}"
MAX_TOKENS="${MAX_TOKENS:-6144}"
python mitigation/src/build_runfiles.py --dataset-root data --out "$OUT" --target-slots "$TARGET_SLOTS" --layers "$LAYERS"
python mitigation/src/materialize_labels.py --dataset-root data \
  --manifest "$OUT/labels/mitigation_labels_manifest.jsonl" --out "$OUT/labels/full_labels.jsonl"
mkdir -p "$OUT/requests" "$OUT/predictions"
for RF in "$OUT"/runfiles/*.jsonl; do
  L=$(basename "$RF" .jsonl)
  python mitigation/src/render_requests.py --package-root mitigation --runfile "$RF" --out "$OUT/requests/${L}.jsonl"
  runner_args=(
    --requests "$OUT/requests/${L}.jsonl"
    --model "$MODEL"
    --provider "$PROVIDER"
    --json-mode "$JSON_MODE"
    --temperature "$TEMPERATURE"
    --top-p "$TOP_P"
    --max-tokens "$MAX_TOKENS"
    --output "$OUT/predictions/${L}.jsonl"
  )
  if [[ -n "${BASE_URL:-}" ]]; then runner_args+=(--base-url "$BASE_URL"); fi
  if [[ -n "${API_KEY:-}" ]]; then runner_args+=(--api-key "$API_KEY"); fi
  python mitigation/src/run_mitigation.py "${runner_args[@]}"
done
python mitigation/src/score_mitigation.py --predictions "$OUT"/predictions/*.jsonl --labels "$OUT/labels/full_labels.jsonl" \
  --candidate-quality data/candidate_quality --source-annotations data/source_annotations \
  --geo-line-annotations data/geo_line_annotations --out-dir "$OUT/scored"
echo "Done -> $OUT"
