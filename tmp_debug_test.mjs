import { createBrowserHarness } from "./tests/browser/harness.mjs";

const SESSION_ID = "session-bubble-refresh";
const CHAT_URL = `/vibecomfy/agent-edit/chat?session_id=${encodeURIComponent(SESSION_ID)}`;
const candidateGraph = {
  nodes: [
    { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
    { id: 2, type: "SaveImage", properties: { vibecomfy_uid: "uid-2" } },
  ],
  links: [],
};

try {
  const harness = await createBrowserHarness({
    graph: { nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }], links: [] },
    responses: {
      "/system_stats": {
        status: 200,
        body: { system: { comfyui_frontend_package: "1.39.19" } },
      },
      "/vibecomfy/agent/status?route=auto": {
        status: 200,
        body: {
          ok: true,
          provider_available: true,
          route: "deepseek",
          requested_route: "auto",
          route_options: {
            auto: { requested_route: "auto", normalized_route: "deepseek", browser_api_key_allowed: false },
            deepseek: { requested_route: "deepseek", normalized_route: "deepseek", browser_api_key_allowed: true },
          },
        },
      },
      "/vibecomfy/agent-executor": {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          turn_id: "0007",
          baseline_turn_id: null,
          canvas_apply_allowed: true,
          apply_allowed: true,
          queue_allowed: true,
          message: "Candidate ready for review.",
          graph: candidateGraph,
          report: {
            change: { content_edits: { preserved: ["uid-1"], edited: ["uid-2"], removed_named: [] } },
            recovery: [],
          },
          audit_ref: { path: "/tmp/audit-turn-0007.json", sha256: "def777" },
          batch_turns: [
            {
              session_id: SESSION_ID,
              turn_number: 0,
              message: "planning edits",
              statement_count: 1,
              batch_ok: true,
              exit_mode: "done",
            },
          ],
        },
      },
      [CHAT_URL]: {
        status: 200,
        body: {
          ok: true,
          session_id: SESSION_ID,
          session_path: `out/editor_sessions/${SESSION_ID}/`,
          detail_json_path: `out/editor_sessions/${SESSION_ID}/session.json`,
          messages: [
            { role: "user", text: "make the save node cleaner", turn_id: "0007" },
            {
              role: "agent",
              text: "Candidate ready for review.",
              turn_id: "0007",
              outcome: {
                kind: "edit",
                changes: [
                  { uid: "uid-2", field_path: "inputs.filename_prefix", old: "old", new: "new" },
                ],
              },
            },
          ],
        },
      },
    },
  });

  await harness.loadExtension();
  await harness.setup();
  await harness.invokeCommand("VibeComfy.AgentEdit");

  harness.document.getElementById("vibecomfy-agent-panel-prompt").value = "bubble detail retention";
  await harness.clickButton("Submit");

  process.stdout.write("=== TEXT DUMP AFTER SUBMIT ===\n");
  process.stdout.write(harness.textDump() + "\n");

  process.stdout.write("\n=== CHAT REGION CHILDREN ===\n");
  const chatRegion = harness.document.getElementById("vibecomfy-agent-panel-region-chat");
  function dumpTree(node, depth = 0) {
    const indent = "  ".repeat(depth);
    const info = `${node.tagName || "TEXT"} id=${node.id || ""} dataset=${JSON.stringify(node.dataset || {})} text=${JSON.stringify(String(node.textContent || "").slice(0, 120))}`;
    process.stdout.write(indent + info + "\n");
    for (const child of node.children || []) {
      dumpTree(child, depth + 1);
    }
  }
  if (chatRegion) dumpTree(chatRegion);

  await new Promise((r) => setTimeout(r, 200));

  process.stdout.write("\n=== AFTER 200ms TEXT DUMP ===\n");
  process.stdout.write(harness.textDump() + "\n");

  process.stdout.write("\n=== CHAT REGION CHILDREN AFTER 200ms ===\n");
  if (chatRegion) dumpTree(chatRegion);

  await harness.dispose();
} catch (err) {
  process.stdout.write("ERROR: " + err.stack + "\n");
}
