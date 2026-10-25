import json
from pathlib import Path

d = Path('results/layer2/compare')
for f in sorted(d.glob('*.json')):
    if f.name.startswith('._'):
        continue
    raw = f.read_bytes()
    r = json.loads(raw.decode('utf-8', errors='replace'))
    print('=' * 70)
    print(f.name, '| run:', r['run_id'], '| tools:', r['n_tool_calls'], r['tool_names'])
    jr = r.get('json_result') or {}
    refs = jr.get('references')
    if refs:
        for x in refs:
            print('  REF', x.get('item_id'),
                  'doi_status=', x.get('doi_status'),
                  'match=', x.get('metadata_match'),
                  'verdict=', x.get('verdict'),
                  'retracted=', x.get('retracted'))
            print('     issue:', str(x.get('issue'))[:220])
    mfs = jr.get('methodology_findings')
    if mfs:
        for x in mfs:
            print('  FIND', x.get('id'), x.get('category'), x.get('severity'),
                  '|', str(x.get('description'))[:130])
    print()
