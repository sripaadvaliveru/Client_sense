"""ClientSense API.

Flow:
  POST /log-interaction  -> retain() the interaction, then reflect() for a nudge
  POST /client-brief     -> reflect() over a client's tagged history
  GET  /clients          -> every client with retained memory
  GET  /timeline/{name}  -> chronological inventory for the timeline view
  POST /check-nudge      -> nudge decision for an unsaved interaction
  GET  /health           -> app health, including real Hindsight reachability
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.hindsight_client import (
    HindsightNotConfigured,
    client_slug,
    memory,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("clientsense")

#: Returned when a client has no retained history at all.
EMPTY_BRIEF_TEXT = "No history available."


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await memory.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    description="A memory-powered freelancer client intelligence agent, built on Hindsight.",
    version="0.2.0",
    lifespan=lifespan,
)

# Explicit origins: a wildcard combined with allow_credentials is rejected by
# browsers, and this app is a public read-only surface during a demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class NonEmptyText(BaseModel):
    """Rejects whitespace-only input.

    min_length alone is not enough: "   " satisfies min_length=1 and would
    otherwise retain an empty memory and brief against a blank client.
    """

    @field_validator("*", mode="before")
    @classmethod
    def _strip_and_check(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("must not be blank")
            return stripped
        return value


class InteractionLog(NonEmptyText):
    client_name: str = Field(min_length=1, max_length=200, examples=["Bloom & Co Boutique"])
    interaction_text: str = Field(min_length=1, max_length=20000)
    timestamp: Optional[datetime] = None
    project: Optional[str] = None
    amount: Optional[float] = None
    event_type: Optional[str] = Field(
        default=None,
        description="Optional label, e.g. design_review, payment, scope_creep.",
    )


class ClientBriefRequest(NonEmptyText):
    client_name: str = Field(min_length=1, max_length=200)


class NudgeCheckRequest(NonEmptyText):
    client_name: str = Field(min_length=1, max_length=200)
    interaction_text: str = Field(min_length=1, max_length=20000)


class RedFlag(BaseModel):
    flag: str
    severity: str = "medium"
    evidence_count: int = 0
    evidence: List[str] = Field(default_factory=list)


class ClientBriefResponse(BaseModel):
    client_name: str
    payment_behavior: str
    revision_scope_behavior: str
    communication_style: str
    red_flags: List[RedFlag] = Field(default_factory=list)
    recommendation: str
    confidence: str = "unknown"
    evidence_summary: Dict[str, Any] = Field(default_factory=dict)
    raw_analysis: Optional[str] = None
    structured_output_error: Optional[str] = None


class ProactiveNudgeResponse(BaseModel):
    should_nudge: bool
    client_name: Optional[str] = None
    pattern_type: Optional[str] = None
    nudge_message: Optional[str] = None
    pattern_matched: Optional[str] = None
    recommended_action: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    cited_memories: List[Dict[str, Any]] = Field(default_factory=list)
    structured_output_error: Optional[str] = None


class ClientListItem(BaseModel):
    slug: str
    tag: str
    memories: int


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _memory_error(exc: Exception, action: str) -> HTTPException:
    if isinstance(exc, HindsightNotConfigured):
        return HTTPException(status_code=503, detail=str(exc))
    logger.exception("%s failed", action)
    return HTTPException(status_code=502, detail=f"{action} failed: {exc}")


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_str(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": app.version,
        "bank_id": settings.HINDSIGHT_BANK_ID,
        "description": "A Memory-Powered Freelancer Client Intelligence Agent",
    }


@app.get("/health")
async def health_check():
    """Health, including whether the Hindsight bank is actually reachable."""
    configured = settings.hindsight_configured
    reachable = await memory.ping() if configured else False
    return {
        "status": "healthy" if (configured and reachable) else "degraded",
        "hindsight": {
            "configured": configured,
            "reachable": reachable,
            "bank_id": settings.HINDSIGHT_BANK_ID,
        },
    }


@app.get("/clients", response_model=List[ClientListItem])
async def list_clients():
    """Every client with retained memory, so the UI needs no hardcoded names."""
    try:
        return await memory.list_clients()
    except Exception as exc:  # noqa: BLE001
        raise _memory_error(exc, "list_clients")


@app.get("/timeline/{client_name:path}")
async def client_timeline(client_name: str, limit: int = 50, offset: int = 0):
    """Chronological inventory of a client's retained memories."""
    try:
        return await memory.timeline(
            client_name=client_name, limit=limit, offset=offset
        )
    except Exception as exc:  # noqa: BLE001
        raise _memory_error(exc, "timeline")


