First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: the handler config bus (argparse Namespace → `args.` everywhere) & handler purity

Body 1b replaces the ~25-field `argparse.Namespace` config bus with a typed `HandlerContext` and
makes `handle_*` pure-ish `(root, state, hctx)` functions. The brief calls this a call-graph
refactor (`args.` read at ~47 sites threading through `_finish_step`→`build_receipt`→`_run_worker`
→`resolve_agent_mode`). Map how bad the foundation really is.

Investigate (cite path:line):
- Trace `args.` reads across `handlers/*`, `cli.py`, `shared.py`. How many distinct attributes?
  Which are config vs runtime services (emitters, sinks, worker_runner)? Which are set in ONE
  place and read 10 layers down (implicit coupling)?
- Handler purity: `handle_gate` reprompt/auto-downgrade loop (`gate.py:466-521`), `handle_execute`
  auto-loop (`execute.py:140-166`). What side effects do handlers have beyond returning a delta —
  disk writes, subprocess spawns, global mutation, reading env vars, time/network?
- Are there hidden inputs (env vars like `MEGAPLAN_*`, cwd assumptions, global config singletons)
  that aren't in `args` at all and would be missed by a HandlerContext that only captures `args`?
- The two `__all__` public exports of `handle_*` (`megaplan/__init__.py`, `handlers/__init__.py`)
  — who actually imports these externally (tests, cloud, chain, bakeoff)? signature blast radius.

Key question: is the handler layer a set of functions-with-a-config-arg (refactorable to
HandlerContext mechanically), or a web of implicit ambient state (env, cwd, globals, disk) where
"pure-ish (root, state, hctx)" is a fiction that will leak? Enumerate every ambient input a
HandlerContext would have to capture, and the ones the brief didn't list.
