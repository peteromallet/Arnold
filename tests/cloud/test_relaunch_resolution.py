from arnold_pipelines.megaplan.cloud.relaunch_resolution import (
    _rejects_foreign_runtime_path,
    is_stale_marker_relaunch_command,
    marker_relaunch_command,
)


def test_all_paths_share_byte_identical_marker_admission() -> None:
    marker = {
        "relaunch_command": "if true; then python -m arnold_pipelines.megaplan chain start; fi"
    }
    assert marker_relaunch_command(marker) == marker["relaunch_command"]
    assert marker_relaunch_command(marker) == marker_relaunch_command(dict(marker))


def test_cutover_stale_marker_is_rejected_for_regeneration() -> None:
    stale = "{ set -e; git pull origin main; pip install -e /workspace/old; }"
    assert is_stale_marker_relaunch_command(stale)
    assert marker_relaunch_command({"relaunch_command": stale}) is None


_SHARED_ROOT_PYTHONPATH_COMMANDS = (
    # The residual builder-selection shape named by the G5 finding.
    "PYTHONPATH=/workspace/arnold:${PYTHONPATH:-} python -P -m arnold_pipelines.megaplan chain start",
    "PYTHONPATH=/workspace/arnold python -P -m arnold_pipelines.megaplan chain start",
    "PYTHONPATH=${PYTHONPATH:-}:/workspace/arnold python -P -m arnold_pipelines.megaplan chain start",
    'PYTHONPATH="/workspace/arnold:${PYTHONPATH:-}" python -P -m arnold_pipelines.megaplan chain start',
    "export PYTHONPATH=/workspace/arnold:${PYTHONPATH:-}; python -P -m arnold_pipelines.megaplan chain start",
    "PYTHONPATH=/workspace/arnold/arnold_pipelines:${PYTHONPATH:-} python -P -m arnold_pipelines.megaplan chain start",
    "cd /workspace/demo/Arnold && PYTHONPATH=/workspace/arnold:${PYTHONPATH:-} python -P -m arnold_pipelines.megaplan chain start",
)


def test_shared_root_pythonpath_marker_is_rejected_for_regeneration() -> None:
    """G5 round-2 finding 2: a persisted command whose PYTHONPATH names the
    shared /workspace/arnold checkout must be blacklisted (never returned).
    """
    for command in _SHARED_ROOT_PYTHONPATH_COMMANDS:
        assert is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) is None, command


