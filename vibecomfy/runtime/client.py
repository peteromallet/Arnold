from __future__ import annotations

from typing import Any

import httpx


class ComfyClient:
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url.rstrip("/")

    async def ready(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.server_url}/system_stats")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def queue_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.server_url}/prompt", json={"prompt": prompt})
            response.raise_for_status()
            return response.json()

    async def free(self, *, unload_models: bool = True, free_memory: bool = True) -> dict[str, Any]:
        """Queue an async Comfy free request; effects apply at a prompt boundary."""
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.server_url}/api/free", json=payload)
            response.raise_for_status()
            if not getattr(response, "content", b""):
                return {}
            return response.json()

    async def object_info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.server_url}/object_info")
            response.raise_for_status()
            return response.json()
