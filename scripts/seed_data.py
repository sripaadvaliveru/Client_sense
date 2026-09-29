#!/usr/bin/env python3
"""
Synthetic data seed script for ClientSense
Generates realistic interaction logs for 3 fictional clients and retains them in Hindsight
"""
import asyncio
import os
import random
import sys
from datetime import datetime

# Add the backend directory to the path so `app.*` imports resolve no matter
# which directory this script is launched from.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

try:
    from app.config import settings
    from app.hindsight_client import client_slug, memory
except ImportError as exc:  # pragma: no cover - setup error path
    print(f"[FAIL] Could not import the backend package: {exc}")
    print(f"       Looked in: {os.path.join(PROJECT_ROOT, 'backend')}")
    sys.exit(1)

# Synthetic data for 3 clients over a 6-month timeline
SYNTHETIC_DATA = {
    "TechCorp Startup": [
        {
            "date": "2026-04-15",
            "project": "Website Redesign",
            "amount": 5000,
            "interaction": "Initial kickoff meeting for website redesign project. Client was very clear about requirements and timeline. Paid 50% deposit upfront as agreed.",
            "type": "kickoff"
        },
        {
            "date": "2026-04-22",
            "project": "Website Redesign",
            "amount": 0,
            "interaction": "Client approved the homepage design mockups after minor tweaks. First revision round completed quickly.",
            "type": "design_review"
        },
        {
            "date": "2026-04-29",
            "project": "Website Redesign",
            "amount": 2500,
            "interaction": "Mid-project check-in. Client reported the development is proceeding well and made a timely payment of the second milestone.",
            "type": "payment"
        },
        {
            "date": "2026-05-06",
            "project": "Website Redesign",
            "amount": 0,
            "interaction": "Client requested to 'just add a quick testimonial section' via Slack message. This was outside original scope but seemed minor.",
            "type": "scope_creep"
        },
        {
            "date": "2026-05-13",
            "project": "Website Redesign",
            "amount": 0,
            "interaction": "Client approved all design mockups. Only 2 revision rounds needed total - much fewer than average.",
            "type": "approval"
        },
        {
            "date": "2026-05-20",
            "project": "Website Redesign",
            "amount": 2500,
            "interaction": "Final payment received promptly upon project completion. Client expressed satisfaction with the results.",
            "type": "payment"
        },
        {
            "date": "2026-06-10",
            "project": "Blog Integration",
            "amount": 1500,
            "interaction": "New project started for blog integration. Client communicated requirements clearly via email and paid deposit on time.",
            "type": "kickoff"
        },
        {
            "date": "2026-06-17",
            "project": "Blog Integration",
            "amount": 0,
            "interaction": "Client asked if we could 'also just add social sharing buttons' - another informal scope request via quick chat.",
            "type": "scope_creep"
        },
        {
            "date": "2026-06-24",
            "project": "Blog Integration",
            "amount": 1500,
            "interaction": "Project completed and final payment received on schedule. Client was happy with the work.",
            "type": "payment"
        }
    ],
    "Bloom & Co Boutique": [
        {
            "date": "2026-03-01",
            "project": "Brand Identity Design",
            "amount": 3000,
            "interaction": "Initial consultation for brand identity work. Client was warm and friendly, paid deposit but mentioned they often run late on payments due to cash flow.",
            "type": "kickoff"
        },
        {
            "date": "2026-03-08",
            "project": "Brand Identity Design",
            "amount": 0,
            "interaction": "First logo concepts presented. Client loved them but requested 4 rounds of revisions to perfect the color palette and typography.",
            "type": "design_review"
        },
        {
            "date": "2026-03-15",
            "project": "Brand Identity Design",
            "amount": 0,
            "interaction": "Second revision round completed. Client requested additional variations to test with their focus group.",
            "type": "design_review"
        },
        {
            "date": "2026-03-22",
            "project": "Brand Identity Design",
            "amount": 1500,
            "interaction": "Partial payment received - 15 days late. Client apologized and explained their payment processing was delayed.",
            "type": "payment_late"
        },
        {
            "date": "2026-03-29",
            "project": "Brand Identity Design",
            "amount": 0,
            "interaction": "Third revision round. Client requested completely different direction for secondary logo mark.",
            "type": "design_review"
        },
        {
            "date": "2026-04-05",
            "project": "Brand Identity Design",
            "amount": 0,
            "interaction": "Fourth revision round completed. Client still not entirely satisfied but agreed to move forward with current direction.",
            "type": "design_review"
        },
        {
            "date": "2026-04-12",
            "project": "Brand Identity Design",
            "amount": 1500,
            "interaction": "Final payment received 22 days after invoice date. Client was very apologetic about the delay and sent a friendly thank-you note.",
            "type": "payment_late"
        },
        {
            "date": "2026-05-01",
            "project": "Social Media Templates",
            "amount": 2000,
            "interaction": "New project for social media template pack. Client was enthusiastic and warm in initial call, but payment terms discussion revealed they typically pay 25-35 days.",
            "type": "kickoff"
        },
        {
            "date": "2026-05-08",
            "project": "Social Media Templates",
            "amount": 0,
            "interaction": "Client requested 5 rounds of revisions on the template designs, wanting to test multiple color combinations.",
            "type": "design_review"
        },
        {
            "date": "2026-05-15",
            "project": "Social Media Templates",
            "amount": 1000,
            "interaction": "Mid-project payment received 28 days late. Client explained their accounting department was backed up.",
            "type": "payment_late"
        },
        {
            "date": "2026-05-22",
            "project": "Social Media Templates",
            "amount": 0,
            "interaction": "Final revision round completed after 5 rounds total. Client was very particular about every detail.",
            "type": "design_review"
        },
        {
            "date": "2026-05-29",
            "project": "Social Media Templates",
            "amount": 1000,
            "interaction": "Final payment received 33 days after invoice. Client sent a warm email expressing appreciation for the patience shown.",
            "type": "payment_late"
        }
    ],
    "Meridian Agency": [
        {
            "date": "2026-02-01",
            "project": "Annual Report Design",
            "amount": 8000,
            "interaction": "Kickoff meeting for annual report design. Client was very professional, referenced specific sections of their brand guidelines, and paid deposit immediately upon signing contract.",
            "type": "kickoff"
        },
        {
            "date": "2026-02-08",
            "project": "Annual Report Design",
            "amount": 0,
            "interaction": "Initial layout concepts presented. Client provided detailed, structured feedback referencing page numbers and specific design elements.",
            "type": "design_review"
        },
        {
            "date": "2026-02-15",
            "project": "Annual Report Design",
            "amount": 4000,
            "interaction": "Midpoint payment received exactly on time per net-15 terms. Communication was formal and business-like.",
            "type": "payment"
        },
        {
            "date": "2026-02-22",
            "project": "Annual Report Design",
            "amount": 0,
            "interaction": "Client went silent for 10 days after requesting access to preliminary drafts. No response to emails or Slack messages.",
            "type": "silence"
        },
        {
            "date": "2026-03-01",
            "project": "Annual Report Design",
            "amount": 0,
            "interaction": "Client returned after 11 days of silence, requesting rush completion in 3 days instead of the originally agreed 2 weeks. Needed immediate attention for upcoming board meeting.",
            "type": "rush_request"
        },
        {
            "date": "2026-03-05",
            "project": "Annual Report Design",
            "amount": 4000,
            "interaction": "Final payment received on time for rush project. Client acknowledged the premium charge for expedited timeline was fair.",
            "type": "payment"
        },
        {
            "date": "2026-04-01",
            "project": "Investor Pitch Deck",
            "amount": 3500,
            "interaction": "New project for investor pitch deck. Client provided detailed brief upfront, signed NDA immediately, and paid deposit within 2 hours of receiving invoice.",
            "type": "kickoff"
        },
        {
            "date": "2026-04-08",
            "project": "Investor Pitch Deck",
            "amount": 0,
            "interaction": "Initial slide concepts reviewed. Client provided actionable feedback in bulleted format with clear priorities.",
            "type": "design_review"
        },
        {
            "date": "2026-04-15",
            "project": "Investor Pitch Deck",
            "amount": 1750,
            "interaction": "Mid-project payment received exactly on schedule. Communication remained professional and to-the-point.",
            "type": "payment"
        },
        {
            "date": "2026-04-18",
            "project": "Investor Pitch Deck",
            "amount": 0,
            "interaction": "Client became unresponsive for 5 days during review period. No explanation provided for the silence.",
            "type": "silence"
        },
        {
            "date": "2026-04-22",
            "project": "Investor Pitch Deck",
            "amount": 0,
            "interaction": "Client requested 48-hour turnaround on final revisions due to unexpected investor meeting moved up.",
            "type": "rush_request"
        },
        {
            "date": "2026-04-25",
            "project": "Investor Pitch Deck",
            "amount": 1750,
            "interaction": "Final payment received promptly. Client noted that while the rush charges were significant, the quality justified the cost.",
            "type": "payment"
        }
    ]
}

