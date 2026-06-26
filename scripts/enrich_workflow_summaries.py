#!/usr/bin/env python3
"""Generate structured summaries for ingested VibeComfy workflows and write them
back into the corpus JSON and manifest.

Design (SD1/SD2):
- ``title``, ``description``, and ``tags`` are LLM-generated.
- ``task_type``, ``media_type``, ``flags``, and ``complexity`` are derived
  deterministically from workflow structure.
- Summaries are cached by SHA-256 of the compact prompt so identical workflows
  are never re-summarized.
- Every write is idempotent: re-running the same command produces the same
  result.

Architecture:
    This is a single-step orchestrator (the old three-step generate/run/apply
    cycle is retired).  It loads each corpus JSON, builds a duck-typed adapter
    so the upstream analysis module can ingest dicts, calls
    ``vibecomfy.ingest.summarize.summarize_workflow`` to produce the merged
    summary, and writes the result to ``workflow.metadata['summary']`` and the
    corresponding ``manifest.json`` row.

Typical usage::

    # Deterministic-only (no LLM → title/description/tags empty):
    python scripts/enrich_workflow_summaries.py --dry-run --limit 5
    python scripts/enrich_workflow_summaries.py --limit 50

    # Full enrichment with LLM (needs OPENROUTER_API_KEY or OPENAI_API_KEY):
    python scripts/enrich_workflow_summaries.py --model deepseek/deepseek-v4-flash

    # Full backfill of all 2,533 workflows:
    python scripts/enrich_workflow_summaries.py --model deepseek/deepseek-v4-flash --limit 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reuse the anonymous Hivemind upload helpers from the external-workflow uploader.
from scripts.upload_external_workflows_to_hivemind import (
    DEFAULT_CONTRIBUTE_URL as _DEFAULT_CONTRIBUTE_URL,
    DEFAULT_HIVEMIND_ANON_KEY as _DEFAULT_HIVEMIND_ANON_KEY,
    DEFAULT_HIVEMIND_API_URL as _DEFAULT_HIVEMIND_API_URL,
    _envelope as _build_hivemind_envelope,
    _find_existing_resource,
    _find_existing_resources,
    _external_key_from_envelope,
    _idempotency_key,
    _post,
    _upload_record,
)
from vibecomfy.ingest.summarize import summarize_workflow

DEFAULT_MANIFEST = REPO_ROOT / "external_workflows" / "manifest.json"
DEFAULT_CORPUS_DIR = REPO_ROOT / "external_workflows" / "corpus"
DEFAULT_CACHE_DIR = REPO_ROOT / "external_workflows" / ".shadow" / "summary-cache"


# ── Duck-typed adapter: corpus dict → VibeWorkflow-like object ──────────
# The analysis functions (vibecomfy.analysis.workflow_summary) expect a
# VibeWorkflow with .nodes.values() → .class_type, .outputs → .output_type,
# .edges, .requirements.models, .requirements.custom_nodes.  We wrap a
# plain corpus dict so those functions work without loading the full object
# graph.


class _DictNodeAdapter:
    __slots__ = ("class_type",)

    def __init__(self, node_dict: dict[str, Any]) -> None:
        self.class_type = node_dict.get("class_type", "?")


class _DictOutputAdapter:
    __slots__ = ("output_type",)

    def __init__(self, output_dict: dict[str, Any]) -> None:
        self.output_type = output_dict.get("output_type", "")


class _DictNodesAdapter:
    """Drop-in for workflow.nodes that supports .values()."""

    __slots__ = ("_nodes",)

    def __init__(self, nodes: dict[str, Any]) -> None:
        self._nodes = {k: _DictNodeAdapter(v) for k, v in nodes.items()}

    def values(self):
        return self._nodes.values()

    def items(self):
        return self._nodes.items()

    def __len__(self) -> int:
        return len(self._nodes)


class _DictReqsAdapter:
    """Drop-in for workflow.requirements."""

    __slots__ = ("models", "custom_nodes")

    def __init__(self, reqs: dict[str, Any] | None) -> None:
        if isinstance(reqs, dict):
            self.models = reqs.get("models", [])
            self.custom_nodes = reqs.get("custom_nodes", [])
        else:
            self.models = []
            self.custom_nodes = []


class DictWorkflowAdapter:
    """Wrap a corpus JSON dict to satisfy the VibeWorkflow duck-type.

    Only the fields consumed by ``vibecomfy.analysis.workflow_summary`` and
    ``vibecomfy.ingest.summarize._build_compact_repr`` are exposed.
    """

    __slots__ = ("nodes", "outputs", "edges", "requirements")

    def __init__(self, workflow_dict: dict[str, Any]) -> None:
        nodes = workflow_dict.get("nodes")
        self.nodes = _DictNodesAdapter(nodes) if isinstance(nodes, dict) else _DictNodesAdapter({})
        outputs = workflow_dict.get("outputs", [])
        if isinstance(outputs, list):
            self.outputs = [_DictOutputAdapter(o) for o in outputs if isinstance(o, dict)]
        else:
            self.outputs = []
        self.edges = workflow_dict.get("edges", [])
        if not isinstance(self.edges, list):
            self.edges = []
        self.requirements = _DictReqsAdapter(workflow_dict.get("requirements"))


# ── Simple LLM client (OpenAI-compatible) ───────────────────────────────
# The ``summarize_workflow`` function expects ``llm_client.complete(prompt)``.
# We provide a thin wrapper around the OpenAI/OpenRouter HTTP API that uses
# environment variables for authentication.


class SimpleLLMClient:
    """OpenAI-compatible LLM client for the summarizer."""

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        self.model = model
        self.base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No API key found. Set OPENROUTER_API_KEY or OPENAI_API_KEY "
                "in the environment."
            )
        import requests
        self._requests = requests
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def complete(self, prompt: str) -> str:
        """Send a completion request and return the response text."""
        resp = self._session.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.3,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ── Content hash for resume/skip ────────────────────────────────────────


def _content_hash(workflow_dict: dict[str, Any]) -> str:
    """Compute a stable hash of the workflow content for resume/skip."""
    # Extract the parts that matter for summarization: node class_types,
    # outputs, requirements, edges count.
    nodes = workflow_dict.get("nodes", {})
    node_types = sorted(
        n.get("class_type", "?")
        for n in (nodes.values() if isinstance(nodes, dict) else [])
    )
    outputs = workflow_dict.get("outputs", [])
    output_types = sorted(
        o.get("output_type", "")
        for o in (outputs if isinstance(outputs, list) else [])
        if isinstance(o, dict)
    )
    reqs = workflow_dict.get("requirements", {}) or {}
    models = sorted(reqs.get("models", [])) if isinstance(reqs, dict) else []
    custom_nodes = sorted(reqs.get("custom_nodes", [])) if isinstance(reqs, dict) else []

    payload = json.dumps({
        "node_types": node_types,
        "output_types": output_types,
        "models": models,
        "custom_nodes": custom_nodes,
        "edge_count": len(workflow_dict.get("edges", []) if isinstance(workflow_dict.get("edges", []), list) else []),
    }, sort_keys=True)

    return hashlib.sha256(payload.encode()).hexdigest()


# ── Manifest helpers ────────────────────────────────────────────────────


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _save_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Hivemind upload helpers ─────────────────────────────────────────────


def _upload_row(
    row: dict[str, Any],
    *,
    contribute_url: str,
    api_url: str,
    anon_key: str,
    skip_existing: bool,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upload a single manifest row to Hivemind via the anonymous endpoint.

    Failures are caught and returned as error statuses so the enrichment run
    never blocks on a network problem.
    """
    workflow_id = str(row.get("workflow_id", "unknown"))
    try:
        envelope = _build_hivemind_envelope(row)
        if skip_existing:
            existing = existing or _find_existing_resource(
                envelope,
                api_url=api_url,
                anon_key=anon_key,
            )
            if existing.get("exists"):
                return {
                    "workflow_id": workflow_id,
                    "status": "skipped_existing",
                    "preflight": existing,
                    "idempotency_key": _idempotency_key(envelope),
                }
        response = _post_with_backoff(
            envelope,
            contribute_url=contribute_url,
            contributor_key=None,
        )
        return {
            "workflow_id": workflow_id,
            "status": "uploaded",
            "response": response,
            "idempotency_key": _idempotency_key(envelope),
        }
    except Exception as exc:  # noqa: BLE001
        return {"workflow_id": workflow_id, "status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _post_with_backoff(
    envelope: dict[str, Any],
    *,
    contribute_url: str,
    contributor_key: str | None,
    attempts: int = 5,
    base_sleep: float = 0.5,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            return _post(envelope, contribute_url=contribute_url, contributor_key=contributor_key)
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else base_sleep * (2**attempt)
            except ValueError:
                wait = base_sleep * (2**attempt)
            time.sleep(wait)
        except TimeoutError as exc:
            last_error = exc
            if attempt >= attempts - 1:
                raise
            time.sleep(base_sleep * (2**attempt))
    raise last_error or TimeoutError("upload failed after retries")


def _preflight_upload_rows(
    rows: list[dict[str, Any]],
    *,
    api_url: str,
    anon_key: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    envelopes = [_build_hivemind_envelope(row) for row in rows]
    if not envelopes:
        return {}
    if len(envelopes) == 1:
        existing = _find_existing_resource(envelopes[0], api_url=api_url, anon_key=anon_key)
        return {_external_key_from_envelope(envelopes[0]): existing}
    return _find_existing_resources(envelopes, api_url=api_url, anon_key=anon_key)


# ── Main enrichment logic ───────────────────────────────────────────────


def _should_skip(
    workflow_dict: dict[str, Any],
    content_hash: str,
    force: bool,
) -> bool:
    """Return True if this workflow already has a current summary."""
    if force:
        return False
    existing = workflow_dict.get("metadata", {}).get("summary")
    if not existing:
        return False
    # If the stored content hash matches, the summary is current.
    return existing.get("_content_hash") == content_hash


def enrich(
    corpus_dir: Path,
    manifest_path: Path,
    *,
    model: str | None = None,
    llm_client: Any = None,
    cache_dir: Path | None = None,
    dry_run: bool = False,
    limit: int = 0,
    force: bool = False,
    workers: int = 1,
    upload: bool = False,
    contribute_url: str | None = None,
    skip_existing_uploads: bool = True,
    upload_sleep: float = 0.1,
    upload_workers: int = 1,
) -> dict[str, int]:
    """Enrich corpus workflows with summaries.

    Parameters
    ----------
    corpus_dir : Path
        Directory containing corpus JSON files.
    manifest_path : Path
        Path to manifest.json.
    model : str or None
        Model name for LLM enrichment.  If None, only deterministic fields
        are written.
    llm_client : optional
        Pre-built LLM client.  If None and *model* is set, a
        ``SimpleLLMClient`` is constructed.
    cache_dir : Path or None
        Directory for LLM response cache.
    dry_run : bool
        If True, print what would happen without writing.
    limit : int
        Maximum number of workflows to process (0 = all).
    force : bool
        If True, re-process workflows that already have summaries.
    upload : bool
        If True, upload each summarized workflow to Hivemind via the anonymous
        ``contribute-resource`` endpoint after enrichment.
    contribute_url : str or None
        Override the Hivemind contribution endpoint.
    skip_existing_uploads : bool
        Preflight Hivemind and skip rows that already exist.
    upload_sleep : float
        Seconds to sleep between uploads.
    upload_workers : int
        Concurrent uploads (default 1).

    Returns
    -------
    dict[str, int]
        Counts: ``processed``, ``skipped``, ``errors``, ``llm_failures``,
        ``dry_run``. When *upload* is true, also ``uploaded``,
        ``upload_skipped``, and ``upload_errors``.
    """
    # Build LLM client if model requested.
    if model and llm_client is None:
        if dry_run:
            # In dry-run mode, don't actually connect to the API.
            llm_client = _DryRunLLMClient(model)
        else:
            try:
                llm_client = SimpleLLMClient(model=model)
                print(f"LLM client ready (model={model})", flush=True)
            except ValueError as exc:
                print(f"WARNING: {exc}", file=sys.stderr)
                print("Continuing with deterministic-only summaries.", file=sys.stderr)
                llm_client = None

    # Load manifest.
    manifest = _load_manifest(manifest_path)
    workflows = manifest.get("workflows", [])
    if not workflows:
        print("Manifest contains no workflows.", file=sys.stderr)
        return {"processed": 0, "skipped": 0, "errors": 0, "llm_failures": 0, "dry_run": 0}

    # Build corpus filename → manifest row lookup.  Ingest may store absolute
    # or relative paths, so we key by the unique filename (canonical hash).
    row_by_corpus: dict[str, dict[str, Any]] = {}
    for row in workflows:
        row_by_corpus[Path(row["corpus_path"]).name] = row

    # Collect corpus files.
    corpus_files = sorted(corpus_dir.glob("*.json"))
    if limit > 0:
        corpus_files = corpus_files[:limit]

    cache_dir_str = str(cache_dir) if cache_dir else None

    counts = {
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "llm_failures": 0,
        "dry_run": 0,
        "uploaded": 0,
        "upload_skipped": 0,
        "upload_errors": 0,
    }
    # Track which rows were actually enriched in this run so the upload phase
    # only touches newly-processed rows, not every summarized row in the manifest.
    processed_corpus_rels: set[str] = set()
    manifest_modified = False

    # Per-thread LLM client so concurrent workers don't share a requests.Session.
    _thread_local = threading.local()

    def _get_thread_client() -> Any:
        if dry_run or not model:
            return None
        # Honor a caller-supplied client (used by tests / orchestrators).
        if llm_client is not None:
            return llm_client
        client = getattr(_thread_local, "client", None)
        if client is None:
            try:
                client = SimpleLLMClient(model=model)
            except ValueError as exc:
                print(f"WARNING: {exc}", file=sys.stderr)
                client = None
            _thread_local.client = client
        return client

    def _process_one(cf_path: Path) -> dict[str, Any]:
        """Process a single corpus file and return a result description."""
        result: dict[str, Any] = {
            "path": cf_path,
            "corpus_rel": cf_path.name,
            "skipped": False,
            "error": False,
            "llm_failure": False,
            "dry_run": dry_run,
            "summary": None,
        }
        try:
            workflow_dict = json.loads(cf_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"ERROR: cannot load {cf_path.name}: {exc}", file=sys.stderr)
            result["error"] = True
            return result

        ch = _content_hash(workflow_dict)
        if _should_skip(workflow_dict, ch, force):
            result["skipped"] = True
            return result

        adapter = DictWorkflowAdapter(workflow_dict)
        summary = summarize_workflow(
            adapter,
            llm_client=_get_thread_client(),
            cache_dir=cache_dir_str,
        )

        if summary is None:
            result["llm_failure"] = True
            summary = summarize_workflow(adapter, llm_client=None, cache_dir=cache_dir_str)
            if summary is None:
                print(f"ERROR: cannot produce summary for {cf_path.name}", file=sys.stderr)
                result["error"] = True
                return result

        summary["_content_hash"] = ch

        if dry_run:
            result["summary"] = summary
            return result

        workflow_dict.setdefault("metadata", {})["summary"] = summary
        try:
            cf_path.write_text(
                json.dumps(workflow_dict, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"ERROR: cannot write {cf_path.name}: {exc}", file=sys.stderr)
            result["error"] = True
            return result

        result["summary"] = summary
        return result

    results: list[dict[str, Any]] = []
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_process_one, cf): cf for cf in corpus_files}
            for future in as_completed(futures):
                results.append(future.result())
    else:
        for cf_path in corpus_files:
            results.append(_process_one(cf_path))

    for res in results:
        if res["error"]:
            counts["errors"] += 1
            continue
        if res["skipped"]:
            counts["skipped"] += 1
            continue
        if res["dry_run"]:
            counts["dry_run"] += 1
            title = res["summary"].get("title") or "(untitled)" if res["summary"] else "(untitled)"
            print(
                f"[DRY-RUN] {res['path'].name}: title={title!r}, "
                f"task_type={res['summary'].get('task_type')}, "
                f"complexity={res['summary'].get('complexity')}"
            )
        else:
            counts["processed"] += 1
            # Use the manifest row's own corpus_path so absolute/relative path
            # mismatches between ingest and enrich don't break upload matching.
            matched_row = row_by_corpus.get(res["corpus_rel"])
            processed_corpus_rels.add(
                matched_row["corpus_path"]
                if matched_row is not None
                else res["corpus_rel"]
            )
            if res["llm_failure"]:
                counts["llm_failures"] += 1
            if counts["processed"] % 100 == 0:
                print(f"  {counts['processed']} workflows processed...", flush=True)

        if res["summary"] is not None:
            row = row_by_corpus.get(res["corpus_rel"])
            if row is not None:
                row["summary"] = res["summary"]
            manifest_modified = True

    # Write manifest if modified.
    if manifest_modified and not dry_run:
        manifest["summary_enrichment"] = {
            "run_at": _utcnow(),
            "model": model or "deterministic-only",
            "processed": counts["processed"],
            "skipped": counts["skipped"],
            "errors": counts["errors"],
            "llm_failures": counts["llm_failures"],
        }
        _save_manifest(manifest, manifest_path)
        print("Manifest written.", flush=True)

    # ── Upload summarized workflows to Hivemind (anonymous endpoint) ────────
    if upload and not dry_run:
        contribute_url = contribute_url or _DEFAULT_CONTRIBUTE_URL
        api_url = _DEFAULT_HIVEMIND_API_URL
        anon_key = _DEFAULT_HIVEMIND_ANON_KEY

        upload_rows = [
            row for row in workflows
            if row.get("summary")
            and not row.get("error")
            and row.get("corpus_path") in processed_corpus_rels
        ]
        if upload_rows:
            print(f"Uploading {len(upload_rows)} workflow(s) to Hivemind...", flush=True)
            preflight_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            if skip_existing_uploads:
                preflight_by_key = _preflight_upload_rows(
                    upload_rows,
                    api_url=api_url,
                    anon_key=anon_key,
                )

            row_by_id = {str(row.get("workflow_id", "unknown")): row for row in upload_rows}

            def _record_upload(result: dict[str, Any]) -> None:
                status = result.get("status")
                if status == "uploaded":
                    counts["uploaded"] += 1
                elif status == "skipped_existing":
                    counts["upload_skipped"] += 1
                elif status == "error":
                    counts["upload_errors"] += 1
                    workflow_id = result.get("workflow_id", "unknown")
                    error = result.get("error", "unknown error")
                    print(f"UPLOAD ERROR: {workflow_id}: {error}", file=sys.stderr)
                workflow_id = str(result.get("workflow_id", "unknown"))
                row = row_by_id.get(workflow_id)
                if row is not None:
                    envelope = _build_hivemind_envelope(row)
                    row["hivemind_upload"] = _upload_record(result, envelope)
                    manifest["upload_summary"] = {
                        "updated_at": _utcnow(),
                        "uploaded": counts["uploaded"],
                        "upload_skipped": counts["upload_skipped"],
                        "upload_errors": counts["upload_errors"],
                    }
                    _save_manifest(manifest, manifest_path)

            if upload_workers > 1:
                with ThreadPoolExecutor(max_workers=upload_workers) as executor:
                    futures = {
                        executor.submit(
                            _upload_row,
                            row,
                            contribute_url=contribute_url,
                            api_url=api_url,
                            anon_key=anon_key,
                            skip_existing=skip_existing_uploads,
                            existing=preflight_by_key.get(
                                _external_key_from_envelope(_build_hivemind_envelope(row))
                            ),
                        ): row
                        for row in upload_rows
                    }
                    for future in as_completed(futures):
                        _record_upload(future.result())
            else:
                for row in upload_rows:
                    _record_upload(
                        _upload_row(
                            row,
                            contribute_url=contribute_url,
                            api_url=api_url,
                            anon_key=anon_key,
                            skip_existing=skip_existing_uploads,
                            existing=preflight_by_key.get(
                                _external_key_from_envelope(_build_hivemind_envelope(row))
                            ),
                        )
                    )
                    if upload_sleep:
                        time.sleep(upload_sleep)

    return counts


class _DryRunLLMClient:
    """Fake LLM client for dry-run mode (logs the prompt, returns empty)."""

    def __init__(self, model: str) -> None:
        self.model = model

    def complete(self, prompt: str) -> str:
        # In dry-run mode, return valid JSON with empty fields so the
        # pipeline exercises the full path.
        return json.dumps({"title": "(dry-run)", "description": "(dry-run)", "tags": []})


# ── CLI ─────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST,
        help="Path to manifest.json (default: %(default)s)",
    )
    parser.add_argument(
        "--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR,
        help="Directory containing corpus JSON files (default: %(default)s)",
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
        help="Directory for LLM response cache (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for LLM enrichment (e.g. 'deepseek/deepseek-v4-flash'). "
             "If not set, only deterministic fields are written.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be done without writing any files.",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Process at most N workflows (0 = all).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-process workflows even if they already have a summary.",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Number of concurrent workflows to process (default: %(default)s).",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="Upload each summarized workflow to Hivemind via the anonymous "
             "contribute-resource endpoint.",
    )
    parser.add_argument(
        "--contribute-url",
        default=None,
        help="Override the Hivemind contribution endpoint (default: anonymous "
             "contribute-resource edge function).",
    )
    parser.add_argument(
        "--skip-existing-uploads", action="store_true", default=True,
        help="Preflight Hivemind and skip rows that already exist (default: true).",
    )
    parser.add_argument(
        "--no-skip-existing-uploads", dest="skip_existing_uploads",
        action="store_false",
        help="Disable preflight existence checks and re-upload every row.",
    )
    parser.add_argument(
        "--upload-sleep", type=float, default=0.1,
        help="Seconds to sleep between sequential uploads (default: %(default)s).",
    )
    parser.add_argument(
        "--upload-workers", type=int, default=1,
        help="Concurrent uploads when --upload is used (default: %(default)s).",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Validate paths.
    if not args.manifest.exists():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    if not args.corpus_dir.is_dir():
        print(f"Corpus directory not found: {args.corpus_dir}", file=sys.stderr)
        return 1

    print(f"Corpus dir: {args.corpus_dir}")
    print(f"Manifest:   {args.manifest}")
    print(f"Model:      {args.model or 'deterministic-only'}")
    print(f"Dry run:    {args.dry_run}")
    print(f"Limit:      {args.limit or 'all'}")
    print(f"Force:      {args.force}")
    print(f"Workers:    {args.workers}")
    print(f"Upload:     {args.upload}")
    if args.upload:
        print(f"  endpoint: {args.contribute_url or _DEFAULT_CONTRIBUTE_URL}")
        print(f"  skip existing: {args.skip_existing_uploads}")
        print(f"  upload sleep: {args.upload_sleep}")
        print(f"  upload workers: {args.upload_workers}")
    print()

    counts = enrich(
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest,
        model=args.model,
        cache_dir=args.cache_dir if args.model else None,
        dry_run=args.dry_run,
        limit=args.limit,
        force=args.force,
        workers=args.workers,
        upload=args.upload,
        contribute_url=args.contribute_url,
        skip_existing_uploads=args.skip_existing_uploads,
        upload_sleep=args.upload_sleep,
        upload_workers=args.upload_workers,
    )

    print()
    print(f"Processed:    {counts['processed']}")
    print(f"Skipped:      {counts['skipped']}")
    print(f"Errors:       {counts['errors']}")
    print(f"LLM failures: {counts['llm_failures']}")
    if counts["dry_run"]:
        print(f"Dry-run:      {counts['dry_run']} (no files written)")
    if args.upload:
        print(f"Uploaded:     {counts['uploaded']}")
        print(f"Upload skips: {counts['upload_skipped']}")
        print(f"Upload errors:{counts['upload_errors']}")

    return 0 if counts["errors"] == 0 and counts["upload_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
