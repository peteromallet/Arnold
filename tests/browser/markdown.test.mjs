import test from "node:test";
import assert from "node:assert/strict";

import { renderMarkdown } from "../../vibecomfy/comfy_nodes/web/markdown.js";

class FakeElement {
  constructor(ownerDocument, tagName) {
    this.ownerDocument = ownerDocument;
    this.tagName = String(tagName).toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.style = {};
    this.dataset = {};
    this.attributes = {};
    this._textContent = "";
  }

  get textContent() {
    if (this.children.length > 0) {
      return this.children.map((child) => (child == null ? "" : String(child.textContent || ""))).join("");
    }
    return this._textContent;
  }

  set textContent(value) {
    this._textContent = String(value == null ? "" : value);
    this.children.length = 0;
  }

  appendChild(child) {
    if (child.parentNode && child.parentNode !== this) {
      child.parentNode.removeChild(child);
    } else if (child.parentNode === this) {
      this.removeChild(child);
    }
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
}

class FakeTextNode {
  constructor(text) {
    this.textContent = String(text);
  }
}

class FakeDocument {
  createElement(tagName) {
    return new FakeElement(this, tagName);
  }

  createTextNode(text) {
    return new FakeTextNode(text);
  }
}

function makeDocument() {
  return new FakeDocument();
}

function firstTag(container, tagName) {
  const visit = (node) => {
    if (node.tagName === tagName.toUpperCase()) {
      return node;
    }
    for (const child of node.children || []) {
      const found = visit(child);
      if (found) return found;
    }
    return null;
  };
  return visit(container);
}

function allTags(container, tagName) {
  const out = [];
  const visit = (node) => {
    if (node.tagName === tagName.toUpperCase()) {
      out.push(node);
    }
    for (const child of node.children || []) {
      visit(child);
    }
  };
  visit(container);
  return out;
}

test("renderMarkdown returns a container with parsed block and inline elements", () => {
  const doc = makeDocument();
  const md = "# Heading\n\nThis is **bold** and _italic_ with `inline code`.\n\n- item one\n- item two\n\n[link](https://example.com)";
  const container = renderMarkdown(doc, md);

  assert.equal(container.tagName, "DIV");
  assert.equal(firstTag(container, "h1")?.textContent, "Heading");

  const strong = firstTag(container, "strong");
  assert.equal(strong?.textContent, "bold");

  const em = firstTag(container, "em");
  assert.equal(em?.textContent, "italic");

  const code = firstTag(container, "code");
  assert.equal(code?.textContent, "inline code");

  const lis = allTags(container, "li");
  assert.equal(lis.length, 2);
  assert.equal(lis[0].textContent, "item one");
  assert.equal(lis[1].textContent, "item two");

  const link = firstTag(container, "a");
  assert.equal(link?.textContent, "link");
  assert.equal(link?.href, "https://example.com");
  assert.equal(link?.target, "_blank");
});

test("renderMarkdown escapes raw HTML and prevents script injection", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "Hello <script>alert(1)</script> world");
  const scripts = allTags(container, "script");
  assert.equal(scripts.length, 0);
  assert.equal(container.textContent, "Hello <script>alert(1)</script> world");
});

test("renderMarkdown renders fenced code blocks", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "```js\nconst x = 1;\n```");
  const pre = firstTag(container, "pre");
  const code = firstTag(container, "code");
  assert.ok(pre);
  assert.ok(code);
  assert.equal(code.dataset.language, "js");
  assert.equal(code.textContent, "const x = 1;");
});

test("renderMarkdown handles plain text without markdown syntax", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "Just a plain message.");
  assert.equal(container.textContent, "Just a plain message.");
  assert.equal(firstTag(container, "p")?.style.marginBottom, "0");
});

test("renderMarkdown keeps plain-text angle brackets and ampersands as text", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "Use x < y && y > z in plain text.");
  assert.equal(container.textContent, "Use x < y && y > z in plain text.");
  assert.equal(allTags(container, "script").length, 0);
  assert.equal(allTags(container, "a").length, 0);
});

test("renderMarkdown collapses single newlines in plain paragraphs", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "First line\nsecond line");
  assert.equal(container.textContent, "First line second line");
  assert.equal(allTags(container, "p").length, 1);
});

test("renderMarkdown returns empty container for empty or non-string input", () => {
  const doc = makeDocument();
  assert.equal(renderMarkdown(doc, "").textContent, "");
  assert.equal(renderMarkdown(doc, null).textContent, "");
  assert.equal(renderMarkdown(doc, undefined).textContent, "");
});

test("renderMarkdown drops unsafe link schemes", () => {
  const doc = makeDocument();
  const container = renderMarkdown(
    doc,
    "[safe](https://example.com) [mail](mailto:test@example.com) [unsafe](javascript:alert) [data](data:text/html;base64,PHNjcmlwdD4=) [relative](/path) [bare](docs/page.md) [anchor](#top) [protocol-relative](//example.com)",
  );
  const links = allTags(container, "a");
  assert.equal(links.length, 5);
  assert.equal(links[0].href, "https://example.com");
  assert.equal(links[1].href, "mailto:test@example.com");
  assert.equal(links[2].href, "/path");
  assert.equal(links[3].href, "docs/page.md");
  assert.equal(links[4].href, "#top");
  assert.equal(container.textContent, "safe mail unsafe data relative bare anchor protocol-relative");
});

test("renderMarkdown rejects links with control characters", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "[unsafe](java\tscript:alert(1))");
  assert.equal(allTags(container, "a").length, 0);
  assert.equal(container.textContent, "unsafe");
});

test("renderMarkdown consumes unsafe links with balanced parentheses as plain label text", () => {
  const doc = makeDocument();
  const container = renderMarkdown(doc, "[unsafe](javascript:alert(1))");
  assert.equal(allTags(container, "a").length, 0);
  assert.equal(container.textContent, "unsafe");
});

test("renderMarkdown preserves text nodes in a real-DOM-like document", () => {
  // Simulate a browser DocumentFragment/text-node environment to ensure the
  // renderer does not rely on FakeElement-only behaviour.
  const textNodes = [];
  const doc = {
    createElement(tag) {
      const el = new FakeElement(doc, tag);
      el.childNodes = [];
      const origAppend = el.appendChild.bind(el);
      el.appendChild = (child) => {
        el.childNodes.push(child);
        return origAppend(child);
      };
      return el;
    },
    createTextNode(t) {
      const node = { textContent: String(t), nodeType: 3 };
      textNodes.push(node);
      return node;
    },
  };
  const container = renderMarkdown(doc, "Plain **bold** text.");
  assert.equal(container.textContent, "Plain bold text.");
  assert.ok(textNodes.length > 0, "text nodes should be created");
});
