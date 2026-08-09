"""Conservative AST-to-resumable-program lowering for native pipelines.

Parses the source of a ``@pipeline``-decorated function, recognises the
milestone grammar (sequential ``yield <phase>``, ``if <decision>``,
``while <guard>``), and emits a :class:`NativeProgram` with explicit
program counters and branch labels.

Unsupported Python constructs are rejected with :class:`NativeCompileError`
naming the offending AST node type.

Ownership:
    The compiler lowers ``.pypeline`` source topology into a
    :class:`NativeProgram`; the topology itself is owned by the
    ``.pypeline`` module and its named subworkflows.  Boundary contracts
    and boundary receipts are durable-effect declarations and checks — they
    are consumed by the compiler for evidence alignment but do not define
    or alter the program shape.
"""

from __future__ import annotations

import ast
import inspect
import threading
import textwrap
from typing import Any, Callable, Mapping, Sequence

from arnold.pipeline.native.decorators import (
    get_decision_meta,
    get_phase_meta,
    get_pipeline_meta,
    is_decision,
    is_phase,
    is_pipeline,
)
from arnold.pipeline.native.effect_taxonomy import derive_idempotency_key
from arnold.pipeline.native.ir import (
    NativeDecision,
    NativeInstruction,
    NativeLoopGuard,
    NativePhase,
    NativeProgram,
    ParallelInstruction,
    ParallelMapInstruction,
)
from arnold.pipeline.types import Port, PortRef


_COMPILE_STACK = threading.local()


class NativeCompileError(Exception):
    """Raised when the compiler encounters an unsupported construct."""

    def __init__(self, message: str, node: ast.AST | None = None) -> None:
        node_info = ""
        if node is not None:
            node_info = f" (AST node: {type(node).__name__}"
            if hasattr(node, "lineno"):
                node_info += f", line {node.lineno}"
            node_info += ")"
        super().__init__(f"{message}{node_info}")


# ── public entry point ────────────────────────────────────────────────


def compile_pipeline(pipeline_func: Callable[..., Any]) -> NativeProgram:
    """Compile a ``@pipeline``-decorated function into a :class:`NativeProgram`.

    Args:
        pipeline_func: A callable decorated with ``@pipeline``.

    Returns:
        A :class:`NativeProgram` with explicit PC-ordered instructions.

    Raises:
        NativeCompileError: If *pipeline_func* is not a pipeline or
            contains unsupported syntax.
        OSError: If source code cannot be retrieved.
    """
    if not is_pipeline(pipeline_func):
        raise NativeCompileError(
            f"Expected a @pipeline-decorated function, got {pipeline_func!r}",
        )

    meta = get_pipeline_meta(pipeline_func)
    if meta is None:  # pragma: no cover - defensive
        raise NativeCompileError("Pipeline metadata missing")

    pipeline_name: str = meta.get("name", pipeline_func.__name__)
    description: str = meta.get("description", "")
    compile_stack: list[tuple[int, str]] = getattr(_COMPILE_STACK, "stack", [])
    func_id = id(pipeline_func)
    if any(existing_id == func_id for existing_id, _ in compile_stack):
        cycle = [name for _, name in compile_stack] + [pipeline_name]
        raise NativeCompileError(f"Workflow cycle detected: {' -> '.join(cycle)}")
    _COMPILE_STACK.stack = [*compile_stack, (func_id, pipeline_name)]

    try:
        try:
            source = inspect.getsource(pipeline_func)
        except OSError as exc:
            # Source may have shifted on disk after the module was imported
            # (e.g. long-running process + edited file).  Fall back to reading the
            # whole source file and finding the function by name in the AST.
            source_file = inspect.getsourcefile(pipeline_func)
            if source_file is None:
                raise NativeCompileError(
                    f"Cannot retrieve source for pipeline {pipeline_name!r}: {exc}"
                ) from exc
            try:
                with open(source_file, encoding="utf-8") as fh:
                    source = fh.read()
            except OSError as read_exc:
                raise NativeCompileError(
                    f"Cannot retrieve source for pipeline {pipeline_name!r}: {read_exc}"
                ) from read_exc

        source = textwrap.dedent(source)
        tree = ast.parse(source)
        func_def = _find_function_def(tree, pipeline_func.__name__)

        # ── async def rejection (M4 settled decision) ──────────────────
        # M4 uses the existing sync generator subset.  Literal ``async def``
        # native pipelines are not required for milestone 4; if a future
        # milestone adds async, only compiler-level lowering (matching the
        # current grammar) is needed — not general async runtime scheduling.
        if func_def is None:
            # Check whether the function exists as an async def instead
            async_func_def = _find_async_function_def(tree, pipeline_func.__name__)
            if async_func_def is not None:
                raise NativeCompileError(
                    f"Async def pipeline {pipeline_name!r} is not supported in M4. "
                    "M4 uses the sync generator subset for native pipelines. "
                    "Use a regular ``def`` (not ``async def``) with ``yield <phase>(ctx)`` syntax.",
                    async_func_def,
                )
            raise NativeCompileError(
                f"Function {pipeline_name!r} not found in parsed source"
            )

        # Pass the pipeline function's globals so the compiler can resolve
        # module-level @phase/@decision references that live in the same module
        # as the @pipeline declaration.
        pipeline_globals: dict[str, Any] = getattr(pipeline_func, "__globals__", {})
        compiler = _Compiler(pipeline_name, pipeline_globals=pipeline_globals)
        compiler.lower_body(func_def.body)
        return compiler.emit(
            pipeline_func,
            description,
            stable_id=meta.get("id"),
            inputs_schema=meta.get("inputs"),
            outputs_schema=meta.get("outputs"),
        )
    finally:
        updated_stack = getattr(_COMPILE_STACK, "stack", [])
        if updated_stack:
            _COMPILE_STACK.stack = updated_stack[:-1]


# ── helpers ───────────────────────────────────────────────────────────


