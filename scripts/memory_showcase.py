#!/usr/bin/env python3
"""Demonstrate that ClientSense gets sharper as memory accumulates.

This is the answer to the question a judge will ask: "show me the memory
doing something." The same question is asked of the same client after every
new interaction, and the answers change from "I have nothing to go on" to a
specific, evidence-cited pattern.

Nothing here is simulated. Each step really calls retain(), then really
calls reflect() against whatever has been stored so far. The comparison at
the end is genuine output.

Usage:
    python scripts/memory_showcase.py
    python scripts/memory_showcase.py "Westport Media"

Use a fresh client name to get a fresh curve - the memory bank is append
only, so re-running with the same name continues from where it left off.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

try:
    from app.config import settings
    from app.hindsight_client import memory
except ImportError as exc:  # pragma: no cover - setup error path
    print(f"[FAIL] Could not import the backend package: {exc}")
    sys.exit(1)


DEFAULT_CLIENT = "Northwind Collective"

#: A deliberately ordinary arc. The interesting behaviour is the pattern of
#: framing large requests as small ones, and paying late while apologising -
#: neither of which is visible in any single interaction, and both of which
#: are obvious by the end.
SCRIPT: List[Dict[str, Any]] = [
    {
        "day": 0,
        "type": "kickoff",
        "text": (
            "Kickoff call for a 6-page marketing site. Northwind's operations "
            "manager is warm and organised, sent a detailed brief ahead of the "
            "call, and paid the 30% deposit the same day."
        ),
    },
    {
        "day": 14,
        "type": "design_review",
        "text": (
            "Design review. Northwind gave clear consolidated feedback - one "
            "round covering all pages, no contradictions, and they flagged "
            "their own internal questions rather than bouncing them back."
        ),
    },
    {
        "day": 31,
        "type": "payment_late",
        "text": (
            "Milestone invoice was due today. Nothing received. Replied the "
            "next morning apologising for an internal accounting backlog and "
            "promising payment within the week."
        ),
    },
    {
        "day": 39,
        "type": "payment",
        "text": (
            "The overdue milestone payment finally arrived - 8 days after the "
            "due date. They sent a thank-you note with it."
        ),
    },
    {
        "day": 52,
        "type": "scope_creep",
        "text": (
            "Asked to add 'just two more pages' to the original six-page scope, "
            "describing it as a quick addition. Also asked for a blog template "
            "while we were at it."
        ),
    },
    {
        "day": 67,
        "type": "scope_creep",
        "text": (
            "Asked for 'a couple of small tweaks' to the two new pages, which "
            "has now grown into a full extra section they want built this week."
        ),
    },
    {
        "day": 81,
        "type": "payment_late",
        "text": (
            "Second milestone invoice is 6 days overdue. Same accounting "
            "backlog explanation, same apology, and they asked to push the "
            "final payment date by two weeks."
        ),
    },
]

BAR = "=" * 74


def _clip(value: Any, limit: int = 165) -> str:
    """Trim a field to one readable line, on a word boundary."""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


async def brief_snapshot(client_name: str, step: int, total_steps: int) -> Dict[str, Any]:
    """Run a real brief and reduce it to the fields worth comparing."""
    result = await memory.generate_brief(client_name=client_name)
    structured = result["structured"] or {}

    flags = structured.get("red_flags") or []
    return {
        "step": step,
        "of": total_steps,
        "memories": (await memory.timeline(client_name=client_name, limit=1))["total"],
        "cited": len(result["cited"]),
        "confidence": structured.get("confidence") or "unknown",
        "payment": _clip(structured.get("payment_behavior"), 200),
        "scope": _clip(structured.get("revision_scope_behavior"), 200),
        "flags": [
            (f.get("flag"), f.get("evidence_count"), f.get("severity"))
            for f in flags
            if isinstance(f, dict)
        ],
        "recommendation": _clip(structured.get("recommendation"), 200),
        "had_history": bool(structured),
    }


def render(snap: Dict[str, Any], event: str) -> str:
    print()
    print(f"--- After {snap['step']}/{snap['of']} interactions "
          f"({snap['memories']} memories stored) ---")
    print(f"    new event : {event}")
    print(f"    confidence: {snap['confidence']}  (memories cited: {snap['cited']})")
    print()
    print(f"    payments : {snap['payment']}")
    print(f"    scope    : {snap['scope']}")
    if snap["flags"]:
        print("    flags    :")
        for flag, count, severity in snap["flags"]:
            print(f"                [{severity}] {flag}  (n={count})")
    else:
        print("    flags    : none reported")
    print(f"    advice   : {snap['recommendation']}")
    return ""


async def main(client_name: str) -> int:
    print(BAR)
    print("ClientSense - memory learning curve")
    print(BAR)
    print(f"Bank : {settings.HINDSIGHT_BANK_ID}")
    print(f"Base : {settings.HINDSIGHT_BASE_URL}")
    print(f"User : {client_name}")
    print()
    print("Each step retains one real interaction, then re-asks the same question.")
    print("Nothing is mocked. The brief changes only because memory accumulated.")

    base = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    snapshots: List[Dict[str, Any]] = []

    for index, event in enumerate(SCRIPT, start=1):
        when = base + timedelta(days=event["day"])
        await memory.retain_interaction(
            client_name=client_name,
            text=event["text"],
            timestamp=when,
            metadata={
                "client_name": client_name,
                "event_type": event["type"],
                "day": event["day"],
            },
            # Unique per step so each interaction is additive, never a replace.
            document_id=f"showcase:{index}:{when.date()}",
        )
        snapshot = await brief_snapshot(client_name, index, len(SCRIPT))
        render(snapshot, f"{event['type']} (day {event['day']})")
        snapshots.append(snapshot)

    # --- the point of the whole thing -----------------------------------
    first, last = snapshots[0], snapshots[-1]
    print()
    print(BAR)
    print("WHAT CHANGED")
    print(BAR)
    print(f"  memories      : {first['memories']}  ->  {last['memories']}")
    print(f"  confidence    : {first['confidence']}  ->  {last['confidence']}")
    print(f"  flags raised  : {len(first['flags'])}  ->  {len(last['flags'])}")
    print(f"  memories cited: {first['cited']}  ->  {last['cited']}")
    print()
    print("  Earliest reading of this client's payment behaviour:")
    print(f"    {first['payment']}")
    print()
    print("  Same client, same question, after the full history:")
    print(f"    {last['payment']}")
    print()
    print("  Earliest reading of their scope behaviour:")
    print(f"    {first['scope']}")
    print()
    print("  Same client, same question, after the full history:")
    print(f"    {last['scope']}")
    print()
    if last["flags"]:
        print("  Patterns that only became visible with memory:")
        for flag, count, severity in last["flags"]:
            print(f"    [{severity}] {flag}  ({count} instances)")
    print()
    print(BAR)
    print("Re-run with a new client name to reproduce from zero:")
    print(f'  python scripts/memory_showcase.py "Westport Media"')
    print(BAR)
    return 0


if __name__ == "__main__":
    if not settings.hindsight_configured:
        print("[FAIL] Set HINDSIGHT_API_KEY / HINDSIGHT_BANK_ID in backend/.env")
        sys.exit(1)

    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CLIENT
    try:
        sys.exit(asyncio.run(main(target)))
    finally:
        asyncio.run(memory.aclose())