def test_per_epic_pythonpath_marker_is_not_blacklisted() -> None:
    """/workspace/arnold-epics/... is a legitimate per-epic manifest root, not
    the shared checkout — a persisted command naming it stays admissible.
    """
    command = (
        "PYTHONPATH=/workspace/arnold-epics/epic-a:${PYTHONPATH:-} "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert not is_stale_marker_relaunch_command(command)
    assert marker_relaunch_command({"relaunch_command": command}) == command


def test_manifest_root_pythonpath_marker_is_still_returned() -> None:
    """A persisted command naming a per-epic manifest runtime root on
    PYTHONPATH is not blacklisted and is returned unchanged.
    """
    command = (
        "PYTHONPATH=/workspace/runtime-candidates/arnold-new:${PYTHONPATH:-} "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert not is_stale_marker_relaunch_command(command)
    assert marker_relaunch_command({"relaunch_command": command}) == command


_SHARED_ROOT_CD_COMMANDS = (
    # The residual builder-selection shape named by the G5 round-5 finding.
    "cd /workspace/arnold && python -P -m arnold_pipelines.megaplan chain start",
    # Exact, mid-command, subtree, trailing-slash, quoted (both styles),
    # exported, and brace-wrapped cd components into the shared checkout.
    "cd /workspace/arnold",
    "python -P -m arnold_pipelines.megaplan chain start && cd /workspace/arnold",
    "cd /workspace/arnold/arnold_pipelines && python -P -m arnold_pipelines.megaplan chain start",
    "cd /workspace/arnold/ && python -P -m arnold_pipelines.megaplan chain start",
    'cd "/workspace/arnold" && python -P -m arnold_pipelines.megaplan chain start',
    "cd '/workspace/arnold' && python -P -m arnold_pipelines.megaplan chain start",
    "export SRC=/workspace/arnold; cd /workspace/arnold && python -P -m arnold_pipelines.megaplan chain start",
    "{ cd /workspace/arnold && exec python -P -m arnold_pipelines.megaplan chain start; }",
)


def test_shared_root_cd_marker_is_rejected_for_regeneration() -> None:
    """G5 round-5 finding 2: a persisted command that cds into the shared
    /workspace/arnold checkout re-selects it exactly as a PYTHONPATH
    assignment would and must be blacklisted (never returned).
    """
    for command in _SHARED_ROOT_CD_COMMANDS:
        assert is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) is None, command


def test_per_epic_cd_marker_is_not_blacklisted() -> None:
    """/workspace/arnold-epics/... is a legitimate per-epic manifest root, not
    the shared checkout — a persisted command that cds into it stays
    admissible.
    """
    command = (
        "cd /workspace/arnold-epics/epic-a && "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert not is_stale_marker_relaunch_command(command)
    assert marker_relaunch_command({"relaunch_command": command}) == command


_SHARED_ROOT_INVOCATION_COMMANDS = (
    # G5 round-10 finding 2: the residual builder-selection shapes — a bare
    # or env-prefixed invocation of a python/binary under the shared
    # checkout, a /workspace/arnold/arnold_pipelines/... path component, or
    # any /workspace/arnold path used as an executable/script argument.
    "/workspace/arnold/bin/python -P -m arnold_pipelines.megaplan chain start",
    "/workspace/arnold/python -P -m arnold_pipelines.megaplan chain start",
    "cd /tmp && /workspace/arnold/bin/python -P -m arnold_pipelines.megaplan chain start",
    "env ARNOLD_SRC=/workspace/arnold /workspace/arnold/bin/python -P -m arnold_pipelines.megaplan chain start",
    "env -i PATH=/usr/bin:/bin /workspace/arnold/venv/bin/python -P -m arnold_pipelines.megaplan chain start",
    "ARNOLD_SRC=/workspace/arnold exec /workspace/arnold/bin/python -P -m arnold_pipelines.megaplan chain start",
    "PATH=/workspace/arnold/bin:$PATH python -P -m arnold_pipelines.megaplan chain start",
    "python -P /workspace/arnold/arnold_pipelines/megaplan/chain/start.py --spec chain.yaml",
    "python -P -m arnold_pipelines.megaplan chain start /workspace/arnold/arnold_pipelines/x.py",
    "exec /workspace/arnold/bin/arnold-chain --spec chain.yaml",
    "/workspace/arnold/bin/bash -lc 'python -P -m arnold_pipelines.megaplan chain start'",
    '"/workspace/arnold/bin/python" -P -m arnold_pipelines.megaplan chain start',
    "python -P -m arnold_pipelines.megaplan chain start --project-dir /workspace/arnold",
)


def test_shared_root_invocation_marker_is_rejected_for_regeneration() -> None:
    """G5 round-10 finding 2: a persisted command that invokes a
    python/binary under the shared /workspace/arnold checkout — bare,
    env-prefixed, exec'd, quoted, or as a script argument — re-selects the
    shared root exactly as a PYTHONPATH assignment would and must be
    blacklisted (never returned).
    """
    for command in _SHARED_ROOT_INVOCATION_COMMANDS:
        assert is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) is None, command


def test_per_epic_invocation_marker_is_not_blacklisted() -> None:
    """/workspace/arnold-epics/... is a legitimate per-epic manifest root, not
    the shared checkout — a persisted command invoking its own python/binary
    (bare, env-prefixed, or as a script argument) stays admissible.
    """
    for command in (
        "/workspace/arnold-epics/epic-a/bin/python -P -m arnold_pipelines.megaplan chain start",
        "env ARNOLD_EPIC_ROOT=/workspace/arnold-epics/epic-a /workspace/arnold-epics/epic-a/venv/bin/python -P -m arnold_pipelines.megaplan chain start",
        "python -P /workspace/arnold-epics/epic-a/arnold_pipelines/megaplan/chain/start.py --spec chain.yaml",
        "cd /tmp && /workspace/arnold-epics/epic-a/bin/python -P -m arnold_pipelines.megaplan chain start",
    ):
        assert not is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) == command, command


