from arnold.pipelines.megaplan.model_seam import audit_step_payload
from arnold.pipelines.megaplan.schemas import SCHEMAS
from arnold.pipelines.megaplan.workers.hermes import clean_parsed_payload


def test_gate_recommendation_enum_is_normalized_before_audit() -> None:
    payload = {
        "recommendation": "proceed",
        "rationale": "Execution can move forward.",
        "signals_assessment": "Preflight is green and no blocking flags remain.",
        "warnings": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "settled_decisions": [],
    }

    clean_parsed_payload(payload, SCHEMAS["gate.json"], "gate")

    assert payload["recommendation"] == "PROCEED"
    audit_step_payload("gate", payload)


def test_single_check_critique_object_is_wrapped_before_audit() -> None:
    payload = {
        "id": "scope",
        "question": "Is the plan scoped correctly?",
        "guidance": "Template-only guidance should not be promoted.",
        "findings": [
            {
                "detail": "Checked the task graph and found the slice boundaries explicit.",
                "flagged": False,
            }
        ],
    }

    clean_parsed_payload(payload, SCHEMAS["critique.json"], "critique")

    assert payload == {
        "checks": [
            {
                "id": "scope",
                "question": "Is the plan scoped correctly?",
                "findings": [
                    {
                        "detail": "Checked the task graph and found the slice boundaries explicit.",
                        "flagged": False,
                    }
                ],
            }
        ],
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    audit_step_payload("critique", payload)
