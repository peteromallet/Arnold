from __future__ import annotations

import argparse
from pathlib import Path

from megaplan.types import (
    DEFAULT_AGENT_ROUTING,
    DEFAULTS,
    KNOWN_AGENTS,
    ROBUSTNESS_ACCEPTED,
    ROBUSTNESS_LEVELS,
    CRITIC_MODEL_CHOICES,
    _SETTABLE_BOOL,
    _SETTABLE_ENUM,
    _SETTABLE_NUMERIC,
)
from megaplan.forms import available_form_ids
from megaplan.profiles import load_profile_sources, load_profiles, resolve_profile
from megaplan.resolutions import SUPPORTED_USER_ACTION_RESOLUTION_STATES
from megaplan.quality_resolutions import VALID_RESOLUTIONS as QUALITY_VALID_RESOLUTIONS

def _add_vendor_critic_args(parser: argparse.ArgumentParser) -> None:
    """Wire profile modifier flags onto a subparser.

    Kept as one helper so the wiring stays consistent across the five
    subcommands that take a ``--profile``. All flags default to
    ``None`` so ``apply_profile_expansion`` can distinguish "user
    didn't say" from "user explicitly picked claude/kimi/etc." and
    consult the config default in the former case.
    """
    parser.add_argument(
        "--vendor",
        choices=["claude", "codex"],
        default=None,
        help="Pick the premium vendor for tier-2-through-4 profile slots. "
        "Swaps claude:X <-> codex:X at the same effort tier; hermes specs "
        "untouched. Defaults to ~/.config/megaplan/config.toml "
        "[defaults].vendor (or 'claude'). Silently ignored when the "
        "active profile is vendor_locked = true.",
    )
    parser.add_argument(
        "--depth",
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
        default=None,
        help="Set author-phase thinking depth (plan / revise / loop_plan / "
        "tiebreaker_researcher / tiebreaker_challenger). Rewrites the "
        "effort suffix on claude:X / codex:X slots; critic and "
        "mechanical phases are not touched (asymmetry principle). "
        "hermes specs and profiles with no premium author slots are a "
        "silent no-op. Defaults to whatever depth the profile already "
        "sets (usually :low). Honored on vendor_locked profiles.",
    )
    parser.add_argument(
        "--critic",
        choices=["kimi", "cross"],
        default=None,
        help="Override the critique+review pair (the critique == review "
        "invariant — same mind pre- and post-execution). 'kimi' swaps "
        "in Kimi (Fireworks-hosted kimi-k2p6) for both phases; 'cross' swaps to the other "
        "premium vendor relative to --vendor. Silently ignored on "
        "vendor_locked profiles.",
    )
    parser.add_argument(
        "--deepseek-provider",
        choices=["fireworks", "direct"],
        default=None,
        help="Choose the provider for canonical DeepSeek v4-pro profile slots. "
        "'fireworks' uses hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro; "
        "'direct' uses hermes:deepseek:deepseek-v4-pro and DEEPSEEK_API_KEY. "
        "Defaults to 'direct'. Non-DeepSeek slots are untouched.",
    )


def _add_workflow_shape_args(parser: argparse.ArgumentParser) -> None:
    """Wire workflow-shape flags (--with-prep, --with-feedback) onto a subparser.

    These flags are only exposed on ``init`` because they determine the
    workflow shape stored in state.config during plan creation.  Step,
    loop, and tiebreaker commands recover the workflow shape from the
    persisted state and do not re-expose these flags.
    """
    parser.add_argument(
        "--with-prep",
        action="store_true",
        default=False,
        help="Force the visible prep phase into the workflow regardless of "
        "--robustness. By default, prep only runs at --robustness "
        "thorough|extreme; this flag adds prep to full / light / "
        "bare so the planner can do explicit research before committing "
        "to a plan. Useful for unfamiliar libraries, novel external "
        "APIs, research-heavy briefs, or ambiguous requirements. "
        "Redundant on --robustness thorough|extreme (no-op).",
    )
    parser.add_argument(
        "--with-feedback",
        action="store_true",
        default=False,
        help="Force the visible feedback phase into the workflow regardless "
        "of --robustness. By default no feedback step runs; this flag "
        "adds a feedback step between review and done that scaffolds "
        "feedback.md (a per-stage ratings template) for the user to "
        "fill in afterward. Runs non-interactively under megaplan auto "
        "\u2014 never blocks on human input.",
    )


