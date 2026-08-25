# Rework tasklist — batch-3 attempt 2 (from GateB3r)
1. [normal] _read_hidden decodes byte-at-a-time -> multi-byte UTF-8 corrupted to U+FFFD.
   Fix: accumulate raw bytes, decode once at line end.
2. [normal] os.read returning b'' (EOF) spins infinite loop appending "". Fix: return None on
   empty read. Regression test: close pty master mid-read -> None.
3. [trivial] remove unused sys import in test file; treat \x08 as backspace.
Deferred (recorded): ask_secret TTY branch bypasses injected stdin (documented contract:
interactive = real fd0; scripted sessions are non-TTY by construction); no newline echo after
Ctrl-C cancel.
