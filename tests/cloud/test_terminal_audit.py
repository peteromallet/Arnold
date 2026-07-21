from __future__ import annotations
import json
from pathlib import Path
import pytest
from arnold_pipelines.megaplan.cloud.repair_contract import read_jsonl_records
from arnold_pipelines.megaplan.cloud.terminal_audit import run_terminal_audit
def fix(t:Path,*,completed=2,total=2,active=None,state="done",side=None,exit=0):
 w=t/"w";w.mkdir();c=w/".megaplan/plans/.chains/x.json";c.parent.mkdir(parents=True);c.write_text(json.dumps({"current_plan_name":"p","last_state":"done","milestones":[{}]*total,"completed":[{}]*completed}));p=w/".megaplan/plans/p/state.json";p.parent.mkdir(parents=True);p.write_text(json.dumps({"current_state":state,**({"active_step":active} if active is not None else {})}));m=t/"m";m.mkdir();m.joinpath("s.json").write_text(json.dumps({"workspace":str(w)}));d=t/"d";d.mkdir();d.joinpath("s.repair-data.json").write_text(json.dumps({"session":"s","outcome":"complete"} if side is None else side));calls=t/"calls";l=t/"l";l.write_text(f"#!/bin/sh\necho x >> {calls}\nexit {exit}\n");l.chmod(0o755);return m,d,l,calls
def test_ok(tmp_path):
 m,d,l,calls=fix(tmp_path);r=run_terminal_audit(session="s",repair_loop_bin=l,marker_dir=m,repair_data_dir=d);assert r["accepted"] and r["post_snapshot"]["captured_at"] and calls.read_text()=="x\n";assert json.loads((d/"index.json").read_text())["sessions"]["s"]["terminal_audit_accepted"]
@pytest.mark.parametrize("kw",[{"completed":1,"total":2},{"active":{"worker_pid":99999999}},{"state":"finalized"}])
def test_reject_before_l1(tmp_path,kw):
 m,d,l,calls=fix(tmp_path,**kw);assert not run_terminal_audit(session="s",repair_loop_bin=l,marker_dir=m,repair_data_dir=d)["accepted"];assert not calls.exists()
def test_malformed(tmp_path):
 m,d,l,calls=fix(tmp_path,side=[]);assert not run_terminal_audit(session="s",repair_loop_bin=l,marker_dir=m,repair_data_dir=d)["accepted"];assert calls.read_text()=="x\n"
def test_l1_nonzero(tmp_path):
 m,d,l,calls=fix(tmp_path,exit=7);assert not run_terminal_audit(session="s",repair_loop_bin=l,marker_dir=m,repair_data_dir=d)["accepted"];assert calls.read_text()=="x\n"

def test_wrapper_terminal_mode_precedes_classification_and_model_dispatch() -> None:
    text=Path("arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop").read_text()
    section=text[text.index('if [[ "$TERMINAL_AUDIT_MODE" == 1 ]]'):text.index('# ---- classify failure')]
    assert 'terminal_audit' in section
    assert 'codex' not in section.lower()
def test_terminal_audit_uses_canonical_remote_spec_when_runtime_omits_milestones(tmp_path):
    m,d,l,calls=fix(tmp_path)
    marker=json.loads((m/'s.json').read_text())
    workspace=Path(marker['workspace'])
    spec=workspace/'chain.yaml'; spec.write_text('milestones:\n  - label: sprint-1\n  - label: sprint-2\n')
    marker['remote_spec']=str(spec); (m/'s.json').write_text(json.dumps(marker))
    chain=next((workspace/'.megaplan/plans/.chains').glob('*.json'))
    payload=json.loads(chain.read_text()); payload.pop('milestones'); chain.write_text(json.dumps(payload))
    record=run_terminal_audit(session='s',repair_loop_bin=l,marker_dir=m,repair_data_dir=d)
    assert record['accepted'] is True
    assert record['post_snapshot']['milestone_total'] == 2
    assert record['post_snapshot']['milestone_total_source'] == 'remote_spec'
    assert calls.read_text() == 'x\n'


def test_terminal_audit_appends_incident_sidecar(tmp_path):
    m,d,l,_calls=fix(tmp_path)
    record=run_terminal_audit(session="s",repair_loop_bin=l,marker_dir=m,repair_data_dir=d)
    sidecar=d.with_name(f"{d.name}.d")/"incidents"/"incidents.jsonl"
    rows=read_jsonl_records(sidecar)
    assert record["sidecar_path"] == str(sidecar)
    assert rows[-1]["session"] == "s"
    assert rows[-1]["kind"] == "terminal_audit"
    assert rows[-1]["summary"] == "complete"
    assert rows[-1]["accepted"] is True
