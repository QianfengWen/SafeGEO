#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow.dataset as pads

SEED = 20260711
DATA = Path("data")
OUT = Path("tmp_human_audit_annotator2")
MANIFEST = Path("tools/tmp_human_audit_manifest.csv")


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


def first(row: dict[str, Any] | None, names: Iterable[str], default: Any = None) -> Any:
    if not row:
        return default
    for name in names:
        if name in row and row[name] not in (None, "", [], {}):
            return decode(row[name])
    return default


def safe_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (dict, list)):
        return json.dumps(x, ensure_ascii=False)
    return str(x)


def load_config(config: str) -> list[dict[str, Any]]:
    path = DATA / config
    if not path.exists():
        raise FileNotFoundError(path)
    table = pads.dataset(str(path), format="parquet").to_table()
    return [decode(r) for r in table.to_pylist()]


def load_manifest() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with MANIFEST.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["scoring_reference_audit"] = row["scoring_reference_audit"].lower() == "true"
            row["evidence_label_audit"] = row["evidence_label_audit"].lower() == "true"
            row["seed"] = int(row["seed"])
            out.append(row)
    return out


def choose_control(visible_rows: list[dict[str, Any]], label_by_instance: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def score(v: dict[str, Any]) -> tuple[int, str]:
        iid = safe_text(v.get("instance_id"))
        lab = label_by_instance.get(iid, {})
        blob = " ".join(
            safe_text(lab.get(k)).lower()
            for k in ["control_type", "scenario_type", "package_id", "expanded_instance_id"]
        )
        if "all_truthful" in blob or "truthful_target" in blob:
            return (0, iid)
        if "truthful" in blob:
            return (1, iid)
        if "no_geo" in blob or "original_no" in blob:
            return (2, iid)
        return (9, iid)
    if not visible_rows:
        raise ValueError("No visible rows")
    return min(visible_rows, key=score)


def candidate_score(row: dict[str, Any]) -> float:
    for key in ["verified_utility_score", "canonical_utility_score_original", "soft_preference_score"]:
        try:
            return float(row.get(key))
        except Exception:
            pass
    return 0.0


def select_candidates(rows: list[dict[str, Any]], case_seed: int) -> list[dict[str, Any]]:
    if len(rows) < 3:
        raise ValueError("Each sampled case must have at least three candidates.")
    local = random.Random(case_seed)
    primary_pool = [r for r in rows if bool(r.get("is_primary_gt"))]
    primary = max(primary_pool or rows, key=candidate_score)
    remaining = [r for r in rows if r is not primary]
    hard_pool = [
        r for r in remaining
        if bool(r.get("is_hard_negative")) or not bool(r.get("hard_constraint_feasible", True))
    ]
    hard = local.choice(hard_pool) if hard_pool else min(remaining, key=candidate_score)
    remaining2 = [r for r in remaining if r is not hard]
    sorted_mid = sorted(remaining2, key=candidate_score)
    mid_candidates = (
        sorted_mid[max(0, len(sorted_mid) // 3):max(1, 2 * len(sorted_mid) // 3)]
        or sorted_mid
    )
    mid = local.choice(mid_candidates)
    selected = [primary, hard, mid]
    local.shuffle(selected)
    out: list[dict[str, Any]] = []
    for i, row in enumerate(selected, 1):
        copied = dict(row)
        copied["_alias"] = f"Candidate {i}"
        out.append(copied)
    return out


def add_line(raw_lines: list[tuple[Any, str]], lid: Any, text: Any) -> None:
    s = safe_text(text).strip()
    if s:
        raw_lines.append((lid, s))


def extract_lines_from_doc(doc: dict[str, Any], fallback_index: int) -> dict[str, Any]:
    did = safe_text(first(doc, ["doc_id", "source_id", "id"], f"DOC{fallback_index:03d}"))
    title = safe_text(first(doc, ["title", "name", "page_title"], did))
    url = safe_text(first(doc, ["url", "source_url", "link"], ""))
    source_type = safe_text(first(doc, ["source_type", "type", "owner_class", "source_owner_class"], ""))
    raw_lines: list[tuple[Any, str]] = []

    def walk(x: Any) -> None:
        x = decode(x)
        if isinstance(x, dict):
            txt = first(x, ["text", "line_text", "content", "opened_text", "excerpt"], None)
            lid = first(x, ["line_id", "line_number", "id"], None)
            if txt is not None and not isinstance(txt, (dict, list)):
                add_line(raw_lines, lid, txt)
                return
            for key in ["lines", "opened_text", "chunks", "opened_chunks", "text_chunks", "paragraphs"]:
                if key in x:
                    walk(x[key])
        elif isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, str):
            parts = [p.strip() for p in x.splitlines() if p.strip()]
            if len(parts) <= 1 and len(x) > 300:
                parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", x) if p.strip()]
            for p in parts:
                add_line(raw_lines, None, p)

    for key in ["opened_text", "lines", "chunks", "opened_chunks", "text", "content", "excerpt"]:
        if key in doc:
            walk(doc[key])
            if raw_lines:
                break
    if not raw_lines:
        for key, val in doc.items():
            if key not in {
                "doc_id", "id", "source_id", "title", "name", "url", "source_url",
                "source_type", "type"
            }:
                walk(val)

    lines: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for idx, (lid, text) in enumerate(raw_lines, 1):
        lid = lid if lid not in (None, "") else idx
        key = (str(lid), text)
        if key in seen:
            continue
        seen.add(key)
        lines.append({"doc_id": did, "line_id": lid, "text": text})
    return {"doc_id": did, "title": title, "url": url, "source_type": source_type, "lines": lines}


def normalize_docs(search_results: Any) -> list[dict[str, Any]]:
    data = decode(search_results)
    if isinstance(data, dict):
        for key in ["documents", "results", "search_results", "sources"]:
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = list(data.values())
    if not isinstance(data, list):
        return []
    docs: list[dict[str, Any]] = []
    for i, d in enumerate(data, 1):
        if not isinstance(d, dict):
            d = {"text": d}
        nd = extract_lines_from_doc(d, i)
        if nd["lines"]:
            docs.append(nd)
    return docs


def recursive_line_refs(obj: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    obj = decode(obj)
    if isinstance(obj, dict):
        doc_id = first(obj, ["doc_id", "source_id"], None)
        line_id = first(obj, ["line_id", "line_number"], None)
        if doc_id is not None and line_id is not None:
            refs.append({
                "doc_id": safe_text(doc_id),
                "line_id": line_id,
                "relation_hint": first(
                    obj,
                    ["relation", "relation_to_candidate_claim", "evidence_role", "role"],
                    "",
                ),
                "truth_status": first(obj, ["truth_status"], ""),
                "valid_for_utility": first(obj, ["valid_for_utility"], ""),
                "path": "/".join(path),
            })
        for k, v in obj.items():
            refs.extend(recursive_line_refs(v, path + (str(k),)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            refs.extend(recursive_line_refs(v, path + (str(i),)))
    return refs


def get_requirement_text(req_row: dict[str, Any], attribute_hint: str) -> str:
    for key in ["hard_constraints", "soft_preferences", "requirements", "structured_query"]:
        obj = decode(req_row.get(key))
        if not obj:
            continue
        if isinstance(obj, dict):
            stack = list(obj.values())
        elif isinstance(obj, list):
            stack = obj
        else:
            stack = [obj]
        for item in stack:
            if isinstance(item, dict):
                ak = safe_text(first(item, ["attribute_key", "key", "id"], ""))
                if attribute_hint and (
                    attribute_hint == ak or attribute_hint in ak or ak in attribute_hint
                ):
                    return safe_text(first(
                        item,
                        ["text", "constraint_text", "preference_text", "description"],
                        ak,
                    ))
    return attribute_hint.replace("_", " ") if attribute_hint else "the candidate claim"


def line_lookup(docs: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for d in docs:
        for line in d["lines"]:
            out[(str(d["doc_id"]), str(line["line_id"]))] = {
                **line,
                "title": d["title"],
                "source_type": d["source_type"],
                "url": d["url"],
            }
    return out


def select_line_items(
    case_id: str,
    candidates: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    req_row: dict[str, Any],
    n: int = 18,
) -> list[dict[str, Any]]:
    lookup = line_lookup(docs)
    local = random.Random(case_id + "|line-audit")
    selected: list[dict[str, Any]] = []
    used: set[tuple[str, str]] = set()

    for cand in candidates:
        alias = cand["_alias"]
        refs = recursive_line_refs(cand.get("evidence_profile"))
        local.shuffle(refs)
        for ref in refs:
            key = (str(ref["doc_id"]), str(ref["line_id"]))
            if key in used or key not in lookup:
                continue
            path = ref.get("path", "")
            attr = ""
            m = re.search(r"hard_constraints/([^/]+)|soft_preferences/([^/]+)", path)
            if m:
                attr = m.group(1) or m.group(2) or ""
            selected.append({
                **lookup[key],
                "candidate_alias": alias,
                "neutral_claim": f"{alias} satisfies: {get_requirement_text(req_row, attr)}",
                "attribute_hint": attr,
            })
            used.add(key)
            if len(selected) >= 12:
                break
        if len(selected) >= 12:
            break

    all_lines = [
        x for x in lookup.values()
        if (str(x["doc_id"]), str(x["line_id"])) not in used
    ]
    local.shuffle(all_lines)
    for x in all_lines:
        alias = local.choice([c["_alias"] for c in candidates])
        key = (str(x["doc_id"]), str(x["line_id"]))
        selected.append({
            **x,
            "candidate_alias": alias,
            "neutral_claim": f"{alias} satisfies one of the stated user requirements.",
            "attribute_hint": "",
        })
        used.add(key)
        if len(selected) >= n:
            break

    selected = selected[:n]
    for i, item in enumerate(selected, 1):
        item["line_item_id"] = f"E{i:02d}"
    return selected


def compact_candidate(c: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "query_id", "base_case_id", "item_id", "candidate_id", "name", "candidate_name",
        "item_name", "hidden_original_role", "canonical_attributes",
        "hard_constraint_satisfaction", "failed_hard_constraints",
        "satisfied_hard_constraints", "hard_constraint_feasible", "soft_preference_score",
        "canonical_utility_score_original", "verified_utility_score", "evidence_profile",
        "source_dates", "candidate_shortlist_rank", "quality_group", "candidate_tier",
        "recommendation_status", "is_primary_gt", "is_acceptable_gt", "is_hard_negative",
        "is_medium_negative", "utility_aligned_sort_key", "tier_rationale",
    ]
    return {k: decode(c.get(k)) for k in keep if k in c} | {"candidate_alias": c["_alias"]}


def main() -> None:
    manifest = load_manifest()
    keep_ids = {m["case_id"] for m in manifest}

    req_rows = load_config("requirement_annotations")
    cand_rows = load_config("candidate_quality")
    visible_rows = load_config("visible")
    label_rows = load_config("labels")

    req_by_q = {
        safe_text(first(r, ["query_id", "base_case_id"])): r
        for r in req_rows
        if safe_text(first(r, ["query_id", "base_case_id"])) in keep_ids
    }
    cand_by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in cand_rows:
        q = safe_text(first(r, ["query_id", "base_case_id"]))
        if q in keep_ids:
            cand_by_q[q].append(r)
    vis_by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in visible_rows:
        q = safe_text(first(r, ["query_id", "base_case_id"]))
        if q in keep_ids:
            vis_by_q[q].append(r)
    label_by_instance = {
        safe_text(r.get("instance_id")): r
        for r in label_rows
        if safe_text(first(r, ["query_id", "base_case_id"])) in keep_ids
    }

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "cases").mkdir(parents=True)
    index: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for m in manifest:
        q = m["case_id"]
        try:
            req = req_by_q[q]
            visible = choose_control(vis_by_q[q], label_by_instance)
            candidates = select_candidates(cand_by_q[q], m["seed"] + sum(map(ord, q)))
            docs = normalize_docs(first(visible, ["search_results", "sources", "documents"], []))
            if not docs:
                raise ValueError("No source documents extracted")
            original_query = safe_text(first(
                req,
                ["original_user_query", "original_query", "construction_query", "query_text", "user_query"],
                "",
            ))
            visible_query = safe_text(first(visible, ["user_query", "query"], ""))
            if not original_query:
                original_query = visible_query
            line_items = (
                select_line_items(q, candidates, docs, req, 18)
                if m["evidence_label_audit"]
                else []
            )
            case = {
                **m,
                "original_query": original_query,
                "visible_query": visible_query,
                "selected_visible_instance_id": safe_text(visible.get("instance_id")),
                "candidate_roster": decode(first(visible, ["candidate_roster"], [])),
                "requirement_record": decode(req),
                "candidates": [compact_candidate(c) for c in candidates],
                "docs": docs,
                "line_items": line_items,
            }
            path = OUT / "cases" / f"{q}.json"
            path.write_text(
                json.dumps(case, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            index.append({
                "case_id": q,
                "vertical": m["vertical"],
                "evidence_label_audit": m["evidence_label_audit"],
                "path": str(path),
                "bytes": path.stat().st_size,
            })
        except Exception as exc:
            errors.append({"case_id": q, "error": repr(exc)})

    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT / "status.json").write_text(
        json.dumps({"cases": len(index), "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"cases": len(index), "errors": errors}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
