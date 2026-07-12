#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.dataset as pads

KEEP_IDS = set([
    "GRT-home-air-purifier-056", "GRT-noise-canceling-headphones-053", "GRT-baby-monitor-046",
    "GRT-ai-meeting-transcription-076", "GRT-ai-meeting-transcription-014", "GRT-carry-on-backpack-052",
    "GRT-carry-on-backpack-051", "GRT-ai-meeting-transcription-052", "GRT-noise-canceling-headphones-051",
    "GRT-baby-monitor-014", "GRT-office-chair-003", "GRT-ai-meeting-transcription-094",
    "GRT-noise-canceling-headphones-069", "GRT-office-chair-064", "GRT-baby-monitor-038",
    "GRT-carry-on-backpack-043", "GRT-baby-monitor-006", "GRT-office-chair-068",
    "GRT-office-chair-038", "GRT-office-chair-036", "GRT-carry-on-backpack-035",
    "GRT-home-air-purifier-048", "GRT-noise-canceling-headphones-072", "GRT-home-air-purifier-003",
    "GRT-ai-meeting-transcription-066", "GRT-carry-on-backpack-091", "GRT-office-chair-031",
    "GRT-ai-meeting-transcription-086", "GRT-carry-on-backpack-038", "GRT-noise-canceling-headphones-035",
    "GRT-ai-meeting-transcription-024", "GRT-noise-canceling-headphones-063", "GRT-office-chair-027",
    "GRT-home-air-purifier-082", "GRT-carry-on-backpack-023", "GRT-carry-on-backpack-010",
    "GRT-office-chair-044", "GRT-baby-monitor-092", "GRT-home-air-purifier-032",
    "GRT-baby-monitor-067", "GRT-home-air-purifier-094", "GRT-baby-monitor-008",
    "GRT-noise-canceling-headphones-033", "GRT-office-chair-010", "GRT-ai-meeting-transcription-047",
    "GRT-home-air-purifier-016", "GRT-ai-meeting-transcription-060", "GRT-carry-on-backpack-099",
    "GRT-carry-on-backpack-007", "GRT-baby-monitor-053", "GRT-home-air-purifier-083",
    "GRT-noise-canceling-headphones-039", "GRT-home-air-purifier-000", "GRT-ai-meeting-transcription-055",
    "GRT-noise-canceling-headphones-093", "GRT-noise-canceling-headphones-026", "GRT-home-air-purifier-033",
    "GRT-office-chair-050", "GRT-baby-monitor-073", "GRT-baby-monitor-083",
])
DATA_ROOT = Path("data")
CONFIGS = [
    "requirement_annotations",
    "candidate_quality",
    "source_annotations",
    "visible",
    "labels",
]


def decode(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if s and s[0] in "[{" and s[-1] in "]}":
            try:
                return decode(json.loads(s))
            except Exception:
                return value
        return value
    if isinstance(value, list):
        return [decode(x) for x in value]
    if isinstance(value, dict):
        return {k: decode(v) for k, v in value.items()}
    return value


def first(row: dict[str, Any] | None, names: list[str], default: Any = None) -> Any:
    if not row:
        return default
    for name in names:
        if name in row and row[name] not in (None, "", [], {}):
            return decode(row[name])
    return default


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def load_filtered(config: str) -> list[dict[str, Any]]:
    dataset = pads.dataset(str(DATA_ROOT / config), format="parquet")
    names = set(dataset.schema.names)
    key = "query_id" if "query_id" in names else "base_case_id" if "base_case_id" in names else None
    if key is None:
        raise RuntimeError(f"{config} has neither query_id nor base_case_id: {sorted(names)}")
    table = dataset.to_table(filter=pads.field(key).isin(sorted(KEEP_IDS)))
    rows = [decode(dict(row)) for row in table.to_pylist()]
    print(config, len(rows), flush=True)
    return rows


def choose_control(rows: list[dict[str, Any]], label_by_instance: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def score(v: dict[str, Any]) -> tuple[int, str]:
        iid = safe_text(v.get("instance_id"))
        lab = label_by_instance.get(iid, {})
        text = " ".join(
            safe_text(lab.get(k)).lower()
            for k in ["control_type", "scenario_type", "package_id", "expanded_instance_id"]
        )
        if "all_truthful" in text or "truthful_target" in text:
            return (0, iid)
        if "truthful" in text:
            return (1, iid)
        if "no_geo" in text or "original_no" in text:
            return (2, iid)
        return (9, iid)

    if not rows:
        raise RuntimeError("No visible rows for selected case")
    return min(rows, key=score)


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    return str(value)


def main() -> None:
    all_rows = {config: load_filtered(config) for config in CONFIGS}
    labels = all_rows.pop("labels")
    visible = all_rows.pop("visible")
    label_by_instance = {safe_text(row.get("instance_id")): row for row in labels}

    visible_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in visible:
        q = safe_text(first(row, ["query_id", "base_case_id"]))
        visible_by_case[q].append(row)

    selected_visible: dict[str, dict[str, Any]] = {}
    for q in sorted(KEEP_IDS):
        selected_visible[q] = choose_control(visible_by_case[q], label_by_instance)

    payload = {
        "dataset": "wieeii/SafeGEO",
        "selected_case_ids": sorted(KEEP_IDS),
        "requirement_annotations": all_rows["requirement_annotations"],
        "candidate_quality": all_rows["candidate_quality"],
        "source_annotations": all_rows["source_annotations"],
        "selected_visible": selected_visible,
    }
    out = Path("safegeo_audit_selected_rows.json.gz")
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(payload, f, ensure_ascii=False, default=json_default)
    print(f"WROTE {out} {out.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    main()
