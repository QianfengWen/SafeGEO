#!/usr/bin/env python3
"""Produce SafeGEO plan-level tables from scored per-instance outputs."""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import json
from math import isnan
from pathlib import Path
import random
from statistics import median
from typing import Any, Iterable

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "src"))
from safegeo.taxonomy import (
    CONTROL_PACKAGES, REALISTIC_PACKAGES as _RP,
    CITATION_FOCUS_PACKAGES, ATTACK_VECTOR_KEYS,
)
REALISTIC_PACKAGES = set(_RP)
PRIMARY_BOOTSTRAP_METRICS = (
    "top1_primary_gt",
    "top3_contains_acceptable_gt",
    "utility_ndcg_at_5",
    "regret_at_1",
    "hard_violation_at_1",
    "attacked_target_top3",
    "attacked_target_rank_gain",
    "misleading_geo_line_citation",
    "paired_refuting_evidence_cited",
)
REGRESSION_OUTCOMES = (
    "attacked_target_top3",
    "attacked_target_rank_gain",
    "hard_violation_at_1",
    "misleading_geo_line_citation",
    "paired_refuting_evidence_cited",
)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        x = float(value)
        if isnan(x):
            return None
        return x
    return None


def mean(values: Iterable[Any]) -> float | None:
    xs = [x for value in values if (x := numeric(value)) is not None]
    return sum(xs) / len(xs) if xs else None


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def group_rows(rows: Iterable[dict[str, Any]], fields: list[str]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(field) for field in fields)].append(row)
    return groups


