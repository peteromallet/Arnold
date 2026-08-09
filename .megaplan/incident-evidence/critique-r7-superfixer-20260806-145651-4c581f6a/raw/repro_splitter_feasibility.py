import json, sys, hashlib
CAND='/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/.megaplan/worker_tmp/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json'
FAIL='/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140/finalize_candidates/36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07.json'
payload=json.load(open(CAND))
fail=json.load(open(FAIL))
tasks=payload['tasks']
print('candidate tasks:', len(tasks))
for t in tasks:
    print(' ', t.get('id'), 'complexity=', t.get('complexity'), 'deps=', t.get('depends_on'))
from arnold_pipelines.megaplan.orchestration.task_splitter import split_high_complexity_tasks
split_tasks, diags = split_high_complexity_tasks(payload)
ids=[t['id'] for t in split_tasks]
print('post-split task count:', len(split_tasks))
print('split diagnostics:', [d.as_dict() if hasattr(d,'as_dict') else str(d) for d in diags])
# find unknown deps
unknown=[]
for t in split_tasks:
    for dep in t.get('depends_on',[]):
        if dep not in ids or dep==t['id']:
            unknown.append((t['id'], dep))
print('unknown deps after split:', unknown)
from arnold_pipelines.megaplan.orchestration.task_feasibility import compile_task_feasibility
config={'mode':'code','project_dir':'/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold'}
feas=compile_task_feasibility({'tasks':split_tasks}, config)
print('feasibility admitted:', feas.get('admitted'))
print('feasibility task_count:', feas.get('task_count'))
codes=[d.get('code') for d in feas.get('diagnostics',[])]
print('feasibility diag codes:', codes)
print('expected failure fingerprint:', fail.get('failure_fingerprint'))
print('repro fingerprint:', feas.get('failure_fingerprint'))
print('MATCH:', codes==[d.get('code') for d in fail.get('diagnostics',[])])