def _build_item(client_name: str, interaction: dict) -> dict:
    """Turn one synthetic record into a Hindsight retain item."""
    base_date = datetime.strptime(interaction["date"], "%Y-%m-%d")
    timestamp = base_date.replace(
        hour=random.randint(9, 17), minute=random.choice([0, 15, 30, 45])
    )
    amount = interaction["amount"]
    amount_line = (
        f"Payment: ${amount:,}." if amount else "No payment in this interaction."
    )

    # Hindsight stores facts extracted from this text rather than the text
    # itself, so it is written as an explicit, self-contained record.
    content = (
        f"Client: {client_name}\n"
        f"Date: {interaction['date']}\n"
        f"Project: {interaction['project']}\n"
        f"Event type: {interaction['type'].replace('_', ' ')}\n"
        f"{amount_line}\n"
        f"Notes: {interaction['interaction']}"
    )

    return {
        "content": content,
        "timestamp": timestamp,
        "metadata": {
            "client_name": client_name,
            "date": interaction["date"],
            "project": interaction["project"],
            "amount": amount,
            "type": interaction["type"],
        },
    }


async def seed_client_data(client_name: str, interactions: list) -> bool:
    """Seed one client's full history as a single idempotent document.

    All items share one document_id, so re-running the seeder replaces this
    client's history instead of duplicating it.
    """
    items = [_build_item(client_name, i) for i in interactions]
    document_id = f"seed:{client_slug(client_name)}"

    try:
        result = await memory.retain_interaction_batch(
            client_name=client_name, items=items, document_id=document_id
        )
    except Exception as exc:
        print(f"  [FAIL] {exc}")
        return False

    print(
        f"  [OK] {len(items)} interactions retained "
        f"(items_count={getattr(result, 'items_count', '?')}, document={document_id})"
    )
    return True


