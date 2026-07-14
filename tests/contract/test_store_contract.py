"""Collected contract tests that drive the store-contract helpers.

The helpers in ``tests/contract/_store_contract.py`` define the cross-backend
store contract (explicit epic IDs, generated default IDs, idempotency replay,
relationship semantics, adapter surface, and error-class parity).  Because the
helper module is prefixed with ``_`` it is treated as a private helper and
pytest collects no tests from it directly.  This module provides the collected
``test_*`` entry points so the contract is exercised by the standard test
selector — including the explicit-epic-ID and relationship-kind contract claims
landed for the ticket/epic lifecycle integration.

The factory uses :class:`FileStore`, which exercises the file-backed
implementation of the ``Store`` protocol.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.contract._store_contract import (
    make_file_store_factory,
    run_arnold_adapter_contract,
    run_store_contract,
    run_ticket_relationship_contract,
)


@pytest.fixture
def file_store_factory(tmp_path: Path):
    """Return a fresh-``FileStore`` factory scoped to a per-test temp dir."""
    return make_file_store_factory(tmp_path)


def test_store_contract_explicit_ids_and_idempotency(file_store_factory) -> None:
    """run_store_contract proves explicit IDs, default IDs, and retry behavior."""
    run_store_contract(file_store_factory)


def test_arnold_adapter_contract_epic_ids(file_store_factory) -> None:
    """run_arnold_adapter_contract proves adapter explicit/generated epic IDs."""
    run_arnold_adapter_contract(file_store_factory)


def test_ticket_relationship_contract(file_store_factory) -> None:
    """run_ticket_relationship_contract proves relationship semantics + auto-address gating."""
    run_ticket_relationship_contract(file_store_factory)
