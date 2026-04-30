import subprocess, sys, os
# Run the real megaplan CLI by explicitly excluding this directory from PYTHONPATH
env = os.environ.copy()
# Prepend the real megaplan source so it's found first
real_megaplan = "/Users/peteromalley/Documents/megaplan"
env["PYTHONPATH"] = real_megaplan + ":" + env.get("PYTHONPATH", "")
args = [sys.executable, "-c", 
    f"import sys; sys.path.insert(0, '{real_megaplan}'); from megaplan.__main__ import main; main()",
] + sys.argv[1:]
sys.exit(subprocess.call(args, env=env))
