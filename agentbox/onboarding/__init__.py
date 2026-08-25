"""First-run provider onboarding: detect what already exists, never leak secrets.

Heavy submodules (catalog/detect/wire/flow) load lazily via PEP 562 so that
``agentbox.onboarding.guards`` — the stdlib-only leaf the `arnold` launcher
imports on EVERY startup — stays cheap. Accessing any name below triggers
the corresponding import on first use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - editor support only
    from agentbox.onboarding.catalog import PROVIDERS, RANK_ORDER, ProviderSpec
    from agentbox.onboarding.detect import (
        Origin,
        ProviderScan,
        ScanReport,
        parse_env_file,
        scan_providers,
    )
    from agentbox.onboarding.wire import (
        VerifyResult,
        WireResult,
        record_provenance,
        verify_route,
        wire_api_key,
        wire_cli_proxy,
        wire_oauth,
    )

__all__ = [
    "PROVIDERS",
    "RANK_ORDER",
    "Origin",
    "ProviderScan",
    "ProviderSpec",
    "ScanReport",
    "parse_env_file",
    "scan_providers",
    "VerifyResult",
    "WireResult",
    "wire_api_key",
    "wire_cli_proxy",
    "wire_oauth",
]

_LAZY_MAP = {
    "PROVIDERS": ("agentbox.onboarding.catalog", "PROVIDERS"),
    "RANK_ORDER": ("agentbox.onboarding.catalog", "RANK_ORDER"),
    "ProviderSpec": ("agentbox.onboarding.catalog", "ProviderSpec"),
    "Origin": ("agentbox.onboarding.detect", "Origin"),
    "ProviderScan": ("agentbox.onboarding.detect", "ProviderScan"),
    "ScanReport": ("agentbox.onboarding.detect", "ScanReport"),
    "parse_env_file": ("agentbox.onboarding.detect", "parse_env_file"),
    "scan_providers": ("agentbox.onboarding.detect", "scan_providers"),
    "VerifyResult": ("agentbox.onboarding.wire", "VerifyResult"),
    "WireResult": ("agentbox.onboarding.wire", "WireResult"),
    "record_provenance": ("agentbox.onboarding.wire", "record_provenance"),
    "verify_route": ("agentbox.onboarding.wire", "verify_route"),
    "wire_api_key": ("agentbox.onboarding.wire", "wire_api_key"),
    "wire_cli_proxy": ("agentbox.onboarding.wire", "wire_cli_proxy"),
    "wire_oauth": ("agentbox.onboarding.wire", "wire_oauth"),
}


def __getattr__(name: str):  # noqa: ANN201 - PEP 562 dynamic attribute
    try:
        module_name, attr = _LAZY_MAP[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, attr)
