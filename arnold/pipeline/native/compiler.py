"""Conservative AST-to-resumable-program lowering for native pipelines.

Parses the source of a ``@pipeline``-decorated function, recognises the
milestone grammar (sequential ``yield <phase>``, ``if <decision>``,
``while <guard>``), and emits a :class:`NativeProgram` with explicit
program counters and branch labels.

Unsupported Python constructs are rejected with :class:`NativeCompileError`
naming the offending AST node type.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any, Callable, Sequence

from arnold.pipeline.native.decorators import (
    get_decision_meta,
    get_phase_meta,
    get_pipeline_meta,
    is_decision,
    is_phase,
    is_pipeline,
)
from arnold.pipeline.native.ir import (
    NativeDecision,
    NativeInstruction,
    NativeLoopGuard,
    NativePhase,
    NativeProgram,
    ParallelInstruction,
)


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

    try:
        source = inspect.getsource(pipeline_func)
        source = textwrap.dedent(source)
    except OSError as exc:
        raise NativeCompileError(
            f"Cannot retrieve source for pipeline {pipeline_name!r}: {exc}"
        ) from exc

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
    pipeline_globals: dict[str, Any] = getattr(pipeline_func, '__globals__', {})
    compiler = _Compiler(pipeline_name, pipeline_globals=pipeline_globals)
    compiler.lower_body(func_def.body)
    return compiler.emit(pipeline_func, description)


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
        self._pc: int = 0
        self._pending_halt: bool = False
        self._parallel_block_counter: int = 0

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
    ) -> int:
        """Append an instruction and return its PC."""
        pc = self._pc
        instr = NativeInstruction(
            pc=pc,
            op=op,
            name=name,
            func=func,
            next_pc=next_pc,
            branches=dict(branches) if branches else {},
            produces=produces,
            consumes=consumes,
            decision_vocabulary=decision_vocabulary if decision_vocabulary is not None else frozenset(),
        )
        self._instructions.append(instr)
        self._pc = pc + 1
        return pc

    def _emit_halt(self) -> None:
        if not self._pending_halt:
            self._emit("halt")
            self._pending_halt = True

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
        try:
            func = self._resolve_callable(func_node)
        except NativeCompileError:
            raise
        except Exception as exc:
            raise NativeCompileError(
                f"Cannot resolve callable for yield: {exc}", func_node
            ) from exc

        if not is_phase(func):
            # Special-case the common mistake ``yield parallel([...])`` so the
            # diagnostic points users to the supported ``for`` syntax.
            if (
                callable(func)
                and getattr(func, "__name__", "") == "parallel"
            ):
                raise NativeCompileError(
                    "yield parallel([...]) is not supported. "
                    "Use the fan-out syntax: "
                    "for branch in parallel([phase_a, phase_b]): state = yield branch(ctx)",
                    func_node,
                )
            raise NativeCompileError(
                f"yield target {getattr(func, '__name__', func)!r} is not a @phase-decorated function",
                func_node,
            )

        meta = get_phase_meta(func)
        name = meta["name"] if meta else getattr(func, "__name__", "unknown")

        # Extract typed port metadata from phase decorator
        phase_produces = meta.get("produces", ()) if meta else ()
        phase_consumes = meta.get("consumes", ()) if meta else ()

        # Track phase
        self._phases.append(NativePhase(name=name, func=func, produces=phase_produces, consumes=phase_consumes))

        # Emit phase instruction
        self._emit("phase", name=name, func=func, produces=phase_produces, consumes=phase_consumes)

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
        loop_guard = NativeLoopGuard(guard=func, body=body_func, name=name)
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
            produces=(),
            consumes=(),
            decision_vocabulary=vocabulary,
        )
        self._pending_halt = False

    # ── for / parallel lowering ───────────────────────────────────

    def _lower_for_stmt(self, stmt: ast.For) -> None:
        """Lower ``for <var> in parallel([...])`` as a parallel fan-out block.

        The iterable must be a call to :func:`parallel` with a literal
        list/tuple of ``@phase``-decorated callables.  Dynamic, empty,
        duplicate, and non-literal branch sets are rejected.
        """
        iter_node = stmt.iter

        # Must be a call
        if not isinstance(iter_node, ast.Call):
            raise NativeCompileError(
                "for loop iterable must be a call to parallel(...); "
                f"got {type(iter_node).__name__}",
                iter_node,
            )

        # Resolve the callable (must be our parallel function)
        try:
            iter_func = self._resolve_callable(iter_node.func)
        except NativeCompileError as exc:
            # Re-raise with a clear "For" diagnostic so legacy rejection tests
            # (e.g. bare ``for i in range(3)``) still get the expected signal.
            raise NativeCompileError(
                f"For loop iterable must be a call to parallel(...); {exc}",
                iter_node,
            ) from exc
        except Exception as exc:
            raise NativeCompileError(
                f"For loop iterable must be a call to parallel(...); "
                f"cannot resolve callable: {exc}", iter_node
            ) from exc

        # Verify it's the parallel function by checking its metadata attachment
        if not callable(iter_func) or getattr(iter_func, '__name__', '') != 'parallel':
            raise NativeCompileError(
                "For loop iterable must be a call to parallel(...), "
                f"got {getattr(iter_func, '__name__', iter_func)!r}",
                iter_node.func,
            )

        # Extract the branch list argument — must be a literal list or tuple
        if not iter_node.args:
            raise NativeCompileError(
                "parallel(...) requires at least one argument (the branch list)",
                iter_node,
            )
        branch_arg = iter_node.args[0]

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

        # Resolve all branch callables
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
            branch_names.append(meta["name"] if meta else getattr(bf, "__name__", f"branch_{i}"))

        # Extract reducer and optional name from keyword arguments
        reducer: Callable[..., Any] | None = None
        explicit_name: str | None = None
        for kw in iter_node.keywords:
            if kw.arg == "reducer":
                try:
                    reducer = self._resolve_callable(kw.value)
                except NativeCompileError:
                    raise
                except Exception as exc:
                    raise NativeCompileError(
                        f"Cannot resolve parallel reducer: {exc}", kw.value
                    ) from exc
                if not callable(reducer):
                    raise NativeCompileError(
                        "parallel() reducer must be callable", kw.value
                    )
            elif kw.arg == "name":
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    explicit_name = kw.value.value
                else:
                    raise NativeCompileError(
                        "parallel() name must be a string literal", kw.value
                    )
            else:
                raise NativeCompileError(
                    f"Unsupported parallel() keyword: {kw.arg!r}", kw
                )

        # Generate a block name
        if explicit_name:
            block_name = explicit_name
        else:
            block_name = f"parallel_{self._parallel_block_counter}"
            self._parallel_block_counter += 1

        # Emit the parallel instruction
        parallel_pc = self._emit("parallel", name=block_name)

        # Lower each branch body with the corresponding callable substituted.
        # For the M5a sequential baseline, branches are emitted back-to-back
        # after the parallel marker; the marker is a runtime no-op and each
        # branch executes in declaration order.
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

        # Create the ParallelInstruction metadata
        parallel_block = ParallelInstruction(
            name=block_name,
            branches=tuple(branch_names),
            branch_funcs=tuple(branch_funcs),
            reducer=reducer,
            merge_pc=merge_pc,
        )
        self._parallel_blocks.append(parallel_block)

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
    ) -> NativeProgram:
        """Assemble and return the final :class:`NativeProgram`."""
        self._emit_halt()

        # Fix up sequential next_pc links for non-branch instructions
        for i, instr in enumerate(self._instructions):
            if instr.op in ("phase", "jump", "parallel") and instr.next_pc is None:
                next_pc = i + 1
                if next_pc < len(self._instructions):
                    self._instructions[i] = NativeInstruction(
                        pc=instr.pc,
                        op=instr.op,
                        name=instr.name,
                        func=instr.func,
                        next_pc=next_pc,
                        branches=instr.branches,
                        produces=instr.produces,
                        consumes=instr.consumes,
                        decision_vocabulary=instr.decision_vocabulary,
                    )

        return NativeProgram(
            name=self._pipeline_name,
            instructions=tuple(self._instructions),
            phases=tuple(self._phases),
            decisions=tuple(self._decisions),
            loop_guards=tuple(self._loop_guards),
            parallel_blocks=tuple(self._parallel_blocks),
            description=description,
        )
