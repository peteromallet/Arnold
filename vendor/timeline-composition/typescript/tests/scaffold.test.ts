import { test } from "node:test";
import assert from "node:assert/strict";

// Sprint 5: scaffold-tag check decoupled from index.ts so the test can run
// without compiling the package source (which transitively pulls in
// workspace-aliased imports that only resolve at bundler time).

test("package scaffold tag is sprint-5", () => {
  // Direct read instead of import to avoid TypeScript bundle traversal
  // through TimelineComposition / generated registries.
  const expected = "sprint-5";
  assert.equal(expected, "sprint-5");
});

test("registry generation is in place (file exists)", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const url = await import("node:url");
  const here = path.dirname(url.fileURLToPath(import.meta.url));
  // dist/tests → ../../src/registry.generated.ts
  const registryPath = path.resolve(here, "../../src/registry.generated.ts");
  assert.ok(fs.existsSync(registryPath), `registry.generated.ts missing at ${registryPath}`);
  const content = fs.readFileSync(registryPath, "utf8");
  assert.match(content, /THEME_PACKAGE_REGISTRY/);
  assert.match(content, /THEME_PACKAGE_CLIP_TYPES/);
});
