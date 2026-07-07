import test from "node:test";
import assert from "node:assert/strict";

// ── Global mocks ──────────────────────────────────────────────────────────

let _mocksInstalled = false;

function installMocks() {
  if (_mocksInstalled) return;
  _mocksInstalled = true;

  // localStorage fake
  const lsStore = new Map();
  globalThis.localStorage = {
    getItem(key) {
      const val = lsStore.get(String(key));
      return val === undefined ? null : val;
    },
    setItem(key, value) {
      lsStore.set(String(key), String(value));
    },
    removeItem(key) {
      lsStore.delete(String(key));
    },
    _clear() {
      lsStore.clear();
    },
    _dump() {
      return Object.fromEntries(lsStore);
    },
  };

  // sessionStorage fake
  const ssStore = new Map();
  globalThis.sessionStorage = {
    getItem(key) {
      const val = ssStore.get(String(key));
      return val === undefined ? null : val;
    },
    setItem(key, value) {
      ssStore.set(String(key), String(value));
    },
    removeItem(key) {
      ssStore.delete(String(key));
    },
    _clear() {
      ssStore.clear();
    },
    _dump() {
      return Object.fromEntries(ssStore);
    },
  };
}

function resetStorage() {
  if (globalThis.localStorage?._clear) globalThis.localStorage._clear();
  if (globalThis.sessionStorage?._clear) globalThis.sessionStorage._clear();
}

// ── Dynamic import after mocks ────────────────────────────────────────────

async function loadModule() {
  // Import the zero-dependency scoped session storage module directly.
  // Use a cache-busting query param so each call gets a fresh module
  // (sessionStorage state is captured at module evaluation time).
  const url = new URL("../../vibecomfy/comfy_nodes/web/scoped_session_storage.js", import.meta.url).href;
  return await import(`${url}?t=${Date.now()}`);
}

// ── Tests ─────────────────────────────────────────────────────────────────

test("sessionStorage wrappers set and get values", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { getScopedSessionId, setScopedSessionId } = mod;

  setScopedSessionId("scope-A", "sess-abc123");
  assert.equal(getScopedSessionId("scope-A"), "sess-abc123");
});

test("sessionStorage wrappers return null for missing keys", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { getScopedSessionId } = mod;

  assert.equal(getScopedSessionId("nonexistent"), null);
});

test("setScopedSessionId with null/empty clears the binding", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { getScopedSessionId, setScopedSessionId } = mod;

  setScopedSessionId("scope-A", "sess-abc123");
  assert.equal(getScopedSessionId("scope-A"), "sess-abc123");

  setScopedSessionId("scope-A", null);
  assert.equal(getScopedSessionId("scope-A"), null);

  setScopedSessionId("scope-A", "");
  assert.equal(getScopedSessionId("scope-A"), null);
});

test("forgetScopedSessionId removes the binding", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { getScopedSessionId, setScopedSessionId, forgetScopedSessionId } = mod;

  setScopedSessionId("scope-A", "sess-abc123");
  assert.equal(getScopedSessionId("scope-A"), "sess-abc123");

  forgetScopedSessionId("scope-A");
  assert.equal(getScopedSessionId("scope-A"), null);
});

test("different scopes have independent session bindings", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { getScopedSessionId, setScopedSessionId } = mod;

  setScopedSessionId("scope-A", "sess-aaa");
  setScopedSessionId("scope-B", "sess-bbb");

  assert.equal(getScopedSessionId("scope-A"), "sess-aaa");
  assert.equal(getScopedSessionId("scope-B"), "sess-bbb");

  // Clearing scope A does not affect scope B
  setScopedSessionId("scope-A", null);
  assert.equal(getScopedSessionId("scope-A"), null);
  assert.equal(getScopedSessionId("scope-B"), "sess-bbb");
});

test("per-tab nonce is stable within a module lifetime", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { _tabNonce } = mod;

  const nonce1 = _tabNonce();
  const nonce2 = _tabNonce();
  const nonce3 = _tabNonce();

  assert.equal(typeof nonce1, "string");
  assert.ok(nonce1.length > 0);
  // Same tab → same nonce
  assert.equal(nonce1, nonce2);
  assert.equal(nonce2, nonce3);
});

test("per-tab nonce differs when sessionStorage is cleared (simulating new tab)", async () => {
  installMocks();
  resetStorage();

  // First tab
  const mod1 = await loadModule();
  const nonce1 = mod1._tabNonce();

  // Clear sessionStorage to simulate a new tab
  resetStorage();

  // Second tab
  const mod2 = await loadModule();
  const nonce2 = mod2._tabNonce();

  // Different tabs get different nonces
  assert.notEqual(nonce1, nonce2);
});

test("resolveScopeSessionId returns null when no binding and no legacy", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { resolveScopeSessionId } = mod;

  assert.equal(resolveScopeSessionId("scope-A"), null);
});

test("resolveScopeSessionId returns scoped binding when set", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { resolveScopeSessionId, setScopedSessionId } = mod;

  setScopedSessionId("scope-A", "sess-direct");
  assert.equal(resolveScopeSessionId("scope-A"), "sess-direct");
});

