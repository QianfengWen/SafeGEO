#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from safegeo.io import read_records

OUT = Path('tmp_probe_output')
OUT.mkdir(exist_ok=True)
configs = ['requirement_annotations','candidate_quality','source_annotations','visible','labels','controlled_documents','geo_line_annotations','targets']
all_rows = {config: read_records(Path('data')/config) for config in configs}
report = {}
for config, rows in all_rows.items():
    report[config] = {
        'count': len(rows),
        'keys': sorted({k for r in rows[:100] for k in r}),
        'sample': rows[:2],
    }
labels = all_rows['labels']
report['label_distributions'] = {
    'scenario_type': Counter(str(r.get('scenario_type')) for r in labels),
    'control_type': Counter(str(r.get('control_type')) for r in labels),
    'package_family': Counter(str(r.get('package_family')) for r in labels),
    'package_id': Counter(str(r.get('package_id')) for r in labels),
    'num_attacked_targets': Counter(str(r.get('num_attacked_targets')) for r in labels),
    'control_samples': [r for r in labels if r.get('package_family') == 'control'][:6],
    'realistic_samples': [r for r in labels if r.get('package_family') == 'realistic'][:3],
}
source_lines = [line for r in all_rows['source_annotations'] for line in (r.get('line_level_annotations') or [])]
report['source_line_distributions'] = {
    'relation': Counter(str(x.get('relation_to_candidate_claim')) for x in source_lines),
    'truth_status': Counter(str(x.get('truth_status')) for x in source_lines),
    'valid_for_utility': Counter(str(x.get('valid_for_utility')) for x in source_lines),
    'claim_type': Counter(str(x.get('claim_type')) for x in source_lines),
}
geo = all_rows['geo_line_annotations']
report['geo_line_distributions'] = {
    'relation': Counter(str(x.get('relation_to_target_gap')) for x in geo),
    'truth_status': Counter(str(x.get('truth_status')) for x in geo),
    'valid_for_utility': Counter(str(x.get('valid_for_utility')) for x in geo),
    'claim_type': Counter(str(x.get('claim_type')) for x in geo),
    'package_id': Counter(str(x.get('package_id')) for x in geo),
}
# Representative query record joined across configs.
qid = all_rows['requirement_annotations'][0]['query_id']
report['joined_example'] = {
    'query_id': qid,
    'requirements': next(r for r in all_rows['requirement_annotations'] if r['query_id']==qid),
    'candidates': [r for r in all_rows['candidate_quality'] if r['query_id']==qid],
    'sources': [r for r in all_rows['source_annotations'] if r['query_id']==qid],
    'controls': [r for r in labels if r['query_id']==qid and r.get('package_family')=='control'],
    'targets': next((r for r in all_rows['targets'] if r['query_id']==qid), None),
}
(OUT/'schema_and_samples.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=lambda x: dict(x)), encoding='utf-8')
print(json.dumps({k:v for k,v in report['label_distributions'].items() if not k.endswith('samples')}, indent=2, default=lambda x: dict(x)))
