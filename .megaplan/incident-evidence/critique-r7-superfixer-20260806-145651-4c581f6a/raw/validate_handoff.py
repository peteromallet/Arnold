import json, sys, hashlib

E = sys.argv[1]
d = json.load(open(f'{E}/recovery-handoff.json'))
print('schema:', d.get('schema'))
print('handoff_id:', d.get('handoff_id'))
c = dict(d)
c.pop('handoff_id', None)
canon = json.dumps(c, sort_keys=True, separators=(',', ':')).encode('utf-8')
calc = 'sha256:' + hashlib.sha256(canon).hexdigest()
print('calculated:', calc)
print('VALID:', calc == d.get('handoff_id'))
print()
ha = d.get('horizon_a', {})
for k in ('route', 'agent_actionable', 'canonical_owner', 'external_gate', 'return_condition'):
    print(k, '=', json.dumps(ha.get(k))[:400])
print('preconditions:', json.dumps(ha.get('preconditions'), indent=1)[:1500])
print()
print('operations:')
for op in ha.get('operations', []):
    print(' *', str(op)[:350])
print()
hb = d.get('horizon_b', {})
print('horizon_b keys:', list(hb.keys()))
print('ticket_or_crosswalk:', json.dumps(hb.get('ticket_or_crosswalk'))[:400])
print('stop_gates:', json.dumps(d.get('stop_gates'))[:800])
