import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const EXTENSION_SOURCE = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web", "vibecomfy_roundtrip.js");

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

class FakeElement {
  constructor(ownerDocument, tagName) {
    this.ownerDocument = ownerDocument;
    this.tagName = String(tagName).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.style = {};
    this.dataset = {};
    this.attributes = {};
    this.title = "";
    this.placeholder = "";
    this.value = "";
    this.disabled = false;
    this.onclick = null;
    this.textContent = "";
    this.id = "";
    this.eventListeners = {};
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) {
      this.children.splice(index, 1);
      child.parentNode = null;
    }
    return child;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
  }

  addEventListener(type, listener) {
    if (!this.eventListeners[type]) {
      this.eventListeners[type] = [];
    }
    this.eventListeners[type].push(listener);
  }

  removeEventListener(type, listener) {
    const listeners = this.eventListeners[type] || [];
    this.eventListeners[type] = listeners.filter((entry) => entry !== listener);
  }

  click() {
    if (this.disabled) {
      return undefined;
    }
    const listeners = this.eventListeners.click || [];
    for (const listener of listeners) {
      listener.call(this, { type: "click", target: this });
    }
    if (typeof this.onclick === "function") {
      return this.onclick();
    }
    return undefined;
  }

  querySelectorAll(predicate) {
    const matcher = typeof predicate === "function" ? predicate : () => false;
    const matches = [];
    const visit = (node) => {
      if (matcher(node)) {
        matches.push(node);
      }
      for (const child of node.children) {
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
}

class FakeDocument {
  constructor() {
    this.head = new FakeElement(this, "head");
    this.body = new FakeElement(this, "body");
  }

  createElement(tagName) {
    return new FakeElement(this, tagName);
  }

  getElementById(id) {
    return this.body.querySelectorAll((node) => node.id === id)[0] || null;
  }
}

function makeResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return clone(body);
    },
    async text() {
      return JSON.stringify(body);
    },
  };
}