_SHARED_ROOT_PARAM_EXPANSION_COMMANDS = (
    # G5 round-11 finding 2: shell parameter expansion can smuggle the shared
    # root past token-boundary admission — the operator characters ('-', '+',
    # '?', '#', '%', '/') are not command boundaries, so the shared checkout
    # inside ${VAR:-...}, ${VAR:=...}, ${VAR:+...}, or any other ${...}
    # construct goes undetected by the earlier checks.  A neutral variable
    # name isolates the expansion mechanism from the round-11 finding-3
    # retired-selector-var rejection (one canonical ${MEGAPLAN_RUNTIME_SRC:-}
    # example is kept since it is the shape the finding names).
    "${MEGAPLAN_RUNTIME_SRC:-/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
    "CHAIN_RUNTIME=${CHAIN_RUNTIME:-/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
    "CHAIN_RUNTIME=${CHAIN_RUNTIME:=/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
    "CHAIN_RUNTIME=${CHAIN_RUNTIME:+/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
    "cd ${CHAIN_RUNTIME:-/workspace/arnold} && python -P -m arnold_pipelines.megaplan chain start",
    "${CHAIN_RUNTIME:+/workspace/arnold}/bin/python -P -m arnold_pipelines.megaplan chain start",
    "export SRC=${CHAIN_RUNTIME:-/workspace/arnold}; exec $SRC/bin/python -P -m arnold_pipelines.megaplan chain start",
    "PYTHONPATH=${PYTHONPATH:+${PYTHONPATH}:/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
    "python -P -m arnold_pipelines.megaplan chain start --project-dir ${CHAIN_RUNTIME:-/workspace/arnold}",
    "${CHAIN_RUNTIME#/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
    "${CHAIN_RUNTIME%*/workspace/arnold} python -P -m arnold_pipelines.megaplan chain start",
)


def test_shared_root_param_expansion_marker_is_rejected_for_regeneration() -> None:
    """G5 round-11 finding 2: a persisted command carrying the shared root
    inside a shell parameter-expansion default/alternate (${VAR:-...},
    ${VAR:=...}, ${VAR:+...}, or any other ${...} construct) re-selects the
    shared checkout once expanded and must be blacklisted (never returned).
    """
    for command in _SHARED_ROOT_PARAM_EXPANSION_COMMANDS:
        assert is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) is None, command


def test_per_epic_param_expansion_marker_is_not_blacklisted() -> None:
    """/workspace/arnold-epics/... inside a parameter expansion is a
    legitimate per-epic manifest root, not the shared checkout — a persisted
    command naming it stays admissible.
    """
    for command in (
        "CHAIN_RUNTIME=${CHAIN_RUNTIME:-/workspace/arnold-epics/epic-a} python -P -m arnold_pipelines.megaplan chain start",
        "cd ${CHAIN_RUNTIME:=/workspace/arnold-epics/epic-a} && python -P -m arnold_pipelines.megaplan chain start",
        "PYTHONPATH=${PYTHONPATH:+${PYTHONPATH}:/workspace/arnold-epics/epic-a} python -P -m arnold_pipelines.megaplan chain start",
    ):
        assert not is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) == command, command


