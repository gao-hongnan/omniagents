"""Background jobs."""

import asyncio
import json
import os


async def cleanup_temp(path: str) -> None:
    await asyncio.sleep(0)
    if os.path.exists(path):
        os.remove(path)


async def process(job: dict[str, str], out_dir: str) -> str:
    result = json.dumps(job)
    out_path = os.path.join(out_dir, f"{job['id']}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(result)
    return out_path
