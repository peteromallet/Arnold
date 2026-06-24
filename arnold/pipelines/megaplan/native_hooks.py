"""Megaplan-specific native runtime hooks.

This module implements the :class:`~arnold.pipeline.native.hooks.NativeRuntimeHooks`
protocol with Megaplan semantics for state merge, overrides, envelope joining,
subloop promotion/suspension-lift, and loop guards.

Milestone: M3 — Megaplan Native Runtime Hooks
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import NativeInstruction

# ── Override kind constants (catalog-driven dispatch) ──────────────
_ADDITIVE_OVERRIDE_KINDS: frozenset[str] = frozenset({"annotation", "config"})
_CONTROL_OVERRIDE_KINDS: frozenset[str] = frozenset(
    {"termination", "transition", "recovery"}
)

# Priority ranking for control override kinds (lower = higher priority).
# Resolver priority: termination (1) > transition (2) > recovery (3).
# This mirrors the resolve_edge dispatch order in arnold.pipeline.routing:
#   halt > override > decision > normal
_KIND_PRIORITY: dict[str, int] = {
    "termination": 1,
    "transition": 2,
    "recovery": 3,
}


class UnknownOverrideError(ValueError):
    """Raised when pending Megaplan override metadata names no known override."""


def resolve_control_override(
    control_entries: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]] | None = None,
) -> str | None:
    """Resolve the highest-priority control override from pending entries.

    Control override priority (lower = higher priority):
        1. **termination** (e.g. ``abort``) — highest
        2. **transition** (e.g. ``force-proceed``, ``replan``)
        3. **recovery** (e.g. ``recover-blocked``, ``resume-clarify``)

    When multiple control overrides are pending, the one with the highest
    priority kind wins.  Within the same kind, the first entry wins
    (stable — insertion order from ``state.meta.overrides``).

    Each *control_entries* element is a dict with keys:
        * ``action`` — internal normalised action name
        * ``kind`` — catalog kind string
        * ``catalog_action`` — original CLI spelling (optional)
        * ``entry`` — the raw override entry dict (optional)

    Args:
        control_entries: List of pending control override descriptors.
        catalog: Optional catalog dict for validation (unused; reserved
            for future catalog-driven target resolution).

    Returns:
        The winning internal action name (e.g. ``"abort"``,
        ``"force_proceed"``), or ``None`` when *control_entries* is empty.
    """
    if not control_entries:
        return None

    # Sort by kind priority (lower = higher priority), stable on tie.
    def _priority(entry: dict[str, Any]) -> int:
        kind: str = entry.get("kind", "")
        return _KIND_PRIORITY.get(kind, 99)

    sorted_entries = sorted(control_entries, key=_priority)
    winner = sorted_entries[0]
    return winner.get("action")


class MegaplanNativeRuntimeHooks(NullNativeRuntimeHooks):
    """Megaplan-specific native runtime hooks.

    Extends :class:`NullNativeRuntimeHooks` with Megaplan semantics for
    state merge (typed-port CAS when active, legacy ``dict.update`` otherwise),
    overrides, envelope joining, subloop promotion/suspension-lift,
    and loop guards.

    Each callback is implemented incrementally per the M3 milestone schedule.
    """

    def __init__(
        self,
        *,
        plan_dir: str | None = None,
        policy_data: dict[str, Any] | None = None,
        policy_path: str | None = None,
    ) -> None:
        super().__init__()
        self._plan_dir = plan_dir
        self._policy_data = policy_data
        self._policy_path = policy_path

    # ── Override injection (T6 / T7) ──────────────────────────────────

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        """Inject pending overrides from ``state["meta"]["overrides"]``.

        Normalises CLI spellings via
        :func:`~arnold.pipelines.megaplan.routing.cli_to_internal_override`,
        validates every override name against
        :func:`~arnold.pipelines.megaplan.planning.operations.override_catalog`,
        and dispatches by catalog ``kind``:

        * **annotation** / **config** — additive mutation applied to state
          and ``EventKind.OVERRIDE_APPLIED`` emitted.
        * **termination** / **transition** / **recovery** — resolved via
          :func:`resolve_control_override` and stored in
          ``ctx["__override_route__"]`` so the runtime can short-circuit
          decision bodies.  Priority: termination > transition > recovery.

        Returns *ctx* with a rewritten ``state`` when additive mutations
        were applied, otherwise returns *ctx* unchanged.
        """
        state = ctx.get("state")
        if not isinstance(state, dict):
            return ctx

        meta = state.get("meta")
        if not isinstance(meta, dict):
            return ctx

        overrides: Any = meta.get("overrides")
        if not isinstance(overrides, list) or not overrides:
            return ctx

        # ── Resolve catalog and normaliser ─────────────────────────
        try:
            from arnold.pipelines.megaplan.planning.operations import (
                override_catalog,
            )
            from arnold.pipelines.megaplan.routing import (
                cli_to_internal_override,
            )

            _catalog = override_catalog()
        except Exception:
            return ctx  # graceful degradation

        # ── Process each pending override ───────────────────────────
        new_state = dict(state)
        modified = False
        control_entries: list[dict[str, Any]] = []

        for entry in overrides:
            if not isinstance(entry, dict):
                continue

            action: Any = entry.get("action")
            if not isinstance(action, str) or not action:
                continue

            # 1. Validate against catalog (catalog keys use CLI spellings)
            entry_meta = _catalog.get(action)
            if entry_meta is None:
                # Try the internal normalised form as a fallback
                internal_action = cli_to_internal_override(action)
                entry_meta = _catalog.get(internal_action)
                if entry_meta is None:
                    raise UnknownOverrideError(
                        f"Unknown Megaplan override: {action!r}"
                    )
            else:
                # Normalise CLI spelling for internal dispatch
                internal_action = cli_to_internal_override(action)

            kind: Any = entry_meta.get("kind")

            # 2. Dispatch by catalog kind
            if kind == "annotation":
                modified |= _apply_annotation_override(
                    internal_action, entry, new_state, self._plan_dir,
                )
            elif kind == "config":
                modified |= _apply_config_override(
                    internal_action, entry, new_state, self._plan_dir,
                )
            elif kind in _CONTROL_OVERRIDE_KINDS:
                # Collect control overrides for resolution (T7)
                control_entries.append({
                    "action": internal_action,
                    "catalog_action": action,
                    "kind": kind,
                    "entry": entry,
                })

        # ── Resolve control override (T7) ──────────────────────────
        if control_entries:
            resolved = resolve_control_override(control_entries, _catalog)
            if resolved is not None:
                winner = next(
                    (
                        entry
                        for entry in control_entries
                        if entry.get("action") == resolved
                    ),
                    control_entries[0],
                )
                _emit_override_applied(
                    self._plan_dir,
                    resolved,
                    {
                        "action": winner.get("catalog_action", resolved),
                        "internal_action": resolved,
                        "route": resolved,
                        "kind": winner.get("kind"),
                        "reason": (
                            winner.get("entry", {}).get("reason")
                            if isinstance(winner.get("entry"), dict)
                            else None
                        ),
                    },
                )
                ctx["__override_route__"] = resolved

        if modified:
            ctx["state"] = new_state

        return ctx

    def should_halt_loop(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        """Halt native loop bodies when explicit Megaplan loop policy requires it.

        The policy is additive: with no ``loop_guards``/iteration cap metadata,
        this hook preserves the null-hook behavior.  Policy may be supplied in
        ``policy_data`` or state metadata/config.  The focused supported shape is:

        ``{"loop_guards": {"guard_name": {"max_iterations": 3}}}``

        A guard can also halt on recommendation state with
        ``halt_on_recommendations`` and either ``recommendation`` in the guard
        metadata or ``subloop:<guard_name>:recommendation`` in state.
        """
        policy = _loop_policy_for_guard(
            instr_name=instr.name,
            state=state,
            policy_data=self._policy_data,
            policy_path=self._policy_path,
        )
        if not policy:
            return False, None

        max_iterations = _coerce_positive_int(
            policy.get("max_iterations")
            or policy.get("max_loop_iterations")
            or policy.get("iteration_limit")
        )
        if max_iterations is not None and iteration >= max_iterations:
            return (
                True,
                f"loop_guard:{instr.name}:max_iterations:{max_iterations}",
            )

        recommendation = _loop_recommendation(instr.name, state, policy)
        halt_recommendations = policy.get("halt_on_recommendations")
        if isinstance(halt_recommendations, str):
            halt_recommendations = [halt_recommendations]
        if (
            isinstance(recommendation, str)
            and isinstance(halt_recommendations, list)
            and recommendation in halt_recommendations
        ):
            return (
                True,
                f"loop_guard:{instr.name}:recommendation:{recommendation}",
            )

        return False, None

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        """Merge phase outputs into working state with Megaplan CAS semantics.

        Normalises native outputs into key/value patches, maintains executor-owned
        produced keys, and applies typed-port updates through
        :class:`~arnold.pipelines.megaplan._pipeline.types.StateDelta` /
        :func:`~arnold.pipelines.megaplan._pipeline.types.apply_delta` using
        current ``_state_meta`` CAS versions when ``MEGAPLAN_TYPED_PORTS=1``.

        When typed ports are inactive (the default), falls back to legacy
        ``dict.update`` — matching the ``executor-key-merge`` write path in
        :func:`~arnold.pipelines.megaplan._core.state.write_plan_state`.
        """
        if not outputs:
            return state, owned_keys

        try:
            from arnold_pipelines.megaplan.feature_flags import typed_ports_on
            from arnold.pipelines.megaplan._pipeline.types import (
                StateDelta,
                StateDeltaConflict,
                apply_delta,
            )
            _flag_on = typed_ports_on()
        except Exception:
            _flag_on = False

        # Build the new owned_keys set: executor now owns every key it has
        # produced in this phase, unioned with previously owned keys.
        new_owned_keys = frozenset(owned_keys | frozenset(outputs.keys()))

        if _flag_on:
            # ── Typed-port CAS path ──────────────────────────────────
            # Apply each output key through StateDelta/apply_delta using
            # the current _state_meta CAS version for that key.
            _state = dict(state)
            for key, value in outputs.items():
                _versions = (
                    _state.get("_state_meta", {}).get("versions", {})
                )
                _current_version = int(_versions.get(key, 0))
                try:
                    _state, _ = apply_delta(
                        _state,
                        StateDelta(
                            op="replace",
                            key=key,
                            value=value,
                            version=_current_version,
                        ),
                    )
                except StateDeltaConflict:
                    # If a conflict is detected (stale version), fall back
                    # to last-writer-wins for this key (matching the
                    # executor-key-merge behaviour on the persistence side).
                    _state[key] = value
            return _state, new_owned_keys
        else:
            # ── Legacy dict.update path ─────────────────────────────
            # When typed ports are inactive, merge all outputs into
            # state via plain dict.update.
            next_state = dict(state)
            next_state.update(outputs)
            return next_state, new_owned_keys

    # ── Envelope joining (T8) ─────────────────────────────────────

    def join_envelope(
        self,
        instr: NativeInstruction,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        """Join a step's envelope into the accumulated envelope.

        Preserves ``trust_state``, ``resume_cursor``, identity fields
        (``plugin_id``, ``run_id``, ``artifact_root``), and cross-cutting
        metadata.  Rejects lease/fencing/capacity-grant conflicts by
        letting :class:`~arnold.runtime.envelope.LeaseIdConflict` propagate
        rather than silently dropping envelope data.

        When *step_envelope* is falsy (``None``, empty dict, etc.), returns
        *current_envelope* unchanged — matching the no-op default of
        :class:`NullNativeRuntimeHooks`.

        When both are :class:`~arnold.runtime.envelope.RunEnvelope`
        instances, delegates to ``RunEnvelope.join()`` for the cross-cutting
        semilattice.

        When both are :class:`~arnold.runtime.envelope.RuntimeEnvelope`
        instances, preserves the runtime identity of the current carrier and
        joins the inner ``cross_cutting`` RunEnvelope.

        Mixed ``RuntimeEnvelope`` / ``RunEnvelope`` joins are handled by
        lifting the simpler type into the richer carrier.
        """
        if not step_envelope:
            return current_envelope

        if current_envelope is None:
            return step_envelope

        # ── Detect types via duck-typing ──────────────────────────
        from arnold.runtime.envelope import (
            EMPTY_ENVELOPE,
            LeaseIdConflict,
            RunEnvelope,
            RuntimeEnvelope,
        )

        cur_is_rte = isinstance(current_envelope, RuntimeEnvelope)
        step_is_rte = isinstance(step_envelope, RuntimeEnvelope)
        cur_is_re = isinstance(current_envelope, RunEnvelope)
        step_is_re = isinstance(step_envelope, RunEnvelope)

        # ── Both RuntimeEnvelope: preserve carrier, join cross_cutting ──
        if cur_is_rte and step_is_rte:
            try:
                joined_cc = current_envelope.cross_cutting.join(
                    step_envelope.cross_cutting
                )
            except LeaseIdConflict:
                raise  # propagate loudly
            # Preserve identity from the current carrier; step identity
            # is intentionally *not* merged (run_id, plugin_id are scoped
            # to the parent run).
            return RuntimeEnvelope(
                plugin_id=current_envelope.plugin_id,
                manifest_hash=current_envelope.manifest_hash,
                plugin_state_schema_version=current_envelope.plugin_state_schema_version,
                run_id=current_envelope.run_id,
                artifact_root=current_envelope.artifact_root,
                resume_cursor=current_envelope.resume_cursor,
                trust_state=current_envelope.trust_state,
                created_at=current_envelope.created_at,
                cross_cutting=joined_cc,
            )

        # ── Current RuntimeEnvelope, step RunEnvelope ─────────────
        if cur_is_rte and step_is_re:
            try:
                joined_cc = current_envelope.cross_cutting.join(step_envelope)
            except LeaseIdConflict:
                raise
            return RuntimeEnvelope(
                plugin_id=current_envelope.plugin_id,
                manifest_hash=current_envelope.manifest_hash,
                plugin_state_schema_version=current_envelope.plugin_state_schema_version,
                run_id=current_envelope.run_id,
                artifact_root=current_envelope.artifact_root,
                resume_cursor=current_envelope.resume_cursor,
                trust_state=current_envelope.trust_state,
                created_at=current_envelope.created_at,
                cross_cutting=joined_cc,
            )

        # ── Current RunEnvelope, step RuntimeEnvelope ─────────────
        if cur_is_re and step_is_rte:
            try:
                joined_cc = current_envelope.join(
                    step_envelope.cross_cutting
                )
            except LeaseIdConflict:
                raise
            return RuntimeEnvelope(
                plugin_id=step_envelope.plugin_id,
                manifest_hash=step_envelope.manifest_hash,
                plugin_state_schema_version=step_envelope.plugin_state_schema_version,
                run_id=step_envelope.run_id,
                artifact_root=step_envelope.artifact_root,
                resume_cursor=step_envelope.resume_cursor,
                trust_state=step_envelope.trust_state,
                created_at=step_envelope.created_at,
                cross_cutting=joined_cc,
            )

        # ── Both RunEnvelope: pure semilattice join ───────────────
        if cur_is_re and step_is_re:
            try:
                return current_envelope.join(step_envelope)
            except LeaseIdConflict:
                raise

        # ── Fallback: unknown types — return step_envelope ────────
        return step_envelope

    def on_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        """Persist state to disk in executor-key-merge mode after every stage.

        Merges the executor's tracked keys with on-disk handler-written keys:
        keys in ``owned_keys`` take the in-memory value; all other on-disk keys
        retain their on-disk value.  Preserves unowned disk keys while
        advancing ``_state_meta.versions`` for owned keys under typed/CAS mode.

        No-op when ``_plan_dir`` is ``None`` or *state* is not a ``dict``.
        """
        if self._plan_dir is None or not isinstance(state, dict):
            return

        try:
            from pathlib import Path

            from arnold.pipelines.megaplan._core.state import write_plan_state

            write_plan_state(
                Path(self._plan_dir),
                mode="executor-key-merge",
                state=dict(state),
                executor_owned_keys=set(owned_keys),
            )
        except Exception:
            pass

    # ── Completed subpipeline helper (T11) ──────────────────────────

    def completed_subloop(
        self,
        name: str,
        child_state: dict[str, Any],
        recommendation: str,
        *,
        child_artifacts: dict[str, Any] | None = None,
        child_envelope: Any = None,
        resume_cursor: Any = None,
        parent_envelope: Any = None,
    ) -> tuple[dict[str, Any], Any]:
        """Promote a completed child subpipeline result into parent keys.

        Returns a ``(state_patch, joined_envelope)`` tuple.

        **state_patch** carries exactly the allowed promotion keys:

        * ``subloop:<name>:state`` — the child's final state dict
        * ``subloop:<name>:recommendation`` — the routing recommendation
        * ``subloop:<name>:resume_cursor`` — only when *resume_cursor* is
          not ``None`` (suspended-child path)
        * ``subloop:<name>:artifacts`` — when *child_artifacts* is non-empty

        **joined_envelope** is produced by calling
        :meth:`join_envelope` with *parent_envelope* and
        *child_envelope*, so lease/fencing conflicts propagate loudly.

        The caller is responsible for merging *state_patch* into parent
        state and storing *joined_envelope* for subsequent phases.
        This method does **not** mutate any argument.

        Child state is **not** promoted wholesale — only the
        ``subloop:<name>:*`` keys are exposed to the parent.  This
        matches the :class:`~arnold.pipelines.megaplan._pipeline.subloop.SubloopStep`
        contract.
        """
        state_patch: dict[str, Any] = {
            f"subloop:{name}:state": dict(child_state),
        }
        state_patch[f"subloop:{name}:recommendation"] = recommendation

        if resume_cursor is not None:
            state_patch[f"subloop:{name}:resume_cursor"] = resume_cursor

        if child_artifacts:
            state_patch[f"subloop:{name}:artifacts"] = dict(child_artifacts)

        # ── Envelope join ──────────────────────────────────────────
        # Use a synthetic NativeInstruction so join_envelope has an instr
        # to carry (it is only used for identity purposes by the join).
        try:
            from arnold.pipeline.native.ir import NativeInstruction

            _instr = NativeInstruction(
                op="phase", name=f"subloop:{name}", pc=0, func=None, next_pc=None,
            )
        except Exception:
            _instr = None  # fallback: join_envelope's instr is unused in practice

        joined_envelope = self.join_envelope(
            _instr, parent_envelope, child_envelope,
        )

        return state_patch, joined_envelope

    # ── Suspended subpipeline helper (T12) ────────────────────────────

    def suspended_subloop(
        self,
        name: str,
        child_state: dict[str, Any],
        *,
        child_artifacts: dict[str, Any] | None = None,
        child_envelope: Any = None,
        child_resume_cursor: Any = None,
        child_frames: dict[str, Any] | None = None,
        child_artifact_root: str | None = None,
        parent_envelope: Any = None,
        parent_pc: int = 0,
        parent_loops: dict[str, int] | None = None,
        parent_frames: dict[str, Any] | None = None,
        parent_stages: list[str] | None = None,
        parent_state: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], Any]:
        """Lift a suspended child subpipeline into a halt and composite cursor.

        Returns a ``(state_patch, joined_envelope)`` tuple, same as
        :meth:`completed_subloop`, so the caller can merge *state_patch*
        into parent state and store *joined_envelope*.

        Side-effect: writes a composite resume cursor under
        ``<plan_dir>/state.json::resume_cursor`` (and dual-writes
        ``composite_resume_cursor.json``) so the parent can be resumed
        with the child's frame stack, resume cursor, artifact root,
        and envelope intact.

        **state_patch** carries:

        * ``subloop:<name>:state`` — the child's final state dict
        * ``subloop:<name>:recommendation`` — always ``"halt"``
        * ``subloop:<name>:resume_cursor`` — when *child_resume_cursor*
          is not ``None``
        * ``subloop:<name>:artifacts`` — when *child_artifacts* is non-empty

        The composite cursor **children** dict includes the child's
        resume cursor, frame stack, artifact root, and state so the
        native runtime can restore the child on resume.  Parent fields
        (pc, loops, frames, stages, state, envelope) are stored as
        top-level extra keys so the parent runtime can resume from
        the suspension point.

        This method does **not** mutate any argument.
        """
        # ── Build state_patch (same shape as completed_subloop) ──────
        state_patch: dict[str, Any] = {
            f"subloop:{name}:state": dict(child_state),
        }
        state_patch[f"subloop:{name}:recommendation"] = "halt"

        if child_resume_cursor is not None:
            state_patch[f"subloop:{name}:resume_cursor"] = child_resume_cursor

        if child_artifacts:
            state_patch[f"subloop:{name}:artifacts"] = dict(child_artifacts)

        # ── Envelope join ──────────────────────────────────────────
        try:
            from arnold.pipeline.native.ir import NativeInstruction

            _instr = NativeInstruction(
                op="phase", name=f"subloop:{name}", pc=0, func=None, next_pc=None,
            )
        except Exception:
            _instr = None

        joined_envelope = self.join_envelope(
            _instr, parent_envelope, child_envelope,
        )

        # ── Composite cursor persistence ────────────────────────────
        # Only persist when self._plan_dir is set (same guard as
        # on_stage_complete).
        if self._plan_dir is not None:
            try:
                from pathlib import Path

                from arnold.pipelines.megaplan._pipeline.resume import (
                    save_composite_resume_cursor,
                )

                # Build child cursor entry
                child_cursor: dict[str, Any] = {}
                if child_resume_cursor is not None:
                    child_cursor["resume_cursor"] = child_resume_cursor
                if child_frames is not None:
                    child_cursor["frames"] = dict(child_frames)
                if child_artifact_root is not None:
                    child_cursor["artifact_root"] = child_artifact_root
                child_cursor["state"] = dict(child_state)

                children: dict[str, Any] = {name: child_cursor}

                # Parent context as extra top-level keys
                extra: dict[str, Any] = {}
                if parent_state is not None:
                    extra["parent_state"] = dict(parent_state)
                if parent_loops is not None:
                    extra["parent_loops"] = dict(parent_loops)
                if parent_frames is not None:
                    extra["parent_frames"] = dict(parent_frames)
                if parent_stages is not None:
                    extra["parent_stages"] = list(parent_stages)
                if joined_envelope is not None:
                    extra["envelope"] = joined_envelope.to_jsonable()
                extra["parent_pc"] = parent_pc

                save_composite_resume_cursor(
                    Path(self._plan_dir),
                    children=children,
                    version=1,
                    **extra,
                )
            except Exception:
                # Best-effort: if persist fails, the caller still gets
                # the state_patch and joined_envelope so the parent can
                # halt without data loss.
                pass

        return state_patch, joined_envelope


# ── Override helper functions (T6) ────────────────────────────────────


def _now_utc() -> str:
    """Return the current UTC time as an ISO-8601 string with ``Z`` suffix."""
    from datetime import datetime, timezone

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _emit_override_applied(
    plan_dir: str | None,
    action: str,
    payload: dict[str, Any],
) -> None:
    """Best-effort emit of ``EventKind.OVERRIDE_APPLIED``.

    When *plan_dir* is ``None``, this is a silent no-op (no event journal
    to write to).  Emission failures are swallowed — matching the existing
    best-effort observability pattern for override events.
    """
    if plan_dir is None:
        return
    try:
        from pathlib import Path

        from arnold.pipelines.megaplan.observability.events import (
            EventKind,
            emit,
        )

        emit(
            EventKind.OVERRIDE_APPLIED,
            plan_dir=Path(plan_dir),
            payload=payload,
        )
    except Exception:
        pass


def _apply_annotation_override(
    internal_action: str,
    entry: dict[str, Any],
    new_state: dict[str, Any],
    plan_dir: str | None,
) -> bool:
    """Apply an additive annotation override (currently ``add-note``).

    Returns ``True`` if *new_state* was mutated.
    """
    if internal_action != "add-note":
        return False

    note_text: Any = entry.get("note", "")
    source: Any = entry.get("source", "user")
    note_entry: dict[str, Any] = {
        "timestamp": _now_utc(),
        "note": note_text if isinstance(note_text, str) else str(note_text),
        "source": source if isinstance(source, str) else "user",
    }

    new_state.setdefault("meta", {}).setdefault("notes", []).append(note_entry)

    _emit_override_applied(
        plan_dir,
        "add-note",
        {
            "action": "add-note",
            "reason": note_entry["note"],
            "source": note_entry["source"],
        },
    )
    return True


def _apply_config_override(
    internal_action: str,
    entry: dict[str, Any],
    new_state: dict[str, Any],
    plan_dir: str | None,
) -> bool:
    """Apply an additive config override (set-model/set-profile/set-robustness/set-vendor).

    Returns ``True`` if *new_state* was mutated.
    """
    config = new_state.setdefault("config", {})

    if internal_action == "set-model":
        phase: Any = entry.get("phase")
        model: Any = entry.get("model")
        if not isinstance(phase, str) or not phase:
            return False
        if not isinstance(model, str) or not model:
            return False
        phase_models: list[str] = list(
            config.get("phase_model") or []
        )
        found = False
        for i, pm in enumerate(phase_models):
            if isinstance(pm, str) and "=" in pm and pm.split("=", 1)[0] == phase:
                phase_models[i] = f"{phase}={model}"
                found = True
                break
        if not found:
            phase_models.append(f"{phase}={model}")
        config["phase_model"] = phase_models

        _emit_override_applied(
            plan_dir,
            "set-model",
            {"action": "set-model", "phase": phase, "model": model},
        )
        return True

    if internal_action == "set-profile":
        profile: Any = entry.get("profile")
        if not isinstance(profile, str) or not profile:
            return False
        config["profile"] = profile

        _emit_override_applied(
            plan_dir,
            "set-profile",
            {"action": "set-profile", "profile": profile},
        )
        return True

    if internal_action == "set-robustness":
        robustness: Any = entry.get("robustness")
        if not isinstance(robustness, str) or not robustness:
            return False
        config["robustness"] = robustness

        _emit_override_applied(
            plan_dir,
            "set-robustness",
            {"action": "set-robustness", "robustness": robustness},
        )
        return True

    if internal_action == "set-vendor":
        vendor: Any = entry.get("vendor")
        if not isinstance(vendor, str) or not vendor:
            return False
        config["premium_vendor"] = vendor

        _emit_override_applied(
            plan_dir,
            "set-vendor",
            {"action": "set-vendor", "vendor": vendor},
        )
        return True

    return False


def _coerce_positive_int(value: Any) -> int | None:
    """Return a positive integer for simple numeric policy values."""
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return None
    return coerced if coerced >= 0 else None


def _load_policy_path(policy_path: str | None) -> dict[str, Any]:
    """Best-effort JSON policy loader used only for loop guard metadata."""
    if not policy_path:
        return {}
    try:
        import json
        from pathlib import Path

        loaded = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _loop_policy_for_guard(
    *,
    instr_name: str,
    state: dict[str, Any],
    policy_data: dict[str, Any] | None,
    policy_path: str | None,
) -> dict[str, Any]:
    """Merge loop-guard policy from persisted policy and Megaplan state."""
    sources: list[dict[str, Any]] = []
    loaded_path = _load_policy_path(policy_path)
    if loaded_path:
        sources.append(loaded_path)
    if isinstance(policy_data, dict):
        sources.append(policy_data)
    if isinstance(state, dict):
        state_meta = state.get("_state_meta")
        if isinstance(state_meta, dict):
            config = state_meta.get("config")
            if isinstance(config, dict):
                sources.append(config)
        config = state.get("config")
        if isinstance(config, dict):
            sources.append(config)
        loop_guards = state.get("loop_guards")
        if isinstance(loop_guards, dict):
            sources.append({"loop_guards": loop_guards})

    merged: dict[str, Any] = {}
    for source in sources:
        guards = source.get("loop_guards")
        if isinstance(guards, dict):
            guard_policy = guards.get(instr_name) or guards.get("*")
            if isinstance(guard_policy, dict):
                merged.update(guard_policy)
        for key in ("max_loop_iterations", "max_iterations"):
            if key in source and key not in merged:
                merged[key] = source[key]
    return merged


def _loop_recommendation(
    instr_name: str,
    state: dict[str, Any],
    policy: dict[str, Any],
) -> str | None:
    """Resolve recommendation metadata for a loop guard, if present."""
    recommendation = policy.get("recommendation")
    if isinstance(recommendation, str):
        return recommendation
    if not isinstance(state, dict):
        return None
    guard_state = state.get("loop_guards")
    if isinstance(guard_state, dict):
        entry = guard_state.get(instr_name)
        if isinstance(entry, dict) and isinstance(entry.get("recommendation"), str):
            return entry["recommendation"]
    subloop_recommendation = state.get(f"subloop:{instr_name}:recommendation")
    if isinstance(subloop_recommendation, str):
        return subloop_recommendation
    recommendation = state.get("recommendation")
    return recommendation if isinstance(recommendation, str) else None


# Compatibility alias — existing callers referencing ``MegaplanNativeHooks``
# continue to resolve the canonical ``MegaplanNativeRuntimeHooks``.
MegaplanNativeHooks = MegaplanNativeRuntimeHooks

__all__ = [
    "MegaplanNativeRuntimeHooks",
    "MegaplanNativeHooks",
    "UnknownOverrideError",
]
