"""Test suite for ClientSense.

The memory layer is mocked throughout: these tests verify routing, validation,
response shaping and the empty-history contract without touching Hindsight or
spending LLM tokens. A contract test also pins the Hindsight request shapes so
the API integration cannot silently drift again.
"""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.hindsight_client import (
    BRIEF_SCHEMA,
    NUDGE_SCHEMA,
    client_slug,
    client_tag,
)


@pytest.fixture
def client(monkeypatch):
    """TestClient with the memory layer stubbed out."""

    async def fake_ping():
        return True

    async def fake_list_clients():
        return [
            {"slug": "bloom-co-boutique", "tag": "client:bloom-co-boutique", "memories": 29},
            {"slug": "meridian-agency", "tag": "client:meridian-agency", "memories": 27},
        ]

    async def fake_timeline(*, client_name, limit=50, offset=0):
        if client_name == "Nobody":
            return {"client_name": client_name, "total": 0, "items": []}
        return {
            "client_name": client_name,
            "total": 29,
            "items": [
                {
                    "id": "m1",
                    "text": "Bloom paid 15 days late.",
                    "occurred_start": "2026-03-22T00:00:00+00:00",
                    "mentioned_at": "2026-03-22T00:00:00+00:00",
                    "context": "payment",
                    "metadata": {},
                }
            ],
        }

    async def fake_brief(*, client_name):
        return {
            "text": "markdown fallback",
            "structured": {
                "payment_behavior": "Pays 15-33 days late.",
                "revision_scope_behavior": "4-5 rounds.",
                "communication_style": "Warm.",
                "red_flags": [
                    {
                        "flag": "Chronic late payment",
                        "severity": "high",
                        "evidence_count": 4,
                        "evidence": ["15 days late (2026-03-22)"],
                    }
                ],
                "recommendation": "Add a revision cap clause.",
                "confidence": "high",
            },
            "cited": [{"id": "a", "text": "f", "type": "world", "occurred_start": None}],
            "structured_output_error": None,
        }

    async def fake_nudge(*, client_name, interaction_text):
        return {
            "text": "markdown",
            "structured": {
                "should_nudge": True,
                "pattern_type": "known_pattern",
                "pattern_matched": "Revision-heavy",
                "message": "This client averages 4-5 rounds.",
                "evidence": ["4 rounds (2026-03-08)"],
                "evidence_count": 2,
                "recommended_action": "Charge beyond round 2.",
            },
            "cited": [],
            "structured_output_error": None,
        }

    async def fake_retain(**kwargs):
        class R:
            success = True
            items_count = 1
            bank_id = "clientsense"

        return R()

    monkeypatch.setattr(main.memory, "ping", fake_ping)
    monkeypatch.setattr(main.memory, "list_clients", fake_list_clients)
    monkeypatch.setattr(main.memory, "timeline", fake_timeline)
    monkeypatch.setattr(main.memory, "generate_brief", fake_brief)
    monkeypatch.setattr(main.memory, "evaluate_nudge", fake_nudge)
    monkeypatch.setattr(main.memory, "retain_interaction", fake_retain)

    with TestClient(main.app) as test_client:
        yield test_client


# ---------------------------------------------------------------- contract
def test_client_slug_is_stable_and_url_safe():
    assert client_slug("Bloom & Co Boutique") == "bloom-co-boutique"
    assert client_slug("  TechCorp  Startup ") == "techcorp-startup"
    assert client_slug("Ünïcödé Ltd") == "unicode-ltd"
    assert client_slug("!!!") == "unknown"


def test_client_tag_is_namespaced():
    assert client_tag("Meridian Agency") == "client:meridian-agency"


def test_schemas_are_valid_json_schema():
    for schema in (BRIEF_SCHEMA, NUDGE_SCHEMA):
        assert schema["type"] == "object"
        assert schema["properties"]
        assert schema["required"]


def test_brief_schema_requires_every_field():
    assert set(BRIEF_SCHEMA["required"]) == set(BRIEF_SCHEMA["properties"])


def test_nudge_decision_is_a_boolean_field():
    """The nudge must be decided by the model, not by keyword matching."""
    should = NUDGE_SCHEMA["properties"]["should_nudge"]
    assert should["type"] == "boolean"
    assert "should_nudge" in NUDGE_SCHEMA["required"]


