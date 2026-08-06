"""Canonical safety policy embedded in every automatic fixer prompt."""

from __future__ import annotations


PROCESS_CUSTODY_FAIL_CLOSED_POLICY = """
## Process custody — hard fail-closed invariant

You may terminate, cancel, signal, clean up, or otherwise destroy an agent or
process only when exact durable evidence proves that this same acting agent/run
launched that exact target. The evidence must bind the acting run identity, the
target's exact durable managed-run/manifest identity, and the supported
lifecycle operation. Mere discovery by `pgrep`, `ps`, name or command matching,
a shared workspace or session, apparent duplication, or inference is never
launch provenance and never authorizes a signal or cleanup.

Never signal or destroy yourself; your launcher, parent, or any ancestor; your
child/descendant custody stack; the process holding your durable goal; or any
process owned by another run. If exact launch provenance and target identity
cannot be proven, do nothing and report the ambiguity. Prefer supported,
manifest-targeted lifecycle operations. Broad `pgrep`-derived kill lists and
ad-hoc cleanup signals are prohibited.
""".strip()


def render_process_custody_policy() -> str:
    """Return the canonical immutable prompt fragment for fixer composition."""

    return PROCESS_CUSTODY_FAIL_CLOSED_POLICY




PROFILE_INTEGRITY_POLICY = """
## Profile integrity — keep the configured profile; never re-route phases

The configured chain/plan profile (for example ``partnered-5-glm``) and its
``phase_model`` are authoritative and must be preserved. Never change a phase
model, vendor, or provider to work around a missing credential, a routing
failure, or any other infrastructure issue. In particular, never re-route
``execute`` (or any other phase) from its configured provider/model to a
different model (for example codex/gpt-5.6-sol) as a workaround.

If a phase fails because a configured provider lacks credentials or is
unreachable:
- source the canonical environment file (for example ``set -a; . /workspace/.cloud-hot-env; set +a``)
  so the configured provider's key reaches the workers; or
- fix the environment plumbing that loads the provider credential; or
- report the provider as genuinely unavailable (a stop condition).

If you change any plan/chain config to diagnose an issue, switch it back to the
configured profile before continuing. Never leave a profile mutation behind.
""".strip()


def render_profile_integrity_policy() -> str:
    """Return the canonical profile-integrity prompt fragment for fixers."""

    return PROFILE_INTEGRITY_POLICY


__all__ = [
    "PROCESS_CUSTODY_FAIL_CLOSED_POLICY",
    "PROFILE_INTEGRITY_POLICY",
    "render_process_custody_policy",
    "render_profile_integrity_policy",
]
