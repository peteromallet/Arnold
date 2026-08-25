# Area A — arnold launch path (Explorer A)
Entry points (pyproject.toml L43-45): `arnold` -> agentbox.arnold_agent:main; `megaplan` -> arnold.cli:main; `agentbox` -> agentbox.cli:main.
Launch: main() parses --agent (default "arnold"); _split_flags -> interactive TUI (empty msg) / one-shot / resume(-c/--resume); _find_launcher() (ARNOLD_AGENT_LAUNCHER > ~/.bun/bin/agent > shutil.which); _select_omp_bin() sets OMP_BIN -> fork dist/omp unless ARNOLD_STOCK_OMP=1; os.execvp("agent", ["agent","run",agent,...]) full process replacement, FDs inherited. ~/.bun/bin/agent bash script strips agent .md frontmatter -> ~/.omp/agent/.prompts/<name>.md then exec $OMP_BIN --system-prompt ...
Resident + cloud paths bypass arnold_agent.py entirely.
RECOMMENDED HOOK: agentbox/arnold_agent.py main() ~L158-165 between launcher resolution and execvp — universal entry, all mode guards computed, TTY still ours, existing guarded-output precedent (_print_one_shot_header).
Guards: skip if message non-empty (one-shot), -c/--resume, --session-dir, not stderr/stdin isatty, CI env, ARNOLD_STOCK_OMP=1 soft-skip, MEGAPLAN_RESIDENT_MODE defensive.
Persistence of "onboarded" marker: file like ~/.omp/agent/.arnold_onboarded.
