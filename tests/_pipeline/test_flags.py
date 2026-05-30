"""Unit tests for megaplan._pipeline.flags."""

from __future__ import annotations

import os
from unittest.mock import patch

from megaplan._pipeline.flags import typed_ports_on


class TestTypedPortsOn:
    """Three canonical cases: on (env='1'), off (env='0'), missing."""

    def test_on_when_env_is_1(self) -> None:
        with patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"}):
            assert typed_ports_on() is True

    def test_off_when_env_is_0(self) -> None:
        with patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "0"}):
            assert typed_ports_on() is False

    def test_off_when_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert typed_ports_on() is False
