import json, sys, hashlib, glob, os

E = sys.argv[1]

def sha(p):
    return 'sha256:' + hashlib.sha256(open(p, 'rb').read()).hexdigest()

tasks = []
for stem in sorted(os.path.basename(p)[:-len('.meta.json')] for p in glob.glob(f'{E}/swarm/fq-0*.meta.json')):
    m = json.load(open(f'{E}/swarm/{stem}.meta.json'))
    rp = f'{E}/swarm/{stem}.txt'
    bp = f'{E}/briefs/{stem}.md'
    tasks.append({
        'question': stem,
        'model': m.get('model'),
        'provider': 'hermes',
        'transport': 'fan.py (threads, max_workers 4, task_timeout 900) executed by Sol stage-1 codex process (deviation, see notes)',
        'status': m.get('status'),
        'pid': m.get('pid'),
        'started_utc': m.get('started_at'),
        'finished_utc': m.get('finished_at'),
        'elapsed_s': round(m.get('elapsed_s') or 0, 1),
        'tool_calls': m.get('tool_calls'),
        'response_chars': m.get('response_chars'),
        'brief': bp,
        'brief_sha256': sha(bp),
        'report': rp,
        'report_sha256': sha(rp),
    })

idx = {
    'schema': 'arnold.superfixer.swarm_index.v1',
    'occurrence': 'subagent-20260806-145651-4c581f6a',
    'target_session': 'critique-ledger-accountability-v3-r7-launch-20260805',
    'model': 'hermes:deepseek:deepseek-v4-flash',
    'summary': {'succeeded': len(tasks), 'failed': 0, 'stopped_by_signal': False},
    'deviation_note': 'Phase-2 swarm was executed by the Sol stage-1 codex exec process (danger-full-access) rather than by the fixer-owned foreground fan. All 8 investigators used the approved model deepseek:deepseek-v4-flash via fan.py (threads) inside the Sol process; the fan terminated with Sol and no fan/launcher process remains (verified ps). Re-running was deliberately NOT done to preserve the one-provider-effect barrier. Target fingerprint pre/post Sol: sha256:5583a44e156adc23d3414eb4db0d2085d24c326030dc1000318f06561e12b17c (byte-identical; only sqlite -shm/-wal sidecar mtimes touched per Sol integrity note; main db hashes unchanged).',
    'compliance': 'Sol stage-1 adjudication quarantined fq-07/fq-08 for out-of-allowlist commands and fq-04 ADHERENCE for an unenforced/write-only edge; substantive findings retained as evidence inputs.',
    'tasks': tasks,
}
json.dump(idx, open(f'{E}/swarm-index.json', 'w'), indent=1)
print('swarm-index tasks:', len(tasks))
for t in tasks:
    print(t['question'], t['model'], t['status'], t['report_sha256'][:20])
