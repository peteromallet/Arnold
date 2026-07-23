from __future__ import annotations

from pathlib import Path


WRAPPER = (
    Path(__file__).parents[2]
    / "arnold_pipelines"
    / "megaplan"
    / "cloud"
    / "wrappers"
    / "arnold-run"
)


def test_arnold_run_sources_durable_hot_env_for_both_launch_paths() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    source = ". /workspace/.cloud-hot-env"

    tmux_fast_path = text.index('if [[ -n "${TMUX:-}" ]]')
    launch = text.index("tmux new-session")

    assert text.count(source) == 2
    assert text.index(source) < tmux_fast_path
    assert text.index(source, launch) > launch
    assert text.index(source, launch) < text.index("${QUOTED}", launch)
