"""Compatibility shim for the historic native runner module path."""

from arnold.pipeline.native.runtime import run_native_pipeline


class NativeMegaplanRunner:
    """Thin adapter preserving the legacy call surface used by tests."""

    def run_native_pipeline(self, **kwargs):
        return run_native_pipeline(**kwargs)
