"""Source compiler foundation for Python-shaped workflow authoring.

This module owns source-oriented parsing data, resolver boundaries, spans, and
result carriers.  It is intentionally separate from ``arnold.workflow.compiler``:
that module lowers explicit DSL objects to manifests, while this one parses
Python-shaped source into compiler-owned intermediate data.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

from arnold.manifest.manifests import (
    ControlTransitionSlot,
    SuspensionRoute,
    WorkflowManifest,
    WorkflowPolicy,
)
from arnold.manifest.refs import ImportRef, SourceSpan
from arnold.workflow.authoring import (
    ComponentContract,
    ComponentKind,
    StepComponent,
)
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.diagnostics import (
    ALLOWED_FUTURE_IMPORTS,
    AuthoringDiagnostic,
    AUTHORING_INTRINSIC_MODULE,
    DiagnosticCode,
    DiagnosticSeverity,
    RESERVED_AUTHORING_INTRINSICS,
    diagnostic_spec,
)
from arnold.workflow.dsl import Input, Output, Pipeline, Route, Step

_DEFAULT_SOURCE_PATH = "<workflow-source>"


class SourceCompileError(ValueError):
    """Raised when a source API requiring a valid source receives diagnostics."""

    def __init__(self, diagnostics: Sequence[AuthoringDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        message = "; ".join(
            f"{diagnostic.code.value}: {diagnostic.message}" for diagnostic in self.diagnostics
        )
        super().__init__(message or "workflow source compilation failed")


SourceCompilationError = SourceCompileError


class ComponentResolver(Protocol):
    """Resolver boundary for static component metadata."""

    def resolve(self, import_ref: ImportRef) -> ComponentContract | None:
        """Return a typed component contract for ``import_ref`` if available."""


@dataclass(frozen=True)
class ImportBinding:
    """A local name bound by an accepted static import."""

    local_name: str
    import_ref: ImportRef
    kind: str
    source_span: SourceSpan
    component: ComponentContract | None = None

    @property
    def component_ref(self) -> str:
        return self.import_ref.spec


@dataclass(frozen=True)
class StepInputBinding:
    """Parsed source-level keyword input binding."""

    name: str
    value_ref: str
    source_span: SourceSpan


@dataclass(frozen=True)
class StepOutputBinding:
    """Parsed source-level assignment output binding."""

    name: str
    source_span: SourceSpan


@dataclass(frozen=True)
class StepCall:
    """Parsed source-level workflow step call."""

    id: str
    local_name: str
    component_ref: str
    source_span: SourceSpan
    component: StepComponent
    arguments: Mapping[str, ast.AST] = field(default_factory=dict)
    inputs: tuple[StepInputBinding, ...] = ()
    outputs: tuple[StepOutputBinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))


@dataclass(frozen=True)
class IntrinsicCall:
    """Parsed source-level compiler intrinsic call."""

    name: str
    arguments: Mapping[str, str]
    source_span: SourceSpan

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True)
class WorkflowDeclaration:
    """The single workflow source form selected from a module."""

    source_form: str
    id: str
    version: str
    source_span: SourceSpan
    function_name: str | None = None
    parameters: tuple[str, ...] = ()
    steps: tuple[StepCall, ...] = ()
    intrinsics: tuple[IntrinsicCall, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "intrinsics", tuple(self.intrinsics))


@dataclass(frozen=True)
class SourceScope:
    """Immutable names visible to a parsed workflow source."""

    imports: Mapping[str, ImportBinding] = field(default_factory=dict)
    parameters: tuple[str, ...] = ()
    locals: Mapping[str, SourceSpan] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "imports", MappingProxyType(dict(self.imports)))
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(self, "locals", MappingProxyType(dict(self.locals)))


@dataclass(frozen=True)
class ParsedWorkflowSource:
    """Parsed source module plus source-oriented compiler state."""

    source: str
    source_path: str
    module: ast.Module
    scope: SourceScope
    workflow: WorkflowDeclaration | None
    diagnostics: tuple[AuthoringDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True)
class CheckWorkflowSourceResult:
    """Result carrier for source validation."""

    parsed_source: ParsedWorkflowSource

    @property
    def diagnostics(self) -> tuple[AuthoringDiagnostic, ...]:
        return self.parsed_source.diagnostics

    @property
    def ok(self) -> bool:
        return not self.diagnostics


@dataclass(frozen=True)
class LowerWorkflowSourceResult(CheckWorkflowSourceResult):
    """Result carrier for source-to-DSL lowering."""

    pipeline: Pipeline | None = None


@dataclass(frozen=True)
class CompileWorkflowSourceResult(LowerWorkflowSourceResult):
    """Result carrier for source-to-manifest compilation."""

    manifest: WorkflowManifest | None = None


@dataclass(frozen=True)
class StaticComponentResolver:
    """Concrete resolver that imports module-level authoring component exports."""

    def resolve(self, import_ref: ImportRef) -> ComponentContract | None:
        try:
            value = import_ref.resolve()
        except Exception:
            return None
        if isinstance(value, ComponentContract):
            return value
        return None


def source_span_for_node(source_path: str | Path | None, node: ast.AST) -> SourceSpan:
    """Convert an AST node span to the 1-based ``SourceSpan`` contract."""

    return SourceSpan(
        path=_coerce_source_path(source_path),
        start_line=getattr(node, "lineno", 1),
        start_column=getattr(node, "col_offset", 0) + 1,
        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        end_column=getattr(node, "end_col_offset", getattr(node, "col_offset", 0)) + 1,
    )


def check_workflow_file(
    source_path: str | Path,
    *,
    resolver: ComponentResolver | None = None,
) -> CheckWorkflowSourceResult:
    path = Path(source_path)
    return check_workflow_source(path.read_text(encoding="utf-8"), source_path=path, resolver=resolver)


def check_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> CheckWorkflowSourceResult:
    return CheckWorkflowSourceResult(
        parsed_source=parse_workflow_source(source, source_path=source_path, resolver=resolver)
    )


def lower_workflow_file(
    source_path: str | Path,
    *,
    resolver: ComponentResolver | None = None,
) -> Pipeline:
    path = Path(source_path)
    return lower_workflow_source(path.read_text(encoding="utf-8"), source_path=path, resolver=resolver)


def lower_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> Pipeline:
    lowered = _lower_workflow_source_result(source, source_path=source_path, resolver=resolver)
    if lowered.diagnostics or lowered.pipeline is None:
        raise SourceCompileError(lowered.diagnostics)
    return lowered.pipeline


def _lower_workflow_source_result(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> LowerWorkflowSourceResult:
    parsed_source = parse_workflow_source(source, source_path=source_path, resolver=resolver)
    pipeline = _lower_parsed_source(parsed_source) if not parsed_source.diagnostics else None
    return LowerWorkflowSourceResult(parsed_source=parsed_source, pipeline=pipeline)


def compile_workflow_file(
    source_path: str | Path,
    *,
    resolver: ComponentResolver | None = None,
) -> WorkflowManifest:
    path = Path(source_path)
    return compile_workflow_source(path.read_text(encoding="utf-8"), source_path=path, resolver=resolver)


def compile_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> WorkflowManifest:
    lowered = _lower_workflow_source_result(source, source_path=source_path, resolver=resolver)
    if lowered.diagnostics or lowered.pipeline is None:
        raise SourceCompileError(lowered.diagnostics)
    return compile_pipeline(lowered.pipeline)


def parse_workflow_source(
    source: str,
    *,
    source_path: str | Path | None = None,
    resolver: ComponentResolver | None = None,
) -> ParsedWorkflowSource:
    path = _coerce_source_path(source_path)
    resolver = StaticComponentResolver() if resolver is None else resolver
    try:
        module = ast.parse(source, filename=path)
    except SyntaxError as exc:
        module = ast.Module(body=[], type_ignores=[])
        diagnostic = _diagnostic(
            DiagnosticCode.UNSUPPORTED_SYNTAX,
            "source is not valid Python syntax",
            source_span=SourceSpan(
                path=path,
                start_line=exc.lineno or 1,
                start_column=exc.offset or 1,
                end_line=exc.end_lineno or exc.lineno or 1,
                end_column=exc.end_offset or exc.offset or 1,
            ),
        )
        return ParsedWorkflowSource(
            source=source,
            source_path=path,
            module=module,
            scope=SourceScope(),
            workflow=None,
            diagnostics=(diagnostic,),
        )

    diagnostics: list[AuthoringDiagnostic] = []
    imports = _parse_imports(module, path, resolver, diagnostics)
    workflow = _parse_workflow_declaration(module, path, imports, diagnostics)
    local_outputs = {
        output.name: output.source_span
        for step in (() if workflow is None else workflow.steps)
        for output in step.outputs
    }
    scope = SourceScope(
        imports=imports,
        parameters=() if workflow is None else workflow.parameters,
        locals=local_outputs,
    )
    return ParsedWorkflowSource(
        source=source,
        source_path=path,
        module=module,
        scope=scope,
        workflow=workflow,
        diagnostics=tuple(diagnostics),
    )


def _parse_imports(
    module: ast.Module,
    source_path: str,
    resolver: ComponentResolver,
    diagnostics: list[AuthoringDiagnostic],
) -> dict[str, ImportBinding]:
    imports: dict[str, ImportBinding] = {}
    for statement in module.body:
        if isinstance(statement, ast.ImportFrom):
            if statement.module == "__future__":
                invalid_future_imports = [
                    alias.name for alias in statement.names if alias.name not in ALLOWED_FUTURE_IMPORTS
                ]
                if invalid_future_imports:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.INVALID_IMPORT_SOURCE,
                            "only future annotations imports are allowed in workflow source",
                            source_span=source_span_for_node(source_path, statement),
                        )
                    )
                continue
            if any(alias.name == "*" for alias in statement.names):
                module_name = _absolute_module_name(statement, source_path)
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.INVALID_IMPORT_SOURCE,
                        "star imports erase stable component provenance",
                        source_span=source_span_for_node(source_path, statement),
                        import_ref=_try_import_ref(module_name, "*"),
                    )
                )
                continue
            module_name = _absolute_module_name(statement, source_path)
            for alias in statement.names:
                local_name = alias.asname or alias.name
                import_ref = ImportRef(module=module_name, qualname=alias.name)
                if local_name in imports:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                            "imported workflow source name is rebound",
                            source_span=source_span_for_node(source_path, statement),
                            component_ref=imports[local_name].component_ref,
                        )
                    )
                    continue
                if module_name == AUTHORING_INTRINSIC_MODULE:
                    if alias.name not in RESERVED_AUTHORING_INTRINSICS:
                        diagnostics.append(
                            _diagnostic(
                                DiagnosticCode.INVALID_IMPORT_SOURCE,
                                "authoring imports may only name reserved compiler intrinsics",
                                source_span=source_span_for_node(source_path, statement),
                                import_ref=import_ref,
                            )
                        )
                        continue
                    if alias.asname is not None and alias.asname != alias.name:
                        diagnostics.append(
                            _diagnostic(
                                DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                                "reserved compiler intrinsic is rebound in workflow source",
                                source_span=source_span_for_node(source_path, statement),
                                component_ref=import_ref.spec,
                            )
                        )
                        continue
                    imports[local_name] = ImportBinding(
                        local_name=local_name,
                        import_ref=import_ref,
                        kind="intrinsic",
                        source_span=source_span_for_node(source_path, statement),
                    )
                    continue
                if local_name in RESERVED_AUTHORING_INTRINSICS:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                            "component import shadows a reserved compiler intrinsic",
                            source_span=source_span_for_node(source_path, statement),
                            component_ref=import_ref.spec,
                        )
                    )
                    continue
                component = resolver.resolve(import_ref)
                if component is None:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.UNKNOWN_COMPONENT,
                            "imported component cannot be found in static resolver metadata",
                            source_span=source_span_for_node(source_path, statement),
                            import_ref=import_ref,
                        )
                    )
                    continue
                if alias.asname is not None and component.provenance.qualname != local_name:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.ALIAS_PROVENANCE_LOSS,
                            "aliased component import is missing original module:qualname provenance",
                            source_span=source_span_for_node(source_path, statement),
                            import_ref=import_ref,
                        )
                    )
                imports[local_name] = ImportBinding(
                    local_name=local_name,
                    import_ref=import_ref,
                    kind=component.kind.value,
                    source_span=source_span_for_node(source_path, statement),
                    component=component,
                )
        elif isinstance(statement, ast.Import):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.INVALID_IMPORT_SOURCE,
                    "root package imports are not valid workflow dependencies",
                    source_span=source_span_for_node(source_path, statement),
                    import_ref=_try_import_ref(statement.names[0].name, "__root__"),
                )
            )
        elif _contains_dynamic_import(statement):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "dynamic imports are not part of the static authoring grammar",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
    return imports


def _parse_workflow_declaration(
    module: ast.Module,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowDeclaration | None:
    declarations: list[ast.Call | ast.FunctionDef | ast.AsyncFunctionDef] = []
    for statement in module.body:
        if isinstance(statement, ast.Expr) and _is_workflow_call(statement.value, imports):
            declarations.append(statement.value)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            _is_workflow_call(decorator, imports) for decorator in statement.decorator_list
        ):
            declarations.append(statement)
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in {"workflow", "halt", "suspend", "transition"}:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                            "reserved compiler intrinsic is rebound in workflow source",
                            source_span=source_span_for_node(source_path, statement),
                            component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{target.id}",
                        )
                    )
    if not declarations:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_WORKFLOW_DECLARATION,
                "module does not declare a workflow(...) source form",
                source_span=SourceSpan(path=source_path, start_line=1),
            )
        )
        return None
    if len(declarations) > 1:
        first = declarations[1]
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MULTIPLE_WORKFLOW_DECLARATIONS,
                "module declares more than one workflow(...) source form",
                source_span=source_span_for_node(source_path, first),
            )
        )
        return None
    declaration = declarations[0]
    if isinstance(declaration, ast.Call):
        return _parse_direct_workflow(declaration, source_path, imports, diagnostics)
    return _parse_function_workflow(declaration, source_path, imports, diagnostics)


def _parse_direct_workflow(
    call: ast.Call,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowDeclaration | None:
    workflow_id = _string_keyword(call, "id")
    steps_keyword = _keyword(call, "steps")
    if workflow_id is None or steps_keyword is None or not isinstance(steps_keyword.value, ast.List):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow(...) declarations must include literal id and steps list",
                source_span=source_span_for_node(source_path, call),
            )
        )
        return None
    steps = tuple(
        step for element in steps_keyword.value.elts if (step := _parse_step_call(element, source_path, imports, diagnostics))
    )
    return WorkflowDeclaration(
        source_form="direct",
        id=workflow_id,
        version=_string_keyword(call, "version") or "1.0",
        source_span=source_span_for_node(source_path, call),
        steps=steps,
    )


def _parse_function_workflow(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> WorkflowDeclaration | None:
    if isinstance(function, ast.AsyncFunctionDef):
        decorator = next(
            decorator for decorator in function.decorator_list if _is_workflow_call(decorator, imports)
        )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "async workflow functions are outside the M2 authoring grammar",
                source_span=source_span_for_node(source_path, function),
            )
        )
        workflow_id = _string_keyword(decorator, "id") or function.name
        return WorkflowDeclaration(
            source_form="function",
            id=workflow_id,
            version=_string_keyword(decorator, "version") or "1.0",
            source_span=source_span_for_node(source_path, function),
            function_name=function.name,
            parameters=_function_parameter_names(function),
            steps=(),
        )
    decorator = next(decorator for decorator in function.decorator_list if _is_workflow_call(decorator, imports))
    header_ok = _validate_workflow_decorator(decorator, source_path, diagnostics)
    header_ok = _validate_function_signature(function, source_path, diagnostics) and header_ok
    workflow_id = _string_keyword(decorator, "id")
    if workflow_id is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow decorators must include a literal id",
                source_span=source_span_for_node(source_path, function),
            )
        )
        workflow_id = function.name
        header_ok = False
    version = _string_keyword(decorator, "version") or "1.0"
    parameters = _function_parameter_names(function)
    initial_scope_ok = _validate_initial_function_scope(parameters, imports, source_path, function, diagnostics)
    steps, intrinsics, local_outputs = (
        _parse_function_body_steps(function, source_path, imports, parameters, diagnostics)
        if header_ok and initial_scope_ok
        else ((), (), {})
    )
    return WorkflowDeclaration(
        source_form="function",
        id=workflow_id,
        version=version,
        source_span=source_span_for_node(source_path, function),
        function_name=function.name,
        parameters=parameters,
        steps=steps,
        intrinsics=intrinsics,
    )


def _validate_workflow_decorator(
    decorator: ast.AST,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    if not isinstance(decorator, ast.Call):
        return False
    valid = True
    if decorator.args or any(keyword.arg is None for keyword in decorator.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow decorators must use literal keyword arguments only",
                source_span=source_span_for_node(source_path, decorator),
            )
        )
        valid = False
    allowed_keywords = {"id", "version"}
    for keyword in decorator.keywords:
        if keyword.arg not in allowed_keywords:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "workflow decorator keyword is outside the M2 authoring grammar",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            valid = False
            continue
        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "workflow decorator metadata must be literal strings",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            valid = False
    return valid


def _validate_function_signature(
    function: ast.FunctionDef,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    args = function.args
    valid = True
    if (
        args.posonlyargs
        or args.vararg is not None
        or args.kwonlyargs
        or args.kwarg is not None
        or args.defaults
        or any(default is not None for default in args.kw_defaults)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow functions may only declare ordered positional parameters",
                source_span=source_span_for_node(source_path, function),
            )
        )
        valid = False
    return valid


def _validate_initial_function_scope(
    parameters: Sequence[str],
    imports: Mapping[str, ImportBinding],
    source_path: str,
    function: ast.FunctionDef,
    diagnostics: list[AuthoringDiagnostic],
) -> bool:
    valid = True
    import_names = set(imports)
    for parameter in parameters:
        if parameter in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "workflow parameter shadows a reserved compiler intrinsic",
                    source_span=_parameter_span(source_path, function, parameter),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{parameter}",
                )
            )
            valid = False
        elif parameter in import_names:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "workflow parameter shadows an imported source name",
                    source_span=_parameter_span(source_path, function, parameter),
                    component_ref=imports[parameter].component_ref,
                )
            )
            valid = False
    return valid


def _function_parameter_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    return tuple(argument.arg for argument in (*function.args.posonlyargs, *function.args.args))


def _parameter_span(source_path: str, function: ast.FunctionDef, parameter: str) -> SourceSpan:
    for argument in (*function.args.posonlyargs, *function.args.args):
        if argument.arg == parameter:
            return source_span_for_node(source_path, argument)
    return source_span_for_node(source_path, function)


def _parse_function_body_steps(
    function: ast.FunctionDef,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    parameters: Sequence[str],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[tuple[StepCall, ...], tuple[IntrinsicCall, ...], Mapping[str, SourceSpan]]:
    steps: list[StepCall] = []
    intrinsics: list[IntrinsicCall] = []
    local_outputs: dict[str, SourceSpan] = {}
    for statement in function.body:
        if isinstance(statement, ast.Assign):
            targets = _assignment_output_bindings(statement, source_path, diagnostics)
            if _is_reserved_intrinsic_call(statement.value, imports):
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.UNSUPPORTED_SYNTAX,
                        "compiler intrinsic calls must be bare workflow statements",
                        source_span=source_span_for_node(source_path, statement.value),
                    )
                )
                continue
            step = _parse_step_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
                output_bindings=targets,
            )
            if step is not None:
                duplicate_outputs = [
                    output for output in targets if output.name in local_outputs
                ]
                for output in duplicate_outputs:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.UNSUPPORTED_SYNTAX,
                            "workflow local output names must be assigned exactly once",
                            source_span=output.source_span,
                        )
                    )
                if not duplicate_outputs:
                    steps.append(step)
                    for output in targets:
                        local_outputs[output.name] = output.source_span
            continue
        elif isinstance(statement, ast.Expr):
            intrinsic = _parse_intrinsic_call(statement.value, source_path, imports, diagnostics)
            if intrinsic is not None:
                intrinsics.append(intrinsic)
                continue
            step = _parse_step_call(
                statement.value,
                source_path,
                imports,
                diagnostics,
                parameters=parameters,
                local_outputs=local_outputs,
            )
            if step is not None:
                steps.append(step)
            continue
        elif isinstance(statement, ast.Return) and statement.value is None:
            continue
        else:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "branching is outside the M2 linear workflow subset",
                    source_span=source_span_for_node(source_path, statement),
                )
            )
            continue
    return tuple(steps), tuple(intrinsics), local_outputs


def _assignment_output_bindings(
    statement: ast.Assign,
    source_path: str,
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepOutputBinding, ...]:
    if len(statement.targets) != 1:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow steps must assign outputs with a single assignment target",
                source_span=source_span_for_node(source_path, statement),
            )
        )
        return ()
    target = statement.targets[0]
    target_nodes: tuple[ast.AST, ...]
    if isinstance(target, ast.Name):
        target_nodes = (target,)
    elif isinstance(target, ast.Tuple) and target.elts and all(isinstance(element, ast.Name) for element in target.elts):
        target_nodes = tuple(target.elts)
    else:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow step outputs must be local names or tuples of local names",
                source_span=source_span_for_node(source_path, target),
            )
        )
        return ()

    seen: set[str] = set()
    outputs: list[StepOutputBinding] = []
    for node in target_nodes:
        assert isinstance(node, ast.Name)
        if node.id in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "workflow local output shadows a reserved compiler intrinsic",
                    source_span=source_span_for_node(source_path, node),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{node.id}",
                )
            )
            continue
        if node.id in seen:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "workflow local output names must be assigned exactly once",
                    source_span=source_span_for_node(source_path, node),
                )
            )
            continue
        seen.add(node.id)
        outputs.append(
            StepOutputBinding(
                name=node.id,
                source_span=source_span_for_node(source_path, node),
            )
        )
    return tuple(outputs)


def _parse_step_call(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
    *,
    parameters: Sequence[str] = (),
    local_outputs: Mapping[str, SourceSpan] | None = None,
    output_bindings: Sequence[StepOutputBinding] = (),
) -> StepCall | None:
    local_outputs = {} if local_outputs is None else local_outputs
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow steps must be direct component calls",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
                "component calls must use explicit keyword authoring arguments",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if node.args:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
                "component calls must use keyword-only authoring arguments",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    binding = imports.get(node.func.id)
    if binding is None or binding.component is None:
        if binding is not None and binding.kind == "intrinsic":
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "compiler intrinsic calls are not workflow component steps",
                    source_span=source_span_for_node(source_path, node),
                    component_ref=binding.component_ref,
                )
            )
            return None
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNKNOWN_COMPONENT,
                "step component is not imported in workflow source",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if binding.component.kind is not ComponentKind.STEP or not isinstance(binding.component, StepComponent):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.WRONG_COMPONENT_KIND,
                "component kind is not valid for a workflow step call",
                source_span=source_span_for_node(source_path, node),
                component_ref=binding.component_ref,
            )
        )
        return None
    step_id = _string_keyword(node, "id")
    if step_id is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MALFORMED_COMPONENT_EXPORT,
                "component calls must include a literal id keyword",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    inputs = _parse_step_inputs(
        node,
        source_path,
        parameters=parameters,
        local_outputs=local_outputs,
        diagnostics=diagnostics,
    )
    if inputs is None:
        return None
    return StepCall(
        id=step_id,
        local_name=node.func.id,
        component_ref=binding.component_ref,
        source_span=source_span_for_node(source_path, node),
        component=binding.component,
        arguments={keyword.arg: keyword.value for keyword in node.keywords if keyword.arg},
        inputs=inputs,
        outputs=tuple(output_bindings),
    )


def _parse_step_inputs(
    node: ast.Call,
    source_path: str,
    *,
    parameters: Sequence[str],
    local_outputs: Mapping[str, SourceSpan],
    diagnostics: list[AuthoringDiagnostic],
) -> tuple[StepInputBinding, ...] | None:
    inputs: list[StepInputBinding] = []
    valid = True
    parameter_names = set(parameters)
    for keyword in node.keywords:
        if keyword.arg in {None, "id"}:
            continue
        if not isinstance(keyword.value, ast.Name):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "component keyword values must reference workflow parameters or prior local outputs",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            valid = False
            continue
        ref_name = keyword.value.id
        if ref_name in RESERVED_AUTHORING_INTRINSICS:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.RESERVED_INTRINSIC_SHADOWING,
                    "compiler intrinsics cannot be passed as dataflow values",
                    source_span=source_span_for_node(source_path, keyword.value),
                    component_ref=f"{AUTHORING_INTRINSIC_MODULE}:{ref_name}",
                )
            )
            valid = False
            continue
        if ref_name in parameter_names:
            value_ref = f"param:{ref_name}"
        elif ref_name in local_outputs:
            value_ref = f"output:{ref_name}"
        else:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNKNOWN_COMPONENT,
                    "keyword dataflow reference is not a workflow parameter or prior local output",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            valid = False
            continue
        inputs.append(
            StepInputBinding(
                name=keyword.arg,
                value_ref=value_ref,
                source_span=source_span_for_node(source_path, keyword),
            )
        )
    return tuple(inputs) if valid else None


def _parse_intrinsic_call(
    node: ast.AST,
    source_path: str,
    imports: Mapping[str, ImportBinding],
    diagnostics: list[AuthoringDiagnostic],
) -> IntrinsicCall | None:
    if not _is_reserved_intrinsic_call(node, imports):
        return None
    assert isinstance(node, ast.Call)
    assert isinstance(node.func, ast.Name)
    intrinsic_name = node.func.id
    if intrinsic_name == "workflow":
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "workflow(...) is only valid as a source declaration",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    if node.args or any(keyword.arg is None for keyword in node.keywords):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "compiler intrinsic calls must use literal keyword arguments only",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None

    arguments: dict[str, str] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "compiler intrinsic arguments must be literal strings",
                    source_span=source_span_for_node(source_path, keyword.value),
                )
            )
            return None
        if keyword.arg in arguments:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNSUPPORTED_SYNTAX,
                    "compiler intrinsic arguments must not repeat keywords",
                    source_span=source_span_for_node(source_path, keyword),
                )
            )
            return None
        arguments[keyword.arg] = keyword.value.value

    allowed_keywords = {
        "halt": {"id", "trigger_ref", "target_ref", "payload_schema_hash", "policy_ref"},
        "suspend": {
            "route_id",
            "capability_id",
            "reentry_id",
            "payload_schema_hash",
            "resume_schema_hash",
            "resume_schema_ref",
            "resume_payload_ref",
        },
        "transition": {
            "id",
            "type",
            "trigger_ref",
            "target_ref",
            "payload_schema_hash",
            "policy_ref",
        },
    }[intrinsic_name]
    required_keywords = {
        "halt": {"id"},
        "suspend": {"route_id"},
        "transition": {"id", "type"},
    }[intrinsic_name]
    if set(arguments) - allowed_keywords or not required_keywords.issubset(arguments):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_SYNTAX,
                "compiler intrinsic call is outside the M2 policy-slot subset",
                source_span=source_span_for_node(source_path, node),
            )
        )
        return None
    return IntrinsicCall(
        name=intrinsic_name,
        arguments=arguments,
        source_span=source_span_for_node(source_path, node),
    )


def _is_reserved_intrinsic_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    binding = imports.get(node.func.id)
    return (
        binding is not None
        and binding.kind == "intrinsic"
        and binding.import_ref.module == AUTHORING_INTRINSIC_MODULE
        and binding.import_ref.qualname == node.func.id
        and binding.local_name == node.func.id
    )


def _lower_parsed_source(parsed_source: ParsedWorkflowSource) -> Pipeline | None:
    workflow = parsed_source.workflow
    if workflow is None:
        return None
    steps = tuple(
        Step(
            id=step.id,
            kind=step.component.step_type,
            label=step.component.label,
            inputs=tuple(
                Input(
                    name=input_binding.name,
                    value_ref=input_binding.value_ref,
                    source_span=input_binding.source_span,
                )
                for input_binding in step.inputs
            ),
            outputs=tuple(
                Output(
                    name=output_binding.name,
                    source_span=output_binding.source_span,
                )
                for output_binding in step.outputs
            ),
            source_span=step.source_span,
            metadata={
                "component_ref": step.component_ref,
                "source_form": workflow.source_form,
            },
        )
        for step in workflow.steps
    )
    routes = tuple(
        Route(
            id=f"{source.id}-{target.id}",
            source=source.id,
            target=target.id,
            source_span=target.source_span,
            metadata={"source_form": workflow.source_form},
        )
        for source, target in zip(workflow.steps, workflow.steps[1:])
    )
    policy = _lower_workflow_policy(workflow.intrinsics)
    return Pipeline(
        id=workflow.id,
        version=workflow.version,
        steps=steps,
        routes=routes,
        policy=policy,
        source_span=workflow.source_span,
        metadata={"source_form": workflow.source_form},
    )


def _lower_workflow_policy(intrinsics: Sequence[IntrinsicCall]) -> WorkflowPolicy | None:
    if not intrinsics:
        return None
    control_transitions: list[ControlTransitionSlot] = []
    suspension_routes: list[SuspensionRoute] = []
    for intrinsic in intrinsics:
        args = intrinsic.arguments
        if intrinsic.name == "suspend":
            suspension_routes.append(
                SuspensionRoute(
                    route_id=args["route_id"],
                    capability_id=args.get("capability_id"),
                    reentry_id=args.get("reentry_id"),
                    payload_schema_hash=args.get("payload_schema_hash"),
                    resume_schema_hash=args.get("resume_schema_hash"),
                    resume_schema_ref=args.get("resume_schema_ref"),
                    resume_payload_ref=args.get("resume_payload_ref"),
                )
            )
        else:
            control_transitions.append(
                ControlTransitionSlot(
                    transition_id=args["id"],
                    transition_type="halt" if intrinsic.name == "halt" else args["type"],
                    trigger_ref=args.get("trigger_ref"),
                    target_ref=args.get("target_ref"),
                    payload_schema_hash=args.get("payload_schema_hash"),
                    policy_ref=args.get("policy_ref"),
                )
            )
    return WorkflowPolicy(
        control_transitions=tuple(control_transitions),
        suspension_routes=tuple(suspension_routes),
    )


def _keyword(call: ast.Call, name: str) -> ast.keyword | None:
    return next((keyword for keyword in call.keywords if keyword.arg == name), None)


def _string_keyword(call: ast.Call, name: str) -> str | None:
    keyword = _keyword(call, name)
    if keyword is None or not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
        return None
    return keyword.value.value


def _is_workflow_call(node: ast.AST, imports: Mapping[str, ImportBinding]) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return False
    binding = imports.get(node.func.id)
    return (
        binding is not None
        and binding.kind == "intrinsic"
        and binding.import_ref.module == AUTHORING_INTRINSIC_MODULE
        and binding.import_ref.qualname == "workflow"
        and binding.local_name == "workflow"
    )


def _contains_dynamic_import(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and (
            (isinstance(child.func, ast.Name) and child.func.id == "__import__")
            or (
                isinstance(child.func, ast.Attribute)
                and child.func.attr == "import_module"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "importlib"
            )
        )
        for child in ast.walk(node)
    )


def _try_import_ref(module: str, qualname: str) -> ImportRef | None:
    try:
        return ImportRef(module=module, qualname=qualname)
    except ValueError:
        return None


def _absolute_module_name(statement: ast.ImportFrom, source_path: str) -> str:
    if statement.level == 0:
        return statement.module or ""
    package_parts = _package_parts_for_source_path(source_path)
    if statement.level > 1:
        package_parts = package_parts[: 1 - statement.level]
    module_parts = tuple(part for part in package_parts if part not in {"", "."})
    if statement.module:
        module_parts = (*module_parts, *statement.module.split("."))
    return ".".join(module_parts)


def _package_parts_for_source_path(source_path: str) -> tuple[str, ...]:
    path = Path(source_path)
    if not path.is_absolute():
        return path.with_suffix("").parts[:-1]
    resolved = path.resolve()
    search_roots = [Path.cwd(), *(Path(entry or ".") for entry in sys.path)]
    for root in search_roots:
        try:
            relative = resolved.with_suffix("").relative_to(root.resolve())
        except ValueError:
            continue
        return relative.parts[:-1]
    return resolved.with_suffix("").parts[:-1]


def _coerce_source_path(source_path: str | Path | None) -> str:
    if source_path is None:
        return _DEFAULT_SOURCE_PATH
    return Path(source_path).as_posix()


def _diagnostic(
    code: DiagnosticCode,
    message: str,
    *,
    source_span: SourceSpan,
    import_ref: ImportRef | None = None,
    component_ref: str | None = None,
) -> AuthoringDiagnostic:
    spec = diagnostic_spec(code)
    return AuthoringDiagnostic(
        code=code,
        message=message,
        severity=DiagnosticSeverity.ERROR,
        source_span=source_span,
        import_ref=import_ref,
        component_ref=component_ref,
        remediation=spec.remediation,
    )


__all__ = [
    "CheckWorkflowSourceResult",
    "CompileWorkflowSourceResult",
    "ComponentResolver",
    "ImportBinding",
    "LowerWorkflowSourceResult",
    "ParsedWorkflowSource",
    "SourceCompilationError",
    "SourceCompileError",
    "SourceScope",
    "StaticComponentResolver",
    "StepCall",
    "StepInputBinding",
    "StepOutputBinding",
    "WorkflowDeclaration",
    "check_workflow_file",
    "check_workflow_source",
    "compile_workflow_file",
    "compile_workflow_source",
    "lower_workflow_file",
    "lower_workflow_source",
    "parse_workflow_source",
    "source_span_for_node",
]
