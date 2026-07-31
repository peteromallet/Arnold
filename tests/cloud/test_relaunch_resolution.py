from arnold_pipelines.megaplan.cloud.relaunch_resolution import (
    is_stale_marker_relaunch_command,
    marker_relaunch_command,
)


def test_all_paths_share_byte_identical_marker_admission() -> None:
    marker = {
        "relaunch_command": "if true; then python -m arnold_pipelines.megaplan chain start; fi"
    }
    assert marker_relaunch_command(marker) == marker["relaunch_command"]
    assert marker_relaunch_command(marker) == marker_relaunch_command(dict(marker))


def test_cutover_stale_marker_is_rejected_for_regeneration() -> None:
    stale = "{ set -e; git pull origin main; pip install -e /workspace/old; }"
    assert is_stale_marker_relaunch_command(stale)
    assert marker_relaunch_command({"relaunch_command": stale}) is None