def summarize(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, group in sorted(group_rows(rows, fields).items(), key=lambda item: str(item[0])):
        attacks = [row for row in group if row.get("package_id") not in CONTROL_PACKAGES]
        record = {field: value for field, value in zip(fields, key)}
        record.update(
            {
                "n": len(group),
                "n_attacks": len(attacks),
                "top1_primary_gt_accuracy": mean(row.get("top1_primary_gt") for row in group),
                "top3_acceptable_gt_recall": mean(row.get("top3_contains_acceptable_gt") for row in group),
                "utility_ndcg_at_5": mean(row.get("utility_ndcg_at_5") for row in group),
                "regret_at_1": mean(row.get("regret_at_1") for row in group),
                "hard_violation_at_1": mean(row.get("hard_violation_at_1") for row in group),
                "attacked_target_top1_rate": mean(row.get("attacked_target_top1") for row in attacks),
                "attacked_target_top3_rate": mean(row.get("attacked_target_top3") for row in attacks),
                "attacked_target_rank_gain": mean(row.get("attacked_target_rank_gain") for row in attacks),
                "target_top3_uplift": mean(row.get("attacked_target_top3_uplift") for row in attacks),
                "geo_doc_citation_rate": mean(row.get("geo_doc_cited") for row in attacks),
                "misleading_geo_line_citation_rate": mean(row.get("misleading_geo_line_citation") for row in attacks),
                "paired_refuting_evidence_recall": mean(row.get("paired_refuting_evidence_cited") for row in attacks),
                "valid_citation_rate": mean(row.get("valid_citation_rate") for row in group),
                "target_gap_detection_rate": mean(row.get("target_gap_detected") for row in attacks),
                "unknown_treated_as_satisfied_rate": mean(row.get("unknown_treated_as_satisfied") for row in attacks),
                "model_instruction_compliance_rate": mean(row.get("model_instruction_compliance") for row in attacks),
                "parse_failure_rate": mean(row.get("parse_failure") for row in group),
            }
        )
        out.append(record)
    return out


def model_robustness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for (model,), group in sorted(group_rows(rows, ["model"]).items()):
        attacks = [r for r in group if r.get("package_id") not in CONTROL_PACKAGES]
        controls = [r for r in group if r.get("package_id") in CONTROL_PACKAGES]
        all_truthful = [r for r in group if r.get("package_id") == "all_truthful_target_control"]
        original = [r for r in group if r.get("package_id") == "original_no_geo_control"]
        out.append(
            {
                "model": model,
                "n_total": len(group),
                "n_controls": len(controls),
                "n_attacks": len(attacks),
                "control_top1_gt_accuracy": mean(r.get("top1_primary_gt") for r in controls),
                "original_control_top1_gt_accuracy": mean(r.get("top1_primary_gt") for r in original),
                "all_truthful_control_top1_gt_accuracy": mean(r.get("top1_primary_gt") for r in all_truthful),
                "attack_top1_gt_accuracy": mean(r.get("top1_primary_gt") for r in attacks),
                "attack_top3_gt_recall": mean(r.get("top3_contains_acceptable_gt") for r in attacks),
                "attack_utility_ndcg_at_5": mean(r.get("utility_ndcg_at_5") for r in attacks),
                "attack_regret_at_1": mean(r.get("regret_at_1") for r in attacks),
                "attack_hard_violation_at_1": mean(r.get("hard_violation_at_1") for r in attacks),
                "attack_target_top3_rate": mean(r.get("attacked_target_top3") for r in attacks),
                "attack_target_rank_gain": mean(r.get("attacked_target_rank_gain") for r in attacks),
                "attack_target_top3_uplift": mean(r.get("attacked_target_top3_uplift") for r in attacks),
                "attack_misleading_geo_line_citation_rate": mean(r.get("misleading_geo_line_citation") for r in attacks),
                "attack_refuting_evidence_recall": mean(r.get("paired_refuting_evidence_cited") for r in attacks),
                "parse_failure_rate": mean(r.get("parse_failure") for r in group),
            }
        )
    return out


def control_comparison(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    controls = [r for r in rows if r.get("package_id") in CONTROL_PACKAGES]
    out = summarize(controls, ["model", "package_id"])
    by_key = group_rows(controls, ["model", "package_id"])
    for record in out:
        group = by_key[(record["model"], record["package_id"])]
        for slot in ("A", "B", "C"):
            record[f"target_{slot}_mean_rank"] = mean(r.get(f"target_{slot}_rank") for r in group)
            ranks = [x for r in group if (x := numeric(r.get(f"target_{slot}_rank"))) is not None]
            record[f"target_{slot}_median_rank"] = median(ranks) if ranks else None
            record[f"target_{slot}_top3_rate"] = mean(r.get(f"target_{slot}_top3") for r in group)
    return out


def dataset_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(str(row.get("instance_id")), row)
    base_cases = {row.get("base_case_id") for row in unique.values()}
    packages = sorted({row.get("package_id") for row in unique.values()})
    verticals = sorted({row.get("vertical") for row in unique.values()})
    families = sorted({row.get("package_family") for row in unique.values()})
    return {
        "models": sorted({row.get("model") for row in rows}),
        "unique_instances": len(unique),
        "base_cases": len(base_cases),
        "verticals": verticals,
        "n_verticals": len(verticals),
        "packages": packages,
        "n_packages": len(packages),
        "package_families": families,
        "n_controls": sum(1 for row in unique.values() if row.get("package_id") in CONTROL_PACKAGES),
        "n_attack_instances": sum(1 for row in unique.values() if row.get("package_id") not in CONTROL_PACKAGES),
    }


def bootstrap_cis(rows: list[dict[str, Any]], reps: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out: list[dict[str, Any]] = []
    for (model,), model_rows in sorted(group_rows(rows, ["model"]).items()):
        attacks = [r for r in model_rows if r.get("package_id") not in CONTROL_PACKAGES]
        by_base = group_rows(attacks, ["base_case_id"])
        base_ids = sorted(by_base)
        if not base_ids:
            continue
        for metric in PRIMARY_BOOTSTRAP_METRICS:
            per_base: list[tuple[float, int]] = []
            for base_key in base_ids:
                xs = [x for r in by_base[base_key] if (x := numeric(r.get(metric))) is not None]
                per_base.append((sum(xs), len(xs)))
            point_sum = sum(total for total, _count in per_base)
            point_count = sum(count for _total, count in per_base)
            if point_count == 0:
                continue
            values: list[float] = []
            for _ in range(reps):
                total = 0.0
                count = 0
                for _sample in base_ids:
                    sample_total, sample_count = per_base[rng.randrange(len(per_base))]
                    total += sample_total
                    count += sample_count
                if count:
                    values.append(total / count)
            out.append(
                {
                    "model": model,
                    "subset": "attack_instances",
                    "metric": metric,
                    "n_base_cases": len(base_ids),
                    "n_rows": point_count,
                    "point_estimate": point_sum / point_count,
                    "ci_low_95": quantile(values, 0.025),
                    "ci_high_95": quantile(values, 0.975),
                    "bootstrap_reps": reps,
                }
            )
    return out


def primitive_regression(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    attacks = [r for r in rows if r.get("package_id") not in CONTROL_PACKAGES]
    if not attacks:
        return []

    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover - depends on environment
        out: list[dict[str, Any]] = []
        for outcome in REGRESSION_OUTCOMES:
            for key in ATTACK_VECTOR_KEYS:
                on = [numeric(r.get(outcome)) for r in attacks if r.get(f"attack_vector_{key}")]
                off = [numeric(r.get(outcome)) for r in attacks if not r.get(f"attack_vector_{key}")]
                on = [x for x in on if x is not None]
                off = [x for x in off if x is not None]
                if not on or not off:
                    continue
                out.append(
                    {
                        "outcome": outcome,
                        "term": f"attack_vector_{key}",
                        "estimate": (sum(on) / len(on)) - (sum(off) / len(off)),
                        "mean_when_present": sum(on) / len(on),
                        "mean_when_absent": sum(off) / len(off),
                        "n_present": len(on),
                        "n_absent": len(off),
                        "estimator": "marginal_difference_fallback",
                        "note": f"numpy unavailable for fixed-effect least squares: {exc}",
                    }
                )
        return out

    cat_fields = ["attacked_target_slot", "attacked_target_difficulty", "vertical", "model", "base_case_id"]
    categories = {field: sorted({str(r.get(field)) for r in attacks if r.get(field) is not None}) for field in cat_fields}
    feature_names = [f"attack_vector_{key}" for key in ATTACK_VECTOR_KEYS]
    for field in cat_fields:
        for value in categories[field][1:]:
            feature_names.append(f"{field}={value}")

    base_x: list[list[float]] = []
    for row in attacks:
        xs = [1.0]
        xs.extend(float(row.get(f"attack_vector_{key}") or 0) for key in ATTACK_VECTOR_KEYS)
        for field in cat_fields:
            value = str(row.get(field))
            xs.extend(1.0 if value == category else 0.0 for category in categories[field][1:])
        base_x.append(xs)
    x_all = np.asarray(base_x, dtype=float)
    names = ["intercept", *feature_names]

    out: list[dict[str, Any]] = []
    for outcome in REGRESSION_OUTCOMES:
        idx: list[int] = []
        y_values: list[float] = []
        for i, row in enumerate(attacks):
            y = numeric(row.get(outcome))
            if y is not None:
                idx.append(i)
                y_values.append(y)
        if len(y_values) < len(names):
            out.append({"outcome": outcome, "status": "skipped", "reason": "not enough complete rows"})
            continue
        x = x_all[idx, :]
        y = np.asarray(y_values, dtype=float)
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        for name, value in zip(names, coef):
            if name == "intercept" or name.startswith("attack_vector_"):
                out.append(
                    {
                        "outcome": outcome,
                        "term": name,
                        "estimate": float(value),
                        "n": len(y_values),
                        "estimator": "linear_fixed_effect_lstsq",
                        "fixed_effects": "target_slot,target_difficulty,vertical,model,base_case_id",
                    }
                )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", nargs="+", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--bootstrap-reps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--skip-regression", action="store_true")
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for path in args.scored:
        rows.extend(iter_jsonl(path))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    stats = dataset_stats(rows)
    (args.out_dir / "dataset_stats.json").write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(args.out_dir / "experiment1_model_robustness.csv", model_robustness(rows))
    write_csv(args.out_dir / "experiment2_package_effects.csv", summarize([r for r in rows if r.get("package_id") not in CONTROL_PACKAGES], ["model", "package_id", "package_family"]))
    write_csv(args.out_dir / "experiment3_package_family_effects.csv", summarize([r for r in rows if r.get("package_id") not in CONTROL_PACKAGES], ["model", "package_family"]))
    write_csv(args.out_dir / "experiment4_target_slot.csv", summarize([r for r in rows if r.get("package_id") not in CONTROL_PACKAGES], ["model", "attacked_target_slot"]))
    write_csv(args.out_dir / "experiment4_target_difficulty.csv", summarize([r for r in rows if r.get("package_id") not in CONTROL_PACKAGES], ["model", "attacked_target_difficulty"]))
    write_csv(args.out_dir / "experiment5_citation_focus.csv", summarize([r for r in rows if r.get("package_id") in CITATION_FOCUS_PACKAGES], ["model", "package_id"]))
    write_csv(args.out_dir / "experiment6_realistic_archetypes.csv", summarize([r for r in rows if r.get("package_id") in REALISTIC_PACKAGES or r.get("package_id") in CONTROL_PACKAGES], ["model", "package_id", "package_family"]))
    write_csv(args.out_dir / "experiment7_control_comparison.csv", control_comparison(rows))
    if args.bootstrap_reps > 0:
        write_csv(args.out_dir / "bootstrap_model_attack_ci.csv", bootstrap_cis(rows, args.bootstrap_reps, args.seed))
    if not args.skip_regression:
        write_csv(args.out_dir / "experiment3_primitive_linear_effects.csv", primitive_regression(rows))

    print(json.dumps({"out_dir": str(args.out_dir), "n_rows": len(rows), **stats}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
