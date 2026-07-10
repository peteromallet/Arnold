"""Deterministic L2 terminal audit with no model dispatch."""
from __future__ import annotations
import argparse, datetime as dt, json, os, subprocess
from pathlib import Path
from typing import Any, Sequence
from arnold_pipelines.megaplan.cloud.meta_repair import RetriggerExecutionResult, authoritative_terminal_snapshot_reason, verify_retrigger_success
from arnold_pipelines.megaplan.cloud.repair_contract import atomic_write_json, update_session_index, validate_repair_data
def _obj(p:Path,label:str)->dict[str,Any]:
    try:v=json.loads(p.read_text())
    except (OSError,json.JSONDecodeError) as e:raise ValueError(f"{label} unreadable: {e}") from e
    if not isinstance(v,dict):raise ValueError(f"{label} must be a JSON object")
    return v
def capture_terminal_snapshot(s:str,md:Path)->dict[str,Any]:
    m=_obj(md/f"{s}.json","session marker"); w=Path(str(m.get("workspace") or ""))
    if not w.is_dir():raise ValueError("session workspace unavailable for authoritative snapshot")
    cs=sorted((w/".megaplan/plans/.chains").glob("*.json"),key=lambda p:p.stat().st_mtime)
    if not cs:raise ValueError("chain state unavailable for authoritative snapshot")
    cp=cs[-1]; c=_obj(cp,"chain state"); n=str(c.get("current_plan_name") or "").strip(); pp=w/".megaplan/plans"/n/"state.json"
    if not n or not pp.exists():
        ps=sorted((w/".megaplan/plans").glob("*/state.json"),key=lambda p:p.stat().st_mtime)
        if not ps:raise ValueError("current plan state unavailable for authoritative snapshot")
        pp=ps[-1]
    p=_obj(pp,"plan state"); ms=c.get("milestones") if isinstance(c.get("milestones"),list) else []; done=c.get("completed") if isinstance(c.get("completed"),list) else []; a=p.get("active_step") if isinstance(p.get("active_step"),dict) else {}; pid=a.get("worker_pid"); alive=None
    if pid not in (None,""):
        try:os.kill(int(pid),0)
        except (OSError,ValueError):alive=False
        else:alive=True
    return {"captured_at":dt.datetime.now(dt.timezone.utc).isoformat(),"workspace":str(w),"chain_path":str(cp),"plan_path":str(pp),"milestone_total":len(ms),"completed_count":len(done),"chain_last_state":str(c.get("last_state") or "").strip().lower(),"plan_current_state":str(p.get("current_state") or p.get("state") or "").strip().lower(),"active_step_present":bool(a),"worker_pid":pid,"worker_pid_alive":alive,"remote_spec":str(m.get("remote_spec") or "").strip()}
def run_terminal_audit(*,session:str,repair_loop_bin:Path,marker_dir:Path,repair_data_dir:Path)->dict[str,Any]:
    started=dt.datetime.now(dt.timezone.utc).isoformat(); pre=post=None; cmd=[]; rc=None; rejection=""
    try:
        pre=capture_terminal_snapshot(session,marker_dir); rejection=authoritative_terminal_snapshot_reason(pre)
        if rejection:v={"accepted":False,"retriggered":False,"rejection_reason":rejection,"outcome":"terminal_audit_rejected","pre_snapshot":pre}
        else:
            cmd=[str(repair_loop_bin),session,pre["workspace"]]+([pre["remote_spec"]] if pre.get("remote_spec") else []); x=subprocess.run(cmd,cwd=pre["workspace"],capture_output=True,text=True,check=False,timeout=3600);rc=int(x.returncode);side=validate_repair_data(repair_data_dir/f"{session}.repair-data.json");post=capture_terminal_snapshot(session,marker_dir);v=verify_retrigger_success(retriggered=True,retrigger_result=RetriggerExecutionResult(tuple(cmd),rc,str(x.stdout or ""),str(x.stderr or "")),post_retrigger_verification={"outcome":side.get("outcome",""),"pre_snapshot":pre,"post_snapshot":post})
    except Exception as e:
        rejection=rejection or f"authoritative terminal audit failed: {type(e).__name__}: {e}";v={"accepted":False,"retriggered":bool(cmd),"rejection_reason":rejection,"outcome":"terminal_audit_rejected","pre_snapshot":pre,"post_snapshot":post}
    ok=bool(v.get("accepted"));now=dt.datetime.now(dt.timezone.utc);r={"kind":"terminal_audit","session":session,"started_at":started,"recorded_at":now.isoformat(),"command":cmd,"l1_returncode":rc,"accepted":ok,"outcome":"complete" if ok else "verifier_rejected","post_retrigger_verification":v,"pre_snapshot":pre,"post_snapshot":post};d=repair_data_dir/"meta";d.mkdir(parents=True,exist_ok=True);path=d/f"terminal-audit-{session}-{now.strftime('%Y%m%dT%H%M%SZ')}.json";atomic_write_json(path,r);update_session_index(repair_data_dir/"index.json",session,{"latest_terminal_audit":str(path),"terminal_audit_accepted":ok,"terminal_audit_outcome":r["outcome"],"terminal_audit_recorded_at":r["recorded_at"]});r["record_path"]=str(path);return r
def main(argv:Sequence[str]|None=None)->int:
    q=argparse.ArgumentParser();q.add_argument("session");q.add_argument("--repair-loop-bin",required=True);q.add_argument("--marker-dir",required=True);q.add_argument("--repair-data-dir",required=True);a=q.parse_args(argv);r=run_terminal_audit(session=a.session,repair_loop_bin=Path(a.repair_loop_bin),marker_dir=Path(a.marker_dir),repair_data_dir=Path(a.repair_data_dir));print(json.dumps(r,sort_keys=True));return 0 if r["accepted"] else 73
if __name__=="__main__":raise SystemExit(main())

