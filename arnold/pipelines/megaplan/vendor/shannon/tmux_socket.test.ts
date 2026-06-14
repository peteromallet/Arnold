import { describe, expect, test } from "bun:test";
import { megaplanTmuxSocket, tmuxArgs } from "./index.ts";

// Regression guard for the "no server running" finalize hang: every Shannon
// session must run on its OWN private tmux server (`tmux -L mp-<session>`), so a
// concurrent chain's last-session teardown / any `tmux kill-server` cannot
// collapse the shared default server out from under a live Claude pane.

describe("private per-session tmux server", () => {
  test("socket name is a deterministic function of the session name", () => {
    expect(megaplanTmuxSocket("abc123")).toBe("mp-abc123");
    expect(megaplanTmuxSocket("abc123")).toBe(megaplanTmuxSocket("abc123"));
    expect(megaplanTmuxSocket("other")).not.toBe(megaplanTmuxSocket("abc123"));
  });

  test("tmuxArgs always pins tmux to the session's private -L socket", () => {
    const sess = "6745e6b5a884"; // the real failing finalize session id shape
    const args = tmuxArgs(sess, "capture-pane", "-pt", sess, "-S", "-40");
    expect(args[0]).toBe("tmux");
    expect(args[1]).toBe("-L");
    expect(args[2]).toBe(`mp-${sess}`);
    // the caller's tmux subcommand + flags follow the socket selector verbatim
    expect(args.slice(3)).toEqual(["capture-pane", "-pt", sess, "-S", "-40"]);
  });

  test("a paste-buffer / kill-session for one session never names another's socket", () => {
    const a = tmuxArgs("AAAA", "kill-session", "-t", "AAAA");
    const b = tmuxArgs("BBBB", "paste-buffer", "-p", "-b", "buf", "-t", "BBBB");
    expect(a[2]).toBe("mp-AAAA");
    expect(b[2]).toBe("mp-BBBB");
    expect(a[2]).not.toBe(b[2]);
  });

  test("SHANNON_TMUX_SOCKET overrides the derived socket (diagnostics/tests)", () => {
    const prev = Bun.env.SHANNON_TMUX_SOCKET;
    try {
      Bun.env.SHANNON_TMUX_SOCKET = "override-sock";
      expect(megaplanTmuxSocket("ignored")).toBe("override-sock");
      expect(tmuxArgs("ignored", "ls")[2]).toBe("override-sock");
    } finally {
      if (prev === undefined) delete Bun.env.SHANNON_TMUX_SOCKET;
      else Bun.env.SHANNON_TMUX_SOCKET = prev;
    }
  });
});
