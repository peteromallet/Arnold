#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
TRACE_ROOT = ROOT / "results" / "auto-improve" / "iteration-007"
OUTPUT_PATH = ROOT / "results" / "model-compare" / "critique_comparison.json"
STRICT_MESSAGE_KEYS = {"reasoning", "finish_reason"}
STRICT_TOOL_CALL_KEYS = {"call_id", "response_item_id"}
TASKS = {
    "django__django-10097": ["colon", "password", ":\\", "[^\\s:@/]"],
    "django__django-10999": ["sign", "negative", "(?P<sign>"],
    "django__django-10973": ["env=None", "no password", "nopass", "os.environ.copy"],
    "astropy__astropy-13977": ["check_output", "broad", "entire method", "NotImplemented"],
}


def load_trace(task_id):
    paths = sorted(TRACE_ROOT.glob(f"worker-*/{task_id}/*/traces/critique_v1.json"))
    if not paths:
        raise FileNotFoundError(f"no critique trace found for {task_id}")
    path = paths[0]
    messages = json.loads(path.read_text())
    return path, messages[:-1]


def clean_messages(messages):
    cleaned = []
    for msg in messages:
        item = {k: v for k, v in msg.items() if k not in STRICT_MESSAGE_KEYS}
        if item.get("role") == "assistant" and isinstance(item.get("tool_calls"), list):
            item["tool_calls"] = [
                {k: v for k, v in tool_call.items() if k not in STRICT_TOOL_CALL_KEYS}
                if isinstance(tool_call, dict) else tool_call
                for tool_call in item["tool_calls"]
            ]
        cleaned.append(item)
    return cleaned


def find_forbidden_fields(messages):
    found = []
    for idx, msg in enumerate(messages):
        for key in STRICT_MESSAGE_KEYS:
            if key in msg:
                found.append(f"message[{idx}].{key}")
        for tc_idx, tool_call in enumerate(msg.get("tool_calls", [])):
            if isinstance(tool_call, dict):
                for key in STRICT_TOOL_CALL_KEYS:
                    if key in tool_call:
                        found.append(f"message[{idx}].tool_calls[{tc_idx}].{key}")
    return found


def load_glm_key():
    if os.getenv("ZHIPU_API_KEY"):
        return os.getenv("ZHIPU_API_KEY"), "https://api.z.ai/api/coding/paas/v4"
    key_path = ROOT / "auto_improve" / "api_keys.json"
    if key_path.exists():
        entries = json.loads(key_path.read_text())
        if entries:
            first = entries[0]
            return first.get("key"), first.get("base_url") or "https://api.z.ai/api/coding/paas/v4"
    return None, "https://api.z.ai/api/coding/paas/v4"


def model_configs():
    glm_key, glm_base_url = load_glm_key()
    return {
        "glm-5.1": {"model": "glm-5.1", "base_url": glm_base_url, "api_key": glm_key},
        "minimax-m2.7": {
            "model": "minimax/minimax-m2.7",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": os.getenv("OPENROUTER_API_KEY"),
        },
    }


def extract_json_payload(text):
    decoder = json.JSONDecoder()
    blocks = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    for label, candidate in [("fenced_json", block) for block in blocks] + [("full_text", text)]:
        candidate = candidate.strip()
        if not candidate:
            continue
        for start, ch in enumerate(candidate):
            if ch not in "[{":
                continue
            try:
                return decoder.raw_decode(candidate[start:])[0], label
            except json.JSONDecodeError:
                continue
    return None, None


def parse_response(content, keywords):
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    payload, source = extract_json_payload(text)
    searchable = json.dumps(payload, ensure_ascii=False) if payload is not None else text
    lowered = searchable.lower()
    matches = {kw: kw.lower() in lowered for kw in keywords}
    return {
        "content": text,
        "json_source": source,
        "parsed_json": payload,
        "matched_keywords": [kw for kw, ok in matches.items() if ok],
        "missed_keywords": [kw for kw, ok in matches.items() if not ok],
    }


def call_model(config, messages):
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
    try:
        resp = client.chat.completions.create(model=config["model"], messages=messages)
        msg = resp.choices[0].message
        content = msg.content or ""
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)
        return {"ok": True, "content": content}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def print_summary(rows):
    headers = ("task", "model", "matched", "missed")
    widths = [max(len(str(row[i])) for row in [headers, *rows]) for i in range(4)]
    print(" | ".join(str(headers[i]).ljust(widths[i]) for i in range(4)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(4)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    traces = {}
    for task_id in TASKS:
        path, replay_messages = load_trace(task_id)
        cleaned = clean_messages(replay_messages)
        traces[task_id] = {"path": str(path), "messages": cleaned}

    if args.dry_run:
        for task_id, data in traces.items():
            roles = [msg.get("role", "?") for msg in data["messages"]]
            forbidden = find_forbidden_fields(data["messages"])
            print(f"{task_id}: {data['path']}")
            print(f"  messages={len(data['messages'])} roles={roles}")
            print(f"  strict_api_fields_remaining={forbidden or 'none'}")
        return 0

    results = {
        "tasks": {task_id: {"trace_path": data["path"], "message_count": len(data["messages"])} for task_id, data in traces.items()},
        "models": {},
    }
    rows = []
    for model_name, config in model_configs().items():
        if not config["api_key"]:
            print(f"warning: skipping {model_name}; API key not available", file=sys.stderr)
            results["models"][model_name] = {"skipped": True, "reason": "missing_api_key"}
            continue
        results["models"][model_name] = {"skipped": False, "runs": {}}
        for task_id, keywords in TASKS.items():
            api_result = call_model(config, traces[task_id]["messages"])
            run = {"keywords": keywords, **api_result}
            if api_result["ok"]:
                run.update(parse_response(api_result["content"], keywords))
                rows.append((task_id, model_name, ", ".join(run["matched_keywords"]) or "-", ", ".join(run["missed_keywords"]) or "-"))
            else:
                rows.append((task_id, model_name, "ERROR", api_result["error"]))
            results["models"][model_name]["runs"][task_id] = run

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUTPUT_PATH}")
    print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
