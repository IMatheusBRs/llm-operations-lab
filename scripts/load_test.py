from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx


async def run_one(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, index: int
) -> tuple[int, float]:
    async with semaphore:
        started = time.perf_counter()
        response = await client.post(
            "/v1/generate",
            headers={"X-API-Key": "demo-key-local-only"},
            json={"model": "mock-echo", "prompt": f"requisição sintética {index}"},
        )
        return response.status_code, time.perf_counter() - started


async def execute(args: argparse.Namespace) -> dict[str, object]:
    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=10.0) as client:
        started = time.perf_counter()
        results = await asyncio.gather(
            *(run_one(client, semaphore, index) for index in range(args.requests))
        )
        elapsed = time.perf_counter() - started
    statuses = Counter(status for status, _ in results)
    durations_ms = sorted(duration * 1000 for _, duration in results)
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "base_url": args.base_url,
        },
        "parameters": {"requests": args.requests, "concurrency": args.concurrency},
        "results": {
            "status_counts": dict(sorted(statuses.items())),
            "elapsed_seconds": round(elapsed, 4),
            "requests_per_second": round(args.requests / elapsed, 2),
            "latency_ms": {
                "min": round(min(durations_ms), 3),
                "mean": round(statistics.fmean(durations_ms), 3),
                "p95": round(durations_ms[max(0, int(len(durations_ms) * 0.95) - 1)], 3),
                "max": round(max(durations_ms), 3),
            },
        },
        "notes": "Mede apenas o provedor mock local; não representa desempenho de LLM real.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga pequena e reproduzível no modo mock")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests e concurrency devem ser positivos")
    result = asyncio.run(execute(args))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")


if __name__ == "__main__":
    main()

