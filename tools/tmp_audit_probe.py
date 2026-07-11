#!/usr/bin/env python3
from pathlib import Path
import json, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from safegeo.io import read_records

OUT = Path('tmp_audit_probe')
OUT.mkdir(exist_ok=True)
configs = ['requirement_annotations','candidate_quality','source_annotations','visible','labels','controlled_documents','geo_line_annotations']
report = {}
for config in configs:
    rows = read_records(Path('data')/config)
    report[config] = {
        'count': len(rows),
        'keys': sorted({k for r in rows[:100] for k in r}),
        'sample': rows[:2],
    }
(OUT/'schema_and_samples.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:{'count':v['count'],'keys':v['keys']} for k,v in report.items()}, indent=2))
