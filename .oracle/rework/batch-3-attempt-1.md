# Rework tasklist — batch-3 attempt 1 (from GateB3)
1. [normal] api_key prompt claims "(input hidden)" but ask_secret is a plain readline -> key
   echoes on a real TTY. Fix: real echo suppression via termios when stdin isatty (per-char
   read, Enter=submit, Ctrl-C=cancel), injectable/plain-line fallback keeps tests deterministic.
   Add TTY-simulation test using a pty if cheap, else assert suppression branch selected by
   monkeypatched isatty + unit-test the termios reader against an os.pipe.
2. [normal] delete dead _default_agent_dir_or NotImplementedError shim + misleading comment.
Acceptance: both fixed; suite green.
