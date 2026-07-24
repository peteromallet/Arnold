"""Shared pack-closure validation for native programs.

Pack registration must fail closed when an exported workflow closes over an
invalid recursive structure. This module centralizes the shared traversal and
depth bound used for pack-time validation before runtime execution begins.
"""

from __future__ import annotations

from dataclasses import dataclass

from arnold.pipeline.native.compiler import NativeCompileError, compile_pipeline
from arnold.pipeline.native.decorators import is_pipeline
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram, ParallelMapInstruction

PACK_CLOSURE_MAX_DEPTH = 32


class PackClosureValidationError(ValueError):
    """Raised when a shared pack export closes over an invalid program graph."""


@dataclass(frozen=True)
class _ChildProgramRef:
    program: NativeProgram
    relation: str
    owner_program: str
    instruction_name: str


def validate_shared_pack_closure(
    program: NativeProgram,
    *,
    pack_id: str | None = None,
    export_stable_id: str | None = None,
) -> None:
    """Validate recursive closure for a pack-exported native program.

    Walks child-workflow ``subprogram`` references and ``parallel_map`` mapper
    workflows with the same cycle/depth semantics the runtime enforces during
    execution. The root program itself is not compiled or mutated here.
    """

    root_identity = _program_identity(program)
    context = _validation_context(
        root_identity=root_identity,
        pack_id=pack_id,
        export_stable_id=export_stable_id,
    )
    _validate_program(
        program,
        active_identities=(root_identity,),
        current_depth=0,
        context=context,
        compiled_mapper_cache={},
    )


def _validate_program(
    program: NativeProgram,
    *,
    active_identities: tuple[str, ...],
    current_depth: int,
    context: str,
    compiled_mapper_cache: dict[int, NativeProgram],
) -> None:
    for child_ref in _referenced_child_programs(
        program,
        context=context,
        compiled_mapper_cache=compiled_mapper_cache,
    ):
        child_identity = _program_identity(child_ref.program)
        if child_identity in active_identities:
            cycle = " -> ".join((*active_identities, child_identity))
            raise PackClosureValidationError(
                f"{context}: pack closure cycle detected via "
                f"{child_ref.relation} {child_ref.instruction_name!r} in "
                f"{child_ref.owner_program!r}: {cycle}"
            )
        if current_depth >= PACK_CLOSURE_MAX_DEPTH:
            raise PackClosureValidationError(
                f"{context}: pack closure depth exceeded "
                f"{PACK_CLOSURE_MAX_DEPTH} at {child_identity!r} via "
                f"{child_ref.relation} {child_ref.instruction_name!r} in "
                f"{child_ref.owner_program!r}"
            )
        _validate_program(
            child_ref.program,
            active_identities=(*active_identities, child_identity),
            current_depth=current_depth + 1,
            context=context,
            compiled_mapper_cache=compiled_mapper_cache,
        )


def _referenced_child_programs(
    program: NativeProgram,
    *,
    context: str,
    compiled_mapper_cache: dict[int, NativeProgram],
) -> tuple[_ChildProgramRef, ...]:
    refs: list[_ChildProgramRef] = []
    owner_program = _program_identity(program)
    for instr in program.instructions:
        child = _subpipeline_child_ref(
            instr,
            owner_program=owner_program,
        )
        if child is not None:
            refs.append(child)
            continue

        mapper_child = _parallel_map_mapper_ref(
            instr,
            owner_program=owner_program,
            context=context,
            compiled_mapper_cache=compiled_mapper_cache,
        )
        if mapper_child is not None:
            refs.append(mapper_child)
    return tuple(refs)


def _subpipeline_child_ref(
    instr: NativeInstruction,
    *,
    owner_program: str,
) -> _ChildProgramRef | None:
    if instr.op != "subpipeline" or not isinstance(instr.subprogram, NativeProgram):
        return None
    return _ChildProgramRef(
        program=instr.subprogram,
        relation="subpipeline",
        owner_program=owner_program,
        instruction_name=_instruction_label(instr),
    )


def _parallel_map_mapper_ref(
    instr: NativeInstruction,
    *,
    owner_program: str,
    context: str,
    compiled_mapper_cache: dict[int, NativeProgram],
) -> _ChildProgramRef | None:
    if instr.op != "parallel_map" or not isinstance(instr.subprogram, ParallelMapInstruction):
        return None
    mapper_program = _compile_mapper_program(
        instr.subprogram,
        context=context,
        owner_program=owner_program,
        instruction_name=_instruction_label(instr),
        compiled_mapper_cache=compiled_mapper_cache,
    )
    if mapper_program is None:
        return None
    return _ChildProgramRef(
        program=mapper_program,
        relation="parallel_map mapper",
        owner_program=owner_program,
        instruction_name=_instruction_label(instr),
    )


def _compile_mapper_program(
    block: ParallelMapInstruction,
    *,
    context: str,
    owner_program: str,
    instruction_name: str,
    compiled_mapper_cache: dict[int, NativeProgram],
) -> NativeProgram | None:
    mapper = block.mapper
    if mapper is None:
        return None
    if isinstance(mapper, NativeProgram):
        return mapper
    if not callable(mapper) or not is_pipeline(mapper):
        return None

    mapper_key = id(mapper)
    cached = compiled_mapper_cache.get(mapper_key)
    if cached is not None:
        return cached

    try:
        compiled = compile_pipeline(mapper)
    except (NativeCompileError, OSError) as exc:
        raise PackClosureValidationError(
            f"{context}: could not compile parallel_map mapper "
            f"{getattr(mapper, '__name__', repr(mapper))!r} referenced from "
            f"{owner_program!r} instruction {instruction_name!r}: {exc}"
        ) from exc
    compiled_mapper_cache[mapper_key] = compiled
    return compiled


def _instruction_label(instr: NativeInstruction) -> str:
    if instr.call_site_path:
        return "/".join(str(segment) for segment in instr.call_site_path if str(segment))
    if instr.name:
        return instr.name
    return instr.op


def _program_identity(program: NativeProgram) -> str:
    return program.stable_id or program.name or "<anonymous>"


def _validation_context(
    *,
    root_identity: str,
    pack_id: str | None,
    export_stable_id: str | None,
) -> str:
    details: list[str] = []
    if pack_id:
        details.append(f"pack {pack_id!r}")
    if export_stable_id:
        details.append(f"export {export_stable_id!r}")
    if not details:
        details.append(f"program {root_identity!r}")
    return f"while validating {', '.join(details)}"


__all__ = [
    "PACK_CLOSURE_MAX_DEPTH",
    "PackClosureValidationError",
    "validate_shared_pack_closure",
]
