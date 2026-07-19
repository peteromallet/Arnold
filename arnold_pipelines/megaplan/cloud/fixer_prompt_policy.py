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


__all__ = [
    "PROCESS_CUSTODY_FAIL_CLOSED_POLICY",
    "render_process_custody_policy",
]
