from __future__ import annotations

from vibecomfy.commands.doctor import _doctor_warnings
from vibecomfy.porting.workbench import _metadata_environment_diagnostics
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def test_doctor_reports_hardware_and_python_env_metadata() -> None:
    workflow = VibeWorkflow("env", WorkflowSource("env"))
    workflow.metadata["hardware"] = {
        "vram_gb_min": 24,
        "vram_gb_recommended": 48,
        "requires_flash_attention": True,
        "tested_on": ["RTX 4090"],
    }
    workflow.metadata["python_env"] = {"python": ">=99.0"}

    warnings = _doctor_warnings(workflow)

    assert any("at least 24GB VRAM" in warning for warning in warnings)
    assert any("flash attention" in warning for warning in warnings)
    assert any("python_env python" in warning for warning in warnings)


def test_port_check_metadata_environment_diagnostics_are_offline_warnings() -> None:
    diagnostics = _metadata_environment_diagnostics(
        {
            "hardware": {"vram_gb_min": 24},
            "python_env": {"missing_package_for_vibecomfy_test": ">=1.0"},
        }
    )

    assert {issue.severity for issue in diagnostics} == {"warning"}
    assert any("24GB VRAM" in issue.message for issue in diagnostics)
    assert any("not installed" in issue.message for issue in diagnostics)
