"""Diagnose what actually landed in the bank: memory counts and tags."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.hindsight_client import memory  # noqa: E402


async def main() -> int:
    print("bank:", settings.HINDSIGHT_BANK_ID)

    response = await memory._client.alist_memories(bank_id=memory.bank_id, limit=5)
    print("total memories in bank:", response.total)
    print()
    for item in (response.items or [])[:5]:
        print("  text :", (getattr(item, "text", "") or "")[:100])
        print("  tags :", getattr(item, "tags", None))
        print("  meta :", getattr(item, "metadata", None))
        print()

    tags = await memory._client.memory.list_tags(bank_id=memory.bank_id, q="*", limit=50)
    print("all tags:", [(t.tag, t.count) for t in (tags.items or [])])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    finally:
        asyncio.run(memory.aclose())
