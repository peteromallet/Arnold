"""Pytest config for the Node Resolution Epic acceptance suite.

Registers the per-sprint markers so `pytest -m sprint_a` works without warnings.
The human-readable contract lives in
``docs/megaplan_chains/node_resolution_epic/testing/testing.md``.
"""


def pytest_configure(config):
    for sprint in ("a", "b", "c"):
        config.addinivalue_line(
            "markers",
            f"sprint_{sprint}: acceptance gate that must pass after Sprint "
            f"{sprint.upper()} (see testing.md).",
        )
