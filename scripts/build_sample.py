#!/usr/bin/env python3
"""Build a tiny `sample/` subset (2 base cases per vertical) for offline smoke tests."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from safegeo.io import read_records, write_parquet

VERTICALS = ["ai_meeting_transcription","baby_monitor","carry_on_backpack",
             "home_air_purifier","noise_canceling_headphones","office_chair"]

def main() -> None:
    import argparse
    argparse.ArgumentParser(
        description="Rebuild the tiny sample/ subset from data/ (2 base cases per vertical) "
                    "for offline smoke tests. Takes no arguments."
    ).parse_args()
    data, out = Path("data"), Path("sample")
    labels = read_records(data / "labels")
    base_by_v: dict[str, list[str]] = {}
    for r in labels:
        base_by_v.setdefault(r["vertical"], [])
        if r["base_case_id"] not in base_by_v[r["vertical"]]:
            base_by_v[r["vertical"]].append(r["base_case_id"])
    keep_bases = {b for v in VERTICALS for b in sorted(base_by_v.get(v, []))[:2]}
    keep_queries = {b for b in keep_bases}  # query_id == base_case_id in this dataset

    def dump(config: str, rows: list[dict]) -> None:
        write_parquet(out / config / "test-00000-of-00001.parquet", rows)

    by_base = lambda rows, key="base_case_id": [r for r in rows if r.get(key) in keep_bases]
    by_q = lambda rows: [r for r in rows if r.get("query_id") in keep_queries]
    dump("labels", by_base(labels))
    dump("visible", [r for r in read_records(data/"visible") if r.get("query_id") in keep_queries])
    dump("candidate_quality", by_q(read_records(data/"candidate_quality")))
    dump("source_annotations", by_q(read_records(data/"source_annotations")))
    dump("geo_line_annotations", by_base(read_records(data/"geo_line_annotations")))
    dump("targets", by_base(read_records(data/"targets")))
    dump("instances_manifest", by_base(read_records(data/"instances_manifest")))
    dump("quality_distributions", by_q(read_records(data/"quality_distributions")))
    dump("requirement_annotations", by_q(read_records(data/"requirement_annotations")))
    # controlled_documents: doc_id encodes base_case_id; keep those that match.
    cd = [r for r in read_records(data/"controlled_documents")
          if any(b in str(r.get("doc_id","")) for b in keep_bases)]
    dump("controlled_documents", cd)
    print("sample built:", sorted(p.name for p in out.iterdir()))

if __name__ == "__main__":
    main()
