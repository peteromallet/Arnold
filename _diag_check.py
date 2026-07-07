"""Temporary diagnostic helper to inspect workflow source state."""
import sys

# Ensure project dir wins over /workspace/arnold
sys.path = [p for p in sys.path if p not in ("/workspace/arnold", "")]
sys.path.insert(0, ".")

from arnold_pipelines.megaplan.workflows import planning as pl

print("=== attrs available in planning ===")
attrs = [a for a in dir(pl) if "workflow" in a.lower() or "check" in a.lower() or "compile" in a.lower()]
print(attrs)
