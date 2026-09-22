from __future__ import annotations

import asyncio
import json
import os

import httpx


async def run_demo() -> None:
    base_url = os.getenv("LAB_BASE_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("LAB_API_KEY", "demo-key-local-only")
    headers = {"X-API-Key": api_key, "X-Correlation-ID": "demo-0001"}
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        health = await client.get("/healthz")
        generation = await client.post(
            "/v1/generate",
            headers=headers,
            json={
                "model": "mock-ops",
                "prompt": "Há um erro de latência no serviço de inferência.",
                "prompt_version": "v1",
            },
        )
        order = await client.get(
            "/v1/tools/purchase-orders/PO-100001", headers=headers
        )
        health.raise_for_status()
        generation.raise_for_status()
        order.raise_for_status()
        payload = {
            "health": health.json(),
            "generation": generation.json(),
            "synthetic_purchase_order": order.json(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
