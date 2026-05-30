from __future__ import annotations

from pathlib import Path

from megaplan.orchestration.plan_contracts import (
    contract_diff_fingerprint,
    diff_assumes_against_provides,
    normalize_contract_payload,
    provided_paths_by_milestone,
    render_contract_markdown,
)


def test_normalize_contract_payload_defaults_to_empty_contract() -> None:
    assert normalize_contract_payload(None) == {"provides": [], "assumes": []}


def test_normalize_contract_payload_ignores_extra_keys_and_normalizes_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = {
        "provides": [
            {
                "name": "Planner surface",
                "description": "shared contract",
                "interfaces": [
                    {
                        "symbol": "Planner.run",
                        "signature": "  Planner.run(config) -> None  ",
                        "path": str(tmp_path / "megaplan" / "planner.py"),
                        "extra": "ignored",
                    },
                    {
                        "symbol": "Planner.status",
                        "signature": "Planner.status() -> str",
                        "path": ".\\megaplan\\status.py",
                    },
                ],
                "unused": True,
            }
        ],
        "assumes": [
            {
                "name": "Runtime contract",
                "upstream_milestone": "m1",
                "interfaces": [
                    {
                        "symbol": "Planner.run",
                        "signature": "  Planner.run(config) -> None  ",
                        "path": "./megaplan/planner.py",
                    }
                ],
                "ignored": "value",
            }
        ],
        "totally_extra": {"ignored": True},
    }

    normalized = normalize_contract_payload(payload)

    assert normalized == {
        "provides": [
            {
                "name": "Planner surface",
                "description": "shared contract",
                "interfaces": [
                    {
                        "symbol": "Planner.run",
                        "signature": "Planner.run(config) -> None",
                        "path": "megaplan/planner.py",
                    },
                    {
                        "symbol": "Planner.status",
                        "signature": "Planner.status() -> str",
                        "path": "megaplan/status.py",
                    },
                ],
            }
        ],
        "assumes": [
            {
                "name": "Runtime contract",
                "upstream_milestone": "m1",
                "interfaces": [
                    {
                        "symbol": "Planner.run",
                        "signature": "Planner.run(config) -> None",
                        "path": "megaplan/planner.py",
                    }
                ],
            }
        ],
    }


def test_render_contract_markdown_renders_non_empty_sections() -> None:
    markdown = render_contract_markdown(
        {
            "provides": [
                {
                    "name": "Planner surface",
                    "description": "shared contract",
                    "interfaces": [
                        {
                            "symbol": "Planner.run",
                            "signature": "Planner.run(config) -> None",
                            "path": "megaplan/planner.py",
                        }
                    ],
                }
            ],
            "assumes": [
                {
                    "name": "Runtime contract",
                    "upstream_milestone": "m1",
                    "interfaces": [
                        {
                            "symbol": "Planner.run",
                            "signature": "Planner.run(config) -> None",
                            "path": "megaplan/planner.py",
                        }
                    ],
                }
            ],
        }
    )

    assert "## Provides" in markdown
    assert "## Assumes" in markdown
    assert "`Planner.run`" in markdown
    assert "from `m1`" in markdown


def test_provided_paths_by_milestone_collects_unique_sorted_paths() -> None:
    contracts = [
        {
            "milestone_label": "m1",
            "contract": {
                "provides": [
                    {
                        "name": "A",
                        "description": "",
                        "interfaces": [
                            {"symbol": "one", "signature": "sig", "path": "src/b.py"},
                            {"symbol": "two", "signature": "sig", "path": "src/a.py"},
                        ],
                    }
                ]
            },
        },
        {
            "label": "m1",
            "provides": [
                {
                    "name": "B",
                    "description": "",
                    "interfaces": [
                        {"symbol": "three", "signature": "sig", "path": "src/a.py"}
                    ],
                }
            ],
        },
        {"label": "m2", "contract": {"provides": []}},
    ]

    assert provided_paths_by_milestone(contracts) == {
        "m1": ["src/a.py", "src/b.py"],
        "m2": [],
    }


def test_diff_assumes_against_provides_reports_ok_missing_and_mismatch() -> None:
    downstream = {
        "assumes": [
            {
                "name": "Uses m1 runtime",
                "upstream_milestone": "m1",
                "interfaces": [
                    {
                        "symbol": "Runtime.run",
                        "signature": "Runtime.run(config) -> None",
                        "path": "src/runtime.py",
                    },
                    {
                        "symbol": "Runtime.status",
                        "signature": "Runtime.status() -> str",
                        "path": "src/runtime.py",
                    },
                ],
            },
            {
                "name": "Uses m2 store",
                "upstream_milestone": "m2",
                "interfaces": [
                    {
                        "symbol": "Store.load",
                        "signature": "Store.load(id: str) -> Item",
                        "path": "src/store.py",
                    }
                ],
            },
        ]
    }
    upstream = [
        {
            "milestone_label": "m1",
            "contract": {
                "provides": [
                    {
                        "name": "Runtime",
                        "description": "",
                        "interfaces": [
                            {
                                "symbol": "Runtime.run",
                                "signature": "Runtime.run(config) -> None",
                                "path": "src/runtime.py",
                            },
                            {
                                "symbol": "Runtime.status",
                                "signature": "Runtime.status() -> bool",
                                "path": "src/runtime_state.py",
                            },
                            {
                                "symbol": "Runtime.extra",
                                "signature": "Runtime.extra() -> None",
                                "path": "src/runtime_extra.py",
                            },
                        ],
                    }
                ]
            },
        }
    ]

    rows = diff_assumes_against_provides(downstream, upstream, downstream_label="m3")

    assert [row["status"] for row in rows] == ["OK", "MISMATCH", "MISSING_UPSTREAM"]
    assert rows[0]["downstream_label"] == "m3"
    assert rows[1]["note"] == "path and signature changed"
    assert rows[1]["actual_path"] == "src/runtime_state.py"
    assert rows[2]["note"] == "upstream contract `m2` missing"


def test_contract_diff_fingerprint_is_deterministic_for_equivalent_material_rows() -> None:
    rows_a = [
        {
            "downstream_label": "m3",
            "upstream_label": "m2",
            "symbol": "Store.load",
            "expected_path": "src/store.py",
            "actual_path": "",
            "expected_signature": "Store.load(id: str) -> Item",
            "actual_signature": "",
            "status": "MISSING_UPSTREAM",
            "note": "upstream contract `m2` missing",
        },
        {
            "downstream_label": "m3",
            "upstream_label": "m1",
            "symbol": "Runtime.status",
            "expected_path": "src/runtime.py",
            "actual_path": "src/runtime_state.py",
            "expected_signature": "Runtime.status() -> str",
            "actual_signature": "Runtime.status() -> bool",
            "status": "MISMATCH",
            "note": "path and signature changed",
        },
    ]
    rows_b = [
        {
            "downstream_label": "m3",
            "upstream_label": "m1",
            "symbol": "Runtime.run",
            "expected_path": "src/runtime.py",
            "actual_path": "src/runtime.py",
            "expected_signature": "Runtime.run(config) -> None",
            "actual_signature": "Runtime.run(config) -> None",
            "status": "OK",
            "note": "",
        },
        rows_a[1],
        rows_a[0],
    ]

    assert contract_diff_fingerprint(rows_a) == contract_diff_fingerprint(rows_b)
