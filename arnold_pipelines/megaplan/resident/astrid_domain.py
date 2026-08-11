"""Astrid resident domain definition for the contract generator.

This is the single source of truth for the Astrid resident operator persona.
The checked-in example files under ``examples/agents/`` and
``examples/resident/astrid/`` are generated from this definition, and the
generator CLI produces byte-identical output (verified by
``tests/resident/test_astrid_resident.py``).

The Astrid contract (B12):

- attach to a project as ``agent:<id>`` and operate on ``projects/<slug>/``
  and ``runs/<slug>/``;
- use the Astrid gateway, with ``--engine arnold`` when invoking the Arnold
  adapter;
- repeatedly call ``astrid next``; execute exactly the one legal action
  returned (``bootstrap``, ``run: ...``, or ``ack ...``);
- never freelance actions outside the gateway's returned command;
- use ``astrid status`` to reorient after restart or uncertainty;
- acknowledge human gates with the explicit approval/acknowledgement action;
- on lease conflict, obey writer-epoch rules and perform takeover only
  through the supported session takeover protocol;
- expose only Astrid gateway tools and file tools constrained to the run
  directory;
- load provider credentials from the repository ``.env.local``, including
  the documented OpenAI/Gemini/Anthropic/RunPod/Hugging Face/Replicate and
  Astrid-specific variables;
- record typed media outputs such as ``video/mp4``, ``audio/wav``, and
  ``x-astrid-timeline``;
- emit typed media evidence plus ``MediaUsage`` cost into the resident
  store, manifest, ledger, notifications, heartbeat, watchdog, and
  restart-recovery paths.
"""

from __future__ import annotations

from .generator import ResidentDomain

ASTRID_PROMPT_BODY = """You are the Astrid resident operator, driving the Astrid project gateway on behalf of the megaplan resident.

Operating rules:

1. Attach as `agent:<id>` and operate inside `projects/<slug>/` and `runs/<slug>/` only.
2. Loop: run `astrid next` (with `--engine arnold` when invoking the Arnold adapter). It returns exactly one legal action: `bootstrap`, `run: ...`, or `ack ...`. Execute exactly that action. NEVER freelance a different command.
3. When the returned action is `run: ...`, execute it; then re-run `astrid next`.
4. When a human gate is pending, acknowledge it with the explicit `astrid ack ... --decision approve|reject` action shown by the gateway. Never self-approve without the gateway returning the ack command.
5. Use `astrid status` to reorient after a restart or when the state is uncertain. Inspect ambiguous state before acting.
6. Lease conflicts: obey writer-epoch rules; perform takeover only through the supported session takeover protocol. Never run two operators against the same run.
7. Tools: only Astrid gateway tools and file tools, constrained to the run directory. Never touch files outside the run.
8. Credentials come from the repository `.env.local` (OpenAI, Gemini, Anthropic, RunPod, Hugging Face, Replicate, and Astrid-specific variables). Never print or echo credentials.
9. Record every produced artifact as typed evidence. Typed media (`video/mp4`, `audio/wav`, `x-astrid-timeline`) plus `MediaUsage` cost go into the resident store, manifest, ledger, notifications, heartbeat, watchdog, and restart-recovery paths.
10. Keep replies concise and evidence-first: state the action you executed, the artifact produced, and the evidence record written.
"""

ASTRID_CREDENTIALS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "Anthropic Claude provider key",
    "FAL_KEY": "FAL.ai media generation key",
    "HF_TOKEN": "Hugging Face token",
    "OPENAI_API_KEY": "OpenAI provider key",
    "REIGH_PAT": "Reigh personal access token",
    "REIGH_SUPABASE_JWKS_URL": "Reigh Supabase JWKS verification URL",
    "REIGH_SUPABASE_SERVICE_ROLE_KEY": "Reigh Supabase service-role key",
    "REIGH_SUPABASE_URL": "Reigh Supabase project URL",
    "REPLICATE_API_TOKEN": "Replicate media generation token",
    "RUNPOD_API_KEY": "RunPod GPU pod key",
    "SUPABASE_URL": "Astrid Supabase project URL",
}

ASTRID_CWD_POLICY: dict[str, str] = {
    "run_root_template": "projects/<slug>/runs/<run-id>",
    "artifact_root": "run-relative artifact root",
    "forbidden": "outside the run directory",
}

ASTRID_TOOLS: tuple[str, ...] = (
    "astrid-gateway",
    "bash",
    "glob",
    "read",
    "write",
)


def build_astrid_domain() -> ResidentDomain:
    """Return the canonical Astrid resident domain definition."""
    return ResidentDomain(
        slug="astrid",
        agent_name="astrid-resident",
        description="Astrid project gateway operator: attach, next-loop, gateway actions, typed media evidence.",
        tools=ASTRID_TOOLS,
        model="@task",
        thinking_level="medium",
        gateway_command=("astrid", "next", "--engine", "arnold"),
        credentials=ASTRID_CREDENTIALS,
        cwd_policy=ASTRID_CWD_POLICY,
        prompt_body=ASTRID_PROMPT_BODY,
    )
