"""First-run provider onboarding: detect what already exists, never leak secrets."""

from __future__ import annotations

from agentbox.onboarding.catalog import (
    PROVIDERS,
    RANK_ORDER,
    ProviderSpec,
)
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
