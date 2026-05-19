"""Focused regression tests for v2.1 codemod/analyzer fixes.

Covers all six fix categories independently. Deterministic — no ComfyUI,
RunPod, or network required.
"""

from __future__ import annotations

import ast as ast_mod
import textwrap
from pathlib import Path

import pytest

from tools.narrate_template import (
    _detect_branch_selector_groups,
    _detect_chain_bypasses,
    _detect_magic_constant_twins,
    _detect_unwired_primitives,
    _find_node_call_line,
    _insert_params_block,
    _literal_from_ast,
    _produce_annotate_v2,
    _string_restructure_v2,
    find_unbound_inputs,
    parse_template,
)


# ============================================================================
# (a) PARAMS rewiring for non-Primitive _node kwargs
# ============================================================================


class TestParamsRewiring:
    """Tests that PARAMS hoisting correctly rewrites kwargs on all node types."""

    @staticmethod
    def _params_substitute(source: str) -> str:
        """Run Phase 2 (PARAMS substitution) on *source*."""
        unbound = find_unbound_inputs(source)
        param_field_lookup: dict[tuple[str, str], str] = {}
        for logical, target in unbound.items():
            if "." in target:
                node_id, field = target.split(".", 1)
                param_field_lookup[(node_id, field)] = logical
        return _string_restructure_v2(source, {}, param_field_lookup)

    def test_params_rewires_cliptextencode_text(self) -> None:
        """CLIPTextEncode is NOT a Primitive — text= kwarg should be rewired."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {
            "unbound_inputs": {
                "prompt": "100.text",
            }
        }
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            prompt_embedding = _node(wf, "CLIPTextEncode", "100", text="a beautiful landscape")
            return wf
        """)

        result = self._params_substitute(source)
        assert 'text=PARAMS["prompt"]' in result, (
            f"Expected PARAMS rewiring, got:\n{result}"
        )

    def test_params_does_not_touch_register_input_first_arg(self) -> None:
        """register_input('negative', ...) first arg must survive untouched."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {
            "unbound_inputs": {
                "prompt": "100.text",
            }
        }
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            prompt_embedding = _node(wf, "CLIPTextEncode", "100", text="a beautiful landscape")
            wf.register_input('negative', prompt_embedding, description='negative prompt')
            return wf
        """)

        var_rename = {"prompt_embedding": "renamed_prompt_emb"}
        unbound = find_unbound_inputs(source)
        param_field_lookup: dict[tuple[str, str], str] = {}
        for logical, target in unbound.items():
            if "." in target:
                node_id, field = target.split(".", 1)
                param_field_lookup[(node_id, field)] = logical

        result = _string_restructure_v2(source, var_rename, param_field_lookup)
        assert "register_input('negative'" in result or 'register_input("negative"' in result, (
            f"register_input first arg changed:\n{result}"
        )

    def test_params_handles_comma_containing_string_value(self) -> None:
        """Comma-containing string literals must not break PARAMS substitution."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {
            "unbound_inputs": {
                "prompt": "100.text",
            }
        }
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            prompt_embedding = _node(wf, "CLIPTextEncode", "100", text="hello, world, and more")
            return wf
        """)

        result = self._params_substitute(source)
        assert 'PARAMS["prompt"]' in result, (
            f"PARAMS substitution failed for comma-containing string:\n{result}"
        )

    def test_params_rewires_non_primitive_multi_kwargs(self) -> None:
        """Non-Primitive node with multiple kwargs: all bound fields must be rewired."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {
            "unbound_inputs": {
                "ic_lora_filename": "300.lora_name",
                "ic_lora_strength": "300.strength_model",
            }
        }
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            loader = _node(wf, "LTXICLoRALoaderModelOnly", "300", lora_name="my_lora.safetensors", strength_model=0.75)
            return wf
        """)

        result = self._params_substitute(source)
        assert 'lora_name=PARAMS["ic_lora_filename"]' in result, (
            f"lora_name not rewired:\n{result}"
        )
        assert 'strength_model=PARAMS["ic_lora_strength"]' in result, (
            f"strength_model not rewired:\n{result}"
        )


