from __future__ import annotations

from vibecomfy.contracts.model import WorkflowRuntimeContract, build_contract

__all__ = [
    "WorkflowRuntimeContract",
    "build_contract",
    "doctor_contract",
    "ContractIssue",
    "ContractReport",
    "LTXFirstLastTwoStageContract",
]


def __getattr__(name: str):
    if name == "doctor_contract":
        from vibecomfy.contracts.doctor import doctor_contract

        return doctor_contract
    if name == "ContractDoctorDiagnostic":
        from vibecomfy.contracts.doctor import ContractDoctorDiagnostic

        return ContractDoctorDiagnostic
    if name == "ContractDoctorReport":
        from vibecomfy.contracts.doctor import ContractDoctorReport

        return ContractDoctorReport
    if name == "ContractIssue":
        from vibecomfy.contracts.validation import ContractIssue

        return ContractIssue
    if name == "ContractReport":
        from vibecomfy.contracts.validation import ContractReport

        return ContractReport
    if name == "LTXFirstLastTwoStageContract":
        from vibecomfy.contracts.ltx_first_last import LTXFirstLastTwoStageContract

        return LTXFirstLastTwoStageContract
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
