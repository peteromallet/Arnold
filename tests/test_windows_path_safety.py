"""Reject tracked paths that cannot be checked out on Windows."""

import subprocess
from pathlib import Path


def test_tracked_paths_are_windows_checkout_safe() -> None:
    root = Path(__file__).parents[1]
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root, text=False
    )
    paths = output.decode().split("\0")[:-1]
    illegal = set('<>:"/\\|?*')
    bad = [
        path
        for path in paths
        if any(any(char in illegal or ord(char) < 32 for char in part)
               for part in path.split("/"))
    ]
    assert not bad, f"Windows-illegal tracked path components: {bad!r}"
