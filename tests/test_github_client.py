from __future__ import annotations

import base64
import json

import httpx

from agent_kit.github_client import GITHUB_API_VERSION, GitHubClient, MAX_FILE_BYTES
from tests.helpers import create_store


def _client(handler, *, store=None) -> GitHubClient:
    return GitHubClient(
        token="ghp_test",
        store=store,
        base_url="https://api.github.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _response(status: int, payload, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers or {})


def test_repo_metadata_headers_and_success() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["version"] = request.headers["X-GitHub-Api-Version"]
        return _response(
            200,
            {
                "name": "Repo",
                "default_branch": "trunk",
                "private": False,
                "owner": {"login": "Owner"},
            },
        )

    result = _client(handler).repo_metadata("Owner", "Repo")

    assert result["ok"] is True
    assert result["repo"]["owner"] == "owner"
    assert result["repo"]["name"] == "repo"
    assert result["repo"]["default_branch"] == "trunk"
    assert seen == {"auth": "Bearer ghp_test", "version": GITHUB_API_VERSION}


def test_org_repo_pagination_and_structured_errors() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.params.get("page") == "1":
            return _response(200, [{"name": f"repo-{i}", "owner": {"login": "Org"}} for i in range(100)])
        return _response(200, [{"name": "last", "owner": {"login": "Org"}}])

    result = _client(handler).org_repos("Org")

    assert result["ok"] is True
    assert len(result["repos"]) == 101
    assert len(calls) == 2

    missing = _client(lambda request: _response(404, {"message": "nope"})).repo_metadata("x", "y")
    assert missing["ok"] is False
    assert missing["error"]["type"] == "not_found"


def test_tree_file_search_and_unsupported_file_size() -> None:
    content = base64.b64encode(b"line1\nline2").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/git/trees/" in path:
            return _response(200, {"tree": [{"path": "src/app.py", "type": "blob", "sha": "abc"}]})
        if "/contents/" in path:
            return _response(200, {"type": "file", "size": 11, "encoding": "base64", "content": content, "sha": "def"})
        if path == "/search/code":
            return _response(200, {"items": [{"path": "src/app.py", "name": "app.py", "sha": "abc", "html_url": "u"}]})
        raise AssertionError(path)

    client = _client(handler)

    assert client.tree("o", "r", "main")["tree"][0]["path"] == "src/app.py"
    assert client.file_content("o", "r", "src/app.py", ref="main")["file"]["content"] == "line1\nline2"
    assert client.search_code("o", "r", "needle")["items"][0]["path"] == "src/app.py"

    too_large = _client(
        lambda request: _response(
            200,
            {"type": "file", "size": MAX_FILE_BYTES + 1, "encoding": "base64", "content": content},
        )
    ).file_content("o", "r", "large.bin", ref="main")
    assert too_large["error"]["type"] == "unsupported_file_size"


def test_rate_limit_warning_is_logged_without_token(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")

    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            200,
            {"name": "repo", "owner": {"login": "owner"}, "default_branch": "main"},
            {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "19",
                "X-RateLimit-Used": "81",
            },
        )

    assert _client(handler, store=store).repo_metadata("owner", "repo")["ok"]
    row = conn.execute("SELECT level, category, event_type, details FROM system_logs").fetchone()
    assert row["level"] == "warn"
    assert row["category"] == "external_api"
    assert row["event_type"] == "github_rate_limit_high"
    assert "ghp_test" not in json.dumps(json.loads(row["details"]))