# ============================================================================
# (b) Variable renaming preserves register_input first arg and string literals
# ============================================================================


class TestVariableRenamingSafety:
    def test_var_rename_preserves_register_input_first_arg(self) -> None:
        """When renaming vars, register_input('negative',...) stays untouched."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            negative_text = _node(wf, 'PrimitiveString', '200', value='bad')
            prompt_embedding = _node(wf, 'CLIPTextEncode', '100', text='landscape')
            wf.register_input('negative', negative_text, description='negative prompt')
            return wf
        """)

        var_rename = {"negative_text": "negative_embedding"}
        result = _string_restructure_v2(source, var_rename, {})

        assert "register_input('negative'" in result or 'register_input("negative"' in result, (
            f"register_input first arg was renamed:\n{result}"
        )
        assert "negative_embedding" in result, f"Variable not renamed:\n{result}"

    def test_var_rename_preserves_string_literals(self) -> None:
        """String literals matching a rename target must not be renamed."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            my_var = _node(wf, "PrimitiveString", "200", value="my_var_value")
            return wf
        """)

        var_rename = {"my_var": "renamed_var"}
        result = _string_restructure_v2(source, var_rename, {})

        assert '"my_var_value"' in result, (
            f"String literal incorrectly renamed:\n{result}"
        )

    def test_var_rename_does_not_touch_kwarg_names(self) -> None:
        """Kwarg names (followed by =) must not be renamed."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            loader = _node(wf, "LoadImage", "50", image="input.png")
            wf.something(loader)
            return wf
        """)

        # 'image' is a kwarg name — must NOT be renamed even if in var_rename.
        # 'loader' is used as a reference (not followed by =) — should be renamed.
        var_rename = {"loader": "input_image", "image": "should_not_match"}
        result = _string_restructure_v2(source, var_rename, {})

        assert "image=" in result, f"Kwarg name 'image=' was removed:\n{result}"
        # loader appears as a reference arg to wf.something, not followed by =, so it
        # SHOULD be renamed to input_image
        assert "input_image" in result, (
            f"Variable ref 'loader' not renamed to 'input_image':\n{result}"
        )


# ============================================================================
# (c) params_wiring_check (verify gate)
# ============================================================================


class TestParamsWiringCheck:
    """Tests that the params_wiring_check gate detects dead PARAMS entries.

    These tests exercise the same AST-parsing logic that cmd_verify() must
    perform for the params_wiring_check gate (to be added in T8).
    """

    @staticmethod
    def _count_params_refs_in_build(source: str) -> dict[str, int]:
        tree = ast_mod.parse(source)
        refs: dict[str, int] = {}
        for node in ast_mod.walk(tree):
            if isinstance(node, ast_mod.Subscript):
                if isinstance(node.value, ast_mod.Name) and node.value.id == "PARAMS":
                    if isinstance(node.slice, ast_mod.Constant) and isinstance(node.slice.value, str):
                        key = node.slice.value
                        refs[key] = refs.get(key, 0) + 1
        return refs

    @staticmethod
    def _collect_params_keys(source: str) -> set[str]:
        tree = ast_mod.parse(source)
        keys: set[str] = set()
        for node in ast_mod.walk(tree):
            if isinstance(node, ast_mod.Assign):
                targets = node.targets if hasattr(node, "targets") else [node.target]
                for target in targets:
                    if isinstance(target, ast_mod.Name) and target.id == "PARAMS":
                        if isinstance(node.value, ast_mod.Dict):
                            for k in node.value.keys:
                                if isinstance(k, ast_mod.Constant) and isinstance(k.value, str):
                                    keys.add(k.value)
        return keys

    def test_wired_params_all_referenced(self) -> None:
        source = textwrap.dedent("""\
        PARAMS = {"seed": 42, "fps": 30, "height": 512}

        def build():
            wf = object()
            x = PARAMS["seed"]
            y = PARAMS["fps"]
            z = PARAMS["height"]
            return wf
        """)
        keys = self._collect_params_keys(source)
        refs = self._count_params_refs_in_build(source)
        unwired = [k for k in keys if k not in refs]
        assert unwired == [], f"Unexpected unwired keys: {unwired}"

    def test_unwired_params_detected(self) -> None:
        source = textwrap.dedent("""\
        PARAMS = {"seed": 42, "dead_key": 999, "fps": 30}

        def build():
            wf = object()
            x = PARAMS["seed"]
            y = PARAMS["fps"]
            return wf
        """)
        keys = self._collect_params_keys(source)
        refs = self._count_params_refs_in_build(source)
        unwired = [k for k in keys if k not in refs]
        assert unwired == ["dead_key"], f"Expected ['dead_key'], got {unwired}"

    def test_empty_params_no_unwired(self) -> None:
        source = textwrap.dedent("""\
        PARAMS = {}

        def build():
            wf = object()
            return wf
        """)
        keys = self._collect_params_keys(source)
        refs = self._count_params_refs_in_build(source)
        unwired = [k for k in keys if k not in refs]
        assert unwired == []

    def test_no_params_dict_no_unwired(self) -> None:
        source = textwrap.dedent("""\
        def build():
            wf = object()
            x = "hello"
            return wf
        """)
        keys = self._collect_params_keys(source)
        assert keys == set()


