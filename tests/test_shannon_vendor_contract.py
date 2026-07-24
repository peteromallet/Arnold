from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.profiles import load_profiles
from arnold_pipelines.megaplan.workers import shannon


_SENTINEL = "MEGAPLAN_SHANNON_VENDORED v1"
_REQUIRED_RUNTIME_FILES = {
    "VENDOR.md",
    "bun.lock",
    "index.ts",
    "package.json",
    "tsconfig.json",
}


def test_vetted_shannon_fork_is_in_the_runtime_package() -> None:
    vendor_root = shannon.VENDORED_SHANNON_PATH.parent

    assert shannon.VENDORED_SHANNON_PATH.is_file()
    assert _SENTINEL in "\n".join(
        shannon.VENDORED_SHANNON_PATH.read_text(encoding="utf-8").splitlines()[:5]
    )
    assert _REQUIRED_RUNTIME_FILES <= {
        path.name for path in vendor_root.iterdir() if path.is_file()
    }

    # Exercise the same fail-closed boundary every real Claude/Shannon launch
    # crosses. Reset the process cache so this assertion cannot pass because a
    # prior test already populated it.
    shannon._shannon_vendor_sentinel_ok = False
    shannon._assert_vendored_shannon_sentinel()
    assert shannon._shannon_vendor_sentinel_ok is True


def test_claude_gate_and_finalize_routes_reach_the_shannon_adapter() -> None:
    profiles = load_profiles()
    all_claude = profiles["all-claude"]

    assert all_claude["gate"] == "claude"
    assert all_claude["finalize"] == "claude"

    # The default Arnold dispatcher registers both public spellings on the
    # Shannon adapter. This proves the profile route and worker route meet.
    import arnold.agent as agent_module

    dispatcher = agent_module._default
    assert isinstance(dispatcher._adapters["claude"], type(dispatcher._adapters["shannon"]))
    assert dispatcher._adapters["claude"]._session_agent == "claude"
    assert dispatcher._adapters["shannon"]._session_agent == "shannon"


def test_vendor_path_is_inside_imported_megaplan_package() -> None:
    package_root = Path(shannon.__file__).resolve().parents[1]
    assert shannon.VENDORED_SHANNON_PATH.is_relative_to(package_root)