test("legacy migration migrates localStorage scalar into scope once", async () => {
  installMocks();
  resetStorage();

  // Set up legacy scalar in localStorage
  globalThis.localStorage.setItem("vibecomfy_active_session_id", "legacy-sess-999");

  const mod = await loadModule();
  const { resolveScopeSessionId, getScopedSessionId } = mod;

  // First resolution should migrate the legacy value
  const result1 = resolveScopeSessionId("scope-legacy");
  assert.equal(result1, "legacy-sess-999");
  assert.equal(getScopedSessionId("scope-legacy"), "legacy-sess-999");

  // Legacy key should be removed after migration
  assert.equal(globalThis.localStorage.getItem("vibecomfy_active_session_id"), null);
});

test("legacy migration only happens once — second scope does not see legacy", async () => {
  installMocks();
  resetStorage();

  // Set up legacy scalar
  globalThis.localStorage.setItem("vibecomfy_active_session_id", "legacy-sess-777");

  const mod = await loadModule();
  const { resolveScopeSessionId, setScopedSessionId } = mod;

  // First scope consumes the legacy
  const resultA = resolveScopeSessionId("scope-A");
  assert.equal(resultA, "legacy-sess-777");

  // Clear the scoped binding for scope-A to test that scope-B can't get legacy
  setScopedSessionId("scope-A", null);

  // Second scope should NOT see the legacy (it's already consumed)
  const resultB = resolveScopeSessionId("scope-B");
  assert.equal(resultB, null);

  // Legacy key is gone
  assert.equal(globalThis.localStorage.getItem("vibecomfy_active_session_id"), null);
});

test("duplicate-tab fork: same scopeId in different tabs gets different sessions", async () => {
  installMocks();
  resetStorage();

  // Tab 1 sets a session for scope "workflow-X"
  const mod1 = await loadModule();
  mod1.setScopedSessionId("workflow-X", "sess-tab1");

  // Simulate tab 2 by clearing sessionStorage (new tab)
  resetStorage();

  const mod2 = await loadModule();
  // Tab 2 has no binding for "workflow-X"
  assert.equal(mod2.getScopedSessionId("workflow-X"), null);

  // Tab 2 starts its own session
  mod2.setScopedSessionId("workflow-X", "sess-tab2");
  assert.equal(mod2.getScopedSessionId("workflow-X"), "sess-tab2");

  // Tab 1's binding would still be "sess-tab1" if sessionStorage weren't cleared
  // Since we cleared it, tab 1's state is gone (as expected for different tabs)
});

test("scopeId validation rejects non-string and empty values", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { getScopedSessionId, setScopedSessionId, forgetScopedSessionId, resolveScopeSessionId } = mod;

  // Non-string scopeId
  assert.equal(getScopedSessionId(null), null);
  assert.equal(getScopedSessionId(undefined), null);
  assert.equal(getScopedSessionId(123), null);
  assert.equal(getScopedSessionId(""), null);

  // setScopedSessionId with non-string scopeId should not throw
  setScopedSessionId(null, "sess");
  setScopedSessionId("", "sess");
  // Should not have stored anything
  assert.equal(getScopedSessionId(null), null);

  // forgetScopedSessionId with non-string
  forgetScopedSessionId(null);

  // resolveScopeSessionId with non-string
  assert.equal(resolveScopeSessionId(null), null);
  assert.equal(resolveScopeSessionId(""), null);
});

test("scoped session survives within tab across multiple resolutions", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { resolveScopeSessionId, setScopedSessionId } = mod;

  // First resolution with no data
  assert.equal(resolveScopeSessionId("scope-persist"), null);

  // Set a binding
  setScopedSessionId("scope-persist", "sess-persist-42");

  // Now resolve should find it
  assert.equal(resolveScopeSessionId("scope-persist"), "sess-persist-42");

  // Resolve again — still there
  assert.equal(resolveScopeSessionId("scope-persist"), "sess-persist-42");
});

// ── T12: Workflow-tab scope isolation ──────────────────────────────────────
// Candidates and session bindings must remain scoped to their workflow tab.
// Two distinct scopes must never resolve to each other's session, and mutating
// one scope must not perturb the other.  This is the runtime invariant that
// keeps a candidate surfaced in tab A from being applied in tab B.

test("distinct workflow scopes keep independent session bindings (scope isolation)", async () => {
  installMocks();
  resetStorage();

  const mod = await loadModule();
  const { resolveScopeSessionId, setScopedSessionId } = mod;

  // Two unrelated workflow tabs each bind their own session.
  setScopedSessionId("workflow-tab-alpha", "sess-alpha-1");
  setScopedSessionId("workflow-tab-beta", "sess-beta-1");

  assert.equal(resolveScopeSessionId("workflow-tab-alpha"), "sess-alpha-1", "alpha resolves its own session");
  assert.equal(resolveScopeSessionId("workflow-tab-beta"), "sess-beta-1", "beta resolves its own session");
  assert.notEqual(
    resolveScopeSessionId("workflow-tab-alpha"),
    resolveScopeSessionId("workflow-tab-beta"),
    "two scopes never alias to the same session",
  );

  // A brand-new workflow tab (never bound) resolves to null — it cannot pick up
  // another tab's candidate session by accident.
  assert.equal(resolveScopeSessionId("workflow-tab-gamma"), null, "unbound scope resolves to null");

  // Mutating alpha must not leak into beta (cross-scope independence).
  setScopedSessionId("workflow-tab-alpha", "sess-alpha-2");
  assert.equal(resolveScopeSessionId("workflow-tab-alpha"), "sess-alpha-2", "alpha updated independently");
  assert.equal(resolveScopeSessionId("workflow-tab-beta"), "sess-beta-1", "beta unaffected by alpha update");
});
