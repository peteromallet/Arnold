import json
from pathlib import Path

from evals.audit import EvalAudit, collect_phase_trace, generate_run_readme


def test_collect_phase_trace_slices_session_log(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session_path = sessions_dir / "session_demo.json"
    session_path.write_text(
        json.dumps(
            {
                "session_id": "demo",
                "messages": [
                    {"role": "assistant", "content": "plan"},
                    {"role": "assistant", "content": "critique"},
                    {"role": "assistant", "content": "gate"},
                ],
            }
        ),
        encoding="utf-8",
    )

    trace = collect_phase_trace("demo", 1, hermes_home=tmp_path)

    assert trace == [
        {"role": "assistant", "content": "critique"},
        {"role": "assistant", "content": "gate"},
    ]


def test_save_audit_writes_versioned_artifacts_and_readme(tmp_path):
    audit = EvalAudit(
        eval_name="demo-eval",
        run_timestamp="20260101T000000Z",
        results_root=tmp_path,
        config_snapshot={"models": {"plan": "model"}},
        environment={"repos": {"hermes-agent": {"git_sha": "abc"}}},
        initial_commit_sha="abc123",
        prompt="build a thing",
        build_result={"success": True},
        eval_result={"success": True},
        results_json={"status": "passed"},
        git_diff="diff --git a/file b/file\n",
    )
    audit.add_phase_result(
        phase="critique",
        model="critic-model",
        iteration=2,
        artifact_payload={"recommendation": "PROCEED"},
        trace_messages=[{"role": "assistant", "content": "critique"}],
        raw_output='{"success": true}',
        token_counts={"input_tokens": 10, "output_tokens": 4},
    )

    output_dir = audit.save_audit()

    assert (output_dir / "summary.json").exists()
    assert (output_dir / "run-config.json").exists()
    assert (output_dir / "environment.json").exists()
    assert (output_dir / "scoring" / "results.json").exists()
    assert (output_dir / "scoring" / "build.json").exists()
    assert (output_dir / "scoring" / "eval.json").exists()
    assert (output_dir / "git" / "diff.patch").read_text(encoding="utf-8").startswith("diff --git")
    assert (output_dir / "megaplan" / "critique_v2.json").exists()
    assert (output_dir / "traces" / "critique_v2.json").exists()
    assert (output_dir / "phases" / "critique_v2.json").exists()
    assert (output_dir / "raw" / "critique_v2.txt").exists()

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "Raw provider HTTP payloads are not captured." in readme
    assert "~/.hermes/sessions/" in readme
    assert "python -m evals.run_evals --config" in readme


def test_generate_run_readme_mentions_diff_when_present(tmp_path):
    audit = EvalAudit(
        eval_name="demo-eval",
        run_timestamp="20260101T000000Z",
        results_root=tmp_path,
        initial_commit_sha="abc123",
        git_diff="diff --git a/file b/file\n",
    )

    readme = generate_run_readme(audit)

    assert "git/diff.patch" in readme
    assert "Initial commit SHA: `abc123`" in readme