@app.post("/client-brief", response_model=ClientBriefResponse)
async def get_client_brief(request: ClientBriefRequest):
    """Structured pre-engagement brief for a client, grounded in their history."""
    client_name = request.client_name.strip()
    try:
        history = await memory.timeline(client_name=client_name, limit=1)
        if not history["total"]:
            # No memory means no brief. Say so rather than inventing one.
            return ClientBriefResponse(
                client_name=client_name,
                payment_behavior=EMPTY_BRIEF_TEXT,
                revision_scope_behavior=EMPTY_BRIEF_TEXT,
                communication_style=EMPTY_BRIEF_TEXT,
                red_flags=[],
                recommendation=(
                    "No retained history for this client yet. Log the first "
                    "interaction, then ask again once a pattern can form."
                ),
                confidence="low",
                evidence_summary={"total_interactions": 0, "cited_memories": 0},
            )

        result = await memory.generate_brief(client_name=client_name)
    except Exception as exc:  # noqa: BLE001
        raise _memory_error(exc, "client brief")

    structured = result["structured"] or {}
    cited = result["cited"]
    red_flags = [
        RedFlag(
            flag=_as_str(flag.get("flag"), "Unspecified risk"),
            severity=_as_str(flag.get("severity"), "medium"),
            evidence_count=int(flag.get("evidence_count") or 0),
            evidence=[str(e) for e in (flag.get("evidence") or [])],
        )
        for flag in (structured.get("red_flags") or [])
        if isinstance(flag, dict)
    ]

    return ClientBriefResponse(
        client_name=client_name,
        payment_behavior=_as_str(structured.get("payment_behavior"), EMPTY_BRIEF_TEXT),
        revision_scope_behavior=_as_str(
            structured.get("revision_scope_behavior"), EMPTY_BRIEF_TEXT
        ),
        communication_style=_as_str(
            structured.get("communication_style"), EMPTY_BRIEF_TEXT
        ),
        red_flags=red_flags,
        recommendation=_as_str(structured.get("recommendation")),
        confidence=_as_str(structured.get("confidence"), "unknown"),
        evidence_summary={
            "total_interactions": history["total"],
            "cited_memories": len(cited),
        },
        raw_analysis=None if structured else result["text"],
        structured_output_error=result["structured_output_error"],
    )


async def _run_nudge(client_name: str, interaction_text: str) -> ProactiveNudgeResponse:
    result = await memory.evaluate_nudge(
        client_name=client_name, interaction_text=interaction_text
    )
    structured = result["structured"] or {}
    cited = result["cited"]
    error = result["structured_output_error"]

    if not structured:
        # Without typed output there is no honest way to judge this, and a
        # false alarm is worse than silence. Stay quiet and say why.
        logger.warning("Nudge unavailable for %s: %s", client_name, error)
        return ProactiveNudgeResponse(
            should_nudge=False,
            client_name=client_name,
            structured_output_error=error or "no structured output returned",
        )

    should_nudge = bool(structured.get("should_nudge"))
    return ProactiveNudgeResponse(
        should_nudge=should_nudge,
        client_name=client_name,
        pattern_type=_as_str(structured.get("pattern_type"), "none") or "none",
        nudge_message=_as_str(structured.get("message")) or None,
        pattern_matched=_as_str(structured.get("pattern_matched")) or None,
        recommended_action=_as_str(structured.get("recommended_action")) or None,
        evidence=[str(e) for e in (structured.get("evidence") or [])],
        evidence_count=int(structured.get("evidence_count") or 0),
        cited_memories=cited,
        structured_output_error=error,
    )


@app.post("/log-interaction")
async def log_interaction(interaction: InteractionLog):
    """Retain an interaction, then immediately check for a proactive nudge."""
    client_name = interaction.client_name.strip()
    text = interaction.interaction_text.strip()
    try:
        retain_result = await memory.retain_interaction(
            client_name=client_name,
            text=text,
            timestamp=interaction.timestamp,
            metadata={
                "client_name": client_name,
                "project": interaction.project,
                "amount": interaction.amount,
                "event_type": interaction.event_type or "interaction_log",
            },
            # Unique per interaction so every log is additive, never a replace.
            document_id=f"log:{client_slug(client_name)}:{uuid.uuid4().hex}",
        )
        logger.info("Logged interaction for %s", client_name)

        # A nudge failure must not lose a successfully retained interaction.
        try:
            nudge = await _run_nudge(client_name, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Nudge check failed for %s: %s", client_name, exc)
            nudge = ProactiveNudgeResponse(should_nudge=False, client_name=client_name)

        return {
            "status": "success",
            "message": f"Interaction logged for {client_name}",
            "retain": {
                "success": getattr(retain_result, "success", None),
                "items_count": getattr(retain_result, "items_count", None),
                "bank_id": getattr(retain_result, "bank_id", None),
            },
            "proactive_nudge": nudge,
        }
    except Exception as exc:  # noqa: BLE001
        raise _memory_error(exc, "log interaction")


@app.post("/check-nudge", response_model=ProactiveNudgeResponse)
async def check_nudge(request: NudgeCheckRequest):
    """Nudge decision for an interaction that has not been logged yet."""
    try:
        return await _run_nudge(
            request.client_name.strip(), request.interaction_text.strip()
        )
    except Exception as exc:  # noqa: BLE001
        raise _memory_error(exc, "nudge check")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
