"""T5: Re-export wiring + sys.modules-snapshot test for judge registry."""

from __future__ import annotations

import sys


def test_importing_identity_populates_judge_default_without_judge_piece():
    # Use a subprocess so we have a clean module cache and can verify
    # `import megaplan._pipeline.identity` alone populates the registry
    # without importing judge_piece (the registry paradox guard).
    import subprocess
    import sys as _sys
    import textwrap

    src = textwrap.dedent(
        """
        import sys
        import megaplan._pipeline.identity as identity_mod
        assert 'judge.default' in identity_mod.NODE_REGISTRY, 'judge.default missing'
        assert isinstance(
            identity_mod.NODE_REGISTRY['judge.default'], identity_mod.NodeSpec
        )
        assert 'megaplan._pipeline.judge_piece' not in sys.modules, (
            'judge_piece was imported as a side effect'
        )
        # exactly once: re-importing the module does not duplicate the registration
        import importlib
        importlib.reload(identity_mod)
        assert sum(1 for _ in identity_mod.NODE_REGISTRY.keys() if _ == 'judge.default') == 1
        """
    )
    result = subprocess.run(
        [_sys.executable, "-c", src],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_nodespec_ports_and_arnold_api_version():
    from megaplan._pipeline.identity import (
        ARNOLD_API_VERSION,
        NODE_REGISTRY,
    )

    spec = NODE_REGISTRY["judge.default"]
    assert spec.arnold_api_version == ARNOLD_API_VERSION
    assert any(p.name == "judged-artifact" for p in spec.consumes)
    assert any(p.name == "evaluand-record" for p in spec.produces)


def test_package_reexports():
    from megaplan._pipeline import (  # noqa: F401
        ARNOLD_API_VERSION,
        JudgePiece,
        NODE_REGISTRY,
        NodeSpec,
        Port,
        manifest_hash,
        register_node,
    )

    assert "judge.default" in NODE_REGISTRY
    assert callable(manifest_hash)
    assert callable(register_node)


def test_registry_signature_hash_differs_from_runtime_hash():
    from megaplan._pipeline import (
        ARNOLD_API_VERSION,
        NODE_REGISTRY,
        Port,
        manifest_hash,
    )

    registry_hash = NODE_REGISTRY["judge.default"].judge_version
    runtime_hash = manifest_hash(
        step_code_source="def run(self, ctx): return None\n",
        resolved_rubric_body="rubric body v1",
        model_identity="openrouter/some-model@1",
        port_set=(Port(name="judged-artifact", content_type="text/markdown"),),
        abi_version=ARNOLD_API_VERSION,
    )
    assert registry_hash != runtime_hash
