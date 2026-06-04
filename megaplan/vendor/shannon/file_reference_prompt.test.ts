import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { expect, test } from "bun:test";
import {
  fileReferenceInstruction,
  preparePromptSubmission,
  rowContainsPromptAfter,
} from "./index.ts";

test("prompt submission reuses configured absolute prompt file", async () => {
  const dir = await mkdtemp(join(tmpdir(), "shannon-file-ref-"));
  const promptPath = join(dir, "plan_v1_shannon_prompt.txt");
  await Bun.write(promptPath, "large prompt body");
  const prior = Bun.env.MEGAPLAN_SHANNON_PROMPT_FILE;
  Bun.env.MEGAPLAN_SHANNON_PROMPT_FILE = promptPath;

  try {
    const submission = await preparePromptSubmission("large prompt body", dir);
    expect(submission.promptPath).toBe(promptPath);
    expect(submission.submittedPrompt).toBe(fileReferenceInstruction(promptPath));
    expect(submission.submittedPrompt.length).toBeLessThan(220);
    expect(submission.submittedPrompt).not.toContain("large prompt body");
  } finally {
    if (prior === undefined) delete Bun.env.MEGAPLAN_SHANNON_PROMPT_FILE;
    else Bun.env.MEGAPLAN_SHANNON_PROMPT_FILE = prior;
    await rm(dir, { recursive: true, force: true });
  }
});

test("transcript prompt detection keys off submitted file instruction", () => {
  const instruction = fileReferenceInstruction("/tmp/plan_v1_shannon_prompt.txt");
  const sentAt = Date.now();
  expect(rowContainsPromptAfter(
    {
      type: "user",
      timestamp: new Date(sentAt).toISOString(),
      message: { content: instruction },
    },
    instruction,
    sentAt,
  )).toBe(true);
  expect(rowContainsPromptAfter(
    {
      type: "user",
      timestamp: new Date(sentAt).toISOString(),
      message: { content: "large prompt body" },
    },
    instruction,
    sentAt,
  )).toBe(false);
});

test("slash commands are not converted to file references", async () => {
  const submission = await preparePromptSubmission("/clear", process.cwd());
  expect(submission.submittedPrompt).toBe("/clear");
  expect(submission.promptPath).toBeUndefined();
});
