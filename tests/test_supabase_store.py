from __future__ import annotations

import os

import pytest


psycopg = pytest.importorskip("psycopg")

if not os.environ.get("SUPABASE_TEST_DB_URL"):
    pytest.skip("SUPABASE_TEST_DB_URL is not set", allow_module_level=True)

from agent_kit.store.supabase import SupabaseStore  # noqa: E402
from tests.store_contract import run_store_contract  # noqa: E402
from tests.store_contract_v1b import run_store_contract_v1b  # noqa: E402


def _store_factory():
    store = SupabaseStore(os.environ["SUPABASE_TEST_DB_URL"])
    conn = psycopg.connect(os.environ["SUPABASE_TEST_DB_URL"])
    _truncate(conn)
    return store, conn


def test_supabase_store_contracts() -> None:
    run_store_contract(_store_factory)
    run_store_contract_v1b(_store_factory)


def _truncate(conn) -> None:
    with conn:
        conn.execute(
            """
            TRUNCATE TABLE
              external_requests,
              tool_calls,
              messages,
              bot_turns,
              system_logs,
              epic_locks,
              images,
              epics
            RESTART IDENTITY CASCADE
            """
        )
