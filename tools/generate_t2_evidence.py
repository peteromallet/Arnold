"""Generate T2 evidence: m6a-f01-f17-substrate-map.json and m6a-schema-only-row-classification.json."""
import json
import hashlib
from datetime import datetime, timezone


def _classify_finding_m6a_relevance(fid, fdata, wbc_rows):
    owner = fdata['canonical_owner']
    if owner == 'WBC':
        if wbc_rows:
            for r in wbc_rows:
                if 'M6A' in r.get('milestone', '') or r['row_index'] in [66, 67, 68]:
                    return 'directly-addressed-by-m6a'
            return 'wbc-owned-deferred-to-later-milestone'
        return 'wbc-owned-no-migration-row'
    elif owner in ('Run Authority',):
        return 'run-authority-owned-out-of-m6a-scope'
    elif owner in ('Observability/projection',):
        return 'observability-owned-out-of-m6a-scope'
    elif owner in ('Planner/compiler',):
        return 'planner-owned-out-of-m6a-scope'
    elif owner in ('Executor/launcher',):
        return 'executor-owned-out-of-m6a-scope'
    elif owner in ('TransitionWriter/repair custody',):
        return 'repair-custody-owned-out-of-m6a-scope'
    else:
        return 'other-owner-out-of-m6a-scope'


def _classify_row(row):
    owner = row['owner']
    status = row['status_raw']
    ri = row['row_index']

    if ri in [66, 67, 68]:
        return 'm6a-owned-substrate'
    if ri in [69, 70]:
        return 'blocked-substrate'
    if ri == 71:
        return 'schema-only'
    if owner == 'WBC' and status in ('substrate gap', 'partial', 'in-flight-WBC', 'legacy'):
        return 'schema-only'
    if owner != 'WBC':
        return 'unmatched'
    if 'blocked' in row['classification']:
        return 'blocked-substrate'
    return 'schema-only'


def _classification_rationale(row, classification):
    owner = row['owner']
    status = row['status_raw']
    rationales = {
        'm6a-owned-substrate': (
            f'M6A target surface — schema declarations exist '
            f'(execution_attempt_ledger.py, payload_policy.py, durable_refs.py) '
            f'but no SqliteAttemptLedgerStore, runtime persistence, outbox, dispatch, '
            f'or external effects are implemented. Current status: {status}.'
        ),
        'blocked-substrate': (
            f'Blocked pending M6A substrate delivery — no runtime store exists '
            f'to support this surface. Current status: {status}.'
        ),
        'schema-only': (
            f'Schema declarations exist but no runtime I/O, mutation, dispatch, '
            f'or external effects are implemented. Owner: {owner}. Status: {status}.'
        ),
        'landed': (
            f'Runtime implementation exists with persistence. Status: {status}.'
        ),
        'unmatched': (
            f'Owner is {owner}, not WBC. This surface is outside WBC ownership scope. '
            f'Status: {status}.'
        ),
    }
    return rationales.get(classification,
        f'Classification: {classification}. Status: {status}.')


