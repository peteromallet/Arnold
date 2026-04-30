from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from typing import Any

from agent_kit.store.sqlite import SQLiteStore


def create_store(path: Path) -> tuple[SQLiteStore, sqlite3.Connection]:
    store = SQLiteStore(path)
    return store, store._conn


def insert_epic(conn: sqlite3.Connection, epic_id: str = "epic_1") -> str:
    conn.execute(
        """
        INSERT INTO epics (id, title, goal, body, state)
        VALUES (?, ?, ?, ?, ?)
        """,
        (epic_id, "Title", "Goal", "# Title", "shaping"),
    )
    conn.commit()
    return epic_id


def env_with_fake_model(script: list[dict[str, Any]]) -> dict[str, str]:
    import json

    env = os.environ.copy()
    env["ARNOLD_FAKE_MODEL_SCRIPT"] = json.dumps(script)
    env["ARNOLD_FAKE_MODEL_SEED"] = "integration"
    return env

