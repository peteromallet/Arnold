"""Small GitHub REST client for codebase research tools."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from agent_kit.code_redaction import redact_code_secrets
from agent_kit.logging import log
from agent_kit.ports import Store


JSONDict = dict[str, Any]
GITHUB_API_VERSION = "2022-11-28"
MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class GitHubClient:
    token: str | None = None
    store: Store | None = None
    base_url: str = "https://api.github.com"
    client: httpx.Client | None = None

    def __post_init__(self) -> None:
        token = self.token if self.token is not None else os.environ.get("GITHUB_PAT")
        object.__setattr__(self, "token", token)
        if not token:
            raise RuntimeError("GITHUB_PAT is required for live GitHub access")
        if self.client is None:
            object.__setattr__(self, "client", httpx.Client(timeout=30.0))

    def repo_metadata(self, owner: str, name: str) -> JSONDict:
        response = self._request("GET", f"/repos/{owner}/{name}")
        if not response["ok"]:
            return response
        data = response["data"]
        return {
            "ok": True,
            "repo": {
                "owner": str(data.get("owner", {}).get("login") or owner).lower(),
                "name": str(data.get("name") or name).lower(),
                "default_branch": data.get("default_branch") or "main",
                "private": bool(data.get("private")),
                "html_url": data.get("html_url"),
                "pushed_at": data.get("pushed_at"),
                "size": data.get("size"),
            },
            "rate_limit": response.get("rate_limit"),
        }

    def org_repos(self, org: str) -> JSONDict:
        repos: list[JSONDict] = []
        page = 1
        while True:
            response = self._request(
                "GET",
                f"/orgs/{org}/repos",
                params={"type": "public", "per_page": 100, "page": page},
            )
            if not response["ok"]:
                return response
            batch = response["data"]
            if not isinstance(batch, list) or not batch:
                break
            repos.extend(
                {
                    "owner": str(row.get("owner", {}).get("login") or org).lower(),
                    "name": str(row.get("name") or "").lower(),
                    "default_branch": row.get("default_branch") or "main",
                    "private": bool(row.get("private")),
                    "html_url": row.get("html_url"),
                }
                for row in batch
            )
            if len(batch) < 100:
                break
            page += 1
        return {"ok": True, "repos": repos}

    def tree(
        self,
        owner: str,
        name: str,
        ref: str,
        *,
        path: str | None = None,
    ) -> JSONDict:
        response = self._request(
            "GET",
            f"/repos/{owner}/{name}/git/trees/{quote(ref, safe='')}",
            params={"recursive": "1"},
        )
        if not response["ok"]:
            return response
        prefix = _normalize_tree_path(path)
        entries = []
        for item in response["data"].get("tree", []):
            item_path = item.get("path")
            if prefix and item_path != prefix and not str(item_path).startswith(prefix + "/"):
                continue
            entries.append(
                {
                    "path": item_path,
                    "type": item.get("type"),
                    "size": item.get("size"),
                    "sha": item.get("sha"),
                }
            )
        return {"ok": True, "tree": entries, "truncated": bool(response["data"].get("truncated"))}

    def file_content(
        self,
        owner: str,
        name: str,
        file_path: str,
        *,
        ref: str,
    ) -> JSONDict:
        if not _valid_file_path(file_path):
            return _error("malformed_path", "File paths must be relative and must not contain '..'.")
        response = self._request(
            "GET",
            f"/repos/{owner}/{name}/contents/{quote(file_path, safe='/')}",
            params={"ref": ref},
        )
        if not response["ok"]:
            return response
        data = response["data"]
        if data.get("type") != "file":
            return _error("unsupported_path", "Path does not refer to a file.")
        size = int(data.get("size") or 0)
        if size > MAX_FILE_BYTES:
            return _error("unsupported_file_size", f"File exceeds {MAX_FILE_BYTES} bytes.")
        encoded = str(data.get("content") or "")
        if data.get("encoding") != "base64":
            return _error("unsupported_encoding", "Only base64 GitHub content responses are supported.")
        content = base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")
        return {
            "ok": True,
            "file": {
                "path": file_path,
                "sha": data.get("sha"),
                "size": size,
                "content": content,
            },
        }

    def search_code(self, owner: str, name: str, query: str) -> JSONDict:
        if not query.strip():
            return _error("malformed_query", "Search query cannot be empty.")
        response = self._request(
            "GET",
            "/search/code",
            params={"q": f"{query} repo:{owner}/{name}", "per_page": 20},
        )
        if not response["ok"]:
            return response
        return {
            "ok": True,
            "items": [
                {
                    "path": item.get("path"),
                    "name": item.get("name"),
                    "sha": item.get("sha"),
                    "url": item.get("html_url"),
                }
                for item in response["data"].get("items", [])
            ],
        }

    def _request(self, method: str, path: str, *, params: JSONDict | None = None) -> JSONDict:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        url = self.base_url.rstrip("/") + path
        response = self.client.request(method, url, params=params, headers=headers)  # type: ignore[union-attr]
        rate = _rate_limit(response.headers)
        self._log_rate_limit(rate, method, path)
        if response.status_code == 404:
            return _error("not_found", "GitHub resource was not found.", status_code=404, rate_limit=rate)
        if response.status_code in {401, 403}:
            error_type = "rate_limited" if rate.get("remaining") == 0 else "forbidden"
            return _error(error_type, "GitHub request was forbidden or rate limited.", status_code=response.status_code, rate_limit=rate)
        if response.status_code >= 400:
            return _error("github_error", "GitHub request failed.", status_code=response.status_code, rate_limit=rate)
        return {"ok": True, "data": response.json(), "rate_limit": rate}

    def _log_rate_limit(self, rate: JSONDict, method: str, path: str) -> None:
        limit = int(rate.get("limit") or 0)
        used = int(rate.get("used") or 0)
        if self.store is None or limit <= 0 or used / limit < 0.8:
            return
        log(
            self.store,
            "warn",
            "external_api",
            "github_rate_limit_high",
            "GitHub API rate-limit usage is at or above 80%.",
            provider="github",
            method=method,
            path=path,
            rate_limit=redact_code_secrets(rate),
        )


def _rate_limit(headers: httpx.Headers) -> JSONDict:
    def as_int(name: str) -> int | None:
        value = headers.get(name)
        return int(value) if value and value.isdigit() else None

    limit = as_int("X-RateLimit-Limit")
    remaining = as_int("X-RateLimit-Remaining")
    used = as_int("X-RateLimit-Used")
    return {
        "limit": limit,
        "remaining": remaining,
        "used": used if used is not None else (limit - remaining if limit is not None and remaining is not None else None),
        "reset": headers.get("X-RateLimit-Reset"),
    }


def _error(error_type: str, message: str, **extra: Any) -> JSONDict:
    return {"ok": False, "error": {"type": error_type, "message": message, **extra}}


def _valid_file_path(path: str) -> bool:
    return bool(path) and not path.startswith("/") and ".." not in path.split("/")


def _normalize_tree_path(path: str | None) -> str | None:
    if path is None:
        return None
    stripped = path.strip("/")
    return stripped or None


__all__ = ["GitHubClient", "GITHUB_API_VERSION", "MAX_FILE_BYTES"]
