"""Manual smoke test against the live Hindsight bank.

Run from the backend directory:
    python scripts/smoke_test.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hindsight_client import memory  # noqa: E402


async def main() -> int:
    print("clients:", await memory.list_clients(), "\n")

    result = await memory.generate_brief(client_name="Bloom & Co Boutique")
    structured = result["structured"] or {}

    print("structured_output_error:", result["structured_output_error"])
    print("cited memories         :", len(result["cited"]))
    print()

    if not structured:
        print("!! No structured output. Markdown fallback:\n")
        print(result["text"][:1500])
        return 1

    for key in (
        "confidence",
        "payment_behavior",
        "revision_scope_behavior",
        "communication_style",
        "recommendation",
    ):
        print(f"{key}:\n  {structured.get(key)}\n")

    print("red flags:")
    for flag in structured.get("red_flags") or []:
        print(f"  [{flag.get('severity')}] {flag.get('flag')} (n={flag.get('evidence_count')})")
        for evidence in (flag.get("evidence") or [])[:4]:
            print(f"      - {evidence}")
    print()

    print("cited:")
    for fact in result["cited"][:5]:
        print(f"  - ({fact.get('type')}, {fact.get('occurred_start')}) {fact.get('text')[:110]}")

    # --- Nudge: a 4th revision request should match the revision history ---
    print("\n" + "=" * 58)
    print("NUDGE CHECK - 'a 4th round of revisions' for Bloom & Co Boutique\n")

    nudge = await memory.evaluate_nudge(
        client_name="Bloom & Co Boutique",
        interaction_text=(
            "Client emailed asking for a 4th round of revisions on the logo, "
            "wanting to try yet another colour combination before sign-off."
        ),
    )
    print("structured_output_error:", nudge["structured_output_error"])
    print("cited memories         :", len(nudge["cited"]))
    print("text:\n ", nudge["text"][:1500])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    finally:
        asyncio.run(memory.aclose())
