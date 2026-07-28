"""Steps 13E2-13E8: Git mutation adapter for destructive, staging,
worktree, remote, PR, and loop git rows.

Step 13E2 routes at most three inventoried git reset/clean/checkout
sink rows through the WBC effect protocol and action gate:

1. ``_refresh_base_branch`` — ``git reset`` (git_ops.py)
2. ``_clean_worktree_for_chain`` — ``git reset`` + ``git clean`` (git_ops.py)
3. ``_checkout_milestone_branch`` — ``git checkout`` (git_ops.py)

Step 13E3 routes at most three git add/commit/update-ref sink rows
with command-specific semantics and idempotency across crashes:

4. ``_commit_phase`` — ``git add`` + ``git commit`` (git_ops.py)
5. ``commit_plan_artifacts_to_base`` — ``git add`` + ``git commit-tree`` + ``git update-ref`` (git_ops.py)
6. ``git_commit`` — ``git add`` + ``git commit`` (loop/git.py)

Step 13E4 routes at most three git rebase/stash/worktree sink rows
with command-specific semantics and stale-fence gating:

7. ``_checkout_milestone_branch`` — ``git rebase`` (git_ops.py)
8. ``_assert_clean_base`` — ``git stash`` (chain/__init__.py)
9. ``_preserve_carried_wip_before_retry`` — ``git stash`` (chain/__init__.py)

Step 13E5 routes at most three git push/force-with-lease sink rows
through provider-idempotency or authoritative reconciliation:

10. ``_commit_and_push_phase`` — ``git push`` (git_ops.py)
11. ``_checkout_milestone_branch`` — ``git push --force-with-lease`` (git_ops.py)
12. ``_recover_missing_remote_base_branch`` — ``git push`` (git_ops.py)

Step 13E6 routes at most three PR-ready and PR-merge rows through
the action gate and WBC protocol:

13. ``_mark_pr_ready`` — ``gh pr ready`` (git_ops.py → pr_merge.py)
14. ``_enable_auto_merge`` auto path — ``gh pr merge --auto`` (git_ops.py → pr_merge.py)
14. ``_enable_auto_merge`` direct path — ``gh pr merge --squash`` (git_ops.py → pr_merge.py)

Step 13E8 routes at most two loop/git.py sink rows through the
WBC protocol and action gate, keeping read-only helpers out of the
sink inventory:

15. ``git_commit`` — ``git add`` + ``git commit`` (loop/git.py)
16. ``git_revert`` — ``git revert --no-edit`` (loop/git.py)

All real Git/GitHub mutations remain action-off (SD3).  The adapter uses
fake Git/GitHub to prove the protocol.  Remote operations (Step 13E5) and
PR merges (Step 13E6) carry a reconciliation query so lost-ACK scenarios
can be resolved through provider-side evidence without a blind re-dispatch.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)
from arnold.workflow.effect_reconciliation import (
    ReconciliationResult,
    ReconciliationVerdict,
    get_provider_capability,
)
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptIdentity,
    AttemptProvenance,
    GlobalEffectIdentity,
    GrantRef,
    RuntimeAdapter,
    VersionSet,
)

from arnold_pipelines.megaplan.custody.action_gate import (
    ActionFamily,
    ActionGateVerdict,
)

LOGGER = logging.getLogger(__name__)


# ── Git effect shard identity ────────────────────────────────────────────────


class GitEffectShard(str, Enum):
    """Git mutation shards routed through the WBC adapter.

    Step 13E2: reset, clean, checkout.
    Step 13E3: add, commit, update-ref.
    Step 13E4: rebase, stash, worktree.
    Step 13E5: push, force_with_lease.
    Step 13E6: pr_ready, pr_merge.
    """

    RESET = "reset"
    CLEAN = "clean"
    CHECKOUT = "checkout"
    ADD = "add"
    COMMIT = "commit"
    UPDATE_REF = "update_ref"
    REBASE = "rebase"
    STASH = "stash"
    WORKTREE = "worktree"
    PUSH = "push"
    FORCE_WITH_LEASE = "force_with_lease"
    PR_READY = "pr_ready"
    PR_MERGE = "pr_merge"
    LOOP_COMMIT = "loop_commit"
    LOOP_REVERT = "loop_revert"


GIT_SHARD_13E2: tuple[GitEffectShard, ...] = (
    GitEffectShard.RESET,
    GitEffectShard.CLEAN,
    GitEffectShard.CHECKOUT,
)
"""The at-most-three destructive rows routed in Step 13E2."""

GIT_SHARD_13E3: tuple[GitEffectShard, ...] = (
    GitEffectShard.ADD,
    GitEffectShard.COMMIT,
    GitEffectShard.UPDATE_REF,
)
"""The at-most-three staging rows routed in Step 13E3."""

GIT_SHARD_13E4: tuple[GitEffectShard, ...] = (
    GitEffectShard.REBASE,
    GitEffectShard.STASH,
    GitEffectShard.WORKTREE,
)
"""The at-most-three worktree rows routed in Step 13E4."""

GIT_SHARD_13E5: tuple[GitEffectShard, ...] = (
    GitEffectShard.PUSH,
    GitEffectShard.FORCE_WITH_LEASE,
)
"""The at-most-two remote rows routed in Step 13E5.
(PUSH and FORCE_WITH_LEASE; push is counted once across all push sinks.)"""

GIT_SHARD_13E6: tuple[GitEffectShard, ...] = (
    GitEffectShard.PR_READY,
    GitEffectShard.PR_MERGE,
)
"""The at-most-two PR rows routed in Step 13E6.
(PR_READY for marking ready; PR_MERGE for auto-merge and direct squash merge.)"""

GIT_SHARD_13E8: tuple[GitEffectShard, ...] = (
    GitEffectShard.LOOP_COMMIT,
    GitEffectShard.LOOP_REVERT,
)
"""The at-most-two loop git rows routed in Step 13E8.
(LOOP_COMMIT for git_commit in loop/git.py; LOOP_REVERT for git_revert.)"""


@dataclass(frozen=True)
class GitTarget:
    """Stable identity for a git mutation target."""

    shard: GitEffectShard
    module: str  # e.g. "arnold_pipelines/megaplan/chain/git_ops.py"
    enclosing_function: str
    repository: str = ""
    branch: str = ""

    @property
    def target_key(self) -> str:
        return f"git:{self.shard.value}:{self.module}:{self.enclosing_function}"


# ── Git outcome ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GitOutcome:
    """Result of a git mutation through the adapter."""

    ok: bool
    shard: str
    glek: str
    outcome_kind: str
    error: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


# ── Git effect adapter ───────────────────────────────────────────────────────


class GitEffectAdapter:
    """Routes git mutation rows through WBC/action gate.

    Step 13E2: at most three destructive rows (reset/clean/checkout).
    Step 13E3: at most three staging rows (add/commit/update-ref).
    Step 13E4: at most three worktree rows (rebase/stash/worktree).
    Step 13E5: at most two remote rows (push/force_with_lease) with
               provider-idempotency and authoritative reconciliation.
    Step 13E6: at most two PR rows (pr_ready/pr_merge) with
               fake-GitHub at-most-once gating and reconciliation.
    Step 13E8: at most two loop git rows (loop_commit/loop_revert)
               routed from loop/git.py through WBC.
    Additional rows require a plan revision with another numbered shard.
    """

    _ROUTED_SHARDS: frozenset[GitEffectShard] = frozenset(
        (*GIT_SHARD_13E2, *GIT_SHARD_13E3, *GIT_SHARD_13E4, *GIT_SHARD_13E5, *GIT_SHARD_13E6, *GIT_SHARD_13E8)
    )

    def __init__(
        self,
        protocol: EffectProtocol,
        *,
        action_gate_check: Optional[
            Callable[[ActionFamily, str], ActionGateVerdict]
        ] = None,
        production_enabled: bool = False,
    ) -> None:
        self._protocol = protocol
        self._action_gate_check = action_gate_check
        self._production_enabled = production_enabled

    # ── shard enforcement ────────────────────────────────────────────────

    def _enforce_shard(self, target: GitTarget) -> None:
        """Fail if the target's shard is not in the routed set."""
        if target.shard not in self._ROUTED_SHARDS:
            raise ValueError(
                f"Git shard {target.shard.value!r} is not routed. "
                f"Routed shards: {[s.value for s in self._ROUTED_SHARDS]}. "
                f"Route through a different numbered shard (Step 13E7 gate)."
            )

    # ── gate ────────────────────────────────────────────────────────────

    def _gate(self, target: GitTarget) -> ActionGateVerdict:
        if self._action_gate_check is None:
            return ActionGateVerdict.SHADOW_AUTHORIZED
        return self._action_gate_check(ActionFamily.GIT, target.target_key)

    # ── GLEK ─────────────────────────────────────────────────────────────

    @staticmethod
    def _build_effect_identity(target: GitTarget) -> GlobalEffectIdentity:
        return GlobalEffectIdentity(
            environment_id=f"git-{target.repository or 'repo'}",
            action_target=target.target_key,
            action_version="m10",
            effect_family=f"git.{target.shard.value}",
            provider_target=f"git:{target.repository or 'local'}",
            canonical_request_identity=target.target_key,
            boundary_schema_hash="m10-git-v1",
        )

    @staticmethod
    def _build_identity_bundle(
        attempt_id: str,
    ) -> tuple[AttemptIdentity, AttemptProvenance, RuntimeAdapter, VersionSet, GrantRef]:
        identity = AttemptIdentity(
            workflow_id=f"git-{attempt_id}",
            run_id=f"git-{attempt_id}",
            graph_revision="m10",
            attempt_id=attempt_id,
        )
        provenance = AttemptProvenance(
            parent_attempt_id=None,
        )
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="m10-git",
        )
        versions = VersionSet(code_version="m10")
        grant_ref = GrantRef(grant_id=f"git-grant-{attempt_id}")
        return identity, provenance, adapter, versions, grant_ref

    # ── stale-fence negative ─────────────────────────────────────────────

    def _check_stale_fence(
        self, target: GitTarget, fence_token: int | None
    ) -> bool:
        """Stale-fence negative: reject dispatch with stale or missing fence.

        Step 13E2 requires a current fence token.  A missing or zero
        token signals stale authorization.
        """
        if fence_token is None or fence_token <= 0:
            LOGGER.warning(
                "Stale fence for git %s (%s): token=%s",
                target.shard.value,
                target.enclosing_function,
                fence_token,
            )
            return False
        return True

    # ── Step 13E3 staging dispatch ────────────────────────────────────────

    def route_staging(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        fence_token: int | None = None,
    ) -> GitOutcome:
        """Route a git add/commit/update-ref staging row (Step 13E3).

        Enforces command-specific semantics:
        - ``add``: requires non-empty ``paths`` in intent payload.
        - ``commit``: requires non-empty ``message`` in intent payload.
        - ``update_ref``: requires ``ref`` and ``target_hash``.

        Crash-idempotent: re-routing the same target with the same
        ``attempt_id`` produces a duplicate-protected GLEK.
        """
        # Enforce 13E3 shard boundary
        if target.shard not in frozenset(GIT_SHARD_13E3):
            raise ValueError(
                f"route_staging only supports Step 13E3 shards "
                f"(add/commit/update_ref), got {target.shard.value!r}"
            )

        # Command-specific semantics
        if target.shard == GitEffectShard.ADD:
            paths = intent_payload.get("paths", [])
            if not paths or (isinstance(paths, list) and len(paths) == 0):
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: add requires non-empty paths",
                )
        elif target.shard == GitEffectShard.COMMIT:
            message = intent_payload.get("message", "")
            if not message or not str(message).strip():
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: commit requires non-empty message",
                )
        elif target.shard == GitEffectShard.UPDATE_REF:
            ref = intent_payload.get("ref", "")
            target_hash = intent_payload.get("target_hash", "")
            if not ref or not target_hash:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: update_ref requires ref and target_hash",
                )

        return self.route(
            target=target,
            intent_payload=intent_payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
            fence_token=fence_token,
        )

    # ── general dispatch ─────────────────────────────────────────────────

    def route(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        fence_token: int | None = None,
    ) -> GitOutcome:
        """Route a git mutation through the WBC protocol.

        Args:
            target: Stable git target identity.
            intent_payload: The effect payload (command, args, etc.).
            apply_fn: The actual git-command callable (fake in M10).
            attempt_id: Explicit attempt id.
            fence_token: Current fence token (stale-fence negative).

        Returns:
            GitOutcome with the GLEK, outcome, and error.
        """
        # Enforce shard boundary
        self._enforce_shard(target)

        if self._production_enabled:
            LOGGER.warning(
                "Production git dispatch attempted for %s — "
                "production is action-off in M10",
                target.target_key,
            )

        # Stale-fence negative
        if not self._check_stale_fence(target, fence_token):
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Stale fence: missing or zero fence token",
                evidence={"fence_token": fence_token},
            )

        # Action gate check
        verdict = self._gate(target)
        if verdict not in (
            ActionGateVerdict.AUTHORIZED,
            ActionGateVerdict.SHADOW_AUTHORIZED,
        ):
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict.value}",
                evidence={"gate_verdict": verdict.value},
            )

        # Intent-failure negative: validate intent payload
        if not intent_payload:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Intent-failure: empty intent payload",
            )

        aid = attempt_id or str(uuid.uuid4())
        ei = self._build_effect_identity(target)
        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        try:
            reservation = self._protocol.reserve_and_start(
                attempt_id=aid,
                effect_identity=ei,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
            glek = reservation.global_logical_effect_key

            self._protocol.persist_intent(
                attempt_id=aid,
                glek=glek,
                intent_payload=intent_payload,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )

            try:
                result = apply_fn(intent_payload)
            except Exception as exc:
                self._protocol.accept_outcome(
                    aid, glek, OUTCOME_FAILED,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek=glek,
                    outcome_kind=OUTCOME_FAILED,
                    error=str(exc),
                )

            self._protocol.accept_outcome(
                aid, glek, OUTCOME_COMPLETED,
                {"exit_code": 0},
            )
            return GitOutcome(
                ok=True,
                shard=target.shard.value,
                glek=glek,
                outcome_kind=OUTCOME_COMPLETED,
                evidence={"result": "ok"},
            )

        except Exception as exc:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_INDETERMINATE,
                error=f"Protocol error: {type(exc).__name__}: {exc}",
            )

    # ── Step 13E4 worktree dispatch ──────────────────────────────────────

    def route_worktree(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        fence_token: int | None = None,
    ) -> GitOutcome:
        """Route a git rebase/stash/worktree row (Step 13E4).

        Enforces command-specific semantics:

        - ``rebase``: requires non-empty ``branch`` (target to rebase onto).
        - ``stash``: optional ``paths`` and ``message``; empty stash is
          a no-op that returns ok without dispatch.
        - ``worktree``: requires ``path`` and ``action``
          (add/remove; ``list`` is read-only and rejected).

        Crash-idempotent: re-routing the same target with the same
        ``attempt_id`` produces a duplicate-protected GLEK.
        """
        # Enforce 13E4 shard boundary
        if target.shard not in frozenset(GIT_SHARD_13E4):
            raise ValueError(
                f"route_worktree only supports Step 13E4 shards "
                f"(rebase/stash/worktree), got {target.shard.value!r}"
            )

        # Command-specific semantics
        if target.shard == GitEffectShard.REBASE:
            branch = intent_payload.get("branch", "")
            if not branch or not str(branch).strip():
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: rebase requires non-empty branch",
                )
        elif target.shard == GitEffectShard.STASH:
            # Stash with empty paths is a no-op (already clean)
            paths = intent_payload.get("paths")
            if paths is not None and (not isinstance(paths, list) or len(paths) == 0):
                return GitOutcome(
                    ok=True,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_COMPLETED,
                    error=None,
                    evidence={"action": "noop", "reason": "empty paths"},
                )
        elif target.shard == GitEffectShard.WORKTREE:
            path = intent_payload.get("path", "")
            action = intent_payload.get("action", "")
            if not path or not action:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: worktree requires path and action",
                )
            if action == "list":
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: worktree list is read-only, not a mutation",
                )
            if action not in ("add", "remove"):
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error=f"Intent-failure: unknown worktree action {action!r}",
                )

        return self.route(
            target=target,
            intent_payload=intent_payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
            fence_token=fence_token,
        )

    # ── Step 13E6 PR dispatch with at-most-once gating ────────────────────

    def route_pr(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        fence_token: int | None = None,
        reconciliation_query: Callable[..., ReconciliationResult] | None = None,
    ) -> GitOutcome:
        """Route a PR-ready or PR-merge row through WBC + action gate (Step 13E6).

        PR state transitions go through ``gh`` CLI (not git), so lost-ACK
        scenarios are real.  This method uses provider-idempotency or
        authoritative reconciliation to decide whether to dispatch, adopt
        an already-applied result, or escalate.

        Command-specific semantics:

        - ``pr_ready``: requires ``pr_number`` (int) in intent payload.
        - ``pr_merge``: requires ``pr_number`` (int) and ``merge_strategy``
          (``\"auto\"`` or ``\"squash\"``) in intent payload.

        Reconciliation flow (same as Step 13E5):

        1. If *reconciliation_query* is provided, call it BEFORE
           dispatching.
        2. ``APPLIED`` → adopt without re-dispatch.
        3. ``NOT_APPLIED`` → proceed to fenced dispatch.
        4. ``UNKNOWN`` / query failure → ``INDETERMINATE``, no blind-dispatch.

        At-most-once: the same ``attempt_id`` + same ``pr_number`` produces
        the same GLEK across retries.

        Fake-GitHub: all tests use a fake ``gh`` that never mutates
        production GitHub (SD3).
        """
        # Enforce 13E6 shard boundary
        if target.shard not in frozenset(GIT_SHARD_13E6):
            raise ValueError(
                f"route_pr only supports Step 13E6 shards "
                f"(pr_ready/pr_merge), got {target.shard.value!r}"
            )

        # Command-specific semantics
        pr_number = intent_payload.get("pr_number")
        if not isinstance(pr_number, int) or pr_number <= 0:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Intent-failure: pr_ready/pr_merge requires valid pr_number (int > 0)",
            )

        if target.shard == GitEffectShard.PR_MERGE:
            merge_strategy = intent_payload.get("merge_strategy", "")
            if merge_strategy not in ("auto", "squash"):
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error=(
                        "Intent-failure: pr_merge requires merge_strategy "
                        "('auto' or 'squash')"
                    ),
                )

        # Stale-fence negative
        if not self._check_stale_fence(target, fence_token):
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Stale fence: missing or zero fence token",
                evidence={"fence_token": fence_token},
            )

        # Action gate check
        verdict = self._gate(target)
        if verdict not in (
            ActionGateVerdict.AUTHORIZED,
            ActionGateVerdict.SHADOW_AUTHORIZED,
        ):
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict.value}",
                evidence={"gate_verdict": verdict.value},
            )

        # Intent-failure negative
        if not intent_payload:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Intent-failure: empty intent payload",
            )

        # Use reconciliation for PR merge to handle lost-ACK
        return self._apply_with_reconciliation(
            target=target,
            intent_payload=intent_payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
            reconciliation_query=reconciliation_query,
        )

    # ── Step 13E8 loop git dispatch ──────────────────────────────────────

    def route_loop_git(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        fence_token: int | None = None,
    ) -> GitOutcome:
        """Route a loop/git.py mutation through the WBC protocol (Step 13E8).

        Routes ``git_commit`` and ``git_revert`` from ``loop/git.py``
        through the WBC/action gate.  Read-only helpers like
        ``git_current_sha``, ``parse_metric``, and status-path helpers
        remain outside the sink inventory.

        Command-specific semantics:

        - ``loop_commit``: requires non-empty ``message`` (str) and
          ``allowed_changes`` (list[str]) in intent payload.  The commit
          is conditional on there being changed paths within
          *allowed_changes* — the adapter dispatches unconditionally
          (the caller is responsible for the conditional logic).

        - ``loop_revert``: requires ``commit_sha`` (str) and
          ``project_dir`` (str) in intent payload.  On failure the
          real implementation aborts the revert; the adapter reflects
          this as a FAILED outcome.

        Crash-idempotent: re-routing the same target with the same
        ``attempt_id`` produces a duplicate-protected GLEK.
        """
        # Enforce 13E8 shard boundary
        if target.shard not in frozenset(GIT_SHARD_13E8):
            raise ValueError(
                f"route_loop_git only supports Step 13E8 shards "
                f"(loop_commit/loop_revert), got {target.shard.value!r}"
            )

        # Command-specific semantics
        if target.shard == GitEffectShard.LOOP_COMMIT:
            message = intent_payload.get("message", "")
            allowed_changes = intent_payload.get("allowed_changes")
            if not message or not str(message).strip():
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: loop_commit requires non-empty message",
                )
            if not isinstance(allowed_changes, list) or len(allowed_changes) == 0:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: loop_commit requires non-empty allowed_changes list",
                )
        elif target.shard == GitEffectShard.LOOP_REVERT:
            commit_sha = intent_payload.get("commit_sha", "")
            project_dir = intent_payload.get("project_dir", "")
            if not commit_sha or not str(commit_sha).strip():
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: loop_revert requires non-empty commit_sha",
                )
            if not project_dir:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: loop_revert requires project_dir",
                )

        return self.route(
            target=target,
            intent_payload=intent_payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
            fence_token=fence_token,
        )

    # ── Step 13E5 remote dispatch with reconciliation ────────────────────

    def route_remote(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        fence_token: int | None = None,
        reconciliation_query: Callable[..., ReconciliationResult] | None = None,
    ) -> GitOutcome:
        """Route a git push/force-with-lease remote row (Step 13E5).

        Remote operations are ambiguous-by-nature (lost ACK, process
        crash after send, network partition).  This method uses
        provider-idempotency or authoritative reconciliation to decide
        whether to dispatch, adopt an already-applied result, or
        escalate.

        Command-specific semantics:

        - ``push``: requires ``branch`` and ``remote``.
        - ``force_with_lease``: requires ``branch``, ``remote``,
          and ``expected_sha`` (the lease).

        Reconciliation flow:

        1. If *reconciliation_query* is provided, call it BEFORE
           dispatching.  This is the authoritative source-of-truth
           check (e.g., query the remote for the current ref).
        2. If the query returns ``APPLIED``, adopt the result without
           re-dispatching (provider-idempotency path).
        3. If the query returns ``NOT_APPLIED``, proceed to fenced
           dispatch through the WBC protocol.
        4. If the query returns ``UNKNOWN`` or fails, return
           ``INDETERMINATE`` — escalate, do NOT blind-dispatch.

        Crash-idempotent: same ``attempt_id`` + same target produces
        the same GLEK.
        """
        # Enforce 13E5 shard boundary
        if target.shard not in frozenset(GIT_SHARD_13E5):
            raise ValueError(
                f"route_remote only supports Step 13E5 shards "
                f"(push/force_with_lease), got {target.shard.value!r}"
            )

        # Command-specific semantics
        if target.shard == GitEffectShard.PUSH:
            branch = intent_payload.get("branch", "")
            remote = intent_payload.get("remote", "")
            if not branch or not remote:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error="Intent-failure: push requires branch and remote",
                )
        elif target.shard == GitEffectShard.FORCE_WITH_LEASE:
            branch = intent_payload.get("branch", "")
            remote = intent_payload.get("remote", "")
            expected_sha = intent_payload.get("expected_sha", "")
            if not branch or not remote or not expected_sha:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_FAILED,
                    error=(
                        "Intent-failure: force_with_lease requires "
                        "branch, remote, and expected_sha"
                    ),
                )

        # Stale-fence negative
        if not self._check_stale_fence(target, fence_token):
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Stale fence: missing or zero fence token",
                evidence={"fence_token": fence_token},
            )

        # Action gate check
        verdict = self._gate(target)
        if verdict not in (
            ActionGateVerdict.AUTHORIZED,
            ActionGateVerdict.SHADOW_AUTHORIZED,
        ):
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error=f"Action gate blocked: {verdict.value}",
                evidence={"gate_verdict": verdict.value},
            )

        # Intent-failure negative
        if not intent_payload:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_FAILED,
                error="Intent-failure: empty intent payload",
            )

        return self._apply_with_reconciliation(
            target=target,
            intent_payload=intent_payload,
            apply_fn=apply_fn,
            attempt_id=attempt_id,
            reconciliation_query=reconciliation_query,
        )

    # ── Reconciliation-driven dispatch ───────────────────────────────────

    def _apply_with_reconciliation(
        self,
        *,
        target: GitTarget,
        intent_payload: dict[str, Any],
        apply_fn: Callable[..., Any],
        attempt_id: str | None = None,
        reconciliation_query: Callable[..., ReconciliationResult] | None = None,
    ) -> GitOutcome:
        """Resolve lost-ACK ambiguity via reconciliation before dispatch.

        If *reconciliation_query* is provided and the remote confirms
        the effect was ALREADY applied, adopt it without re-dispatch.

        If *reconciliation_query* is ``None``, fall through to normal
        dispatch (the caller is responsible for ensuring this is safe).
        """
        aid = attempt_id or str(uuid.uuid4())
        ei = self._build_effect_identity(target)

        # Provider idempotency key for reconciliation
        provider_key = (
            f"git-{target.shard.value}-"
            f"{target.repository or 'repo'}-"
            f"{intent_payload.get('branch', '')}-"
            f"{aid}"
        )

        # --- Reconciliation phase: check remote before dispatch ---
        if reconciliation_query is not None:
            try:
                rec_result = reconciliation_query(provider_key)
            except Exception as exc:
                LOGGER.warning(
                    "Reconciliation query failed for %s: %s",
                    target.target_key,
                    exc,
                )
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_INDETERMINATE,
                    error=f"Reconciliation query error: {type(exc).__name__}: {exc}",
                )

            if rec_result.query_failure:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_INDETERMINATE,
                    error="Reconciliation query failure — indeterminate",
                    evidence={"reconciliation": "query_failure"},
                )

            if rec_result.verdict == ReconciliationVerdict.UNKNOWN:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_INDETERMINATE,
                    error="Reconciliation returned UNKNOWN — indeterminate",
                    evidence={"reconciliation": "unknown"},
                )

            if rec_result.verdict == ReconciliationVerdict.APPLIED:
                # Provider confirms the effect was already applied.
                # Adopt without re-dispatch.
                return GitOutcome(
                    ok=True,
                    shard=target.shard.value,
                    glek=ei.global_logical_effect_key,
                    outcome_kind=OUTCOME_COMPLETED,
                    error=None,
                    evidence={
                        "reconciliation": "applied",
                        "provider_key": provider_key,
                    },
                )

            # NOT_APPLIED: proceed to fenced dispatch.
            if not rec_result.is_authoritative:
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek="",
                    outcome_kind=OUTCOME_INDETERMINATE,
                    error="Non-authoritative NOT_APPLIED — indeterminate",
                    evidence={"reconciliation": "non_authoritative"},
                )

        # --- Dispatch phase ---
        # Check provider capability for idempotency
        cap = get_provider_capability("fake-effect-provider")
        if not cap.can_authorize_redispatch:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_INDETERMINATE,
                error="Provider lacks query+idempotency — indeterminate",
            )

        ident, prov, adapter, versions, grant_ref = self._build_identity_bundle(aid)

        try:
            reservation = self._protocol.reserve_and_start(
                attempt_id=aid,
                effect_identity=ei,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )
            glek = reservation.global_logical_effect_key

            self._protocol.persist_intent(
                attempt_id=aid,
                glek=glek,
                intent_payload=intent_payload,
                identity=ident,
                provenance=prov,
                adapter=adapter,
                versions=versions,
                grant_ref=grant_ref,
            )

            # Pass the provider idempotency key in the payload
            dispatch_payload = dict(intent_payload)
            dispatch_payload["_provider_idempotency_key"] = provider_key

            try:
                result = apply_fn(dispatch_payload)
            except Exception as exc:
                self._protocol.accept_outcome(
                    aid, glek, OUTCOME_FAILED,
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
                return GitOutcome(
                    ok=False,
                    shard=target.shard.value,
                    glek=glek,
                    outcome_kind=OUTCOME_FAILED,
                    error=str(exc),
                )

            self._protocol.accept_outcome(
                aid, glek, OUTCOME_COMPLETED,
                {"exit_code": 0, "provider_key": provider_key},
            )
            return GitOutcome(
                ok=True,
                shard=target.shard.value,
                glek=glek,
                outcome_kind=OUTCOME_COMPLETED,
                evidence={
                    "result": "ok",
                    "provider_key": provider_key,
                },
            )

        except Exception as exc:
            return GitOutcome(
                ok=False,
                shard=target.shard.value,
                glek="",
                outcome_kind=OUTCOME_INDETERMINATE,
                error=f"Protocol error: {type(exc).__name__}: {exc}",
            )


__all__ = [
    "GitEffectShard",
    "GIT_SHARD_13E2",
    "GIT_SHARD_13E3",
    "GIT_SHARD_13E4",
    "GIT_SHARD_13E5",
    "GIT_SHARD_13E6",
    "GIT_SHARD_13E8",
    "GitTarget",
    "GitOutcome",
    "GitEffectAdapter",
]
