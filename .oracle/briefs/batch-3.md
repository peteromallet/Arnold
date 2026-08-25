# Executor brief — Batch 3 (Interactive flow)
North Star: one verified route is success; detect-before-asking; never re-prompt; secrets masked.
Worktree /Users/peteromalley/Documents/Arnold-onboard-oracle. Commit NOTHING.

## agentbox/onboarding/flow.py
Dataclasses: FlowResult(exit_code, wired_provider, route, verified).
Public API:
- should_offer(*, stdin_tty, stderr_tty, message, flags, environ=os.environ) -> bool
  Guards (ALL must hold to offer): stdin+stderr TTY; not message (one-shot); no -c/--resume;
  no --session-dir; env CI unset; ARNOLD_STOCK_OMP!=1; MEGAPLAN_RESIDENT_MODE unset.
  Pure function — trivially unit-testable.
- run_flow(*, scan=None, stdin=input, stdout=print, omp_bin="omp", agent_dir=None) -> FlowResult
  Screens (all output via stdout param, all input via stdin param — NO direct input()/print(),
  so tests script sessions):
  S0 header "Welcome to Arnold..." + run scan (reuse detect.scan_providers).
  S1 summary bucketed ready/found/missing ranked by catalog; options: found/ready providers
     first (recommended = best ready, else best candidate), then "Set up OpenRouter…" lane
     (always visible if openrouter not already selected), then "show everything" toggle.
     Prompt: number selection.
  S2 wiring menu per provider auth_kinds (from catalog): api_key -> mask input via getpass-like
     (use stdin-based masked read: accept plain line for testability but never echo to logs),
     oauth -> wire_oauth (only if stdin_tty), cli_proxy -> wire_cli_proxy.
  S3 model pick: default_route preselected "[Enter=keep]", allow typing alternate model id.
  S4 verify via wire.verify_route(default chosen route); fail -> loop back to S2 for that
     provider (max 3 attempts) offering re-paste/different provider; never exit half-wired:
     exit 1 only if user declines/cancels at any prompt ("n"/EOF/Ctrl-C handled as decline).
  S5 success screen prints route + persistence note + provenance confirmation; ask
     "Add another provider now? [y/N]" default No -> loop to S1 minus configured.
  Exit contract: 0 >=1 verified route; 1 cancelled; 2 non-TTY (print one-line hint mentioning
  onboarding scan --json style introspection... actually print: "Non-interactive shell; run
  `arnold` in a terminal to set up providers." ).
- offer_and_repreflight(guards..., repreflight: Callable[[],bool], omp_bin="omp") -> bool|None:
  if not should_offer: return None. Print failed-route summary lines passed in. Ask
  "Set up providers now? [Y/n]". Decline->None. Accept->run_flow; on exit 0 call
  repreflight() and return its bool. OLD-PIN FALLBACK: any FileNotFoundError/OSError raised
  while invoking omp binary during flow startup => catch, print nothing extra, return None
  (caller falls through to original failure path). EOFError/KeyboardInterrupt -> exit 1 semantics.
Add `scan --json` CLI? NOT in scope (tasklist B3 only flow). Keep module import-light.

## Tests tests/agentbox/test_onboarding_flow.py
- guards matrix table test (~10 cases).
- scripted sessions: monkeypatch scan_providers to canned ScanReport + _run/_verify seams;
  full happy path (select candidate deepseek -> paste key (fake) -> verify ok) asserting
  FlowResult(0,...), wire called with consent, provenance recorded.
- verify-fail loop-back (fail twice then pass) capped at 3.
- decline at main prompt -> cancelled; EOF mid-flow -> 1; non-TTY -> 2 with hint text.
- old-pin: omp invocation raising FileNotFoundError -> offer_and_repreflight returns None,
  original repreflight result untouched.
- secret masking: captured transcript never contains the pasted key value.
Run: uv run pytest tests/agentbox -q -k onboarding. Report verbatim + deviations.
