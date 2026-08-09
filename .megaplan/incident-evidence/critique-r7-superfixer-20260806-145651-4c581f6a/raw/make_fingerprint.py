import json, sys, hashlib, os, subprocess, glob

E = sys.argv[1]
WS = '/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold'
P = f'{WS}/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140'
RT = '/workspace/runtime-candidates/arnold-r7-fresh-child-20260805'
MARK = '/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.json'

paths = [
    f'{WS}/.megaplan/plans/.chains/chain-880bd6e04632.json',
    f'{P}/state.json',
    f'{P}/events.ndjson',
    f'{P}/work_ledger.ndjson',
    f'{P}/planner_repair.json',
    f'{P}/faults.json',
    f'{P}/finalize_v5_raw.txt',
    f'{P}/gate.json', f'{P}/gate_v1.json', f'{P}/gate_v2.json', f'{P}/gate_v3.json', f'{P}/gate_v4.json', f'{P}/gate_v5.json',
    f'{P}/gate_carry.json', f'{P}/gate_output.json', f'{P}/gate_signals_v2.json', f'{P}/gate_signals_v4.json',
    f'{P}/step_receipt_gate_v5.json', f'{P}/step_receipt_critique_v5.json', f'{P}/step_receipt_revise_v5.json',
    f'{P}/critique_custody_v3.json', f'{P}/critique_custody_v5.json',
    f'{P}/fresh_child_admission.json', f'{P}/canonical_source_binding.json',
    f'{P}/.phase_wbc_attempts.sqlite3',
    f'{P}/.megaplan/worker_tmp/local-strict-artifacts/finalize-15274aaf2cb2445487647129704dcccd.candidate.json',
    f'{P}/.megaplan/worker_tmp/local-strict-artifacts/finalize-59daae926dcd4447b40cbb790e68e36b.candidate.json',
    f'{P}/finalize_candidates/36bcefafd10ff23e6af1162c5b7186275630cec534cfd5aa0f257e9a9d69bc07.json',
    f'{P}/.events.store-incarnation',
    MARK,
    '/workspace/.megaplan/cloud-sessions/.critique-ledger-accountability-v3-r7-launch-20260805.liveness-fence.lock',
    f'{WS}/.megaplan/authority/run-authority.sqlite3',
    f'{WS}/.megaplan/authority/wbc.sqlite3',
]
paths += sorted(glob.glob(f'{P}/boundary_receipts/*.json'))

entries = {}
for p in paths:
    try:
        with open(p, 'rb') as fh:
            entries[p] = hashlib.sha256(fh.read()).hexdigest()
    except OSError as exc:
        entries[p] = f'MISSING:{exc}'

def git_out(path, args):
    try:
        r = subprocess.run(['git', '-C', path] + args, capture_output=True, text=True)
        return r.stdout.strip()
    except Exception as exc:
        return f'ERR:{exc}'

entries['git:project:head'] = git_out(WS, ['rev-parse', 'HEAD'])
entries['git:project:tracked_dirty'] = git_out(WS, ['status', '--porcelain=v1', '--untracked-files=no'])
entries['git:runtime:head'] = git_out(RT, ['rev-parse', 'HEAD'])
entries['git:runtime:tracked_dirty'] = git_out(RT, ['status', '--porcelain=v1', '--untracked-files=no'])

manifest = {
    'schema': 'arnold.superfixer.occurrence_fingerprint.v1',
    'observed_at_utc': '2026-08-06T15:06:00Z',
    'entries': entries,
}
canon = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode('utf-8')
manifest['aggregate_sha256'] = 'sha256:' + hashlib.sha256(canon).hexdigest()
with open(f'{E}/fingerprint-before.json', 'w') as fh:
    json.dump(manifest, fh, indent=1, sort_keys=True)
print('aggregate:', manifest['aggregate_sha256'])
print('entries:', len(entries))
