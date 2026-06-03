from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from vibecomfy.comfy_nodes.agent_session import payload_hash, structural_graph_hash


def test_browser_harness_smoke() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser harness smoke")

    result = subprocess.run(
        [node, "--test", "tests/browser/roundtrip_smoke.test.mjs"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_browser_canonical_hash_matches_python_payload_hash() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser hash parity")

    payloads = [
        {
            "graph": {
                "meta": {"locale": "café 漢字", "seed": 9007199254740991, "cfg": 7.5},
                "nodes": [
                    {
                        "id": 2,
                        "type": "SaveImage",
                        "widgets_values": [{"beta": 2, "alpha": 1}, ["frame-1", {"z": 3, "a": 2}]],
                        "properties": {"vibecomfy_uid": "uid-2", "nested": {"zeta": 2, "alpha": 1}},
                    },
                    {
                        "id": 1,
                        "type": "Input",
                        "properties": {"vibecomfy_uid": "uid-1", "prompt": "naïve façade"},
                    },
                ],
                "links": [[1, 1, 0, 2, 0, "IMAGE"]],
            }
        },
        {
            "graph": {
                "links": [],
                "nodes": [
                    {
                        "id": 4,
                        "type": "KSampler",
                        "widgets_values": [123456789, 20, 0.125, "euler"],
                        "properties": {"vibecomfy_uid": "uid-4", "labels": ["ä", "ß", "ç"]},
                    }
                ],
                "extras": {
                    "sorted_key_edge_case": {
                        "zebra": 1,
                        "alpha": 2,
                        "middle": {"omega": 9, "beta": 3},
                    }
                },
            }
        },
        {
            "graph": {
                "nodes": [
                    {
                        "id": 7,
                        "type": "PreviewImage",
                        "properties": {"vibecomfy_uid": "uid-7", "floats": [0.5, 1.25, 2.75]},
                    }
                ],
                "links": [],
                "audit": {
                    "reviewer": {"notes": ["résumé", "jalapeño"], "accepted": False},
                    "history": [
                        {"turn_id": "0001", "state": "candidate"},
                        {"turn_id": "0002", "state": "unknown"},
                    ],
                },
            }
        },
    ]

    script = """
import crypto from "node:crypto";

function canonicalizeJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => canonicalizeJsonValue(entry));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, canonicalizeJsonValue(entryValue)]),
    );
  }
  return value;
}

const payloads = JSON.parse(process.argv[1]);
const hashes = payloads.map((value) =>
  crypto.createHash("sha256").update(JSON.stringify(canonicalizeJsonValue(value)), "utf8").digest("hex"),
);
process.stdout.write(JSON.stringify(hashes));
"""
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, json.dumps(payloads, ensure_ascii=False)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    js_hashes = json.loads(result.stdout)
    py_hashes = [payload_hash(payload) for payload in payloads]
    assert js_hashes == py_hashes


def test_browser_structural_hash_matches_python_structural_graph_hash() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser structural hash parity")

    graphs = [
        {
            "extra": {"ds": {"scale": 1.0}},
            "nodes": [
                {
                    "id": 10,
                    "type": "KSampler",
                    "pos": [100, 200],
                    "size": [300, 400],
                    "order": 7,
                    "flags": {"collapsed": True},
                    "properties": {"vibecomfy_uid": "volatile"},
                    "mode": 0,
                    "inputs": [{"name": "model", "link": 99, "type": "MODEL"}],
                    "outputs": [{"name": "LATENT", "links": [12, 3]}],
                    "widgets_values": [
                        123,
                        {"keep": "value", "videopreview": {"frame": 9, "url": "/view"}},
                    ],
                }
            ],
            "links": [[99, 1, 0, 10, 0, "MODEL"], [3, 10, 0, 11, 0, "LATENT"]],
            "groups": [{"title": "ignored"}],
        }
    ]

    script = """
import crypto from "node:crypto";

function canonicalizeJsonValue(value) {
  if (Array.isArray(value)) return value.map((entry) => canonicalizeJsonValue(entry));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, canonicalizeJsonValue(entryValue)]),
    );
  }
  return value;
}
function normalizeStructuralLink(value) {
  if (Array.isArray(value)) return value.map((entry) => canonicalizeJsonValue(entry));
  if (value && typeof value === "object") return canonicalizeJsonValue(value);
  return value;
}
function isPreviewLikeKey(key) {
  return /(?:^|_)(?:video)?preview(?:_|$)/i.test(String(key || ""));
}
function normalizeStructuralWidgetValue(value) {
  if (Array.isArray(value)) return value.map((entry) => normalizeStructuralWidgetValue(entry));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !isPreviewLikeKey(key))
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entryValue]) => [key, normalizeStructuralWidgetValue(entryValue)]),
    );
  }
  return value;
}
function project(graph) {
  const nodes = Array.isArray(graph?.nodes)
    ? graph.nodes.map((node) => ({
        id: node?.id ?? null,
        type: node?.type ?? null,
        mode: node?.mode ?? null,
        inputs: Array.isArray(node?.inputs)
          ? node.inputs.map((input) => ({ name: input?.name ?? null, link: input?.link ?? null }))
          : [],
        outputs: Array.isArray(node?.outputs)
          ? node.outputs.map((output) => ({
              name: output?.name ?? null,
              links: Array.isArray(output?.links) ? [...output.links].sort() : output?.links ?? null,
            }))
          : [],
        widgets_values: normalizeStructuralWidgetValue(node?.widgets_values ?? []),
      }))
    : [];
  nodes.sort((left, right) => {
    const idCmp = String(left.id ?? "").localeCompare(String(right.id ?? ""), undefined, { numeric: true });
    return idCmp || String(left.type ?? "").localeCompare(String(right.type ?? ""));
  });
  const links = Array.isArray(graph?.links) ? graph.links.map((link) => normalizeStructuralLink(link)) : [];
  links.sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
  return { nodes, links };
}
const graphs = JSON.parse(process.argv[1]);
const hashes = graphs.map((graph) =>
  crypto.createHash("sha256").update(JSON.stringify(canonicalizeJsonValue(project(graph))), "utf8").digest("hex"),
);
process.stdout.write(JSON.stringify(hashes));
"""
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, json.dumps(graphs, ensure_ascii=False)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert json.loads(result.stdout) == [structural_graph_hash(graph) for graph in graphs]