_RETIRED_SELECTOR_VAR_COMMANDS = (
    # G5 round-11 finding 3: persisted commands referencing a RETIRED runtime
    # selector variable — bare $VAR or braced ${VAR...} — select a runtime the
    # same way a literal shared-root path does and must be regenerated from the
    # accepted root, never returned verbatim.
    "exec $MEGAPLAN_RUNTIME_SRC/bin/python -P -m arnold_pipelines.megaplan chain start",
    'exec "$MEGAPLAN_RUNTIME_SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'exec "${MEGAPLAN_RUNTIME_SRC}/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'SRC="$MEGAPLAN_RUNTIME_SRC" exec "$SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'PYTHONPATH="$MEGAPLAN_RUNTIME_SRC:${PYTHONPATH:-}" exec "$MEGAPLAN_RUNTIME_SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'cd "$MEGAPLAN_LAUNCH_RUNTIME_SRC" && exec "$MEGAPLAN_LAUNCH_RUNTIME_SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'exec "$MEGAPLAN_SUPERVISOR_SOURCE/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'export ARNOLD_REPAIR_RUNTIME_SRC="${ARNOLD_REPAIR_RUNTIME_SRC:-/workspace/runtime-candidates/arnold-new}"; exec "$ARNOLD_REPAIR_RUNTIME_SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'PYTHONPATH="${MEGAPLAN_DISCOVER_ARNOLD_SRC:-/workspace/runtime-candidates/arnold-new}:${PYTHONPATH:-}" python -P -m arnold_pipelines.megaplan chain start',
    'export KIMI_GOAL_ARNOLD_SRC="${KIMI_GOAL_ARNOLD_SRC:-/workspace/runtime-candidates/arnold-new}"; exec "$KIMI_GOAL_ARNOLD_SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    # Retired branch selectors (*_SYNC_BRANCH) choose the sync/push target.
    'export CLOUD_WATCHDOG_SYNC_BRANCH="${CLOUD_WATCHDOG_SYNC_BRANCH:-main}"; exec "$MEGAPLAN_RUNTIME_SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
    'export KIMI_GOAL_SYNC_BRANCH="$KIMI_GOAL_SYNC_BRANCH"',
    'export MEGAPLAN_META_SYNC_BRANCH="${MEGAPLAN_META_SYNC_BRANCH:-main}"',
)


def test_retired_selector_var_marker_is_rejected_for_regeneration() -> None:
    """G5 round-11 finding 3: a persisted command referencing any retired
    runtime selector variable ($VAR or ${VAR...}) re-selects a runtime the
    same way a literal shared-root path would and must be blacklisted (never
    returned verbatim).
    """
    for command in _RETIRED_SELECTOR_VAR_COMMANDS:
        assert is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) is None, command


def test_non_selector_var_marker_is_not_blacklisted() -> None:
    """A persisted command referencing ordinary (non-retired) variables — $SRC
    / ${SRC:-...} naming a per-epic manifest root, ${PYTHONPATH:-} merging, or
    the manifest-derived plain SYNC_BRANCH — is not a runtime selector and
    stays admissible.
    """
    for command in (
        'SRC=/workspace/runtime-candidates/arnold-new exec "$SRC/bin/python" -P -m arnold_pipelines.megaplan chain start',
        'PYTHONPATH="${SRC:-/workspace/runtime-candidates/arnold-new}:${PYTHONPATH:-}" exec "${SRC:-/workspace/runtime-candidates/arnold-new}/bin/python" -P -m arnold_pipelines.megaplan chain start',
        'SYNC_BRANCH="main" exec python -P -m arnold_pipelines.megaplan chain start',
    ):
        assert not is_stale_marker_relaunch_command(command), command
        assert marker_relaunch_command({"relaunch_command": command}) == command, command


def test_content_addressed_marker_rejects_command_for_previous_runtime() -> None:
    marker = {
        "runtime_binding": {
            "current_identity": {
                "import_root": "/workspace/runtime-candidates/arnold-new",
                "source_revision": "b" * 40,
            }
        },
        "relaunch_command": (
            "SRC=/workspace/runtime-candidates/arnold-old\n"
            + 'test "$(git -C "$SRC" rev-parse HEAD)" = '
            + "a" * 40
            + "\nexec $SRC/bin/python -m arnold_pipelines.megaplan chain start"
        ),
    }
    assert marker_relaunch_command(marker) is None

    marker["relaunch_command"] = (
        "SRC=/workspace/runtime-candidates/arnold-new\n"
        + 'test "$(git -C "$SRC" rev-parse HEAD)" = '
        + "b" * 40
        + "\nexec $SRC/bin/python -m arnold_pipelines.megaplan chain start"
    )
    assert marker_relaunch_command(marker) == marker["relaunch_command"]


_ACCEPTED_ROOT = "/workspace/runtime-candidates/arnold-new"
_OTHER_PER_EPIC_ROOT = "/workspace/runtime-candidates/arnold-old"


