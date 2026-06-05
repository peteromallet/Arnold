from __future__ import annotations

import io
import socket
import time
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

import auto_improve.probe_keys as probe_keys


TEST_URL = probe_keys.ZHIPU_ENDPOINT


class FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b""):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


def _http_error(code: int, message: str, *, reason: str = "error") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        TEST_URL,
        code,
        reason,
        {},
        io.BytesIO(message.encode("utf-8")),
    )


def _status(key: str, status: probe_keys.Status) -> probe_keys.KeyStatus:
    return probe_keys.KeyStatus(
        key=key,
        provider="zhipu",
        status=status,
        detail="detail",
        reset_at=None,
        masked_key=f"{key[:8]}...{key[-4:]}",
    )


def test_probe_key_classifies_alive() -> None:
    with mock.patch("auto_improve.probe_keys.urllib.request.urlopen", return_value=FakeResponse(status=200)):
        result = probe_keys.probe_key("alive-key-123456")

    assert result.status == "alive"
    assert result.reset_at is None


def test_probe_key_classifies_exhausted_and_parses_reset() -> None:
    error = _http_error(429, "quota exhausted, reset at 2026-04-08 11:55:35", reason="Too Many Requests")
    with mock.patch("auto_improve.probe_keys.urllib.request.urlopen", side_effect=error):
        result = probe_keys.probe_key("exhausted-key-123456")

    assert result.status == "exhausted"
    assert result.reset_at == "2026-04-08 11:55:35"


@pytest.mark.parametrize("code", [401, 403])
def test_probe_key_classifies_invalid(code: int) -> None:
    error = _http_error(code, "invalid auth", reason="Unauthorized")
    with mock.patch("auto_improve.probe_keys.urllib.request.urlopen", side_effect=error):
        result = probe_keys.probe_key(f"invalid-key-{code}-123456")

    assert result.status == "invalid"


def test_probe_key_classifies_unreachable_timeout() -> None:
    with mock.patch("auto_improve.probe_keys.urllib.request.urlopen", side_effect=socket.timeout()):
        result = probe_keys.probe_key("timeout-key-123456")

    assert result.status == "unreachable"
    assert result.reset_at is None


def test_load_candidate_keys_dedupes_json_and_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "home"
    hermes_dir = fake_home / ".hermes"
    hermes_dir.mkdir(parents=True)
    (hermes_dir / ".env").write_text(
        "ZHIPU_API_KEY=json-key-123456\n"
        "ZHIPU_API_KEY_1='env-key-654321'\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_keys,
        "_load_api_keys_json",
        lambda _: ["json-key-123456", "json-key-abcdef", "json-key-123456"],
    )
    monkeypatch.setattr(probe_keys.Path, "home", classmethod(lambda cls: fake_home))

    assert probe_keys.load_candidate_keys() == [
        "json-key-123456",
        "json-key-abcdef",
        "env-key-654321",
    ]


def test_alive_keys_preserves_alive_order() -> None:
    results = [
        _status("alive-key-aaaa1111", "alive"),
        _status("dead-key-bbbb2222", "invalid"),
        _status("alive-key-cccc3333", "alive"),
    ]

    assert probe_keys.alive_keys(results) == [
        "alive-key-aaaa1111",
        "alive-key-cccc3333",
    ]


def test_format_status_table_masks_raw_keys() -> None:
    results = [
        probe_keys.KeyStatus(
            key="secret-key-aaaa1111",
            provider="zhipu",
            status="alive",
            detail="all good",
            reset_at=None,
            masked_key="secret-k...1111",
        ),
        probe_keys.KeyStatus(
            key="secret-key-bbbb2222",
            provider="zhipu",
            status="exhausted",
            detail="quota exhausted",
            reset_at="2026-04-08 11:55:35",
            masked_key="secret-k...2222",
        ),
    ]

    rendered = probe_keys.format_status_table(results, assignments={"secret-key-aaaa1111": "worker-0"})

    assert "secret-k...1111" in rendered
    assert "secret-k...2222" in rendered
    for result in results:
        assert result.key not in rendered


def test_main_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    alive_result = [_status("alive-key-123456", "alive")]
    dead_result = [_status("dead-key-123456", "unreachable")]

    monkeypatch.setattr(probe_keys, "probe_all_keys", lambda **_: alive_result)
    assert probe_keys.main([]) == 0

    monkeypatch.setattr(probe_keys, "probe_all_keys", lambda **_: dead_result)
    assert probe_keys.main([]) == 1


def test_probe_keys_runs_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_probe_key(key: str, *, provider: str = "zhipu", timeout: float = 5.0) -> probe_keys.KeyStatus:
        time.sleep(0.3)
        return probe_keys.KeyStatus(
            key=key,
            provider=provider,
            status="alive",
            detail="ok",
            reset_at=None,
            masked_key=f"{key[:8]}...{key[-4:]}",
        )

    keys = [f"parallel-key-{index:02d}-123456" for index in range(5)]
    monkeypatch.setattr(probe_keys, "probe_key", fake_probe_key)

    single_start = time.perf_counter()
    fake_probe_key(keys[0])
    single_duration = time.perf_counter() - single_start

    parallel_start = time.perf_counter()
    results = probe_keys.probe_keys(keys)
    parallel_duration = time.perf_counter() - parallel_start

    assert [result.key for result in results] == keys
    assert parallel_duration < single_duration * 2
