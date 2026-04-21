from __future__ import annotations

from megaplan.cloud.providers.base import _logs_follow


class _LineStream:
    def __init__(self, owner) -> None:
        self._owner = owner
        self._lines = [
            "OPENAI_API_KEY=supersecretvalue\n",
            "tail ghp_abc123456789\n",
        ]
        self._index = 0

    def readline(self) -> str:
        self._owner.readline_calls += 1
        if self._index >= len(self._lines):
            return ""
        if self._index == 1:
            assert self._owner.output == ["OPENAI_API_KEY=***REDACTED***\n"]
        line = self._lines[self._index]
        self._index += 1
        return line

    def read(self) -> str:
        return ""


class _FakeProc:
    def __init__(self) -> None:
        self.output: list[str] = []
        self.readline_calls = 0
        self.stdout = _LineStream(self)

    def wait(self) -> int:
        return 0


def test_logs_follow_redacts_each_line_before_reading_the_next(
    monkeypatch,
) -> None:
    proc = _FakeProc()
    writes: list[str] = []

    class _Stdout:
        def write(self, chunk: str) -> None:
            writes.append(chunk)
            proc.output.append(chunk)

    monkeypatch.setattr(
        "megaplan.cloud.providers.base.subprocess.Popen",
        lambda *args, **kwargs: proc,
    )
    monkeypatch.setattr("megaplan.cloud.providers.base.sys.stdout", _Stdout())

    assert _logs_follow(
        ["docker", "logs", "-f", "agent"],
        secret_names=["OPENAI_API_KEY"],
        env={"OPENAI_API_KEY": "supersecretvalue"},
    ) == 0

    assert proc.readline_calls >= 3
    assert writes == ["OPENAI_API_KEY=***REDACTED***\n", "tail ***REDACTED***\n"]