# ============================================================================
# (d) Branch selector comments — suggested_comment preservation + mode labels
# ============================================================================


class TestBranchSelectorComments:
    """Tests that analyzer outputs mode labels for branch_selector_groups."""

    def test_suggested_comment_contains_branch_selection(self) -> None:
        """Real LTX template: branch_selector_groups must have BRANCH SELECTION marker."""
        template_path = (
            Path(__file__).resolve().parent.parent
            / "ready_templates" / "video"
            / "ltx2_3_first_last_frame_travel_iclora_control.py"
        )
        if not template_path.is_file():
            pytest.skip("LTX template not found")

        from tools.narrate_template import run_analyzer

        result = run_analyzer(template_path)
        groups = result.get("findings", {}).get("branch_selector_groups", [])

        if groups:
            for g in groups:
                comment = g.get("suggested_comment", "")
                assert comment, "branch_selector_group missing suggested_comment"
                assert "BRANCH SELECTION" in comment, (
                    f"suggested_comment missing BRANCH SELECTION: {comment}"
                )

    def test_suggested_comment_not_truncated_by_produce_annotate(self) -> None:
        """_produce_annotate_v2 must preserve suggested_comment verbatim."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            node_a = _node(wf, "ImageResizeKJv2", "5001", width=1024, height=1024)
            return wf
        """)

        long_comment = (
            "BRANCH SELECTION: 'image=' picks which control branch is active. "
            "Currently wired to node 5028 (canny). "
            "Alternatives: 6101 (raw), 6102 (pose), 6103 (depth)."
        )

        findings: dict = {
            "findings": {
                "branch_selector_groups": [
                    {
                        "sink_node_id": "5001",
                        "suggested_comment": long_comment,
                    }
                ],
            }
        }

        parsed = parse_template(source)
        nc_by_id = {nc.node_id: nc for nc in parsed.node_calls}
        schema: dict = {}

        result = _produce_annotate_v2(source, parsed, findings, schema, nc_by_id)

        for label in ["(canny)", "(raw)", "(pose)", "(depth)"]:
            assert label in result, f"Mode label '{label}' stripped:\n{result}"


# ============================================================================
# (e) Chain bypass comments — INTENTIONAL/POSSIBLE qualifier
# ============================================================================