def _add_execute_tier_cap_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-execute-tier",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=None,
        metavar="N",
        help=(
            "Cap tier-routed execute lookup at N (1-5). A complexity above N "
            "routes as tier N; unset means no cap."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    import megaplan.cli as cli_mod

    parser = argparse.ArgumentParser(description="Megaplan orchestration CLI")
    parser.add_argument(
        "--actor",
        default=None,
        metavar="ID",
        help="Actor ID for DB writes (also MEGAPLAN_ACTOR_ID)",
    )
    parser.add_argument(
        "--backend",
        choices=["file", "db"],
        default=None,
        help="Storage backend (also MEGAPLAN_BACKEND)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup", help="Install megaplan into agent configs (global by default)"
    )
    setup_parser.add_argument(
        "--local",
        action="store_true",
        help="Install AGENTS.md into a project instead of global agent configs",
    )
    setup_parser.add_argument(
        "--target-dir", help="Directory to install into (default: cwd, implies --local)"
    )
    setup_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing files"
    )
    setup_parser.add_argument(
        "--regen-composed",
        action="store_true",
        help="Regenerate composed skill bundles from source files",
    )
    setup_parser.add_argument(
        "--install-hooks",
        action="store_true",
        help="Install the canonical megaplan git hooks into this repository",
    )

    init_parser = subparsers.add_parser("init")
    # --project-dir is normally required; the special case is --in-worktree,
    # which supplies the project-dir itself (the newly-created worktree).
    # We validate the mutual relationship in main() after parsing.
    init_parser.add_argument("--project-dir", required=False)
    init_parser.add_argument(
        "--in-worktree",
        default=None,
        metavar="NAME",
        help="Create a new git worktree at ~/Documents/.megaplan-worktrees/<name>/ "
        "on a new branch and initialize the plan inside it. Name must match "
        "^[a-z0-9][a-z0-9._-]{0,63}$. Substitutes for --project-dir.",
    )
    init_parser.add_argument(
        "--worktree-from",
        default=None,
        metavar="GITREF",
        help="Base ref for the new worktree (default: current HEAD of the repo "
        "where `megaplan init` was invoked). Only valid with --in-worktree.",
    )
    init_parser.add_argument(
        "--clean-worktree",
        action="store_true",
        default=False,
        help="With --in-worktree: fork from a clean base ref and leave any "
        "uncommitted state behind in the source repo (no carry).",
    )
    init_parser.add_argument(
        "--carry-dirty",
        action="store_true",
        default=False,
        help="With --in-worktree: explicitly opt into carrying uncommitted "
        "state from the source repo into the new worktree (this is the "
        "default already when the source is dirty; the flag exists for "
        "test/script clarity). Mutually exclusive with --clean-worktree.",
    )
    init_parser.add_argument("--name")
    init_parser.add_argument("--auto-approve", action="store_true", default=None)
    init_parser.add_argument("--adaptive-critique", action="store_true", default=None)
    init_parser.add_argument(
        "--strict-adaptive-critique",
        action="store_true",
        default=None,
        help=(
            "Raise AdaptiveCritiqueDegradedError instead of silently falling back "
            "to static lenses when the adaptive critique evaluator fails. "
            "Recommended for production / CI / important runs. "
            "Has no effect when --adaptive-critique is off."
        ),
    )
    init_parser.add_argument(
        "--critic-model",
        default=None,
        choices=[c for c in CRITIC_MODEL_CHOICES if c],
        help="Pin every farmed-out adaptive-critique critic to this model "
        "(the Opus evaluator still selects lenses; no per-lens escalation).",
    )
    init_parser.add_argument(
        "--strict-notes",
        action="store_true",
        default=None,
        help=(
            "Reject force-proceed while unabsorbed user notes exist; turn ESCALATE "
            "guidance into a hard human-required signal. Auto-on for --mode metaplan/doc."
        ),
    )
    # Accept canonical names plus legacy aliases (tiny|standard|robust|superrobust);
    # ``normalize_robustness`` collapses them downstream.
    init_parser.add_argument(
        "--robustness", choices=list(ROBUSTNESS_ACCEPTED), default=None
    )
    init_parser.add_argument(
        "--mode",
        choices=["code", "doc", "metaplan", "joke", "creative"],
        default=None,
        help="Deliverable type: 'code' (source changes), 'doc' / 'metaplan' "
        "(design/spec artifact — 'metaplan' is an alias for 'doc'), or "
        "'joke' (film scene script; requires --output), or "
        "'creative' (creative work; requires --form and --output). "
        "Defaults to 'code' unless the idea strongly suggests a design document, "
        "in which case --mode must be passed explicitly.",
    )
    init_parser.add_argument(
        "--form",
        choices=available_form_ids(),
        default=None,
        help="Creative form to use with --mode creative.",
    )
    init_parser.add_argument(
        "--output",
        default=None,
        help="Relative path where the prose artifact will be written. "
        "Required with --mode doc, --mode joke, or --mode creative; rejected with --mode code.",
    )
    init_parser.add_argument(
        "--primary-criterion",
        default=None,
        help="Declare the creative-work primary criterion (for example: 'weirdest coherent'). "
        "Valid only with --mode joke or --mode creative.",
    )
    init_parser.add_argument(
        "--from-doc",
        default=None,
        help="Relative path to a prior doc-mode artifact whose ## Settled "
        "Decisions section should be imported. Valid with --mode "
        "code, --mode doc, --mode joke, or --mode creative.",
    )
    init_parser.add_argument(
        "--idea-file",
        default=None,
        help="Read the idea text from a UTF-8 file instead of the positional CLI argument.",
    )
    init_parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Immediately run the auto driver after initializing the plan.",
    )
    init_parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent for all phases. Optional: specify default model",
    )
    init_parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-phase model override: --phase-model critique=hermes:openai/gpt-5",
    )
    init_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(init_parser)
    _add_execute_tier_cap_arg(init_parser)
    _add_workflow_shape_args(init_parser)
    init_parser.add_argument(
        "--prep-direction",
        default=None,
        metavar="TEXT",
        help="Steering text shown to the prep worker as 'User direction for prep'. "
        "Use to point prep at specific files, subsystems, or questions to explore "
        "(e.g. 'focus on the worker shutdown path; ignore CLI plumbing'). "
        "Only effective when prep runs (robustness thorough|extreme, or --with-prep).",
    )
    init_parser.add_argument(
        "--from-arnold-epic",
        default=None,
        metavar="EPIC_ID",
        help="Load plan idea from Arnold epic via DBStore (read-only; --backend db not required for read path)",
    )
    init_parser.add_argument("idea", nargs="?")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="Search all .megaplan directories system-wide (~)",
    )
    list_parser.add_argument(
        "--no-tree",
        action="store_true",
        help="Only show plans from the current directory (default includes parent + child)",
    )
    list_parser.add_argument(
        "--include-done",
        action="store_true",
        help="Include terminal plans; excluded by default",
    )
    list_parser.add_argument(
        "--status",
        dest="filter_status",
        help="Filter by state (e.g. 'done', 'finalized', 'executed', or comma-separated 'planned,critiqued')",
    )
    list_parser.add_argument(
        "--summary", action="store_true", help="Show count breakdown by state"
    )
    list_parser.add_argument(
        "list_target",
        nargs="?",
        choices=["pipelines"],
        help="List pipelines instead of plans (use 'pipelines')",
    )
    list_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose pipeline listing (description, version, profile)",
    )

    describe_parser = subparsers.add_parser(
        "describe", help="Show metadata and SKILL.md for a YAML pipeline"
    )
    describe_parser.add_argument(
        "pipeline_name",
        help="Name of the pipeline to describe (e.g. 'writing-panel-strict')",
    )
    describe_parser.set_defaults(func=cli_mod.handle_describe)

    epic_parser = subparsers.add_parser("epic", help="Inspect or migrate Arnold epics")
    epic_parser.add_argument("--project-dir", default=None)
    epic_subparsers = epic_parser.add_subparsers(dest="epic_action", required=True)
    epic_snapshot_parser = epic_subparsers.add_parser(
        "snapshot", help="Write an offline JSON snapshot for an epic"
    )
    epic_snapshot_parser.add_argument("epic_id")
    epic_snapshot_parser.add_argument("--project-dir", default=None)
    epic_migrate_parser = epic_subparsers.add_parser(
        "migrate", help="Promote or demote an epic between backends"
    )
    epic_migrate_parser.add_argument("epic_id", nargs="?")
    epic_migrate_parser.add_argument("--to", choices=["file", "db"], default=None)
    epic_migrate_parser.add_argument("--resume", metavar="MIGRATION_ID", default=None)
    epic_migrate_parser.add_argument(
        "--actor", default=None, metavar="ID", help="Actor ID for migration writes"
    )
    epic_migrate_parser.add_argument("--ttl", type=int, default=300)
    epic_migrate_parser.add_argument("--project-dir", default=None)
    epic_export_parser = epic_subparsers.add_parser(
        "export", help="Write a deterministic tar backup for an epic"
    )
    epic_export_parser.add_argument("epic_id")
    epic_export_parser.add_argument("--output", required=True)
    epic_export_parser.add_argument("--gzip", action="store_true")
    epic_export_parser.add_argument("--allow-missing-blobs", action="store_true")
    epic_export_parser.add_argument("--project-dir", default=None)

    # --- brief subcommand group ---
    brief_parser = subparsers.add_parser(
        "brief", help="Create canonical .megaplan/briefs source artifacts"
    )
    brief_parser.add_argument("--project-dir", default=None)
    brief_sub = brief_parser.add_subparsers(dest="brief_action", required=True)

    brief_new_parser = brief_sub.add_parser(
        "new", help="Create .megaplan/briefs/<slug>.md"
    )
    brief_new_parser.add_argument("slug", help="Brief slug")
    brief_new_body_group = brief_new_parser.add_mutually_exclusive_group(required=True)
    brief_new_body_group.add_argument(
        "-b", "--body", default=None, metavar="BODY", help="Brief text"
    )
    brief_new_body_group.add_argument(
        "--from",
        dest="from_file",
        default=None,
        metavar="PATH",
        help="Copy brief text from a UTF-8 file",
    )
    brief_new_body_group.add_argument(
        "-", dest="stdin_body", action="store_true", help="Read brief text from stdin"
    )
    brief_new_parser.add_argument("--force", action="store_true")
    brief_new_parser.add_argument(
        "--init",
        action="store_true",
        help="After writing the brief, run `megaplan init --idea-file` against it.",
    )

    brief_list_parser = brief_sub.add_parser("list", help="List briefs")
    brief_list_parser.add_argument("--json", action="store_true", help="Output as JSON")

    brief_epic_parser = brief_sub.add_parser(
        "epic", help="Create .megaplan/briefs/<epic>/chain.yaml plus milestone stubs"
    )
    brief_epic_parser.add_argument("slug", help="Epic slug")
    brief_epic_parser.add_argument(
        "--milestone",
        action="append",
        required=True,
        metavar="LABEL=TITLE",
        help="Milestone label and optional title. Repeat for each milestone.",
    )
    brief_epic_parser.add_argument("--base-branch", default="main")
    brief_epic_parser.add_argument("--force", action="store_true")

    brief_show_parser = brief_sub.add_parser("show", help="Show a single brief")
    brief_show_parser.add_argument("brief_id", help="Brief id, slug, or path")
    brief_show_parser.add_argument("--json", action="store_true", help="Output as JSON")

    brief_search_parser = brief_sub.add_parser("search", help="Search briefs")
    brief_search_parser.add_argument(
        "keywords",
        nargs="*",
        help="Keywords to match across id, title, body, tags, and epic.",
    )
    brief_search_parser.add_argument(
        "--all",
        dest="keywords_all",
        action="store_true",
        help="Require all keywords to match.",
    )
    brief_search_parser.add_argument(
        "--sort",
        choices=["path", "title", "length"],
        default="path",
        help="Sort key (default: path)",
    )
    brief_search_parser.add_argument(
        "--desc",
        action="store_true",
        help="Descending order (default: ascending)",
    )
    brief_search_parser.add_argument("--limit", type=int, default=None)
    brief_search_parser.add_argument("--json", action="store_true", help="Output as JSON")
    brief_search_parser.add_argument(
        "--no-snippet",
        dest="snippet",
        action="store_false",
        default=True,
        help="Hide snippet fields in JSON output",
    )

    # --- ticket subcommand group ---
    ticket_parser = subparsers.add_parser(
        "ticket", help="Manage repo-scoped issue/problem tickets"
    )
    ticket_sub = ticket_parser.add_subparsers(dest="ticket_action", required=True)

    # ticket new
    ticket_new_parser = ticket_sub.add_parser("new", help="Create a new ticket")
    ticket_new_parser.add_argument("title", help="Ticket title")
    ticket_new_body_group = ticket_new_parser.add_mutually_exclusive_group(
        required=True
    )
    ticket_new_body_group.add_argument(
        "-b", dest="body", default=None, metavar="BODY", help="Body text"
    )
    ticket_new_body_group.add_argument(
        "--edit", action="store_true", help="Open $EDITOR for body"
    )
    ticket_new_body_group.add_argument(
        "-", dest="stdin_body", action="store_true", help="Read body from stdin"
    )
    ticket_new_parser.add_argument("--tags", default=None, help="Comma-separated tags")
    ticket_new_parser.add_argument(
        "--project",
        default=None,
        help="Target project/repo for the new ticket; defaults to the current repo",
    )

    # ticket list
    ticket_list_parser = ticket_sub.add_parser("list", help="List tickets")
    ticket_list_parser.add_argument("--status", default=None, help="Filter by status")
    ticket_list_parser.add_argument(
        "--tags", default=None, help="Filter by tags (comma-separated)"
    )
    ticket_list_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # ticket show
    ticket_show_parser = ticket_sub.add_parser("show", help="Show a single ticket")
    ticket_show_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_show_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # ticket edit
    ticket_edit_parser = ticket_sub.add_parser("edit", help="Edit a ticket")
    ticket_edit_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_edit_parser.add_argument("--title", default=None, help="New title")
    ticket_edit_parser.add_argument("--body", default=None, help="New body")
    ticket_edit_parser.add_argument("--status", default=None, help="New status")
    ticket_edit_parser.add_argument("--add-tag", default=None, help="Tag to add")
    ticket_edit_parser.add_argument("--remove-tag", default=None, help="Tag to remove")

    # ticket link
    ticket_link_parser = ticket_sub.add_parser("link", help="Link a ticket to an epic")
    ticket_link_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_link_parser.add_argument("epic_id", help="Epic ID")
    ticket_link_parser.add_argument(
        "--resolves", action="store_true", help="Epic completion resolves this ticket"
    )

    # ticket unlink
    ticket_unlink_parser = ticket_sub.add_parser(
        "unlink", help="Unlink a ticket from an epic"
    )
    ticket_unlink_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_unlink_parser.add_argument("epic_id", help="Epic ID")

    # ticket addressed
    ticket_addressed_parser = ticket_sub.add_parser(
        "addressed", help="Mark ticket as addressed"
    )
    ticket_addressed_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_addressed_parser.add_argument("--note", default=None, help="Resolution note")

    # ticket dismiss
    ticket_dismiss_parser = ticket_sub.add_parser("dismiss", help="Dismiss a ticket")
    ticket_dismiss_parser.add_argument("ticket_id", help="Ticket ULID")
    ticket_dismiss_parser.add_argument(
        "--reason", default=None, help="Reason for dismissal"
    )

    # ticket reopen
    ticket_reopen_parser = ticket_sub.add_parser("reopen", help="Reopen a ticket")
    ticket_reopen_parser.add_argument("ticket_id", help="Ticket ULID")

    # ticket search
    ticket_search_parser = ticket_sub.add_parser(
        "search",
        help="Search tickets across local and cloud, multi-project, multi-keyword",
    )
    ticket_search_parser.add_argument(
        "keywords",
        nargs="*",
        help="Keywords to match (case-insensitive substring across title, body, tags, resolution_note). Default OR; pass --all for AND.",
    )
    ticket_search_parser.add_argument(
        "--all",
        dest="keywords_all",
        action="store_true",
        help="Require ALL keywords to match (AND). Default is OR (any).",
    )
    ticket_search_parser.add_argument(
        "--project",
        dest="projects",
        action="append",
        default=None,
        help="Repo to search — path, owner/name, or bare name. Repeatable.",
    )
    ticket_search_parser.add_argument(
        "--all-projects",
        action="store_true",
        help="Search every known repo (local) or every codebase (cloud).",
    )
    ticket_search_parser.add_argument("--status", default=None, help="Filter by status")
    ticket_search_parser.add_argument(
        "--tags", default=None, help="Filter by tags (comma-separated)"
    )
    ticket_search_parser.add_argument(
        "--sort",
        choices=["created", "edited", "length", "title"],
        default="created",
        help="Sort key (default: created)",
    )
    ticket_search_parser.add_argument(
        "--asc",
        action="store_true",
        help="Ascending order (default: descending)",
    )
    ticket_search_parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of results"
    )
    ticket_search_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    ticket_search_parser.add_argument(
        "--no-snippet",
        dest="snippet",
        action="store_false",
        default=True,
        help="Hide snippet column in human output",
    )

    migrate_local_parser = subparsers.add_parser(
        "migrate-local-plans", help="Import legacy ~/.megaplan/<project>/plans trees"
    )
    migrate_local_parser.add_argument("--source-home", default=str(Path.home()))
    migrate_local_parser.add_argument("--source-project", default=None)
    migrate_local_parser.add_argument("--all-projects", action="store_true")
    migrate_local_parser.add_argument("--project-dir", required=True)
    migrate_local_parser.add_argument(
        "--mode", choices=["orphan", "legacy-epic"], default="orphan"
    )
    migrate_local_parser.add_argument("--dry-run", action="store_true")

    for name in ["status", "progress", "watch"]:
        step_parser = subparsers.add_parser(name)
        step_parser.add_argument("--project-dir", default=None)
        step_parser.add_argument("--plan")
        if name == "status":
            step_parser.add_argument(
                "--pending-human",
                action="store_true",
                help="List plans awaiting human verification",
            )

    feedback_parser = subparsers.add_parser(
        "feedback",
        help="Scaffold, edit, or search external feedback.md for plans (per-stage 0-10 ratings + comments)",
    )
    feedback_parser.add_argument(
        "operation",
        nargs="?",
        default="edit",
        choices=["edit", "show", "search", "workflow"],
        help="edit (default): scaffold/open feedback.md. show: print parsed summary. search: query feedback across plans",
    )
    feedback_parser.add_argument(
        "--plan", required=False, help="Plan name (required for edit/show)"
    )
    feedback_parser.add_argument("--project-dir", default=None)
    feedback_parser.add_argument(
        "--no-edit",
        action="store_true",
        help="edit: just scaffold the template (if missing) and print the path; do not open $EDITOR",
    )
    feedback_parser.add_argument(
        "--force",
        action="store_true",
        help="workflow: re-run the AI rating pass even if feedback.md already has user fields. "
        "Overwrites ai_rating/ai_comment only; never touches user rating:/comment:.",
    )
    feedback_parser.add_argument(
        "--profile",
        default=None,
        help="search: substring match on plan profile (e.g. 'claude', 'apex')",
    )
    feedback_parser.add_argument(
        "--repo",
        default=None,
        help="search: substring match on plan project_dir / repo path",
    )
    feedback_parser.add_argument(
        "--min-rating",
        type=int,
        default=None,
        help="search: only show plans with Overall rating >= N",
    )
    feedback_parser.add_argument(
        "--max-rating",
        type=int,
        default=None,
        help="search: only show plans with Overall rating <= N",
    )
    feedback_parser.add_argument(
        "--stage",
        default=None,
        help="search: only show plans that have a rating for this stage",
    )
    feedback_parser.add_argument(
        "--has-comment",
        action="store_true",
        help="search: only show plans whose Overall comment is non-empty",
    )
    feedback_parser.add_argument(
        "--all",
        action="store_true",
        help="search: scan all megaplan project roots on this machine, not just the current tree",
    )
    feedback_parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="search: emit raw JSON instead of a table",
    )

    resume_parser = subparsers.add_parser(
        "resume", help="Resume a failed or blocked plan from its stored cursor"
    )
    resume_parser.add_argument("--plan", required=True)
    resume_parser.add_argument("--project-dir", default=None)
    resume_parser.add_argument(
        "--choice",
        default=None,
        help="For YAML pipelines paused at human_gate: the choice to resume with (e.g. continue, stop)",
    )

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--plan")
    audit_sub = audit_parser.add_subparsers(dest="audit_action", required=False)
    audit_query_parser = audit_sub.add_parser(
        "query", help="Query step receipts across plans"
    )
    audit_query_parser.add_argument("--model")
    audit_query_parser.add_argument("--phase")
    audit_query_parser.add_argument("--profile")
    audit_query_parser.add_argument("--since")
    audit_query_parser.add_argument("--agg", default="")
    audit_query_parser.add_argument("--json", action="store_true")
    audit_query_parser.add_argument("--audit-dir", default=None)
    audit_report_parser = audit_sub.add_parser("report", help="Render a plan retrospective from local audit artifacts")
    audit_report_parser.add_argument("--plan", help="Plan name. May also be passed before the report subcommand.")
    audit_report_parser.add_argument("--compare", help="Optional prior plan name to compare receipt totals against")
    audit_report_parser.add_argument("--output", help="Write Markdown report to this path instead of stdout")
    audit_report_parser.add_argument("--json-output", help="Write the structured report payload to this path")
    audit_report_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")

    for name in [
        "plan",
        "prep",
        "critique",
        "revise",
        "gate",
        "finalize",
        "execute",
        "review",
    ]:
        step_parser = subparsers.add_parser(name)
        step_parser.add_argument("--project-dir", default=None)
        step_parser.add_argument("--plan")
        step_parser.add_argument("--agent", choices=KNOWN_AGENTS)
        step_parser.add_argument(
            "--hermes",
            nargs="?",
            const="",
            default=None,
            help="Use Hermes agent for all phases. Optional: specify default model (e.g. --hermes anthropic/claude-sonnet-4.6)",
        )
        step_parser.add_argument(
            "--phase-model",
            action="append",
            default=[],
            help="Per-phase model override: --phase-model critique=hermes:openai/gpt-5",
        )
        step_parser.add_argument(
            "--profile",
            default=None,
            help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
        )
        _add_vendor_critic_args(step_parser)
        step_parser.add_argument("--fresh", action="store_true")
        step_parser.add_argument("--persist", action="store_true")
        step_parser.add_argument("--ephemeral", action="store_true")
        step_parser.add_argument(
            "--work-dir",
            default=None,
            help="Override the source-code working directory passed to subprocess workers "
            "(--add-dir / -C). Defaults to the current working directory. Use this to "
            "force a specific path (e.g. a git worktree) regardless of where the plan was created.",
        )
        if name == "prep":
            step_parser.add_argument(
                "--direction",
                dest="prep_direction",
                default=None,
                metavar="TEXT",
                help="Set or replace the prep direction (state.config.prep_direction) "
                "before the prep worker runs. Same semantics as `init --prep-direction`, "
                "but applied at prep time so you can steer prep without re-initializing.",
            )
        if name == "execute":
            step_parser.add_argument("--confirm-destructive", action="store_true")
            step_parser.add_argument("--user-approved", action="store_true")
            _add_execute_tier_cap_arg(step_parser)
            step_parser.add_argument(
                "--batch",
                type=int,
                default=None,
                help="Execute a specific global batch number (1-indexed)",
            )
            step_parser.add_argument(
                "--retry-blocked-tasks",
                action="store_true",
                help=(
                    "Reset any tasks persisted at status=blocked back to pending "
                    "before computing batches. Use when re-running execute after "
                    "resolving an external prerequisite that previously blocked a "
                    "task. The auto-driver passes this on every fresh invocation."
                ),
            )
            step_parser.add_argument(
                "--tier-drop",
                type=int,
                default=0,
                help=(
                    "Drop the per-batch tier-routed model by this many tiers for "
                    "this dispatch (only meaningful when a profile defines "
                    "tier_models.execute). The effective complexity used to look "
                    "up the tier map is max(floor, batch_complexity - tier_drop), "
                    "clamped at the premium floor (tier 3). The auto-driver raises "
                    "this automatically after repeated worker stalls so an "
                    "Opus-tier task that keeps stalling falls back to Sonnet "
                    "before the run halts for manual review (default 0)."
                ),
            )
        if name == "review":
            step_parser.add_argument("--confirm-self-review", action="store_true")

    config_parser = subparsers.add_parser(
        "config", help="View or edit megaplan configuration"
    )
    config_sub = config_parser.add_subparsers(dest="config_action", required=True)
    config_sub.add_parser("show")
    set_parser = config_sub.add_parser("set")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    config_sub.add_parser("reset")
    profiles_parser = config_sub.add_parser(
        "profiles",
        help="Inspect model profiles from built-in, user, and project layers",
    )
    profiles_sub = profiles_parser.add_subparsers(dest="profiles_action", required=True)
    profiles_sub.add_parser(
        "list",
        help="List profiles from all layers",
        description="List profiles from all layers. Project-layer profiles are only visible when run from that project directory.",
    )
    profiles_show_parser = profiles_sub.add_parser(
        "show", help="Show the fully resolved phase map for one profile"
    )
    profiles_show_parser.add_argument("name")
    use_profile_parser = config_sub.add_parser(
        "use-profile",
        help="Apply a profile as the user-config default agent routing (writes every agents.<phase>)",
        description=(
            "Apply a named profile from built-in/user/project layers as the persisted default "
            "agent routing in ~/.config/megaplan/config.json. Equivalent to running "
            "'config set agents.<phase> <agent>' for every phase in the profile, but accepts "
            "agent specs with model qualifiers (e.g. 'hermes:glm-5.1') the same way profiles do."
        ),
    )
    use_profile_parser.add_argument(
        "name", help="Profile name (see 'megaplan config profiles list')"
    )

    step_parser = subparsers.add_parser(
        "step", help="Edit plan step sections without hand-editing markdown"
    )
    step_subparsers = step_parser.add_subparsers(dest="step_action", required=True)

    step_add_parser = step_subparsers.add_parser(
        "add", help="Insert a new step after an existing step"
    )
    step_add_parser.add_argument("--plan")
    step_add_parser.add_argument("--after")
    step_add_parser.add_argument("description")

    step_remove_parser = step_subparsers.add_parser(
        "remove", help="Remove a step and renumber the plan"
    )
    step_remove_parser.add_argument("--plan")
    step_remove_parser.add_argument("step_id")

    step_move_parser = step_subparsers.add_parser(
        "move", help="Move a step after another step and renumber"
    )
    step_move_parser.add_argument("--plan")
    step_move_parser.add_argument("step_id")
    step_move_parser.add_argument("--after", required=True)

    override_parser = subparsers.add_parser("override")
    override_parser.add_argument(
        "override_action",
        choices=[
            "abort",
            "force-proceed",
            "add-note",
            "replan",
            "recover-blocked",
            "set-robustness",
            "set-profile",
            "set-model",
            "set-vendor",
        ],
    )
    override_parser.add_argument("--plan")
    override_parser.add_argument("--project-dir", default=None)
    override_parser.add_argument("--reason", default="")
    override_parser.add_argument("--note")
    override_parser.add_argument(
        "--robustness", choices=list(ROBUSTNESS_ACCEPTED), default=None
    )
    override_parser.add_argument("--profile", default=None)
    override_parser.add_argument("--phase", default=None)
    override_parser.add_argument("--model", default=None)
    override_parser.add_argument("--effort", default=None)
    override_parser.add_argument(
        "--vendor",
        default=None,
        help="(set-vendor) Target premium vendor for the phase: claude or codex.",
    )
    # strict-notes plumbing. Only meaningful for specific override_action values, but
    # the override parser is flat (single positional + flags), so the flags live here.
    override_parser.add_argument(
        "--source",
        choices=["user", "driver"],
        default="user",
        help="(add-note) Note source. Driver-attached notes don't block strict-notes force-proceed.",
    )
    override_parser.add_argument(
        "--user-approved",
        action="store_true",
        help="(force-proceed) Acknowledge a strict-notes ESCALATE before forcing proceed.",
    )

    user_action_parser = subparsers.add_parser(
        "user-action",
        help="Resolve user action prerequisites",
    )
    ua_subparsers = user_action_parser.add_subparsers(
        dest="user_action_action", required=True
    )

    from megaplan.user_actions import VALID_RESOLUTIONS as _UA_VALID_RESOLUTIONS

    ua_resolve_parser = ua_subparsers.add_parser(
        "resolve",
        help="Record a resolution for a user action prerequisite",
    )
    ua_resolve_parser.add_argument("--plan")
    ua_resolve_parser.add_argument(
        "--action-id",
        required=True,
        help="User action ID (from finalize.json)",
    )
    ua_resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=list(_UA_VALID_RESOLUTIONS),
        help="Resolution to record",
    )
    ua_resolve_parser.add_argument(
        "--fallback-mode",
        default=None,
        help="Fallback execution mode (for accepted_blocked / waived)",
    )
    ua_resolve_parser.add_argument(
        "--tasks",
        default=None,
        help="Comma-separated task IDs this resolution applies to",
    )
    ua_resolve_parser.add_argument(
        "--instructions",
        default=None,
        help="Fallback instructions for the executor",
    )
    ua_resolve_parser.add_argument(
        "--reason",
        default=None,
        help="Human-readable reason for the resolution",
    )
    ua_resolve_parser.add_argument(
        "--phase",
        default=None,
        help="Phase where this resolution was recorded",
    )
    ua_resolve_parser.add_argument(
        "--evidence",
        action="append",
        default=None,
        help="Evidence for the resolution; repeat or comma-separate values",
    )
    ua_resolve_parser.add_argument(
        "--debt-note",
        default=None,
        help="Debt note to carry with the resolution",
    )

    quality_gate_parser = subparsers.add_parser(
        "quality-gate",
        help="Resolve quality gate blockers",
    )
    qg_subparsers = quality_gate_parser.add_subparsers(
        dest="quality_gate_action", required=True
    )
    qg_resolve_parser = qg_subparsers.add_parser(
        "resolve",
        help="Record a resolution for a quality gate blocker",
    )
    qg_resolve_parser.add_argument("--plan")
    qg_resolve_parser.add_argument(
        "--blocker-id",
        required=True,
        help="Quality blocker ID from phase_result/status output",
    )
    qg_resolve_parser.add_argument(
        "--resolution",
        required=True,
        choices=list(QUALITY_VALID_RESOLUTIONS),
        help="Resolution to record",
    )
    qg_resolve_parser.add_argument(
        "--phase",
        default=None,
        help="Phase where this resolution was recorded",
    )
    qg_resolve_parser.add_argument(
        "--evidence",
        action="append",
        default=None,
        help="Evidence for the resolution; repeat or comma-separate values",
    )
    qg_resolve_parser.add_argument(
        "--debt-note",
        default=None,
        help="Debt note for accepted_with_debt resolutions",
    )
    qg_resolve_parser.add_argument(
        "--fallback-mode",
        default=None,
        help="Fallback execution mode associated with this quality resolution",
    )

    verify_human_parser = subparsers.add_parser(
        "verify-human", help="Record human verification for a criterion"
    )
    verify_human_parser.add_argument("--plan")
    verify_human_parser.add_argument(
        "--criterion", required=False, default=None, help="Criterion name or index"
    )
    vh_group = verify_human_parser.add_mutually_exclusive_group(required=False)
    vh_group.add_argument("--pass", dest="pass_flag", action="store_true")
    vh_group.add_argument("--fail", dest="fail_flag", action="store_true")
    verify_human_parser.add_argument(
        "--evidence", required=False, default=None, help="Evidence supporting the verdict"
    )
    verify_human_parser.add_argument(
        "--list", dest="list_flag", action="store_true", help="List verification status for all criteria"
    )
    verify_human_parser.add_argument(
        "--json", dest="json_flag", action="store_true", help="Output machine-readable JSON"
    )

    audit_verifiability_parser = subparsers.add_parser(
        "audit-verifiability", help="Audit criteria verifiability"
    )
    audit_verifiability_parser.add_argument("--plan")

    debt_parser = subparsers.add_parser(
        "debt", help="Inspect or manage persistent tech debt entries"
    )
    debt_subparsers = debt_parser.add_subparsers(dest="debt_action", required=True)

    debt_list_parser = debt_subparsers.add_parser("list", help="List debt entries")
    debt_list_parser.add_argument(
        "--all", action="store_true", help="Include resolved entries"
    )

    debt_add_parser = debt_subparsers.add_parser(
        "add", help="Add or increment a debt entry"
    )
    debt_add_parser.add_argument("--subsystem", required=True)
    debt_add_parser.add_argument("--concern", required=True)
    debt_add_parser.add_argument("--flag-ids", default="")
    debt_add_parser.add_argument("--plan")

    debt_resolve_parser = debt_subparsers.add_parser(
        "resolve", help="Resolve a debt entry"
    )
    debt_resolve_parser.add_argument("debt_id")
    debt_resolve_parser.add_argument("--plan")

    loop_init_parser = subparsers.add_parser(
        "loop-init", help="Initialize a MegaLoop workflow"
    )
    loop_init_parser.add_argument("--project-dir", required=True)
    loop_init_parser.add_argument("--command", required=True)
    loop_init_parser.add_argument("--goal", dest="goal_option")
    loop_init_parser.add_argument("--name")
    loop_init_parser.add_argument("--iterations", type=int, default=3)
    loop_init_parser.add_argument("--time-budget", type=int, default=300)
    loop_init_parser.add_argument("--observe-interval", type=int)
    loop_init_parser.add_argument("--observe-break-patterns")
    loop_init_parser.add_argument("--agent", choices=KNOWN_AGENTS)
    loop_init_parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent for loop phases. Optional: specify default model",
    )
    loop_init_parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-phase model override: --phase-model loop_execute=hermes:openai/gpt-5",
    )
    loop_init_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(loop_init_parser)
    loop_init_parser.add_argument("--fresh", action="store_true")
    loop_init_parser.add_argument("--persist", action="store_true")
    loop_init_parser.add_argument("--ephemeral", action="store_true")
    loop_init_parser.add_argument(
        "--work-dir",
        default=None,
        help="Override the source-code working directory for subprocess workers (default: CWD)",
    )
    loop_init_parser.add_argument("goal", nargs="?")

    loop_run_parser = subparsers.add_parser(
        "loop-run", help="Run an existing MegaLoop workflow"
    )
    loop_run_parser.add_argument("name")
    loop_run_parser.add_argument("--project-dir")
    loop_run_parser.add_argument("--iterations", type=int)
    loop_run_parser.add_argument("--time-budget", type=int)
    loop_run_parser.add_argument("--agent", choices=KNOWN_AGENTS)
    loop_run_parser.add_argument(
        "--hermes",
        nargs="?",
        const="",
        default=None,
        help="Use Hermes agent for loop phases. Optional: specify default model",
    )
    loop_run_parser.add_argument(
        "--phase-model",
        action="append",
        default=[],
        help="Per-phase model override: --phase-model loop_execute=hermes:openai/gpt-5",
    )
    loop_run_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(loop_run_parser)
    loop_run_parser.add_argument("--fresh", action="store_true")
    loop_run_parser.add_argument("--persist", action="store_true")
    loop_run_parser.add_argument("--ephemeral", action="store_true")
    loop_run_parser.add_argument(
        "--work-dir",
        default=None,
        help="Override the source-code working directory for subprocess workers (default: CWD)",
    )

    loop_status_parser = subparsers.add_parser(
        "loop-status", help="Show MegaLoop state"
    )
    loop_status_parser.add_argument("name")
    loop_status_parser.add_argument("--project-dir")

    loop_pause_parser = subparsers.add_parser(
        "loop-pause", help="Pause a MegaLoop workflow"
    )
    loop_pause_parser.add_argument("name")
    loop_pause_parser.add_argument("--project-dir")
    loop_pause_parser.add_argument("--reason", default="")

    from megaplan.auto import build_auto_parser

    build_auto_parser(subparsers)

    from megaplan._pipeline.run_cli import build_run_parser

    build_run_parser(subparsers)

    from megaplan.chain import build_chain_parser

    build_chain_parser(subparsers)

    cloud_parser = subparsers.add_parser(
        "cloud",
        add_help=False,
        help="Manage provider-backed megaplan cloud runners",
    )
    cloud_parser.add_argument("cloud_args", nargs=argparse.REMAINDER)

    resident_parser = subparsers.add_parser(
        "resident",
        add_help=False,
        help="Run resident Discord orchestration services",
    )
    resident_parser.add_argument("resident_args", nargs=argparse.REMAINDER)

    bakeoff_parser = subparsers.add_parser(
        "bakeoff",
        add_help=False,
        help="Run concurrent multi-profile bake-offs",
    )
    bakeoff_parser.add_argument("bakeoff_args", nargs=argparse.REMAINDER)

    from megaplan.prompts.tiebreaker_orchestrator import build_tiebreaker_parser

    build_tiebreaker_parser(subparsers)

    # tiebreaker-run is a top-level command because auto.py:_phase_command
    # translates next_step directly to CLI args.
    tb_run_parser = subparsers.add_parser(
        "tiebreaker-run",
        help="Run tiebreaker researcher+challenger (used by auto driver)",
    )
    tb_run_parser.add_argument("--plan", required=True, help="Plan name")
    tb_run_parser.add_argument("--agent", choices=KNOWN_AGENTS, default=None)
    tb_run_parser.add_argument("--hermes", nargs="?", const="", default=None)
    tb_run_parser.add_argument("--phase-model", action="append", default=[])
    tb_run_parser.add_argument(
        "--profile",
        default=None,
        help="Named preset from profiles.toml; see 'megaplan config profiles list'.",
    )
    _add_vendor_critic_args(tb_run_parser)
    tb_run_parser.add_argument("--fresh", action="store_true")
    tb_run_parser.add_argument("--persist", action="store_true")
    tb_run_parser.add_argument("--ephemeral", action="store_true")
    tb_run_parser.add_argument(
        "--work-dir",
        default=None,
        help="Override the source-code working directory for subprocess workers (default: CWD)",
    )

    introspect_parser = subparsers.add_parser(
        "introspect",
        help="Structured JSON snapshot of a plan's live state",
    )
    introspect_parser.add_argument("--plan", required=True, help="Plan name")

    cost_parser = subparsers.add_parser(
        "cost",
        help="Token usage and cost breakdown for a plan",
    )
    cost_parser.add_argument("--plan", required=True, help="Plan name")
    cost_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    cost_parser.add_argument(
        "--by-phase",
        action="store_true",
        default=False,
        help="Break down cost and tokens by phase",
    )

    trace_parser = subparsers.add_parser(
        "trace",
        help="Event stream over a plan's events.ndjson",
    )
    trace_parser.add_argument("--plan", required=True, help="Plan name")
    trace_parser.add_argument("--phase", default=None, help="Filter events to this phase")
    trace_parser.add_argument(
        "--since",
        default=None,
        help="Only show events within this duration (e.g. 30s, 5m, 1h)",
    )
    trace_parser.add_argument(
        "--follow",
        action="store_true",
        default=False,
        help="Poll for new events (1Hz, no inotify)",
    )
    trace_parser.add_argument(
        "--format",
        choices=["json", "pretty", "narrative"],
        default="pretty",
        help="Output format (default: pretty)",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnostic: plan-level, repo-level, or adaptive-critique health checks",
    )
    doctor_group = doctor_parser.add_mutually_exclusive_group(required=True)
    doctor_group.add_argument("--plan", default=None, help="Plan name to check")
    doctor_group.add_argument("--repo", action="store_true", default=False, help="Check the repo")
    doctor_group.add_argument(
        "--adaptive-critique",
        action="store_true",
        default=False,
        help=(
            "Probe every load-bearing piece of the adaptive critique path "
            "(step schema, schema dict entry, prompt template, required-keys "
            "table). Exits non-zero if any probe fails."
        ),
    )

    record_tag_parser = subparsers.add_parser(
        "record-tag",
        help="Write a named note into a plan's events.ndjson",
    )
    record_tag_parser.add_argument("--plan", required=True, help="Plan name")
    record_tag_parser.add_argument("--tag", required=True, help="Tag name")
    record_tag_parser.add_argument("--note", default="", help="Optional tag note")

    return parser
