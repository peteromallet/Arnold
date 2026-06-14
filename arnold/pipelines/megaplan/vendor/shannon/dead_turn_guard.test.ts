// Regression tests for the bun "dead-wedge" finalize hang (py-spy: bun alive,
// blocked awaiting EOF on a stuck tmux child; Python reader threads block on
// read1() with no bytes / no EOF until the 2h wall-clock timeout).
//
// Two guards under test:
//   1. runCommand() caps EVERY spawned child at SHANNON_TMUX_CMD_TIMEOUT_MS and
//      SIGKILLs a wedged child so its pipes EOF and bun makes progress instead
//      of hanging forever inside `new Response(proc.stdout).text()`.
//   2. tmuxSessionAlive() reports a gone session as dead so waitForAssistantReply
//      can fast-fail a dead turn instead of spinning the full TURN_TIMEOUT_MS.

import { afterEach, expect, test } from "bun:test";
import { runCommand, tmuxSessionAlive, megaplanTmuxSocket } from "./index.ts";

const SOCKET = "mp-deadturn-guard-test";

afterEach(async () => {
  delete Bun.env.SHANNON_TMUX_CMD_TIMEOUT_MS;
  // Best-effort reap any test server.
  Bun.spawnSync(["tmux", "-L", SOCKET, "kill-server"], {
    stdout: "ignore",
    stderr: "ignore",
  });
});

test("runCommand SIGKILLs a child that outlives the per-command timeout", async () => {
  // A child that would otherwise hold its stdout write-end open for 30s — the
  // shape that wedged bun forever (a tmux client stuck talking to its server).
  Bun.env.SHANNON_TMUX_CMD_TIMEOUT_MS = "300";
  const started = Date.now();
  const result = await runCommand(["sleep", "30"], false);
  const elapsed = Date.now() - started;

  // Must return in ~the timeout, NOT after 30s.
  expect(elapsed).toBeLessThan(5_000);
  // Non-zero exit code surfaces the wedge as a (retryable) turn failure.
  expect(result.exitCode).not.toBe(0);
});

test("runCommand throwOnFailure=true raises on a timed-out child", async () => {
  Bun.env.SHANNON_TMUX_CMD_TIMEOUT_MS = "300";
  let threw = false;
  try {
    await runCommand(["sleep", "30"], true);
  } catch (error) {
    threw = true;
    expect(String(error)).toContain("was killed");
  }
  expect(threw).toBe(true);
});

test("runCommand returns promptly for a fast child (guard never clips a normal call)", async () => {
  const started = Date.now();
  const result = await runCommand(["echo", "ok"], true);
  expect(Date.now() - started).toBeLessThan(2_000);
  expect(result.exitCode).toBe(0);
  expect(result.stdout.trim()).toBe("ok");
});

test("tmuxSessionAlive is false for a session whose server is gone", async () => {
  // No server on this private socket → has-session exits non-zero → dead.
  Bun.spawnSync(["tmux", "-L", SOCKET, "kill-server"], {
    stdout: "ignore",
    stderr: "ignore",
  });
  Bun.env.SHANNON_TMUX_SOCKET = SOCKET;
  try {
    expect(megaplanTmuxSocket("anything")).toBe(SOCKET);
    const alive = await tmuxSessionAlive("no-such-session");
    expect(alive).toBe(false);
  } finally {
    delete Bun.env.SHANNON_TMUX_SOCKET;
  }
});

test("tmuxSessionAlive is true for a live session, false after it is killed", async () => {
  Bun.env.SHANNON_TMUX_SOCKET = SOCKET;
  try {
    const spawn = Bun.spawnSync(
      ["tmux", "-L", SOCKET, "new-session", "-d", "-s", "live", "sleep", "120"],
      { stdout: "ignore", stderr: "pipe" },
    );
    if (spawn.exitCode !== 0) {
      // tmux unavailable in this environment — skip rather than false-fail.
      return;
    }
    expect(await tmuxSessionAlive("live")).toBe(true);

    Bun.spawnSync(["tmux", "-L", SOCKET, "kill-session", "-t", "live"], {
      stdout: "ignore",
      stderr: "ignore",
    });
    expect(await tmuxSessionAlive("live")).toBe(false);
  } finally {
    delete Bun.env.SHANNON_TMUX_SOCKET;
  }
});