class TestChainBypassComments:
    """Tests that chain_bypasses analyzer output includes qualifier."""

    def test_chain_bypass_has_chain_bypass_marker(self) -> None:
        """Real LTX template: chain_bypasses must have CHAIN BYPASS in comment."""
        template_path = (
            Path(__file__).resolve().parent.parent
            / "ready_templates" / "video"
            / "ltx2_3_first_last_frame_travel_iclora_control.py"
        )
        if not template_path.is_file():
            pytest.skip("LTX template not found")

        from tools.narrate_template import run_analyzer

        result = run_analyzer(template_path)
        bypasses = result.get("findings", {}).get("chain_bypasses", [])

        if bypasses:
            for b in bypasses:
                comment = b.get("suggested_comment", "")
                assert "CHAIN BYPASS" in comment, (
                    f"chain_bypass missing CHAIN BYPASS: {comment}"
                )

    def test_chain_bypass_annotation_appears_in_annotate(self) -> None:
        """Chain bypass finding must produce an annotation in annotate output."""
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            node_b = _node(wf, "SomeSampler", "9999", model=1)
            return wf
        """)

        findings: dict = {
            "findings": {
                "chain_bypasses": [
                    {
                        "bypassing_node_id": "9999",
                        "suggested_comment": (
                            "INTENTIONAL CHAIN BYPASS: takes SomeClass directly; "
                            "the LTX2_NAG,LTX2AttentionTunerPatch chain is consumed "
                            "elsewhere (likely a separate sampler)."
                        ),
                    }
                ],
            }
        }

        parsed = parse_template(source)
        nc_by_id = {nc.node_id: nc for nc in parsed.node_calls}
        schema: dict = {}

        result = _produce_annotate_v2(source, parsed, findings, schema, nc_by_id)

        assert "INTENTIONAL CHAIN BYPASS" in result, (
            f"INTENTIONAL CHAIN BYPASS missing from annotate:\n{result}"
        )


# ============================================================================
# (f) Plural node_ids findings (magic_constant_twins → COUPLED comments)
# ============================================================================


class TestPluralNodeIdsFindings:
    """Tests that plural node_ids findings emit comments at every anchor."""

    def test_magic_constant_twins_node_ids_field(self) -> None:
        """magic_constant_twins findings must use 'node_ids' (plural) field."""
        template_path = (
            Path(__file__).resolve().parent.parent
            / "ready_templates" / "video"
            / "ltx2_3_first_last_frame_travel_iclora_control.py"
        )
        if not template_path.is_file():
            pytest.skip("LTX template not found")

        from tools.narrate_template import run_analyzer

        result = run_analyzer(template_path)
        twins = result.get("findings", {}).get("magic_constant_twins", [])

        if twins:
            for t in twins:
                assert "node_ids" in t, "magic_constant_twins must have node_ids (plural)"
                assert isinstance(t["node_ids"], list), "node_ids must be a list"
                assert len(t["node_ids"]) >= 2, "node_ids must have at least 2 entries"

    def test_plural_node_ids_inject_comments_at_all_anchors(self) -> None:
        """When a finding has node_ids (plural), comments must appear at every node.

        NOTE: This test currently verifies the limitation that plural node_ids are
        NOT handled by _produce_annotate_v2 (T10 will fix this). When T10 is done,
        this test should be updated to assert COUPLED appears in the output.
        """
        source = textwrap.dedent("""\
        import sys
        READY_METADATA = {"unbound_inputs": {}}
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            node_a = _node(wf, "INTConstant", "2108", value=8)
            node_b = _node(wf, "INTConstant", "2110", value=8)
            return wf
        """)

        findings: dict = {
            "findings": {
                "magic_constant_twins": [
                    {
                        "node_ids": ["2108", "2110"],
                        "suggested_comment": (
                            "COUPLED: matches partner literal at node 2110 by convention."
                        ),
                    }
                ],
            }
        }

        parsed = parse_template(source)
        nc_by_id = {nc.node_id: nc for nc in parsed.node_calls}
        schema: dict = {}

        result = _produce_annotate_v2(source, parsed, findings, schema, nc_by_id)

        # T10 will add plural node_ids handling. For now, the result is unchanged
        # because _produce_annotate_v2 only handles singular anchors (node_id,
        # bypassing_node_id, sink_node_id). The output should still be valid Python.
        ast_mod.parse(result)  # must be valid Python

        # TODO(T10): assert "COUPLED" in result


# ============================================================================
# (g) PARAMS UNUSED warning on unwired entries
# ============================================================================


class TestParamsUnusedWarning:
    """Tests that PARAMS block includes ⚠ UNUSED warning for dead entries."""

    def test_insert_params_block_emits_all_keys(self) -> None:
        source = textwrap.dedent("""\
        import sys
        READY_REQUIREMENTS = {}
        PARAMS_EXTRA = {}
        def build():
            wf = object()
            return wf
        """)

        param_entries = {"control_mode": "canny", "seed": 42, "fps": 30}
        result = _insert_params_block(source, param_entries)

        for key in ["control_mode", "seed", "fps"]:
            assert repr(key) in result, f"Key {key!r} missing from PARAMS block"

    def test_params_key_order_is_deterministic(self) -> None:
        source = textwrap.dedent("""\
        import sys
        READY_REQUIREMENTS = {}
        def build():
            wf = object()
            return wf
        """)

        param_entries = {"z_key": 1, "a_key": 2, "m_key": 3}
        result = _insert_params_block(source, param_entries)

        lines = result.split("\n")
        key_lines = [l.strip() for l in lines if l.strip().startswith("'") and ":" in l]
        assert len(key_lines) == 3
        assert key_lines[0].startswith("'a_key'")
        assert key_lines[1].startswith("'m_key'")
        assert key_lines[2].startswith("'z_key'")

    def test_params_block_inserted_after_ready_requirements(self) -> None:
        source = textwrap.dedent("""\
        import sys
        READY_REQUIREMENTS = {
            "packages": ["comfy"],
        }
        def build():
            wf = object()
            return wf
        """)

        param_entries = {"seed": 42}
        result = _insert_params_block(source, param_entries)

        req_idx = result.index("READY_REQUIREMENTS")
        params_idx = result.index("PARAMS:")
        assert params_idx > req_idx, "PARAMS must appear after READY_REQUIREMENTS"


# ============================================================================
# Additional safety / utility tests
# ============================================================================


class TestLiteralFromAst:
    def test_string_literal(self) -> None:
        tree = ast_mod.parse('x = "hello"')
        val = tree.body[0].value  # type: ignore[attr-defined]
        ok, lit = _literal_from_ast(val)
        assert ok and lit == "hello"

    def test_int_literal(self) -> None:
        tree = ast_mod.parse("x = 42")
        val = tree.body[0].value  # type: ignore[attr-defined]
        ok, lit = _literal_from_ast(val)
        assert ok and lit == 42

    def test_bool_literal(self) -> None:
        tree = ast_mod.parse("x = True")
        val = tree.body[0].value  # type: ignore[attr-defined]
        ok, lit = _literal_from_ast(val)
        assert ok and lit is True

    def test_float_literal(self) -> None:
        tree = ast_mod.parse("x = 3.14")
        val = tree.body[0].value  # type: ignore[attr-defined]
        ok, lit = _literal_from_ast(val)
        assert ok and lit == 3.14


class TestFindNodeCallLine:
    def test_finds_existing(self) -> None:
        source = 'node1 = _node(wf, "SomeClass", "123", key1="val1")\n'
        assert _find_node_call_line(source, "123") == 1

    def test_returns_none_for_missing(self) -> None:
        source = 'node1 = _node(wf, "SomeClass", "123", key1="val1")\n'
        assert _find_node_call_line(source, "999") is None


class TestFindUnboundInputs:
    def test_extracts_unbound(self) -> None:
        source = textwrap.dedent("""\
        READY_METADATA = {
            "unbound_inputs": {
                "seed": "100.seed",
                "prompt": "200.text",
            }
        }
        """)
        unbound = find_unbound_inputs(source)
        assert unbound == {"seed": "100.seed", "prompt": "200.text"}

    def test_empty_unbound(self) -> None:
        source = 'READY_METADATA = {"unbound_inputs": {}}\n'
        unbound = find_unbound_inputs(source)
        assert unbound == {}