def _find_function_def(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    """Return the top-level ``FunctionDef`` named *name*, or None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _find_async_function_def(tree: ast.AST, name: str) -> ast.AsyncFunctionDef | None:
    """Return the top-level ``AsyncFunctionDef`` named *name*, or None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    return None


# ── compiler state machine ────────────────────────────────────────────


class _Compiler:
    """Internal compiler that walks the AST and emits instructions."""

    def __init__(self, pipeline_name: str, pipeline_globals: dict[str, Any] | None = None) -> None:
        self._pipeline_name = pipeline_name
        self._pipeline_globals: dict[str, Any] = pipeline_globals or {}
        self._instructions: list[NativeInstruction] = []
        self._phases: list[NativePhase] = []
        self._decisions: list[NativeDecision] = []
        self._loop_guards: list[NativeLoopGuard] = []
        self._parallel_blocks: list[ParallelInstruction] = []
        self._parallel_map_blocks: list[ParallelMapInstruction] = []
        self._pc: int = 0
        self._pending_halt: bool = False
        self._parallel_block_counter: int = 0

    def _build_native_phase(
        self,
        func: Callable[..., Any],
        *,
        fallback_name: str,
        call_site_path: tuple[str, ...] = (),
    ) -> NativePhase:
        """Build a NativePhase carrying additive decorator metadata."""
        meta = get_phase_meta(func)
        name = meta["name"] if meta else fallback_name
        # ── Side-effect metadata (M1) ──
        operation: str | None = meta.get("operation") if meta else None
        target: str | None = meta.get("target") if meta else None
        idempotency_key: str | None = meta.get("idempotency_key") if meta else None
        effect_class: str | None = meta.get("effect_class") if meta else None
        # Derive stable idempotency key when operation is declared but no
        # explicit key is supplied.
        if operation is not None and idempotency_key is None:
            step_path = self._derive_step_path(name, call_site_path)
            idempotency_key = derive_idempotency_key(step_path, operation, target)
        return NativePhase(
            name=name,
            func=func,
            stable_id=meta.get("id") if meta else None,
            inputs_schema=meta.get("inputs") if meta else None,
            outputs_schema=meta.get("outputs") if meta else None,
            produces=meta.get("produces", ()) if meta else (),
            consumes=meta.get("consumes", ()) if meta else (),
            operation=operation,
            target=target,
            idempotency_key=idempotency_key,
            effect_class=effect_class,
        )

    # ── emit helpers ──────────────────────────────────────────────

    def _emit(
        self,
        op: str,
        *,
        name: str = "",
        func: Callable[..., Any] | None = None,
        next_pc: int | None = None,
        branches: dict[str, int] | None = None,
        produces: tuple = (),
        consumes: tuple = (),
        decision_vocabulary: frozenset[str] | None = None,
        subprogram: Any | None = None,
        parallel_index: int | None = None,
        parallel_map_index: int | None = None,
        call_site_path: tuple[str, ...] = (),
        output_bindings: Mapping[str, str] | None = None,
        # ── Side-effect metadata (M1) ──
        operation: str | None = None,
        target: str | None = None,
        idempotency_key: str | None = None,
        effect_class: str | None = None,
    ) -> int:
        """Append an instruction and return its PC."""
        pc = self._pc
        instr = NativeInstruction(
            pc=pc,
            op=op,
            name=name,
            call_site_path=call_site_path,
            func=func,
            next_pc=next_pc,
            branches=dict(branches) if branches else {},
            output_bindings=dict(output_bindings) if output_bindings else {},
            produces=produces,
            consumes=consumes,
            decision_vocabulary=decision_vocabulary if decision_vocabulary is not None else frozenset(),
            subprogram=subprogram,
            parallel_index=parallel_index,
            parallel_map_index=parallel_map_index,
            operation=operation,
            target=target,
            idempotency_key=idempotency_key,
            effect_class=effect_class,
        )
        self._instructions.append(instr)
        self._pc = pc + 1
        return pc

    def _derive_step_path(
        self, phase_name: str, call_site_path: tuple[str, ...] = ()
    ) -> str:
        """Derive a stable compile-time step path for idempotency-key generation.

        Uses the pipeline name as the root prefix and appends any call-site
        path segments plus the phase name.  This path is stable across
        recompilations and is used only for key derivation — it is NOT the
        same as the runtime step path used for checkpoint addressing.
        """
        segments: list[str] = [self._pipeline_name]
        segments.extend(call_site_path)
        segments.append(phase_name)
        return "/".join(segments)

    def _emit_halt(self) -> None:
        if not self._pending_halt:
            self._emit("halt")
            self._pending_halt = True

    def _extract_call_site_path(self, call_node: ast.Call) -> tuple[str, ...]:
        for kw in call_node.keywords:
            if kw.arg != "id":
                continue
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return (kw.value.value,)
            raise NativeCompileError("Call-site id must be a string literal", kw.value)
        return ()

    def _schema_field_names(self, schema: Mapping[str, Any] | None) -> tuple[str, ...]:
        if not isinstance(schema, Mapping):
            return ()
        required = schema.get("required")
        if isinstance(required, Sequence) and not isinstance(required, (str, bytes)):
            fields = tuple(name for name in required if isinstance(name, str))
            if fields:
                return fields
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            return tuple(name for name in properties.keys() if isinstance(name, str))
        return ()

    def _schema_consumes(self, schema: Mapping[str, Any] | None) -> tuple[PortRef, ...]:
        return tuple(
            PortRef(port_name=name, content_type="application/json")
            for name in self._schema_field_names(schema)
        )

    def _schema_produces(self, schema: Mapping[str, Any] | None) -> tuple[Port, ...]:
        return tuple(
            Port(name=name, content_type="application/json")
            for name in self._schema_field_names(schema)
        )

    def _extract_output_bindings(self, call_node: ast.Call) -> dict[str, str]:
        for kw in call_node.keywords:
            if kw.arg not in {"outputs", "output_bindings"}:
                continue
            if not isinstance(kw.value, ast.Dict):
                raise NativeCompileError(
                    "Child output bindings must be a dict literal",
                    kw.value,
                )
            bindings: dict[str, str] = {}
            for key_node, value_node in zip(kw.value.keys, kw.value.values, strict=True):
                if not (
                    isinstance(key_node, ast.Constant)
                    and isinstance(key_node.value, str)
                    and isinstance(value_node, ast.Constant)
                    and isinstance(value_node.value, str)
                ):
                    raise NativeCompileError(
                        "Child output bindings must map string literals to string literals",
                        kw.value,
                    )
                bindings[key_node.value] = value_node.value
            return bindings
        return {}

    # ── resolution helpers ────────────────────────────────────────

    def _resolve_callable(self, node: ast.expr) -> Callable[..., Any]:
        """Resolve a callable from an AST expression node.

        Returns the callable object referenced by a ``Name`` or
        ``Attribute`` node.  Raises ``NativeCompileError`` for
        unsupported expressions.
        """
        if isinstance(node, ast.Name):
            name = node.id
            # Look up in the pipeline function's globals via the frame
            return self._lookup_name(name, node)
        if isinstance(node, ast.Attribute):
            raise NativeCompileError(
                f"Attribute calls ({ast.dump(node)}) are not supported in the milestone grammar",
                node,
            )
        raise NativeCompileError(
            f"Unsupported call target type: {type(node).__name__}",
            node,
        )

    def _lookup_name(self, name: str, node: ast.AST) -> Callable[..., Any]:
        """Look up *name* in the pipeline globals, then the calling frame's globals/locals."""
        # First, check the pipeline function's own module globals.
        # This allows @phase/@decision functions defined in the same module
        # as the @pipeline declaration to be resolved without frame walking.
        if name in self._pipeline_globals:
            candidate = self._pipeline_globals[name]
            if callable(candidate):
                return candidate

        frame = inspect.currentframe()
        try:
            # Walk up to the frame that called compile_pipeline
            while frame is not None:
                # The compile_pipeline caller is our target
                if frame.f_code.co_name == "compile_pipeline":
                    frame = frame.f_back
                    continue
                candidate = frame.f_globals.get(name) or frame.f_locals.get(name)  # type: ignore[arg-type]
                if candidate is not None and callable(candidate):
                    return candidate
                frame = frame.f_back
            raise NativeCompileError(
                f"Cannot resolve name {name!r} to a callable", node
            )
        finally:
            del frame

    # ── body lowering ─────────────────────────────────────────────

    def lower_body(self, body: list[ast.stmt]) -> None:
        """Lower a list of body statements (top-level, if-body, loop-body)."""
        for stmt in body:
            self._lower_stmt(stmt)

    def _lower_stmt(self, stmt: ast.stmt) -> None:
        """Dispatch a single statement to the correct lowerer."""
        if isinstance(stmt, ast.Expr):
            self._lower_expr_stmt(stmt)
        elif isinstance(stmt, ast.Assign):
            self._lower_assign_stmt(stmt)
        elif isinstance(stmt, ast.AnnAssign):
            self._lower_ann_assign_stmt(stmt)
        elif isinstance(stmt, ast.If):
            self._lower_if_stmt(stmt)
        elif isinstance(stmt, ast.While):
            self._lower_while_stmt(stmt)
        elif isinstance(stmt, ast.For):
            self._lower_for_stmt(stmt)
        elif isinstance(stmt, ast.Return):
            self._emit_halt()
        elif isinstance(stmt, ast.Pass):
            pass
        else:
            raise NativeCompileError(
                f"Unsupported statement type: {type(stmt).__name__}",
                stmt,
            )

    # ── expression / assignment lowering ──────────────────────────

    def _lower_expr_stmt(self, stmt: ast.Expr) -> None:
        """Handle a bare expression statement (may contain yield)."""
        self._lower_expr(stmt.value)

    def _lower_assign_stmt(self, stmt: ast.Assign) -> None:
        """Handle an assignment statement; value may contain yield."""
        self._lower_expr(stmt.value)

    def _lower_ann_assign_stmt(self, stmt: ast.AnnAssign) -> None:
        """Handle an annotated assignment; value may contain yield."""
        if stmt.value is not None:
            self._lower_expr(stmt.value)

    def _lower_expr(self, expr: ast.expr) -> None:
        """Lower an expression, recognising ``yield <phase_call>``."""
        if isinstance(expr, ast.Yield):
            self._lower_yield(expr)
        elif isinstance(expr, ast.Constant):
            # Literal — nothing to emit, e.g. '...'
            pass
        elif isinstance(expr, ast.Dict):
            for key in expr.keys:
                if key is not None:
                    self._lower_expr(key)
            for value in expr.values:
                self._lower_expr(value)
        elif isinstance(expr, ast.Tuple) or isinstance(expr, ast.List):
            for elt in expr.elts:
                self._lower_expr(elt)
        elif isinstance(expr, ast.Call):
            # Non-yield calls (e.g. ``results.append(r)`` inside a parallel body)
            # are allowed as no-ops; we just validate their arguments.
            self._lower_expr(expr.func)
            for arg in expr.args:
                self._lower_expr(arg)
            for kw in expr.keywords:
                self._lower_expr(kw.value)
        elif isinstance(expr, ast.Attribute):
            self._lower_expr(expr.value)
        elif isinstance(expr, ast.Name):
            pass
        elif isinstance(expr, ast.Subscript):
            self._lower_expr(expr.value)
            if expr.slice is not None:
                self._lower_expr(expr.slice)
        else:
            raise NativeCompileError(
                f"Unsupported expression type: {type(expr).__name__}",
                expr,
            )

    def _lower_yield(self, yield_node: ast.Yield) -> None:
        """Lower ``yield <call>`` where call is a decorated phase."""
        value = yield_node.value
        if value is None:
            raise NativeCompileError(
                "Bare 'yield' without a value is not supported", yield_node
            )
        if not isinstance(value, ast.Call):
            raise NativeCompileError(
                f"yield value must be a call to a @phase, got {type(value).__name__}",
                value,
            )

        func_node = value.func
        if not isinstance(func_node, ast.Name):
            raise NativeCompileError(
                "yield target must be a direct named @phase/@workflow/@pipeline callable; "
                "dynamic expressions are not supported",
                func_node,
            )
        try:
            func = self._resolve_callable(func_node)
        except NativeCompileError:
            raise
        except Exception as exc:
            raise NativeCompileError(
                f"Cannot resolve callable for yield: {exc}", func_node
            ) from exc

        if is_pipeline(func):
            if not isinstance(func_node, ast.Name):
                raise NativeCompileError(
                    "yielded child workflow must be a direct named @workflow/@pipeline callable",
                    func_node,
                )
            child_program = compile_pipeline(func)
            self._emit(
                "subpipeline",
                name=child_program.name,
                subprogram=child_program,
                call_site_path=self._extract_call_site_path(value),
                output_bindings=self._extract_output_bindings(value),
                consumes=self._schema_consumes(child_program.inputs_schema),
                produces=self._schema_produces(child_program.outputs_schema),
            )
            return

        if not is_phase(func):
            if callable(func) and getattr(func, "__name__", "") == "parallel":
                self._lower_yield_parallel(yield_node)
                return
            if callable(func) and getattr(func, "__name__", "") == "parallel_map":
                self._lower_yield_parallel_map(yield_node)
                return
            raise NativeCompileError(
                f"yield target {getattr(func, '__name__', func)!r} is not a @phase-decorated function",
                func_node,
            )

        phase_ir = self._build_native_phase(
            func,
            fallback_name=getattr(func, "__name__", "unknown"),
        )
        name = phase_ir.name

        # Track phase
        self._phases.append(phase_ir)

        # Emit phase instruction
        self._emit(
            "phase",
            name=name,
            func=func,
            produces=phase_ir.produces,
            consumes=phase_ir.consumes,
            operation=phase_ir.operation,
            target=phase_ir.target,
            idempotency_key=phase_ir.idempotency_key,
            effect_class=phase_ir.effect_class,
        )

    def _lower_yield_parallel(self, yield_node: ast.Yield) -> None:
        """Lower ``yield parallel([...])`` into one resumable parallel instruction.

        Validates the ``parallel(...)`` call via :meth:`_parse_parallel_call`,
        emits a single ``NativeInstruction(op='parallel')`` with no per-branch
        phase instructions or jumps, and sets ``merge_pc`` to the next sequential
        program counter.  The runtime uses the :class:`ParallelInstruction`
        metadata stored in ``subprogram`` for fan-out/fan-in.

        Branch order is deterministic — taken from the literal list/tuple in the
        AST.  Invalid reducers and non-``@phase`` branch callables are rejected
        at compile time.
        """
        value = yield_node.value
        assert isinstance(value, ast.Call), "_lower_yield already guards this"

        # Validate and extract branch metadata
        branch_funcs, branch_names, reducer, explicit_name, call_site_id = (
            self._parse_parallel_call(value, context_name="yield parallel(...)")
        )

        block_name = self._new_parallel_block_name(explicit_name)
        call_site_path: tuple[str, ...] = (call_site_id,) if call_site_id else ()

        # Emit a single parallel instruction — no per-branch phase instructions
        parallel_pc = self._emit(
            "parallel", name=block_name, call_site_path=call_site_path
        )
        merge_pc = self._pc  # next sequential PC after this instruction

        # Register each branch callable as a known phase (for metadata/reflection)
        for bf, bn in zip(branch_funcs, branch_names):
            self._phases.append(self._build_native_phase(bf, fallback_name=bn))

        # Build ParallelInstruction metadata and attach to the instruction
        parallel_index = len(self._parallel_blocks)
        parallel_block = ParallelInstruction(
            name=block_name,
            branches=tuple(branch_names),
            branch_funcs=tuple(branch_funcs),
            reducer=reducer,
            merge_pc=merge_pc,
        )
        self._parallel_blocks.append(parallel_block)

        # Patch the emitted instruction with subprogram and next_pc
        old = self._instructions[parallel_pc]
        self._instructions[parallel_pc] = NativeInstruction(
            pc=old.pc,
            op=old.op,
            name=old.name,
            call_site_path=old.call_site_path,
            func=old.func,
            next_pc=merge_pc,
            branches=old.branches,
            output_bindings=old.output_bindings,
            produces=old.produces,
            consumes=old.consumes,
            decision_vocabulary=old.decision_vocabulary,
            subprogram=parallel_block,
            parallel_index=parallel_index,
            parallel_map_index=old.parallel_map_index,
            operation=old.operation,
            target=old.target,
            idempotency_key=old.idempotency_key,
            effect_class=old.effect_class,
        )

    def _parse_parallel_map_call(
        self,
        call_node: ast.Call,
        *,
        context_name: str = "yield parallel_map(...)",
    ) -> tuple[str, Callable[..., Any], str, Callable[..., Any] | None, str | None]:
        try:
            func = self._resolve_callable(call_node.func)
        except NativeCompileError as exc:
            raise NativeCompileError(
                f"{context_name} must be a call to parallel_map(...); {exc}",
                call_node,
            ) from exc

        if not callable(func) or getattr(func, "__name__", "") != "parallel_map":
            raise NativeCompileError(
                f"{context_name} must be a call to parallel_map(...), got {getattr(func, '__name__', func)!r}",
                call_node.func,
            )
        if call_node.args:
            raise NativeCompileError(
                "parallel_map() requires keyword arguments only",
                call_node,
            )

        seen_keywords: set[str] = set()
        items_ref: str | None = None
        mapper: Callable[..., Any] | None = None
        path_template = ""
        reducer: Callable[..., Any] | None = None
        explicit_name: str | None = None

        for kw in call_node.keywords:
            if kw.arg is None:
                raise NativeCompileError("parallel_map() does not accept **kwargs", kw)
            if kw.arg in seen_keywords:
                raise NativeCompileError(
                    f"parallel_map() received duplicate keyword {kw.arg!r}",
                    kw,
                )
            seen_keywords.add(kw.arg)

            if kw.arg == "items":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    items_ref = kw.value.value
                else:
                    raise NativeCompileError(
                        "parallel_map() items must be a string literal reference",
                        kw.value,
                    )
            elif kw.arg == "step":
                if not isinstance(kw.value, ast.Name):
                    raise NativeCompileError(
                        "parallel_map() step must be a direct named callable",
                        kw.value,
                    )
                mapper = self._resolve_callable(kw.value)
                if not (is_phase(mapper) or is_pipeline(mapper)):
                    raise NativeCompileError(
                        "parallel_map() step must be a @phase/@workflow/@pipeline callable",
                        kw.value,
                    )
            elif kw.arg == "reducer":
                if not isinstance(kw.value, ast.Name):
                    raise NativeCompileError(
                        "parallel_map() reducer must be a direct named callable",
                        kw.value,
                    )
                reducer = self._resolve_callable(kw.value)
            elif kw.arg == "path_template":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    path_template = kw.value.value
                else:
                    raise NativeCompileError(
                        "parallel_map() path_template must be a string literal",
                        kw.value,
                    )
            elif kw.arg == "name":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    explicit_name = kw.value.value
                else:
                    raise NativeCompileError(
                        "parallel_map() name must be a string literal",
                        kw.value,
                    )
            elif kw.arg == "id":
                if not (
                    isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    raise NativeCompileError(
                        "parallel_map() id must be a string literal",
                        kw.value,
                    )
            else:
                raise NativeCompileError(
                    f"Unsupported parallel_map() keyword: {kw.arg!r}",
                    kw,
                )

        if items_ref is None:
            raise NativeCompileError("parallel_map() requires an items=... argument", call_node)
        if mapper is None:
            raise NativeCompileError("parallel_map() requires a step=... argument", call_node)
        return items_ref, mapper, path_template, reducer, explicit_name

    def _infer_parallel_map_collection_schema(
        self,
        mapper: Callable[..., Any],
    ) -> Mapping[str, Any] | None:
        """Best-effort static item schema for a ``parallel_map`` mapper."""
        if is_pipeline(mapper):
            meta = get_pipeline_meta(mapper)
        else:
            meta = get_phase_meta(mapper)
        if not isinstance(meta, Mapping):
            return None
        schema = meta.get("inputs")
        return schema if isinstance(schema, Mapping) else None

    def _new_parallel_map_block_name(self, explicit_name: str | None) -> str:
        if explicit_name:
            return explicit_name
        name = f"parallel_map_{self._parallel_block_counter}"
        self._parallel_block_counter += 1
        return name

    def _lower_yield_parallel_map(self, yield_node: ast.Yield) -> None:
        value = yield_node.value
        assert isinstance(value, ast.Call), "_lower_yield already guards this"

        items_ref, mapper, path_template, reducer, explicit_name = self._parse_parallel_map_call(
            value
        )
        block_name = self._new_parallel_map_block_name(explicit_name)
        mapper_name = getattr(mapper, "__name__", "mapper")
        call_site_path = self._extract_call_site_path(value) or (block_name,)

        parallel_map_pc = self._emit(
            "parallel_map",
            name=block_name,
            call_site_path=call_site_path,
        )
        merge_pc = self._pc
        if is_phase(mapper):
            self._phases.append(self._build_native_phase(mapper, fallback_name=mapper_name))

        parallel_map_index = len(self._parallel_map_blocks)
        parallel_map_block = ParallelMapInstruction(
            name=block_name,
            items_ref=items_ref,
            mapper=mapper,
            mapper_name=mapper_name,
            collection_schema=self._infer_parallel_map_collection_schema(mapper),
            reducer=reducer,
            path_template=path_template,
            merge_pc=merge_pc,
        )
        self._parallel_map_blocks.append(parallel_map_block)

        old = self._instructions[parallel_map_pc]
        self._instructions[parallel_map_pc] = NativeInstruction(
            pc=old.pc,
            op=old.op,
            name=old.name,
            call_site_path=old.call_site_path,
            func=old.func,
            next_pc=merge_pc,
            branches=old.branches,
            output_bindings=old.output_bindings,
            produces=old.produces,
            consumes=old.consumes,
            decision_vocabulary=old.decision_vocabulary,
            subprogram=parallel_map_block,
            parallel_index=old.parallel_index,
            parallel_map_index=parallel_map_index,
            operation=old.operation,
            target=old.target,
            idempotency_key=old.idempotency_key,
            effect_class=old.effect_class,
        )


    # ── if lowering ───────────────────────────────────────────────

    def _lower_if_stmt(self, stmt: ast.If) -> None:
        """Lower ``if <decision_call>`` with optional else.

        Handles both bare ``if decide(ctx):`` and
        ``if decide(ctx) == 'label':`` patterns.
        """
        test = stmt.test

        # Unwrap Compare nodes (e.g. ``decide(ctx) == 'yes'``)
        compare_label: str | None = None
        if isinstance(test, ast.Compare):
            # Extract the decision call from the comparison
            call_node = None
            if isinstance(test.left, ast.Call):
                call_node = test.left
            elif len(test.comparators) == 1 and isinstance(test.comparators[0], ast.Call):
                call_node = test.comparators[0]
            if call_node is None:
                raise NativeCompileError(
                    f"if test Compare must contain a call to a @decision, got {ast.dump(test)}",
                    test,
                )
            # Extract the comparison label if it's a constant
            for op_node, comp in zip(test.ops, test.comparators):
                if isinstance(op_node, ast.Eq) and isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    compare_label = comp.value
            test = call_node

        if not isinstance(test, ast.Call):
            raise NativeCompileError(
                f"if test must be a call to a @decision, got {type(test).__name__}",
                test,
            )

        func_node = test.func
        try:
            func = self._resolve_callable(func_node)
        except NativeCompileError:
            raise
        except Exception as exc:
            raise NativeCompileError(
                f"Cannot resolve callable for if test: {exc}", func_node
            ) from exc

        if not is_decision(func):
            raise NativeCompileError(
                f"if test target {getattr(func, '__name__', func)!r} is not a @decision-decorated function",
                func_node,
            )

        dec_meta = get_decision_meta(func)
        name = dec_meta["name"] if dec_meta else getattr(func, "__name__", "unknown")
        vocabulary: frozenset[str] = dec_meta.get("vocabulary", frozenset()) if dec_meta else frozenset()

        # Track decision
        self._decisions.append(
            NativeDecision(name=name, func=func, vocabulary=vocabulary)
        )

        # Emit decision instruction placeholder — branches filled after lowering
        decision_pc = self._emit(
            "decision",
            name=name,
            func=func,
            decision_vocabulary=vocabulary,
        )

        # Lower then-body
        then_start_pc = self._pc
        self._pending_halt = False
        self.lower_body(stmt.body)
        then_halts = self._pending_halt

        # After then-body, jump to merge point
        then_end_pc = self._pc
        if not then_halts:
            # We'll need a jump instruction to the merge point, but we don't
            # know the merge PC yet.  Emit a placeholder jump.
            jump_pc = self._emit("jump", name="if_then_exit")
        else:
            jump_pc = then_end_pc

        # Lower else-body (if present)
        else_start_pc = self._pc
        self._pending_halt = False
        if stmt.orelse:
            self.lower_body(stmt.orelse)
        else_halts = self._pending_halt if stmt.orelse else False

        # Merge point
        merge_pc = self._pc

        # Now patch the decision instruction with branch targets.
        # When a compare_label was extracted (e.g. ``if decide(ctx) == 'yes'``),
        # the then-branch targets that label and everything else goes to else.
        branches: dict[str, int] = {}
        if compare_label is not None:
            branches[compare_label] = then_start_pc
            # All other vocabulary labels go to else
            for label in vocabulary:
                if label != compare_label:
                    branches[label] = else_start_pc
            if not branches:
                branches = {compare_label: then_start_pc}
        elif vocabulary:
            vocab_list = sorted(vocabulary)
            if len(vocab_list) >= 2:
                branches[vocab_list[0]] = then_start_pc
                for label in vocab_list[1:]:
                    branches[label] = else_start_pc
            else:
                branches = {vocab_list[0]: then_start_pc}
        else:
            # No vocabulary — use truthy/falsy convention
            branches = {"__truthy__": then_start_pc, "__falsy__": else_start_pc}

        # Patch the decision instruction
        self._instructions[decision_pc] = NativeInstruction(
            pc=decision_pc,
            op="decision",
            name=name,
            func=func,
            branches=branches,
            produces=(),
            consumes=(),
            decision_vocabulary=vocabulary,
        )

        # Patch the then-exit jump to point to merge
        if not then_halts:
            self._instructions[jump_pc] = NativeInstruction(
                pc=jump_pc,
                op="jump",
                name="if_then_exit",
                next_pc=merge_pc,
                produces=(),
                consumes=(),
                decision_vocabulary=frozenset(),
            )
        self._pending_halt = then_halts and bool(stmt.orelse) and else_halts

    # ── while lowering ────────────────────────────────────────────

    def _lower_while_stmt(self, stmt: ast.While) -> None:
        """Lower ``while <guard_call>`` where guard is a decorated decision/guard.

        Handles both ``while guard(ctx):`` and ``while guard(ctx) == 'label':``.
        """
        test = stmt.test

        # Unwrap Compare nodes
        compare_label: str | None = None
        if isinstance(test, ast.Compare):
            call_node = None
            if isinstance(test.left, ast.Call):
                call_node = test.left
            elif len(test.comparators) == 1 and isinstance(test.comparators[0], ast.Call):
                call_node = test.comparators[0]
            if call_node is None:
                raise NativeCompileError(
                    f"while test Compare must contain a call to a guard, got {ast.dump(test)}",
                    test,
                )
            for op_node, comp in zip(test.ops, test.comparators):
                if isinstance(op_node, ast.Eq) and isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    compare_label = comp.value
            test = call_node

        if not isinstance(test, ast.Call):
            raise NativeCompileError(
                f"while test must be a call to a guard, got {type(test).__name__}",
                test,
            )

        func_node = test.func
        try:
            func = self._resolve_callable(func_node)
        except NativeCompileError:
            raise
        except Exception as exc:
            raise NativeCompileError(
                f"Cannot resolve callable for while test: {exc}", func_node
            ) from exc

        guard_name = getattr(func, "__name__", "unknown")

        if is_decision(func):
            dec_meta = get_decision_meta(func)
            name = dec_meta["name"] if dec_meta else guard_name
            vocabulary = dec_meta.get("vocabulary", frozenset()) if dec_meta else frozenset()
        elif is_phase(func):
            raise NativeCompileError(
                f"while test target {guard_name!r} is a @phase, not a @decision or guard",
                func_node,
            )
        else:
            raise NativeCompileError(
                f"while test target {guard_name!r} is not a @decision-decorated function",
                func_node,
            )

        # Pre-scan: reject unsupported constructs in the while body and
        # locate the ``yield <phase>`` call whose callable becomes the
        # :attr:`NativeLoopGuard.body`.
        body_func: Callable[..., Any] | None = None
        for body_stmt in stmt.body:
            if isinstance(body_stmt, ast.Break):
                raise NativeCompileError(
                    "'break' inside 'while' is not supported in the milestone grammar",
                    body_stmt,
                )
            if isinstance(body_stmt, ast.Continue):
                raise NativeCompileError(
                    "'continue' inside 'while' is not supported in the milestone grammar",
                    body_stmt,
                )
            if isinstance(body_stmt, (ast.Expr, ast.Assign)):
                value = body_stmt.value if isinstance(body_stmt, ast.Expr) else body_stmt.value
                if isinstance(value, ast.Yield) and isinstance(value.value, ast.Call):
                    try:
                        candidate = self._resolve_callable(value.value.func)
                        if is_phase(candidate) and body_func is None:
                            body_func = candidate
                    except NativeCompileError:
                        pass

        if body_func is None:
            raise NativeCompileError(
                "while loop body must contain at least one yield to a @phase",
                stmt,
            )

        # Create loop guard
        decision_meta = get_decision_meta(func)
        loop_guard = NativeLoopGuard(
            guard=func,
            body=body_func,
            name=name,
            stable_id=decision_meta.get("id") if isinstance(decision_meta, Mapping) else None,
        )
        self._loop_guards.append(loop_guard)

        # Emit: loop header (decision-like), body lowered via normal
        # statement lowering, then jump back to header.
        header_pc = self._emit(
            "decision",
            name=f"{name}_guard",
            func=func,
            decision_vocabulary=vocabulary,
        )

        # Body PC
        body_pc = self._pc
        self._pending_halt = False
        self.lower_body(stmt.body)
        body_halts = self._pending_halt

        # Jump back to header
        if not body_halts:
            self._emit("jump", name=f"{name}_loop_back", next_pc=header_pc)

        # Exit PC (after loop)
        exit_pc = self._pc

        # Patch header with branch targets.
        # When a compare_label was extracted, it maps to the body;
        # everything else exits.
        branches: dict[str, int] = {}
        if compare_label is not None:
            branches[compare_label] = body_pc
            for label in vocabulary:
                if label != compare_label:
                    branches[label] = exit_pc
        elif vocabulary:
            vocab_list = sorted(vocabulary)
            branches[vocab_list[0]] = body_pc
            for label in vocab_list[1:]:
                branches[label] = exit_pc
        else:
            branches = {"__truthy__": body_pc, "__falsy__": exit_pc}

        self._instructions[header_pc] = NativeInstruction(
            pc=header_pc,
            op="decision",
            name=f"{name}_guard",
            func=func,
            branches=branches,
            output_bindings={},
            produces=(),
            consumes=(),
            decision_vocabulary=vocabulary,
        )
        self._pending_halt = False

    # ── for / parallel lowering ───────────────────────────────────

    def _parse_parallel_call(
        self,
        call_node: ast.Call,
        *,
        context_name: str = "parallel(...)",
    ) -> tuple[list[Callable[..., Any]], list[str], Callable[..., Any] | None, str | None, str | None]:
        """Validate a ``parallel([...])`` call and return its components.

        Returns ``(branch_funcs, branch_names, reducer, explicit_name, call_site_id)``.
        Raises ``NativeCompileError`` for invalid branch sets, reducers, or
        unsupported keyword arguments.
        """
        # Resolve the callable (must be our parallel function)
        try:
            func = self._resolve_callable(call_node.func)
        except NativeCompileError as exc:
            raise NativeCompileError(
                f"{context_name} must be a call to parallel(...); {exc}",
                call_node,
            ) from exc
        except Exception as exc:
            raise NativeCompileError(
                f"{context_name} must be a call to parallel(...); "
                f"cannot resolve callable: {exc}", call_node
            ) from exc

        if not callable(func) or getattr(func, "__name__", "") != "parallel":
            raise NativeCompileError(
                f"{context_name} must be a call to parallel(...), "
                f"got {getattr(func, '__name__', func)!r}",
                call_node.func,
            )

        if not call_node.args:
            raise NativeCompileError(
                "parallel(...) requires at least one argument (the branch list)",
                call_node,
            )
        branch_arg = call_node.args[0]

        if isinstance(branch_arg, ast.List) or isinstance(branch_arg, ast.Tuple):
            branch_nodes = branch_arg.elts
        else:
            raise NativeCompileError(
                "parallel() argument must be a literal list or tuple of branches, "
                f"got {type(branch_arg).__name__}. "
                "Dynamic/non-literal branch sets are not supported.",
                branch_arg,
            )

        if not branch_nodes:
            raise NativeCompileError(
                "parallel() branch list must not be empty",
                branch_arg,
            )

        branch_funcs: list[Callable[..., Any]] = []
        branch_names: list[str] = []
        seen_ids: set[int] = set()
        for i, bn in enumerate(branch_nodes):
            try:
                bf = self._resolve_callable(bn)
            except NativeCompileError:
                raise
            except Exception as exc:
                raise NativeCompileError(
                    f"Cannot resolve parallel branch {i}: {exc}", bn
                ) from exc

            if not is_phase(bf):
                raise NativeCompileError(
                    f"parallel() branch {i} ({getattr(bf, '__name__', bf)!r}) "
                    "is not a @phase-decorated function",
                    bn,
                )

            bid = id(bf)
            if bid in seen_ids:
                raise NativeCompileError(
                    f"parallel() contains duplicate branch: "
                    f"{getattr(bf, '__name__', bf)!r}",
                    bn,
                )
            seen_ids.add(bid)
            branch_funcs.append(bf)
            meta = get_phase_meta(bf)
            branch_names.append(
                meta["name"] if meta else getattr(bf, "__name__", f"branch_{i}")
            )

        reducer: Callable[..., Any] | None = None
        explicit_name: str | None = None
        call_site_id: str | None = None
        for kw in call_node.keywords:
            if kw.arg == "reducer":
                try:
                    reducer = self._resolve_callable(kw.value)
                except NativeCompileError as exc:
                    raise NativeCompileError(
                        f"parallel() reducer must be callable: {exc}", kw.value
                    ) from exc
                except Exception as exc:
                    raise NativeCompileError(
                        f"Cannot resolve parallel reducer: {exc}", kw.value
                    ) from exc
                if not callable(reducer):
                    raise NativeCompileError(
                        "parallel() reducer must be callable", kw.value
                    )
            elif kw.arg == "name":
                if (
                    isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    explicit_name = kw.value.value
                else:
                    raise NativeCompileError(
                        "parallel() name must be a string literal", kw.value
                    )
            elif kw.arg == "id":
                if (
                    isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    call_site_id = kw.value.value
                else:
                    raise NativeCompileError(
                        "parallel() id must be a string literal", kw.value
                    )
            else:
                raise NativeCompileError(
                    f"Unsupported parallel() keyword: {kw.arg!r}", kw
                )

        return branch_funcs, branch_names, reducer, explicit_name, call_site_id

    def _new_parallel_block_name(self, explicit_name: str | None) -> str:
        if explicit_name:
            return explicit_name
        name = f"parallel_{self._parallel_block_counter}"
        self._parallel_block_counter += 1
        return name

    def _parse_native_panel_call(
        self,
        call_node: ast.Call,
    ) -> tuple:
        """Validate a native_panel(name, reviewers) call and return components.

        native_panel(name, (("id1", phase1), ("id2", phase2))) is a thin
        wrapper around parallel() that adds a collation reducer.
        This method extracts the phase callables and builds the same
        metadata that _parse_parallel_call would return.

        Returns (branch_funcs, branch_names, reducer, explicit_name, call_site_id).
        """
        call_site_id: str | None = None
        for kw in call_node.keywords:
            if kw.arg == "id":
                if (
                    isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    call_site_id = kw.value.value
                else:
                    raise NativeCompileError(
                        "native_panel() id must be a string literal", kw.value
                    )
            else:
                raise NativeCompileError(
                    f"Unsupported native_panel() keyword: {kw.arg!r}", kw
                )
        if len(call_node.args) < 2:
            raise NativeCompileError(
                "native_panel(...) requires at least two arguments "
                "(name, reviewers)",
                call_node,
            )

        # Resolve name
        name_arg = call_node.args[0]
        if (
            isinstance(name_arg, ast.Constant)
            and isinstance(name_arg.value, str)
        ):
            explicit_name = name_arg.value
        else:
            raise NativeCompileError(
                "native_panel() first argument must be a string literal name",
                name_arg,
            )

        # Resolve reviewers tuple
        reviewers_arg = call_node.args[1]
        if not isinstance(reviewers_arg, (ast.Tuple, ast.List)):
            raise NativeCompileError(
                "native_panel() second argument must be a literal tuple "
                "of (reviewer_id, callable) pairs, "
                f"got {type(reviewers_arg).__name__}",
                reviewers_arg,
            )

        pair_nodes = reviewers_arg.elts
        if not pair_nodes:
            raise NativeCompileError(
                "native_panel() reviewers tuple must not be empty",
                reviewers_arg,
            )

        branch_funcs = []
        branch_names = []
        seen_ids = set()
        reviewer_ids = []

        for i, pair_node in enumerate(pair_nodes):
            if not isinstance(pair_node, (ast.Tuple, ast.List)):
                raise NativeCompileError(
                    f"native_panel() reviewer {i} must be a "
                    f"(reviewer_id, callable) pair, "
                    f"got {type(pair_node).__name__}",
                    pair_node,
                )
            pair_elts = pair_node.elts
            if len(pair_elts) != 2:
                raise NativeCompileError(
                    f"native_panel() reviewer {i} pair must have exactly "
                    f"2 elements (reviewer_id, callable), "
                    f"got {len(pair_elts)}",
                    pair_node,
                )

            # Extract reviewer id (must be string literal)
            rid_node = pair_elts[0]
            if (
                isinstance(rid_node, ast.Constant)
                and isinstance(rid_node.value, str)
            ):
                rid = rid_node.value
            else:
                raise NativeCompileError(
                    f"native_panel() reviewer {i} id must be a "
                    f"string literal, got {type(rid_node).__name__}",
                    rid_node,
                )
            if not rid:
                raise NativeCompileError(
                    f"native_panel() reviewer {i} id must be non-empty",
                    rid_node,
                )
            reviewer_ids.append(rid)

            # Resolve the callable
            func_node = pair_elts[1]
            try:
                bf = self._resolve_callable(func_node)
            except NativeCompileError:
                raise
            except Exception as exc:
                raise NativeCompileError(
                    f"Cannot resolve native_panel reviewer {i} "
                    f"callable: {exc}",
                    func_node,
                ) from exc

            if not is_phase(bf):
                raise NativeCompileError(
                    f"native_panel() reviewer {i} "
                    f"({getattr(bf, '__name__', bf)!r}) "
                    "is not a @phase-decorated function",
                    func_node,
                )

            bid = id(bf)
            if bid in seen_ids:
                raise NativeCompileError(
                    f"native_panel() contains duplicate callable: "
                    f"{getattr(bf, '__name__', bf)!r}",
                    func_node,
                )
            seen_ids.add(bid)
            branch_funcs.append(bf)
            meta = get_phase_meta(bf)
            branch_names.append(
                meta["name"] if meta else getattr(bf, "__name__", f"branch_{i}")
            )

        # Build collation reducer
        def _panel_reducer(results):
            outputs = {}
            for rid, result in zip(reviewer_ids, results):
                if isinstance(result, dict):
                    for label, value in result.items():
                        outputs[f"{rid}.{label}"] = value
            return outputs

        return branch_funcs, branch_names, _panel_reducer, explicit_name, call_site_id


    def _lower_for_stmt(self, stmt: ast.For) -> None:
        """Lower ``for <var> in parallel([...])`` or
        ``for <var> in native_panel(...)`` as a parallel fan-out block.

        The iterable must be a call to :func:`parallel` with a literal
        list/tuple of ``@phase``-decorated callables, or a call to
        :func:`native_panel` with a tuple of ``(reviewer_id, callable)``
        pairs.  Dynamic, empty, duplicate, and non-literal branch sets
        are rejected.
        """
        iter_node = stmt.iter
        if not isinstance(iter_node, ast.Call):
            raise NativeCompileError(
                "For loop iterable must be a call to parallel(...) "
                "or native_panel(...); "
                f"got {type(iter_node).__name__}",
                iter_node,
            )

        # Determine which helper is being called
        try:
            func = self._resolve_callable(iter_node.func)
        except NativeCompileError as exc:
            raise NativeCompileError(
                f"For loop iterable must be a call to parallel(...) "
                f"or native_panel(...); {exc}",
                iter_node,
            ) from exc
        except Exception as exc:
            raise NativeCompileError(
                "For loop iterable must be a call to parallel(...) "
                f"or native_panel(...); cannot resolve callable: {exc}",
                iter_node,
            ) from exc

        func_name = getattr(func, "__name__", "")

        if func_name == "parallel":
            (
                branch_funcs,
                branch_names,
                reducer,
                explicit_name,
                call_site_id,
            ) = self._parse_parallel_call(
                iter_node, context_name="For loop iterable"
            )
        elif func_name == "native_panel":
            (
                branch_funcs,
                branch_names,
                reducer,
                explicit_name,
                call_site_id,
            ) = self._parse_native_panel_call(iter_node)
        else:
            raise NativeCompileError(
                "For loop iterable must be a call to parallel(...) "
                f"or native_panel(...), got {func_name!r}",
                iter_node.func,
            )
        block_name = self._new_parallel_block_name(explicit_name)
        call_site_path: tuple[str, ...] = (call_site_id,) if call_site_id else ()

        # Emit the parallel instruction as a placeholder; its metadata is
        # patched after branch bodies are lowered.  At runtime the marker is a
        # no-op, so sequential fall-through executes the inlined bodies.
        parallel_pc = self._emit(
            "parallel", name=block_name, call_site_path=call_site_path
        )

        # Lower each branch body with the corresponding callable substituted.
        # For the M5a sequential baseline, branches are emitted back-to-back
        # after the parallel marker and execute in declaration order.
        branch_start_pcs: list[int] = []
        for bf in branch_funcs:
            branch_start_pcs.append(self._pc)
            self._pending_halt = False
            target_var = stmt.target
            if not isinstance(target_var, ast.Name):
                raise NativeCompileError(
                    "for loop target must be a simple name", target_var
                )
            self._lower_for_body_with_substitution(
                stmt.body, target_var.id, bf
            )

        # Merge point is the PC immediately after the last branch body.
        merge_pc = self._pc

        # Create the ParallelInstruction metadata and patch the marker.
        parallel_index = len(self._parallel_blocks)
        parallel_block = ParallelInstruction(
            name=block_name,
            branches=tuple(branch_names),
            branch_funcs=tuple(branch_funcs),
            reducer=reducer,
            merge_pc=merge_pc,
        )
        self._parallel_blocks.append(parallel_block)
        old_marker = self._instructions[parallel_pc]
        self._instructions[parallel_pc] = NativeInstruction(
            pc=old_marker.pc,
            op=old_marker.op,
            name=old_marker.name,
            func=old_marker.func,
            next_pc=old_marker.next_pc,
            branches=old_marker.branches,
            output_bindings=old_marker.output_bindings,
            produces=old_marker.produces,
            consumes=old_marker.consumes,
            decision_vocabulary=old_marker.decision_vocabulary,
            subprogram=parallel_block,
            parallel_index=parallel_index,
        )

    def _lower_for_body_with_substitution(
        self,
        body: list[ast.stmt],
        var_name: str,
        substitute_func: Callable[..., Any],
    ) -> None:
        """Lower a for-loop body with the iteration variable substituted.

        Temporarily adds *substitute_func* to ``_pipeline_globals`` under
        *var_name* so that ``_resolve_callable`` can find it when the body
        contains ``yield <var_name>(ctx)``.
        """
        # Save the old globals entry (if any) and inject the substitute
        old_value = self._pipeline_globals.get(var_name)
        self._pipeline_globals[var_name] = substitute_func
        try:
            for stmt in body:
                self._lower_stmt(stmt)
        finally:
            # Restore the old globals entry
            if old_value is not None:
                self._pipeline_globals[var_name] = old_value
            else:
                self._pipeline_globals.pop(var_name, None)

    # ── final assembly ────────────────────────────────────────────

    def emit(
        self,
        pipeline_func: Callable[..., Any],
        description: str,
        *,
        stable_id: str | None,
        inputs_schema: dict[str, Any] | None,
        outputs_schema: dict[str, Any] | None,
    ) -> NativeProgram:
        """Assemble and return the final :class:`NativeProgram`."""
        self._emit_halt()

        # Fix up sequential next_pc links for non-branch instructions
        for i, instr in enumerate(self._instructions):
            if instr.op in ("phase", "jump", "parallel", "parallel_map", "subpipeline") and instr.next_pc is None:
                next_pc = i + 1
                if next_pc < len(self._instructions):
                    self._instructions[i] = NativeInstruction(
                        pc=instr.pc,
                        op=instr.op,
                        name=instr.name,
                        call_site_path=instr.call_site_path,
                        func=instr.func,
                        next_pc=next_pc,
                        branches=instr.branches,
                        output_bindings=instr.output_bindings,
                        produces=instr.produces,
                        consumes=instr.consumes,
                        decision_vocabulary=instr.decision_vocabulary,
                        subprogram=instr.subprogram,
                        parallel_index=instr.parallel_index,
                        parallel_map_index=instr.parallel_map_index,
                        operation=instr.operation,
                        target=instr.target,
                        idempotency_key=instr.idempotency_key,
                        effect_class=instr.effect_class,
                    )

        program = NativeProgram(
            name=self._pipeline_name,
            stable_id=stable_id,
            inputs_schema=inputs_schema,
            outputs_schema=outputs_schema,
            instructions=tuple(self._instructions),
            phases=tuple(self._phases),
            decisions=tuple(self._decisions),
            loop_guards=tuple(self._loop_guards),
            parallel_blocks=tuple(self._parallel_blocks),
            parallel_map_blocks=tuple(self._parallel_map_blocks),
            description=description,
        )
        from arnold.pipeline.native.graph_projection import derive_topology

        return NativeProgram(
            name=program.name,
            stable_id=program.stable_id,
            inputs_schema=program.inputs_schema,
            outputs_schema=program.outputs_schema,
            instructions=program.instructions,
            phases=program.phases,
            decisions=program.decisions,
            loop_guards=program.loop_guards,
            parallel_blocks=program.parallel_blocks,
            parallel_map_blocks=program.parallel_map_blocks,
            routing_topology=program.routing_topology,
            topology=derive_topology(program),
            description=program.description,
        )
