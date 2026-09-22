from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx


async def evaluate() -> int:
    base_url = os.getenv("LAB_BASE_URL", "http://127.0.0.1:8000")
    api_key = os.getenv("LAB_API_KEY", "demo-key-local-only")
    cases_path = Path(os.getenv("LAB_EVAL_CASES", "evals/cases.jsonl"))
    raw_cases = await asyncio.to_thread(cases_path.read_text, encoding="utf-8")
    cases = [json.loads(line) for line in raw_cases.splitlines() if line.strip()]
    passed = 0
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        for case in cases:
            response = await client.post(
                "/v1/generate",
                headers={"X-API-Key": api_key},
                json={"model": case["model"], "prompt": case["prompt"]},
            )
            output = response.json().get("output", "") if response.is_success else ""
            ok = response.is_success and case["expected_contains"] in output
            print(f"{'PASS' if ok else 'FAIL'} {case['id']}: status={response.status_code}")
            passed += int(ok)
    print(f"resultado: {passed}/{len(cases)} casos sintéticos")
    return 0 if passed == len(cases) else 1


def main() -> None:
    raise SystemExit(asyncio.run(evaluate()))


if __name__ == "__main__":
    main()