def test_per_epic_path_other_than_accepted_root_is_rejected() -> None:
    """G5 round-14 finding 1: the predicate only blacklisted shared-root /
    retired-selector text, so a persisted command naming a DIFFERENT
    per-epic runtime (``arnold-old`` while the accepted root is
    ``arnold-new``) passed and was returned verbatim.  With the accepted
    root supplied, any runtime-path reference (cd / PYTHONPATH / executable
    / script arg / env assignment / ${...} default) that is not the
    accepted root marks the command stale so it is regenerated.
    """
    for command in (
        f"cd {_OTHER_PER_EPIC_ROOT} && python -P -m arnold_pipelines.megaplan chain start",
        f"PYTHONPATH={_OTHER_PER_EPIC_ROOT}:${{PYTHONPATH:-}} python -P -m arnold_pipelines.megaplan chain start",
        f"export PYTHONPATH={_OTHER_PER_EPIC_ROOT}; python -P -m arnold_pipelines.megaplan chain start",
        f"{_OTHER_PER_EPIC_ROOT}/bin/python -P -m arnold_pipelines.megaplan chain start",
        f"env ARNOLD_EPIC_ROOT={_OTHER_PER_EPIC_ROOT} {_OTHER_PER_EPIC_ROOT}/venv/bin/python -P -m arnold_pipelines.megaplan chain start",
        f"CHAIN_RUNTIME=${{CHAIN_RUNTIME:-{_OTHER_PER_EPIC_ROOT}}} python -P -m arnold_pipelines.megaplan chain start",
        f"SRC={_OTHER_PER_EPIC_ROOT}; exec $SRC/bin/python -m arnold_pipelines.megaplan chain start",
        f"python -P {_OTHER_PER_EPIC_ROOT}/arnold_pipelines/megaplan/chain/start.py --spec chain.yaml",
        f"cd {_OTHER_PER_EPIC_ROOT}/arnold_pipelines && python -P -m arnold_pipelines.megaplan chain start",
    ):
        assert is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT), command
        assert (
            marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) is None
        ), command


def test_accepted_root_runtime_path_references_are_preserved() -> None:
    """G5 round-14 finding 1: a persisted command whose runtime-path
    references are the accepted root (or a subpath of it) stays admissible
    and is returned unchanged.  Non-runtime path positions (--project-dir,
    redirects) are not runtime references.
    """
    for command in (
        f"cd {_ACCEPTED_ROOT} && python -P -m arnold_pipelines.megaplan chain start",
        f"PYTHONPATH={_ACCEPTED_ROOT} python -P -m arnold_pipelines.megaplan chain start",
        f"PYTHONPATH={_ACCEPTED_ROOT}:${{PYTHONPATH:-}} python -P -m arnold_pipelines.megaplan chain start",
        f"{_ACCEPTED_ROOT}/bin/python -P -m arnold_pipelines.megaplan chain start",
        f"CHAIN_RUNTIME=${{CHAIN_RUNTIME:-{_ACCEPTED_ROOT}}} python -P -m arnold_pipelines.megaplan chain start",
        f"SRC={_ACCEPTED_ROOT}; exec $SRC/bin/python -m arnold_pipelines.megaplan chain start",
        f"python -P {_ACCEPTED_ROOT}/arnold_pipelines/megaplan/chain/start.py --spec chain.yaml",
        # --project-dir is a workspace path, not a runtime reference.
        f"cd {_ACCEPTED_ROOT} && python -P -m arnold_pipelines.megaplan chain start --project-dir /workspace/demo",
    ):
        assert not is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT), command
        assert (
            marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) == command
        ), command


def test_no_runtime_path_reference_stays_admissible_with_accepted_root() -> None:
    """G5 round-14 finding 1: a pure `chain start` style command carries no
    runtime-path reference and stays admissible even with an accepted root
    supplied.  A bare variable reference (``cd \"$SRC\"``) is not a literal
    runtime path and stays admissible (the retired-selector check still
    rejects the known selector names).
    """
    for command in (
        "python -P -m arnold_pipelines.megaplan chain start",
        "if true; then python -m arnold_pipelines.megaplan chain start; fi",
        'cd "$SRC" && exec "$SRC/bin/python" -m arnold_pipelines.megaplan chain start',
    ):
        assert not is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT), command
        assert (
            marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) == command
        ), command


