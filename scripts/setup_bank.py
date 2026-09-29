#!/usr/bin/env python3
"""Provision the ClientSense Hindsight bank.

Everything the README describes about the memory bank - the mission, the
directives, the skepticism setting - used to be prose only. This script makes
it real by applying it through the API, so `reflect` is actually bound by those
rules rather than merely being asked nicely in a prompt.

Usage:
    python scripts/setup_bank.py

The bank is created automatically on its first write, so seed_data.py can run
before this script. Config and directive calls return 404 until the bank
exists; this script detects that and says so rather than failing obscurely.

Safe to re-run: configuration is an upsert and directives are skipped when a
directive of the same name already exists.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

try:
    from app.config import settings
    from app.hindsight_client import memory
except ImportError as exc:  # pragma: no cover - setup error path
    print(f"[FAIL] Could not import the backend package: {exc}")
    sys.exit(1)


# --- What the memory bank is for -------------------------------------------
BANK_NAME = "ClientSense"

BANK_MISSION = (
    "You are a business advisor for an independent freelancer. Your job is to "
    "help them avoid repeating past mistakes with specific clients, spot risk "
    "patterns early, and negotiate better terms based on real history."
)

RETAIN_MISSION = (
    "You are recording a freelancer's working history with a client. Extract the "
    "behavioural facts that will matter in a future engagement: how the client "
    "pays and how late, how many rounds of revision they request, how they "
    "communicate, and how they react to scope changes. Always carry through the "
    "date, the project, the amount, and the specific number of days or rounds. "
    "Ignore pleasantries and logistics that carry no behavioural signal."
)

REFLECT_MISSION = (
    "You are a business advisor for an independent freelancer. Brief them before "
    "an engagement and warn them during one, based only on this client's retained "
    "history. Be direct and specific. An honest 'not enough history' is always "
    "better than a confident guess."
)

OBSERVATIONS_MISSION = (
    "Observations are durable, recurring client behaviours, not one-off events. "
    "Consolidate payment punctuality, revision counts, scope-creep habits, and "
    "communication patterns. Always attach the supporting dates and counts. "
    "Ignore isolated incidents that do not yet establish a pattern."
)

#: Scale is 1-5. 1 = trusting, 3 = balanced, 5 = skeptical.
DISPOSITION = {"skepticism": 4, "literalism": 4, "empathy": 3}

DIRECTIVES: List[Dict[str, Any]] = [
    {
        "name": "Cite evidence",
        "content": (
            "Always cite specific evidence (dates, day counts, amounts, quotes) "
            "whenever you state a pattern, behaviour or risk."
        ),
        "priority": 10,
    },
    {
        "name": "Two instance threshold",
        "content": (
            "Flag a payment or behavioural risk only when it is supported by at "
            "least 2 separate past interactions. A single incident is an anecdote, "
            "not a pattern."
        ),
        "priority": 20,
    },
    {
        "name": "No fabrication",
        "content": (
            "Never assert a pattern that is not backed by retained memory. If the "
            "evidence is thin, say so plainly instead of filling the gap."
        ),
        "priority": 30,
    },
    {
        "name": "Nudge discipline",
        "content": (
            "When judging whether a new interaction warrants a proactive nudge, "
            "default to silence. Nudge only when at least 2 prior interactions "
            "genuinely establish the pattern. A routine interaction must not "
            "trigger an alert."
        ),
        "priority": 40,
    },
]


async def _bank_exists() -> bool:
    return await memory.bank_exists()


async def apply_config() -> bool:
    """Upsert missions and disposition onto the bank."""
    try:
        await memory.apply_bank_config(
            retain_mission=RETAIN_MISSION,
            reflect_mission=REFLECT_MISSION,
            observations_mission=OBSERVATIONS_MISSION,
            retain_extraction_mode="verbose",
            **DISPOSITION,
        )
    except Exception as exc:
        print(f"  [FAIL] Could not apply bank config: {exc}")
        return False

    print("  [OK] Missions applied (retain / reflect / observations)")
    print(
        "  [OK] Disposition applied: "
        + ", ".join(f"{k}={v}" for k, v in DISPOSITION.items())
    )
    return True


async def apply_directives() -> bool:
    """Create any directive that does not already exist."""
    try:
        existing = await memory.list_directives()
    except Exception as exc:
        print(f"  [FAIL] Could not list directives: {exc}")
        return False

    present = {
        (getattr(d, "name", "") or "").strip().lower() for d in existing
    }

    created = skipped = 0
    for directive in DIRECTIVES:
        if directive["name"].lower() in present:
            print(f"  [SKIP] Directive already present: {directive['name']}")
            skipped += 1
            continue
        try:
            await memory.create_directive(
                name=directive["name"],
                content=directive["content"],
                priority=directive["priority"],
            )
            print(f"  [OK] Directive created: {directive['name']}")
            created += 1
        except Exception as exc:
            print(f"  [FAIL] Directive '{directive['name']}': {exc}")

    print(f"  -> {created} created, {skipped} already present")
    return created == len(DIRECTIVES) - skipped


async def main() -> int:
    print("ClientSense - Hindsight bank setup")
    print("=" * 58)

    if not settings.hindsight_configured:
        print("[FAIL] HINDSIGHT_API_KEY / HINDSIGHT_BANK_ID missing from backend/.env")
        return 1

    print(f"Target : {settings.HINDSIGHT_BASE_URL}")
    print(f"Bank   : {settings.HINDSIGHT_BANK_ID}\n")

    exists = await _bank_exists()
    if not exists:
        # Banks auto-create on first write. Try explicitly, but do not treat a
        # rejection as fatal - the config call below will tell us the truth.
        print("Bank not found yet - attempting to create it...")
        try:
            await memory.create_bank(name=BANK_NAME, mission=BANK_MISSION)
            print("  [OK] Bank created")
        except Exception as exc:
            print(f"  [--] Explicit create not available ({type(exc).__name__}).")

    if not await _bank_exists():
        print(
            "\n[FAIL] Bank does not exist yet, and config cannot be applied to a\n"
            "       bank that has never been written to. Run the seeder first:\n\n"
            "           python scripts/seed_data.py\n\n"
            "       then re-run this script."
        )
        return 1

    print("\nApplying configuration...")
    config_ok = await apply_config()

    print("\nApplying directives...")
    directives_ok = await apply_directives()

    print("\n" + "=" * 58)
    if config_ok and directives_ok:
        print("[OK] Bank is fully configured. `reflect` is now bound by these rules.")
        return 0

    print("[WARN] Bank is usable but not fully configured - see failures above.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    finally:
        # The SDK holds an aiohttp session; closing it avoids an
        # "Unclosed client session" warning on exit.
        asyncio.run(memory.aclose())
