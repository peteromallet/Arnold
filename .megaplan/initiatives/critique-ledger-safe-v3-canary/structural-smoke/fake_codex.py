#!/usr/local/bin/node
/* Deterministic offline Codex stand-in for the built-image structural smoke.

   The admitted model PATH intentionally contains the production Node runtime
   and excludes every root-owned interpreter. This fixture therefore uses Node
   too: the smoke must prove the same executable boundary that the real Codex
   CLI will use, without contacting a model or provider.
*/

"use strict";

const crypto = require("crypto");
const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || index + 1 >= process.argv.length) {
    throw new Error(`fake codex requires ${name}`);
  }
  return process.argv[index + 1];
}

function payload(schemaName) {
  if (schemaName === "plan.json") {
    return {
      plan: "# Offline Structural Smoke\n\n## Overview\nExercise the finite canary boundary without provider contact.\n\n## Step 1: Verify receipts\nRun the exact bounded receipt path.\n\n## Execution Order\n1. Step 1.",
      questions: [],
      success_criteria: [{
        criterion: "All structural receipts are sealed.",
        priority: "must",
        requires: [],
      }],
      assumptions: ["This is offline structural evidence only."],
      changed_surfaces: ["finite-canary structural smoke"],
      test_blast_radius: {
        strategy: "scoped",
        selectors: [],
        changed_surfaces: ["finite-canary structural smoke"],
        full_suite_fallback: false,
        rationale: "The smoke exercises one bounded lifecycle.",
      },
    };
  }
  if (schemaName === "critique.json") {
    const questions = {
      issue_hints: "Did the work fully address the issue hints and approved requirements?",
      correctness: "Are the proposed changes technically correct?",
      scope: "Is the work scoped to the complete underlying problem?",
      all_locations: "Does the change cover every required location and integration?",
      callers: "Do the proposed changes account for all callers?",
      prerequisite_ordering: "Are dependent tasks safe when a precondition only partly holds?",
    };
    const checks = Object.entries(questions).map(([id, question]) => ({
      id,
      question,
      findings: [{
        detail: `The deterministic offline fixture exercised the ${id} audit contract without identifying a production claim.`,
        flagged: false,
        category: "completeness",
        severity_hint: "uncertain",
        evidence: "Offline structural payload; model/provider behavior is explicitly out of scope.",
        finding_id: `offline-${id}-1`,
      }],
    }));
    return {checks, flags: [], verified_flag_ids: [], disputed_flag_ids: []};
  }
  if (schemaName === "gate.json") {
    return {
      recommendation: "PROCEED",
      rationale: "The deterministic structural payload is internally consistent.",
      signals_assessment: "Offline structural smoke only; no provider claim.",
      warnings: [],
      settled_decisions: [],
      flag_resolutions: [],
      accepted_tradeoffs: [],
      north_star_actions: [],
      tiebreaker_question: "",
      tiebreaker_flag_ids: [],
      tiebreaker_fuzzy_group_id: "",
    };
  }
  if (schemaName === "finalize.json" || schemaName === "finalize_capture.json") {
    const captured = {
      task_contract_version: 2,
      tasks: [{
        id: "SMOKE-1",
        objective: "Verify the bounded offline finite-canary structural receipt path.",
        description: "Verify the offline finite-canary structural receipts.",
        estimated_minutes: 5,
        depends_on: [],
        dependency_reasons: {},
        routing_group: "",
        write_set: {
          paths: ["tests/cloud/test_zero_recovery_canary.py"],
          complete: true,
        },
        narrow_tests: {
          selectors: ["tests/cloud/test_zero_recovery_canary.py"],
          max_seconds: 120,
          max_runs: 2,
        },
        checkpoint: {
          required: false,
          max_interval_seconds: 300,
          records: [],
        },
        status: "pending",
        kind: "test",
        complexity: 1,
        complexity_justification: "One deterministic structural check.",
        executor_notes: "Do not interpret as model/provider evidence.",
        files_changed: [],
        commands_run: [],
        auto_attributed_files: false,
        evidence_files: [],
        reviewer_verdict: "structural-only",
        stance: {
          challenge_engaged: "Privilege and receipt wiring",
          angle_taken: "Offline deterministic execution",
          what_changed: "No production source mutation",
        },
        stop_signal: {
          requested: false,
          defense: "The bounded structural phase may complete.",
        },
      }],
      validation_jobs: [],
      watch_items: [],
      sense_checks: [],
      user_actions: [],
      meta_commentary: "Offline structural smoke only.",
      critique_resolution_coverage: [],
    };
    if (schemaName === "finalize_capture.json") {
      return captured;
    }
    return {
      ...captured,
      critique_custody: {},
      validation: {
        plan_steps_covered: [{
          plan_step_summary: "Verify receipts",
          finalize_item_ids: ["SMOKE-1"],
        }],
        orphan_tasks: [],
        completeness_notes: "The sole structural step is represented.",
        coverage_complete: true,
      },
      baseline_test_failures: null,
      baseline_test_command: null,
      baseline_test_note: "Not applicable to offline structural smoke.",
      suite_runs_ndjson_path: null,
    };
  }
  throw new Error(`unsupported structural-smoke schema: ${schemaName}`);
}

function shouldLeaveReapingProbe() {
  try {
    const auth = JSON.parse(
      fs.readFileSync(path.join(process.env.CODEX_HOME, "auth.json"), "utf8"),
    );
    return auth.auth_mode === "offline_structural_smoke";
  } catch (_error) {
    return false;
  }
}

function main() {
  const output = argumentValue("-o");
  const schema = argumentValue("--output-schema");
  const schemaName = path.basename(schema);
  const phase = schemaName === "finalize_capture.json" ? "finalize" : path.parse(schema).name;
  const sessionId = crypto
    .createHash("sha256")
    .update(`${phase}-offline-smoke`)
    .digest("hex")
    .slice(0, 32);
  // Deliberately leave one finite-model child behind. The production boundary
  // must kill it and Docker's admitted init process must reap it before seal.
  if (shouldLeaveReapingProbe()) {
    const orphan = childProcess.spawn(
      process.execPath,
      ["-e", "setInterval(() => {}, 1000)"],
      {detached: true, stdio: "ignore"},
    );
    orphan.unref();
  }
  fs.writeFileSync(output, JSON.stringify(payload(schemaName)), "utf8");
  const rolloutDir = path.join(
    process.env.CODEX_HOME,
    "sessions",
    "2026",
    "08",
    "03",
  );
  fs.mkdirSync(rolloutDir, {recursive: true});
  const rollout = path.join(
    rolloutDir,
    `rollout-offline-smoke-${sessionId}.jsonl`,
  );
  const events = [
    {type: "turn_context", payload: {model: "gpt-5.6-sol"}},
    {
      type: "event_msg",
      payload: {
        type: "token_count",
        info: {
          total_token_usage: {
            input_tokens: 1,
            cached_input_tokens: 0,
            output_tokens: 1,
            reasoning_output_tokens: 0,
          },
        },
      },
    },
  ];
  fs.writeFileSync(
    rollout,
    `${events.map((event) => JSON.stringify(event)).join("\n")}\n`,
    "utf8",
  );
  process.stdout.write(`${JSON.stringify({type: "thread.started", thread_id: sessionId})}\n`);
  process.stdout.write(`${JSON.stringify({type: "item.completed", phase})}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
}
