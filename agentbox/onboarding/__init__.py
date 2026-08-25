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

__all__ = [
    "PROVIDERS",
    "RANK_ORDER",
    "Origin",
    "ProviderScan",
    "ProviderSpec",
    "ScanReport",
    "parse_env_file",
    "scan_providers",
]