def main():
    with open('evidence/migration-matrix-reconciled.json', 'r') as f:
        mm = json.load(f)

    with open('evidence/finding-prevention-register.json', 'r') as f:
        fpr = json.load(f)

    with open('evidence/m6a-prerequisite-resolution.json', 'r') as f:
        pr = json.load(f)

    # Extract findings
    findings = {}
    for row in fpr['rows']:
        fid = row['finding_id']
        findings[fid] = {
            'finding_id': fid,
            'title': row['title'],
            'root_cause': row['root_cause'],
            'canonical_owner': row['canonical_owner'],
            'owner_control': row['owner_control'],
            'acceptance_proof': row['acceptance_proof'],
            'row_hash': row['row_hash'],
        }

    # Map findings to migration matrix rows
    finding_row_map = {}
    for fid in [f'F{i:02d}' for i in range(1, 18)]:
        finding_row_map[fid] = []
        for row in mm['rows']:
            findings_refs = row['evidence'].get('finding_register_matches', [])
            if fid in findings_refs:
                finding_row_map[fid].append({
                    'row_index': row['row_index'],
                    'consumer_surface': row['consumer_surface'],
                    'owner': row['owner'],
                    'owner_raw': row['owner_raw'],
                    'status_raw': row['status_raw'],
                    'classification': row['classification'],
                    'milestone': row['milestone'],
                    'proof_requirement': row['proof_requirement'],
                })

    # --- SUBSTRATE MAP ---
    substrate_map = {
        'schema': 'm6a.f01-f17-substrate-map.v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generator': 'hermes-executor: T2 substrate mapping',
        'repository_head': pr['repository_head'],
        'm6_merge_commit': pr['m6_merge_commit'],
        'sources': {
            'migration_matrix': 'evidence/migration-matrix-reconciled.json',
            'finding_prevention_register': 'evidence/finding-prevention-register.json',
            'prerequisite_resolution': 'evidence/m6a-prerequisite-resolution.json',
        },
        'dispatch_and_external_effects_status': {
            'dispatch_enabled': False,
            'external_effects_enabled': False,
            'evidence': [
                'arnold/workflow/execution_attempt_ledger.py line 45: "This is schema-only — no I/O, mutation, or runtime effects."',
                'arnold/workflow/boundary_templates.py line 100: "Profiles are declarative: they do not route or dispatch."',
                'No SqliteAttemptLedgerStore, outbox, or adapter code exists at current HEAD (904560e).',
                'External effect event types (EXTERNAL_EFFECT_INTENT, EXTERNAL_EFFECT_OUTCOME) exist only as schema declarations in AttemptEventType enum.',
                'External effect template (BoundaryTemplateKind.EXTERNAL_EFFECT) is a declarative template profile only.',
                'No producer adoption path exists; all WBC store rows (66-70) are blocked substrate/adoption.',
            ],
        },
        'producer_adoption_status': {
            'claimed': False,
            'evidence': [
                'Row 66 (WBC declarations/attempt ledger): blocked substrate/adoption',
                'Row 67 (WBC payload/privacy/retention/encryption): blocked substrate',
                'Row 68 (WBC schema/data migration): blocked substrate',
                'Row 69 (WBC universal producer adoption): blocked adoption',
                'Row 70 (WBC universal consumer adoption): blocked adoption',
                'No SqliteAttemptLedgerStore exists at current HEAD.',
                'Plan assumption: "No universal producer or consumer migration is included in M6A; exports and support records must not claim adoption."',
            ],
        },
        'F01_F17_overview': {
            'total_findings': 17,
            'wbc_owned_findings': ['F02', 'F03', 'F04', 'F17'],
            'run_authority_owned_findings': ['F01', 'F05'],
            'observability_projection_owned_findings': ['F06', 'F14', 'F16'],
            'planner_compiler_owned_findings': ['F07', 'F08', 'F09', 'F12'],
            'executor_launcher_owned_findings': ['F10', 'F11', 'F13'],
            'transition_writer_repair_custody_owned_findings': ['F15'],
        },
        'findings': {},
    }

    for fid in sorted(findings.keys()):
        fdata = findings[fid]
        rows = finding_row_map[fid]
        wbc_rows = [r for r in rows if r['owner'] == 'WBC']
        non_wbc_rows = [r for r in rows if r['owner'] != 'WBC']

        substrate_map['findings'][fid] = {
            'title': fdata['title'],
            'canonical_owner': fdata['canonical_owner'],
            'root_cause': fdata['root_cause'],
            'acceptance_proof': fdata['acceptance_proof'],
            'migration_matrix_row_count': len(rows),
            'wbc_owned_rows': len(wbc_rows),
            'non_wbc_rows': len(non_wbc_rows),
            'wbc_surfaces': [
                {
                    'row_index': r['row_index'],
                    'consumer_surface': r['consumer_surface'],
                    'status_raw': r['status_raw'],
                    'classification': r['classification'],
                }
                for r in wbc_rows
            ],
            'other_owner_surfaces': [
                {
                    'row_index': r['row_index'],
                    'consumer_surface': r['consumer_surface'],
                    'owner': r['owner'],
                    'status_raw': r['status_raw'],
                    'classification': r['classification'],
                }
                for r in non_wbc_rows
            ],
            'm6a_substrate_relevance': _classify_finding_m6a_relevance(fid, fdata, wbc_rows),
        }

    content = json.dumps(substrate_map, sort_keys=True, indent=2)
    substrate_map['composite_hash'] = 'sha256:' + hashlib.sha256(content.encode('utf-8')).hexdigest()

    with open('evidence/m6a-f01-f17-substrate-map.json', 'w') as f:
        json.dump(substrate_map, f, indent=2, sort_keys=True)

    print("Generated evidence/m6a-f01-f17-substrate-map.json")

    # --- ROW CLASSIFICATION ---
    row_classification = {
        'schema': 'm6a.schema-only-row-classification.v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generator': 'hermes-executor: T2 row classification',
        'repository_head': pr['repository_head'],
        'm6_merge_commit': pr['m6_merge_commit'],
        'classification_categories': {
            'schema_only': (
                'Schema declarations exist but no runtime store, I/O, mutation, '
                'dispatch, or external effects are implemented.'
            ),
            'landed': (
                'Runtime implementation exists with persistence, dispatch, '
                'or external effects wired.'
            ),
            'unmatched': (
                'No WBC surface exists for this row; it belongs to another owner '
                'and has no WBC mapping.'
            ),
            'm6a_owned_substrate': (
                'Row is the M6A target substrate — schema-only currently, '
                'implementation planned for this milestone.'
            ),
            'blocked_substrate': (
                'Row requires WBC substrate that is blocked pending M6A implementation.'
            ),
        },
        'dispatch_and_external_effects_status': (
            substrate_map['dispatch_and_external_effects_status']
        ),
        'rows': [],
    }

    counts = {
        'schema-only': 0,
        'landed': 0,
        'unmatched': 0,
        'm6a-owned-substrate': 0,
        'blocked-substrate': 0,
    }

    for row in mm['rows']:
        ri = row['row_index']
        surface = row['consumer_surface']
        owner = row['owner']
        findings_refs = row['evidence'].get('finding_register_matches', [])
        classification = _classify_row(row)

        counts[classification] = counts.get(classification, 0) + 1

        row_classification['rows'].append({
            'row_index': ri,
            'consumer_surface': surface,
            'owner': owner,
            'owner_raw': row['owner_raw'],
            'status_raw': row['status_raw'],
            'migration_classification': row['classification'],
            'finding_register_matches': findings_refs,
            'milestone': row['milestone'],
            'surface_classification': classification,
            'classification_rationale': _classification_rationale(row, classification),
            'dispatch_enabled': False,
            'external_effects_enabled': False,
        })

    row_classification['summary'] = {
        'total_rows': len(mm['rows']),
        **counts,
    }

    content = json.dumps(row_classification, sort_keys=True, indent=2)
    row_classification['composite_hash'] = (
        'sha256:' + hashlib.sha256(content.encode('utf-8')).hexdigest()
    )

    with open('evidence/m6a-schema-only-row-classification.json', 'w') as f:
        json.dump(row_classification, f, indent=2, sort_keys=True)

    print("Generated evidence/m6a-schema-only-row-classification.json")
    print(f"Classification summary: {counts}")


if __name__ == '__main__':
    main()
