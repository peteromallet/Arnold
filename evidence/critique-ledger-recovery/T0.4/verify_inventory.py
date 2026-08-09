#!/usr/bin/env python3
"""Strict verifier for the read-only T0.4 incident inventory.

The verifier treats T0.2's manifest as the source index. It never trusts a
path or digest copied into the inventory without re-reading the corresponding
manifest claim and content-addressed object.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
T02 = ROOT.parent / 'T0.2'
INVENTORY = ROOT / 'inventory.json'
UNRESOLVED = ROOT / 'unresolved.json'
RECEIPT = ROOT / 'verification-receipt.json'

ROW_KEYS = {
    'record_id', 'target_id', 'category', 'logical_identity_scope',
    'owner_system', 'owner_record_path_or_uri', 'current_state',
    'authority_classification', 'ids', 'source_evidence',
    'required_later_action', 'prerequisite_authority',
    'downstream_checklist_tasks', 'confidence', 'gap_or_reason',
}
SOURCE_KEYS = {
    'claim_index', 'claim_logical_name', 'object_path', 'sha256',
    'claim_status', 'query_basis', 'minimal_safe_excerpt',
}
T4_TASKS = ('T4.1', 'T4.2', 'T4.3', 'T4.4', 'T4.5', 'T4.6')
T4_ACTIONS = {'fence', 'revoke', 'expire', 'reconcile', 'quarantine',
              'CAS-away', 'read-only-freeze', 'no-redispatch'}
NAMED_TARGETS = {
    'target-v2-selection-session-spec-workspace-plan-branch-runtime',
    'target-v2-run-authority-grants-decisions-fences-revocations',
    'target-v2-custody-leases-epochs-fence-tokens-claims',
    'target-v2-wbc-glexams-operations-intents-attempts-outcomes-receipts',
    'target-v2-chain-selection-cursor-marker',
    'target-v2-workspace-branch-worktree-plan-artifacts',
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def main() -> int:
    failures: list[str] = []
    checked_sources = 0
    verified_sources = 0
    inventory = json.loads(INVENTORY.read_text())
    manifest_path = T02 / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    claims = manifest.get('claims', [])
    schema = inventory.get('schema', {})

    if schema.get('schema_id') != 't0.4.authoritative-incident-inventory.v1':
        failures.append('wrong inventory schema id')
    if schema.get('strict') is not True:
        failures.append('schema is not strict')
    required_top = {'schema', 'inventory_id', 'target', 'source_manifest', 't4_action_targets', 'rows'}
    if set(inventory) != required_top:
        failures.append(f'top-level keys mismatch: {sorted(set(inventory) ^ required_top)}')
    if inventory.get('source_manifest', {}).get('claim_count') != len(claims):
        failures.append('source manifest claim count mismatch')

    rows = inventory.get('rows', [])
    record_ids = [r.get('record_id') for r in rows]
    target_ids = [r.get('target_id') for r in rows]
    if len(record_ids) != len(set(record_ids)):
        failures.append('duplicate record_id')
    if len(target_ids) != len(set(target_ids)):
        failures.append('duplicate target_id')

    claim_by_index = {i: c for i, c in enumerate(claims)}
    for n, row in enumerate(rows):
        if set(row) != ROW_KEYS:
            failures.append(f'row {n}: keys mismatch')
            continue
        if row['category'] not in schema.get('categories', []):
            failures.append(f'row {n}: illegal category {row["category"]!r}')
        if row['current_state'] not in schema.get('states', []):
            failures.append(f'row {n}: illegal state {row["current_state"]!r}')
        if row['authority_classification'] not in schema.get('authority_classifications', []):
            failures.append(f'row {n}: illegal authority classification')
        if row['required_later_action'] not in schema.get('actions', []):
            failures.append(f'row {n}: illegal action')
        if row['confidence'] not in {'high', 'medium', 'low'}:
            failures.append(f'row {n}: illegal confidence')
        if not isinstance(row['logical_identity_scope'], dict) or not row['logical_identity_scope']:
            failures.append(f'row {n}: identity tuple missing')
        if not isinstance(row['source_evidence'], list) or not row['source_evidence']:
            failures.append(f'row {n}: source evidence missing')
        expected_record = 'record-' + digest({
            'category': row['category'],
            'identity': row['logical_identity_scope'],
            'sources': [x.get('claim_index') for x in row.get('source_evidence', [])],
            'action': row['required_later_action'],
        })
        if row['record_id'] != expected_record:
            failures.append(f'row {n}: nondeterministic record_id')
        if row['target_id'] not in NAMED_TARGETS and not re.fullmatch(r'target-[0-9a-f]{64}', row['target_id']):
            failures.append(f'row {n}: malformed target_id {row["target_id"]!r}')
        for ref in row['source_evidence']:
            checked_sources += 1
            if set(ref) != SOURCE_KEYS:
                failures.append(f'row {n}: source keys mismatch')
                continue
            idx = ref['claim_index']
            claim = claim_by_index.get(idx)
            if claim is None:
                failures.append(f'row {n}: missing claim index {idx}')
                continue
            if ref['claim_logical_name'] != claim.get('logical_name'):
                failures.append(f'row {n}: source claim_logical_name does not match manifest claim {idx}')
            for key in ('object_path', 'sha256'):
                if ref[key] != claim.get(key):
                    failures.append(f'row {n}: source {key} does not match manifest claim {idx}')
            if ref['claim_status'] != claim.get('status'):
                failures.append(f'row {n}: source claim_status does not match manifest claim {idx}')
            object_rel = ref['object_path']
            object_path = (T02 / object_rel).resolve()
            if T02.resolve() not in object_path.parents:
                failures.append(f'row {n}: object escapes T0.2 root')
                continue
            if not object_path.is_file():
                failures.append(f'row {n}: missing object {object_rel}')
                continue
            actual = sha256(object_path)
            if actual != ref['sha256']:
                failures.append(f'row {n}: digest mismatch for {object_rel}')
            else:
                verified_sources += 1

    mapping = inventory.get('t4_action_targets', {})
    if set(mapping) != set(T4_TASKS):
        failures.append('T4 target mapping must contain exactly T4.1-T4.6')
    target_to_rows = {r['target_id']: r for r in rows}
    expected_actions = {'T4.1':{'quarantine'}, 'T4.2':{'revoke','fence'}, 'T4.3':{'expire','fence'},
                       'T4.4':{'reconcile','no-redispatch'}, 'T4.5':{'CAS-away'}, 'T4.6':{'read-only-freeze'}}
    for task in T4_TASKS:
        targets = mapping.get(task, [])
        if not isinstance(targets, list) or not targets:
            failures.append(f'{task} has no exact target')
            continue
        for target in targets:
            row = target_to_rows.get(target)
            if row is None:
                failures.append(f'{task} target {target} is not an inventory row')
            elif task not in row['downstream_checklist_tasks']:
                failures.append(f'{task} target {target} does not name its task')
            elif row['required_later_action'] not in expected_actions[task]:
                failures.append(f'{task} target {target} has wrong action')
    for row in rows:
        if row['required_later_action'] in T4_ACTIONS:
            tasks = set(row['downstream_checklist_tasks'])
            if not tasks or not tasks.issubset(set(T4_TASKS)):
                failures.append(f'non-exact later action target: {row["record_id"]}')
            if not any(row['target_id'] in mapping.get(task, []) for task in tasks):
                failures.append(f'later action has no mapped exact target: {row["record_id"]}')

    unresolved = json.loads(UNRESOLVED.read_text())
    if unresolved.get('fail_closed') is not True:
        failures.append('unresolved.json is not fail-closed')
    unresolved_ids = {r.get('record_id') for r in unresolved.get('unresolved', [])}
    row_ids = {r.get('record_id') for r in rows}
    if not unresolved_ids.issubset(row_ids):
        failures.append('unresolved.json contains unknown row')

    inv_bytes = INVENTORY.read_bytes()
    inventory_sha = hashlib.sha256(inv_bytes).hexdigest()
    receipt = {
        'schema': 't0.4.verification-receipt.v1',
        'receipt_id': 't04-receipt-' + inventory_sha[:24],
        'verified_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'verifier': 'verify_inventory.py',
        'verifier_path': str(Path(__file__).resolve()),
        'inventory_sha256': inventory_sha,
        'inventory_byte_size': len(inv_bytes),
        'row_count': len(rows),
        'unresolved_row_count': len(unresolved.get('unresolved', [])),
        'source_refs_checked': checked_sources,
        'source_objects_verified': verified_sources,
        'unique_record_ids': len(set(record_ids)),
        'unique_target_ids': len(set(target_ids)),
        't4_tasks_with_exact_targets': [t for t in T4_TASKS if mapping.get(t)],
        'failures': failures,
        'result': 'PASS' if not failures else 'FAIL',
        't04_completion_criterion': bool(not failures and all(mapping.get(t) for t in T4_TASKS)),
    }
    RECEIPT.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