def test_no_accepted_root_keeps_per_epic_path_admissible() -> None:
    """G5 round-14 finding 1: without an accepted root the path comparison
    cannot run — the module-level (non-wrapper) callers that do not know
    the accepted root keep the pre-existing blacklist behavior, and a
    per-epic path that is not the shared root stays admissible there.
    """
    command = (
        f"PYTHONPATH={_OTHER_PER_EPIC_ROOT}:${{PYTHONPATH:-}} "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert not is_stale_marker_relaunch_command(command)
    assert marker_relaunch_command({"relaunch_command": command}) == command
    # The same command with the accepted root supplied is rejected.
    assert is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT)


_FOREIGN_CANDIDATE_ROOT = "/workspace/runtime-candidates/arnold-OTHER"


def test_foreign_runtime_candidate_on_pythonpath_is_rejected() -> None:
    """G7 negative: a persisted command selecting a DIFFERENT runtime
    candidate (``arnold-OTHER`` while the accepted root is ``arnold-new``)
    on PYTHONPATH is a foreign runtime selection — with the accepted root
    supplied it is stale and regenerated, never returned verbatim.
    """
    command = (
        f"PYTHONPATH={_FOREIGN_CANDIDATE_ROOT}:${{PYTHONPATH:-}} "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert _rejects_foreign_runtime_path(command, _ACCEPTED_ROOT)
    assert is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT)
    assert marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) is None


def test_megaplan_state_paths_are_not_foreign_runtime_references() -> None:
    """G7 negative: workspace STATE paths under ``/.megaplan/``
    (cloud-session marker dir, repair queue, the per-epic manifest) are
    named by a relaunch while it binds a single runtime root — they are not
    runtime selections and must never mark the command stale.
    """
    command = (
        "ARNOLD_REPAIR_MARKER_DIR=/workspace/.megaplan/cloud-sessions "
        "ARNOLD_REPAIR_QUEUE_ROOT=/workspace/.megaplan/repair-queue "
        "MANIFEST=/workspace/.megaplan/megaplan-maintenance.json "
        f"PYTHONPATH={_ACCEPTED_ROOT}:${{PYTHONPATH:-}} "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert not _rejects_foreign_runtime_path(command, _ACCEPTED_ROOT)
    assert not is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT)
    assert marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) == command


def test_builder_style_log_redirect_fragments_are_admissible() -> None:
    """G7 negative: the canonical ``_refresh_then_chain_start_command``
    builder emits ``>> .megaplan/cloud-chain.log 2>&1`` (and ``> /tmp/x``
    style redirects) while binding a matching runtime root — the removed
    over-broad `` >>`` / `` >`` stale fragments rejected the builder's own
    output.  Redirect targets are not runtime references and stay
    admissible.
    """
    command = (
        f"{{ cd {_ACCEPTED_ROOT}; }} >> .megaplan/cloud-chain.log 2>&1 && "
        f"PYTHONPATH={_ACCEPTED_ROOT}:${{PYTHONPATH:-}} "
        "python -P -m arnold_pipelines.megaplan chain start "
        "> /tmp/x 2>&1"
    )
    assert not _rejects_foreign_runtime_path(command, _ACCEPTED_ROOT)
    assert not is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT)
    assert marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) == command


def test_foreign_candidate_still_wins_over_megaplan_state_paths() -> None:
    """G7 negative (mixed): a ``.megaplan`` state path alongside a foreign
    runtime candidate stays stale — the foreign path IS a runtime selection
    and wins.
    """
    command = (
        "ARNOLD_REPAIR_MARKER_DIR=/workspace/.megaplan/cloud-sessions "
        f"PYTHONPATH={_FOREIGN_CANDIDATE_ROOT}:${{PYTHONPATH:-}} "
        "python -P -m arnold_pipelines.megaplan chain start"
    )
    assert _rejects_foreign_runtime_path(command, _ACCEPTED_ROOT)
    assert is_stale_marker_relaunch_command(command, _ACCEPTED_ROOT)
    assert marker_relaunch_command({"relaunch_command": command}, _ACCEPTED_ROOT) is None
