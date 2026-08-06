import json

c = json.load(open('/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/.megaplan/worker_tmp/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json'))
print('top keys:', list(c.keys()))
for k in ('critique_resolution_coverage', 'sense_checks', 'user_actions', 'watch_items', 'validation', 'meta_commentary'):
    v = c.get(k)
    print('---', k, type(v).__name__, (len(v) if isinstance(v, list) else ''))
    print(json.dumps(v, indent=1)[:1000] if v else v)