# ------------------------------------------------------------------- routes
def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ClientSense" in response.json()["message"]


def test_health_reports_memory_reachability(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert body["hindsight"]["reachable"] is True
    assert body["hindsight"]["bank_id"]


def test_list_clients(client):
    response = client.get("/clients")
    assert response.status_code == 200
    slugs = [c["slug"] for c in response.json()]
    assert "bloom-co-boutique" in slugs


def test_timeline_filters_by_client(client):
    response = client.get("/timeline/Bloom%20%26%20Co%20Boutique")
    assert response.status_code == 200
    assert response.json()["total"] == 29


def test_timeline_empty_for_unknown_client(client):
    body = client.get("/timeline/Nobody").json()
    assert body["total"] == 0
    assert body["items"] == []


# --------------------------------------------------------------------- brief
def test_brief_returns_structured_fields(client):
    body = client.post(
        "/client-brief", json={"client_name": "Bloom & Co Boutique"}
    ).json()

    assert body["payment_behavior"] == "Pays 15-33 days late."
    assert body["confidence"] == "high"
    assert len(body["red_flags"]) == 1
    assert body["red_flags"][0]["evidence_count"] == 4
    assert body["evidence_summary"]["total_interactions"] == 29
    assert body["evidence_summary"]["cited_memories"] == 1
    assert body["raw_analysis"] is None


def test_brief_for_new_client_says_so_instead_of_inventing(client):
    body = client.post("/client-brief", json={"client_name": "Nobody"}).json()

    assert body["payment_behavior"] == main.EMPTY_BRIEF_TEXT
    assert body["red_flags"] == []
    assert body["confidence"] == "low"
    assert body["evidence_summary"]["total_interactions"] == 0


def test_brief_rejects_blank_client_name(client):
    assert client.post("/client-brief", json={"client_name": "  "}).status_code == 422


# -------------------------------------------------------------------- nudge
def test_log_interaction_returns_nudge(client):
    body = client.post(
        "/log-interaction",
        json={
            "client_name": "Bloom & Co Boutique",
            "interaction_text": "Asked for a 4th round of revisions.",
        },
    ).json()

    assert body["status"] == "success"
    nudge = body["proactive_nudge"]
    assert nudge["should_nudge"] is True
    assert nudge["pattern_type"] == "known_pattern"
    assert nudge["evidence_count"] == 2


def test_check_nudge_accepts_a_json_body(client):
    """Regression: scalar params on a POST route become query params (422)."""
    response = client.post(
        "/check-nudge",
        json={
            "client_name": "Bloom & Co Boutique",
            "interaction_text": "Asked for a 4th round of revisions.",
        },
    )
    assert response.status_code == 200
    assert response.json()["should_nudge"] is True


def test_log_interaction_requires_text(client):
    response = client.post(
        "/log-interaction",
        json={"client_name": "Bloom & Co Boutique", "interaction_text": "   "},
    )
    assert response.status_code == 422


# ------------------------------------------------------------------ failure
def test_nudge_failure_does_not_lose_a_retained_interaction(client, monkeypatch):
    async def boom(*, client_name, interaction_text):
        raise RuntimeError("reflect exploded")

    monkeypatch.setattr(main.memory, "evaluate_nudge", boom)

    body = client.post(
        "/log-interaction",
        json={
            "client_name": "Bloom & Co Boutique",
            "interaction_text": "Something happened.",
        },
    ).json()

    assert body["status"] == "success"
    assert body["proactive_nudge"]["should_nudge"] is False


def test_brief_surfaces_upstream_failure_as_502(client, monkeypatch):
    async def boom(*, client_name):
        raise RuntimeError("bank unreachable")

    monkeypatch.setattr(main.memory, "generate_brief", boom)

    response = client.post("/client-brief", json={"client_name": "Bloom & Co Boutique"})
    assert response.status_code == 502


def test_missing_credentials_return_503(client, monkeypatch):
    from app.hindsight_client import HindsightNotConfigured

    async def boom(**kwargs):
        raise HindsightNotConfigured("HINDSIGHT_API_KEY missing from backend/.env")

    monkeypatch.setattr(main.memory, "generate_brief", boom)

    response = client.post("/client-brief", json={"client_name": "Bloom & Co Boutique"})
    assert response.status_code == 503