export async function createBrowserHarness({
  graph,
  responses = {},
  withQueuePrompt = true,
} = {}) {
  const document = new FakeDocument();
  const requests = [];
  const operationLog = [];
  const consoleCapture = { log: [], warn: [], error: [] };
  const loadGraphDataCalls = [];
  const graphClearCalls = [];
  const graphConfigureCalls = [];
  const graphChangeCalls = [];
  const graphDirtyCanvasCalls = [];
  const canvasDrawCalls = [];
  const queuePromptCalls = [];
  const serializeCalls = [];
  const toasts = [];
  const registeredExtensions = [];
  let liveCanvasRevision = 1;
  let currentGraph = clone(
    graph || {
      nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
      links: [],
    },
  );

  function syncLiveGraphNodes() {
    app.canvas.graph._vibecomfyLiveCanvasToken = `rev:${liveCanvasRevision}`;
    app.canvas.graph._nodes = (currentGraph?.nodes || []).map((node) => ({
      id: node.id,
      type: node.type,
      properties: clone(node.properties || {}),
      inputs: clone(node.inputs || []),
      outputs: clone(node.outputs || []),
    }));
  }

  const app = {
    canvas: {
      graph: {
        serialize() {
          const snapshot = clone(currentGraph);
          serializeCalls.push(snapshot);
          return snapshot;
        },
        _nodes: [],
        clear() {
          graphClearCalls.push(clone(currentGraph));
          operationLog.push({ kind: "graph.clear" });
          liveCanvasRevision += 1;
          currentGraph = { nodes: [], links: [] };
          syncLiveGraphNodes();
        },
        configure(nextGraph) {
          const snapshot = clone(nextGraph);
          graphConfigureCalls.push(snapshot);
          operationLog.push({ kind: "graph.configure", graph: snapshot });
          liveCanvasRevision += 1;
          currentGraph = snapshot;
          syncLiveGraphNodes();
        },
        change() {
          graphChangeCalls.push(clone(currentGraph));
          operationLog.push({ kind: "graph.change" });
        },
        setDirtyCanvas(fg, bg) {
          graphDirtyCanvasCalls.push([fg, bg]);
          operationLog.push({ kind: "graph.setDirtyCanvas", fg, bg });
        },
      },
      draw(fg, bg) {
        canvasDrawCalls.push([fg, bg]);
        operationLog.push({ kind: "canvas.draw", fg, bg });
      },
    },
    extensionManager: {
      toast: {
        add(entry) {
          toasts.push(clone(entry));
        },
      },
    },
    registerExtension(extension) {
      registeredExtensions.push(extension);
    },
    loadGraphData(nextGraph) {
      const snapshot = clone(nextGraph);
      loadGraphDataCalls.push(snapshot);
      operationLog.push({ kind: "loadGraphData", graph: snapshot });
      liveCanvasRevision += 1;
      currentGraph = snapshot;
      syncLiveGraphNodes();
    },
  };
  if (withQueuePrompt) {
    app.queuePrompt = (...args) => {
      queuePromptCalls.push(args);
      return { queued: true, args: clone(args) };
    };
  }
  syncLiveGraphNodes();

  const LiteGraphCanvas = function LiteGraphCanvas() {};
  LiteGraphCanvas.prototype.getCanvasMenuOptions = function getCanvasMenuOptions() {
    return [{ content: "Original", callback: () => null }];
  };

  const fetchImpl = async (url, options = {}) => {
    const key = String(url);
    requests.push({
      url: key,
      method: options.method || "GET",
      headers: clone(options.headers || {}),
      body: options.body,
    });
    operationLog.push({ kind: "request", url: key, method: options.method || "GET" });
    const entry = responses[key];
    if (entry instanceof Error) {
      throw entry;
    }
    if (entry == null) {
      operationLog.push({ kind: "response", url: key, status: 404 });
      return makeResponse(404, { error: `No mock for ${key}` });
    }
    if (typeof entry === "function") {
      const value = await entry({ url: key, options: clone(options) });
      operationLog.push({ kind: "response", url: key, status: value.status || 200 });
      return makeResponse(value.status || 200, value.body);
    }
    operationLog.push({ kind: "response", url: key, status: entry.status || 200 });
    return makeResponse(entry.status || 200, entry.body);
  };

  const tempRoot = await mkdtemp(path.join(os.tmpdir(), "vibecomfy-browser-"));
  const comfyRoot = path.join(tempRoot, "comfy");
  const webRoot = path.join(comfyRoot, "custom_nodes", "web");
  const scriptsRoot = path.join(comfyRoot, "scripts");
  await mkdir(webRoot, { recursive: true });
  await mkdir(scriptsRoot, { recursive: true });
  await writeFile(path.join(comfyRoot, "package.json"), '{ "type": "module" }\n');
  await writeFile(path.join(scriptsRoot, "app.js"), "export const app = globalThis.__VIBECOMFY_BROWSER_APP__;\n");
  await writeFile(path.join(scriptsRoot, "api.js"), "export const api = globalThis.__VIBECOMFY_BROWSER_API__;\n");
  await writeFile(path.join(webRoot, "vibecomfy_roundtrip.js"), await readFile(EXTENSION_SOURCE, "utf8"));

  const apiEventListeners = {};
  const mockApi = {
    clientId: `test-client-${Date.now()}`,
    addEventListener(event, listener) {
      if (!apiEventListeners[event]) {
        apiEventListeners[event] = [];
      }
      apiEventListeners[event].push(listener);
    },
    removeEventListener(event, listener) {
      const listeners = apiEventListeners[event] || [];
      apiEventListeners[event] = listeners.filter((entry) => entry !== listener);
    },
  };

  function dispatchApiEvent(event, data) {
    const listeners = apiEventListeners[event] || [];
    const detail = data != null ? { detail: data } : {};
    for (const listener of listeners) {
      try {
        listener(detail);
      } catch (_err) {
        // Best-effort: event listener errors must not break dispatch.
      }
    }
  }

  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;
  const originalFetch = globalThis.fetch;
  const originalConsole = globalThis.console;
  const originalURL = globalThis.URL;
  const originalApp = globalThis.__VIBECOMFY_BROWSER_APP__;
  const originalApi = globalThis.__VIBECOMFY_BROWSER_API__;
  const hadCrypto = "crypto" in globalThis;

  const blobUrls = [];
  globalThis.URL = {
    createObjectURL(_blob) {
      const url = `blob:mock-${blobUrls.length}`;
      blobUrls.push(url);
      return url;
    },
    revokeObjectURL(url) {
      const idx = blobUrls.indexOf(url);
      if (idx >= 0) {
        blobUrls.splice(idx, 1);
      }
    },
  };

  globalThis.document = document;
  globalThis.window = { document, LiteGraph: { LGraphCanvas: LiteGraphCanvas } };
  globalThis.fetch = fetchImpl;
  globalThis.__VIBECOMFY_BROWSER_APP__ = app;
  globalThis.__VIBECOMFY_BROWSER_API__ = mockApi;
  if (!hadCrypto) {
    globalThis.crypto = (await import("node:crypto")).webcrypto;
  }
  globalThis.console = {
    ...originalConsole,
    log: (...args) => consoleCapture.log.push(args.map(String).join(" ")),
    warn: (...args) => consoleCapture.warn.push(args.map(String).join(" ")),
    error: (...args) => consoleCapture.error.push(args.map(String).join(" ")),
  };

  let importedModule = null;

  async function loadExtension() {
    if (importedModule) {
      return importedModule;
    }
    const target = pathToFileURL(path.join(webRoot, "vibecomfy_roundtrip.js")).href;
    importedModule = await import(`${target}?t=${Date.now()}`);
    return importedModule;
  }

  function getExtension() {
    assert.equal(registeredExtensions.length, 1, "expected one registered extension");
    return registeredExtensions[0];
  }

  function findButtons(label) {
    return document.body.querySelectorAll(
      (node) => node.tagName === "BUTTON" && node.textContent === label,
    );
  }

  return {
    app,
    api: mockApi,
    apiEventListeners,
    dispatchApiEvent,
    document,
    window: globalThis.window,
    requests,
    operationLog,
    consoleCapture,
    loadGraphDataCalls,
    graphClearCalls,
    graphConfigureCalls,
    graphChangeCalls,
    graphDirtyCanvasCalls,
    canvasDrawCalls,
    queuePromptCalls,
    serializeCalls,
    toasts,
    registeredExtensions,
    async loadExtension() {
      return loadExtension();
    },
    async setup() {
      const extension = getExtension();
      if (typeof extension.setup === "function") {
        await extension.setup();
      }
      return extension;
    },
    getExtension,
    getMenuCommands() {
      return getExtension().menuCommands || [];
    },
    getCommands() {
      return getExtension().commands || [];
    },
    async invokeCommand(id) {
      const command = this.getCommands().find((entry) => entry.id === id);
      assert(command, `missing command ${id}`);
      return command.function();
    },
    clickButton(label) {
      const button = findButtons(label)[0];
      assert(button, `missing button ${label}`);
      return button.click();
    },
    getPanelRoots() {
      return document.body.querySelectorAll(
        (node) => node.dataset?.vibecomfyPanelRoot === "1",
      );
    },
    getCanvasMenuOptions() {
      const canvas = new LiteGraphCanvas();
      return canvas.getCanvasMenuOptions();
    },
    textDump() {
      return document.body.querySelectorAll(() => true).map((node) => node.textContent).join("\n");
    },
    setCurrentGraph(nextGraph) {
      liveCanvasRevision += 1;
      currentGraph = clone(nextGraph);
      syncLiveGraphNodes();
    },
    setCurrentGraphWithoutRevisionBump(nextGraph) {
      currentGraph = clone(nextGraph);
      syncLiveGraphNodes();
    },
    bumpLiveCanvasToken() {
      liveCanvasRevision += 1;
      syncLiveGraphNodes();
    },
    getCurrentGraph() {
      return clone(currentGraph);
    },
    async dispose() {
      if (originalDocument === undefined) delete globalThis.document;
      else globalThis.document = originalDocument;
      if (originalWindow === undefined) delete globalThis.window;
      else globalThis.window = originalWindow;
      if (originalFetch === undefined) delete globalThis.fetch;
      else globalThis.fetch = originalFetch;
      if (originalURL === undefined) delete globalThis.URL;
      else globalThis.URL = originalURL;
      if (originalApp === undefined) delete globalThis.__VIBECOMFY_BROWSER_APP__;
      else globalThis.__VIBECOMFY_BROWSER_APP__ = originalApp;
      if (originalApi === undefined) delete globalThis.__VIBECOMFY_BROWSER_API__;
      else globalThis.__VIBECOMFY_BROWSER_API__ = originalApi;
      if (!hadCrypto) delete globalThis.crypto;
      globalThis.console = originalConsole;
      await rm(tempRoot, { recursive: true, force: true });
    },
  };
}
