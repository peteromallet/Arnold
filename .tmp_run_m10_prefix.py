import json
import shlex
import subprocess
import sys


payload = json.load(open(sys.argv[1], encoding="utf-8"))
args = shlex.split(payload["command"])
end = args.index("tests/cloud/test_watchdog_wrappers.py")
command = args[: end + 1] + ["-x", "--tb=long", "-q"]
raise SystemExit(subprocess.run(command, check=False).returncode)
