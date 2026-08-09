import json, hashlib, os
EVID="/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold/.megaplan/incident-evidence/critique-r7-superfixer-20260806-093148-0d3c3bc5"
rep=json.load(open(EVID+"/swarm/_report.json"))
idx={"schema":"arnold.superfixer.swarm_index.v1","occurrence":"occ_critique_r7_superfixer_retry_20260806_v1_70c522f651d6859e134250ee","model":"hermes:deepseek:deepseek-v4-flash","transport":"hermes via subagent-launcher/fan.py (threads, max_workers=4)","owner_pid":897988,"tasks":[]}
for t in rep["tasks"]:
    f=t["response_file"]
    h="sha256:"+hashlib.sha256(open(f,'rb').read()).hexdigest()
    idx["tasks"].append({"question":t["stem"],"brief":os.path.basename(t["brief"]),"brief_sha256":"sha256:"+hashlib.sha256(open(t["brief"],'rb').read()).hexdigest(),"report":f,"report_sha256":h,"model":t["model"],"provider":"hermes","transport":"hermes:deepseek:deepseek-v4-flash via fan.py","started_utc":t["started_at"],"finished_utc":t["finished_at"],"elapsed_s":round(t["elapsed_s"],1),"status":t["status"],"tool_calls":t["tool_calls"],"response_chars":t["response_chars"]})
idx["summary"]={"succeeded":rep["succeeded_count"],"failed":rep["failed_count"],"stopped_by_signal":rep["stopped_by_signal"],"sum_agent_seconds":round(rep["sum_agent_seconds"],1)}
json.dump(idx,open(EVID+"/swarm-index.json","w"),indent=1,sort_keys=True)
print("index written, tasks:",len(idx["tasks"]))
for t in idx["tasks"]:
    print(t["question"], t["status"], t["report_sha256"][:22], t["elapsed_s"])