async def main() -> int:
    """Seed all synthetic clients into the configured Hindsight bank."""
    print("ClientSense - synthetic data seeder")
    print("=" * 58)

    if not settings.hindsight_configured:
        print("[FAIL] Hindsight is not configured.")
        print("       Set HINDSIGHT_API_KEY and HINDSIGHT_BANK_ID in backend/.env\n")
        for client_name, interactions in SYNTHETIC_DATA.items():
            print(f"Would seed {len(interactions)} interactions for {client_name}")
            for interaction in interactions[:2]:
                print(
                    f"  - {interaction['date']}: {interaction['type']} "
                    f"({interaction['project']})"
                )
            print()
        return 1

    print(f"Target : {settings.HINDSIGHT_BASE_URL}")
    print(f"Bank   : {settings.HINDSIGHT_BANK_ID}")
    print(f"Timeout: {settings.HINDSIGHT_TIMEOUT}s\n")

    succeeded = True
    for client_name, interactions in SYNTHETIC_DATA.items():
        print(f"Seeding {client_name} ({len(interactions)} interactions)...")
        succeeded &= await seed_client_data(client_name, interactions)

    print("=" * 58)
    if succeeded:
        total = sum(len(v) for v in SYNTHETIC_DATA.values())
        print(f"[OK] Seeding complete - {total} interactions across "
              f"{len(SYNTHETIC_DATA)} clients.")
        print("     Run scripts/setup_bank.py to (re)apply mission and directives.")
        return 0

    print("[FAIL] Seeding finished with errors - see messages above.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    finally:
        # The SDK holds an aiohttp session; closing it avoids an
        # "Unclosed client session" warning on exit.
        asyncio.run(memory.aclose())