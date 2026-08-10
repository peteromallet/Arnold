"""Active compatibility coverage independent of the deleted umbrella CLI facade."""

from arnold_pipelines.megaplan.cli import _normalize_execute_compat_argv


def test_normalize_execute_compat_argv_infers_missing_execute_for_execute_only_flags() -> None:
    assert _normalize_execute_compat_argv(
        ["--confirm-destructive", "--user-approved", "--retry-blocked-tasks"]
    ) == ["execute", "--confirm-destructive", "--user-approved", "--retry-blocked-tasks"]


def test_normalize_execute_compat_argv_infers_missing_execute_after_root_flags() -> None:
    assert _normalize_execute_compat_argv(
        [
            "--actor", "repair-loop-dev-fix", "--backend", "file",
            "--confirm-destructive", "--user-approved", "--retry-blocked-tasks",
        ]
    ) == [
        "--actor", "repair-loop-dev-fix", "--backend", "file", "execute",
        "--confirm-destructive", "--user-approved", "--retry-blocked-tasks",
    ]


def test_normalize_execute_compat_argv_infers_missing_execute_for_mixed_execute_tail() -> None:
    assert _normalize_execute_compat_argv(
        [
            "--actor", "repair-loop-dev-fix", "--backend", "file",
            "--confirm-destructive", "--user-approved", "--retry-blocked-tasks",
            "--plan", "m7-runtime-conformance-and-20260628-1118",
        ]
    ) == [
        "--actor", "repair-loop-dev-fix", "--backend", "file", "execute",
        "--confirm-destructive", "--user-approved", "--retry-blocked-tasks",
        "--plan", "m7-runtime-conformance-and-20260628-1118",
    ]
