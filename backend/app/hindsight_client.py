"""Hindsight Cloud memory layer for ClientSense.

Wraps the official ``hindsight_client`` SDK (v0.10.x) and encodes the three
decisions that make the rest of the app correct:

1. **Everything is bank-scoped.** Every call targets the single memory bank in
   ``HINDSIGHT_BANK_ID``. Banks auto-create on first write, and reads against a
   bank that does not exist return 404 rather than an empty result - so a
   misspelled bank id is reported loudly instead of looking like a client with
   no history.

2. **Per-client isolation uses tags, not metadata filters.** The recall API has
   no ``metadata_filter``. The supported scoping primitive is ``tags`` +
   ``tags_match``. Every retain therefore stamps ``client:<slug>`` onto the
   memory, and every read scopes to that tag with ``all_strict`` (which excludes
   untagged memories, so one client's history can never leak into another's).

3. **LLM output is structured, not scraped.** ``reflect`` accepts a
   ``response_schema`` and returns ``structured_output``; with
   ``include_facts=True`` it also returns ``based_on``, the exact memories it
   cited. Briefs and nudges are therefore typed objects with real evidence
   behind them, instead of keyword-matching over prose.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from hindsight_client import Hindsight

from app.config import settings

logger = logging.getLogger(__name__)

CLIENT_TAG_PREFIX = "client:"

#: Interaction source label stamped on every retain. The Hindsight docs are
#: explicit that ``context`` shapes fact extraction, so this is set
#: consistently rather than left blank.
INTERACTION_CONTEXT = "freelancer client interaction log"


# --------------------------------------------------------------------------
# Client name -> tag slug
# --------------------------------------------------------------------------
def client_slug(client_name: str) -> str:
    """Normalise a client name into a stable, URL-safe tag suffix.

    "Bloom & Co Boutique" -> "bloom-and-co-boutique"
    """
    normalised = unicodedata.normalize("NFKD", client_name)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug or "unknown"


def client_tag(client_name: str) -> str:
    """Tag used to scope every memory to a single client."""
    return f"{CLIENT_TAG_PREFIX}{client_slug(client_name)}"


# --------------------------------------------------------------------------
# Response schemas handed to reflect()
# --------------------------------------------------------------------------
_BRIEF_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "payment_behavior": {
            "type": "string",
            "description": (
                "How this client pays, with inline evidence (dates, amounts, day "
                "counts). State plainly when there is too little history."
            ),
        },
        "revision_scope_behavior": {
            "type": "string",
            "description": (
                "Revision counts, scope-creep patterns and how changes get "
                "requested, with inline evidence."
            ),
        },
        "communication_style": {
            "type": "string",
            "description": "Tone, channel habits, responsiveness, with evidence.",
        },
        "red_flags": {
            "type": "array",
            "description": "Only risks actually backed by retained history.",
            "items": {
                "type": "object",
                "properties": {
                    "flag": {"type": "string", "description": "The risk, in one line."},
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "evidence_count": {
                        "type": "integer",
                        "description": "How many separate interactions support this flag.",
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Short citations, each with a date where known.",
                    },
                },
                "required": ["flag", "severity", "evidence_count", "evidence"],
            },
        },
        "recommendation": {
            "type": "string",
            "description": (
                "One concrete, actionable instruction for the next engagement - "
                "a specific term to write into the contract or payment schedule."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How much history supports this brief.",
        },
    },
    "required": [
        "payment_behavior",
        "revision_scope_behavior",
        "communication_style",
        "red_flags",
        "recommendation",
        "confidence",
    ],
}

_NUDGE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "should_nudge": {
            "type": "boolean",
            "description": (
                "True when this interaction touches a pattern the client's "
                "history has established and the freelancer would act "
                "differently if they knew it right now."
            ),
        },
        "pattern_type": {
            "type": "string",
            "enum": ["new_escalation", "known_pattern", "none"],
            "description": (
                "'new_escalation' when this goes beyond the client's own normal; "
                "'known_pattern' when it repeats their established behaviour; "
                "'none' when there is nothing to warn about."
            ),
        },
        "pattern_matched": {
            "type": "string",
            "description": "Name of the recurring pattern, or an empty string if none.",
        },
        "message": {
            "type": "string",
            "description": "The warning shown to the freelancer. One short paragraph.",
        },
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Dated citations from prior interactions that establish the pattern.",
        },
        "evidence_count": {
            "type": "integer",
            "description": "Number of prior interactions supporting the match.",
        },
        "recommended_action": {
            "type": "string",
            "description": "What to do right now, in one line.",
        },
    },
    "required": [
        "should_nudge",
        "pattern_type",
        "pattern_matched",
        "message",
        "evidence",
        "evidence_count",
        "recommended_action",
    ],
}

BRIEF_SCHEMA = _BRIEF_SCHEMA
NUDGE_SCHEMA = _NUDGE_SCHEMA

_BRIEF_PROMPT = """You are briefing an independent freelancer BEFORE they start work \
with a client.

Build a brief for "{client_name}" strictly from what is in this memory bank.

Cover:
a. Payment behaviour - on time or late, with the specific day counts and dates you can see.
b. Revision and scope behaviour - how many rounds they typically take, and how they request changes.
c. Communication style - tone, channel, responsiveness.
d. Red flags. Only include a flag when at least 2 separate past interactions support it.
e. One concrete, actionable recommendation for the next engagement.

Rules:
- Ground every claim in a specific retained memory. Cite dates, counts and amounts inline.
- Never infer a pattern that the bank does not actually evidence.
- If a section has too little history to support a conclusion, say so plainly instead \
of guessing. An honest "not enough history" is a better answer than a confident invention.
- Calibrate confidence to the volume of evidence, not to caution: "high" when several \
interactions across multiple projects establish the pattern, "medium" for a couple of \
data points, "low" for a single incident or a near-empty bank."""

_NUDGE_PROMPT = """A freelancer has just logged this new interaction with {client_name}:

"{interaction_text}"

They are deciding how to respond RIGHT NOW, and they will not remember this \
client's history unless you put it in front of them at this moment. Your job is \
to tell them whether their past experience with this client should change how \
they handle it.

Warn them when this interaction touches a pattern their history has established, \
and where knowing it now would change their response. For example:
- A revision request from a client who consistently runs four to five rounds, \
when the freelancer is about to absorb another round without charging for it.
- A payment-delay excuse from a chronically late payer, before they waive a term.
- Informal scope creep from a client with a scope-creep record.
- A rush deadline from a client who routinely goes silent first.

Stay silent when the interaction is genuinely unremarkable: routine scheduling, \
ordinary progress, a normal on-time payment, or a request that matches no \
established pattern. A warning that fires on everything gets ignored, which is \
worse than never warning at all.

A repeat of a known pattern still deserves a flag - the cost is cumulative and \
the freelancer is making a scope or pricing decision at this moment. Set \
pattern_type to "new_escalation" when this goes beyond the client's own normal, \
"known_pattern" when it repeats their established behaviour, and "none" when \
there is nothing to say. If should_nudge is false, leave message and \
pattern_matched empty."""


class HindsightNotConfigured(RuntimeError):
    """Raised when a memory operation is attempted without an API key."""


class HindsightService:
    """Typed, bank-scoped access to Hindsight for the ClientSense domain."""

    def __init__(self) -> None:
        if not settings.HINDSIGHT_API_KEY:
            logger.warning(
                "HINDSIGHT_API_KEY is not set - memory operations will fail"
            )
        self._client = Hindsight(
            base_url=settings.HINDSIGHT_BASE_URL,
            api_key=settings.HINDSIGHT_API_KEY or None,
            timeout=settings.HINDSIGHT_TIMEOUT,
            max_attempts=3,
        )

    # -- plumbing ---------------------------------------------------------
    @property
    def bank_id(self) -> str:
        return settings.HINDSIGHT_BANK_ID

    def _require_config(self) -> None:
        if not settings.hindsight_configured:
            raise HindsightNotConfigured(
                "HINDSIGHT_API_KEY / HINDSIGHT_BANK_ID missing from backend/.env"
            )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ping(self) -> bool:
        """True when the configured bank is reachable."""
        try:
            await self._client.alist_memories(bank_id=self.bank_id, limit=1)
            return True
        except Exception as exc:  # noqa: BLE001 - health probe must not raise
            logger.warning("Hindsight ping failed: %s", exc)
            return False

    @staticmethod
    def _stringify(metadata: Dict[str, Any]) -> Dict[str, str]:
        """Hindsight stores metadata as strings; None values are dropped."""
        return {str(k): str(v) for k, v in metadata.items() if v is not None}

    # -- write ------------------------------------------------------------
    async def retain_interaction(
        self,
        *,
        client_name: str,
        text: str,
        timestamp: Optional[datetime] = None,
        context: str = INTERACTION_CONTEXT,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None,
    ):
        """Store one interaction against a client.

        ``document_id`` makes the write idempotent - re-retaining the same id
        replaces the previous version instead of creating duplicate memories.
        """
        self._require_config()
        payload = {"client_name": client_name}
        payload.update(metadata or {})

        response = await self._client.aretain(
            bank_id=self.bank_id,
            content=text,
            timestamp=timestamp,
            context=context,
            document_id=document_id,
            metadata=self._stringify(payload),
            tags=[client_tag(client_name)],
        )
        logger.info("Retained interaction for %s", client_name)
        return response

    async def retain_interaction_batch(
        self,
        *,
        client_name: str,
        items: List[Dict[str, Any]],
        document_id: str,
        context: str = INTERACTION_CONTEXT,
    ):
        """Store many interactions for one client under a single document.

        Used by the seeder. Because every item shares one ``document_id``,
        re-running the seed replaces that client's whole history rather than
        duplicating it - which matters when you seed repeatedly before a demo.
        """
        self._require_config()
        tag = client_tag(client_name)
        payload = []
        for item in items:
            payload.append(
                {
                    "content": item["content"],
                    "timestamp": item.get("timestamp"),
                    "context": item.get("context", context),
                    "metadata": self._stringify(item.get("metadata") or {}),
                    # Tags must be set per item. The batch-level document_tags
                    # argument is deprecated, and without per-item tags nothing
                    # is client-scoped - every recall comes back empty.
                    "tags": [tag],
                }
            )

        response = await self._client.aretain_batch(
            bank_id=self.bank_id,
            items=payload,
            document_id=document_id,
        )
        logger.info(
            "Retained %d interactions for %s under document %s",
            len(payload),
            client_name,
            document_id,
        )
        return response

    # -- read -------------------------------------------------------------
    async def recall_interactions(
        self,
        *,
        client_name: str,
        query: str,
        max_tokens: int = 4096,
        budget: str = "mid",
    ) -> List[Any]:
        """Retrieve this client's memories only.

        Recall is a semantic search, so ``query`` must be a real question -
        there is no "give me everything" mode. Callers that want a full
        inventory should use :meth:`timeline` instead.
        """
        self._require_config()
        response = await self._client.arecall(
            bank_id=self.bank_id,
            query=query,
            max_tokens=max_tokens,
            budget=budget,
            tags=[client_tag(client_name)],
            tags_match="all_strict",
        )
        return list(response.results or [])

    async def list_clients(self) -> List[Dict[str, Any]]:
        """Every client that has retained memory, with a memory count."""
        self._require_config()
        response = await self._client.memory.list_tags(
            bank_id=self.bank_id,
            q=f"{CLIENT_TAG_PREFIX}*",
            limit=200,
        )
        clients = []
        for item in response.items or []:
            tag = getattr(item, "tag", "") or ""
            clients.append(
                {
                    "slug": tag[len(CLIENT_TAG_PREFIX):],
                    "tag": tag,
                    "memories": getattr(item, "count", 0) or 0,
                }
            )
        return sorted(clients, key=lambda c: c["slug"])

    async def timeline(
        self,
        *,
        client_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Chronological inventory of a client's retained memories.

        ``list_memories`` has no tag filter, so the client tag is applied here
        and the totals are recomputed from the filtered set.
        """
        self._require_config()
        tag = client_tag(client_name)
        response = await self._client.alist_memories(
            bank_id=self.bank_id,
            time_field="occurred_start",
            limit=200,
            offset=0,
        )

        matched = []
        for item in response.items or []:
            tags = getattr(item, "tags", None) or []
            if tag not in tags:
                continue
            matched.append(
                {
                    "id": getattr(item, "id", None),
                    "text": getattr(item, "text", "") or "",
                    "context": getattr(item, "context", None),
                    "occurred_start": getattr(item, "occurred_start", None),
                    "mentioned_at": getattr(item, "mentioned_at", None),
                    "document_id": getattr(item, "document_id", None),
                    "metadata": getattr(item, "metadata", None) or {},
                }
            )

        matched.sort(key=lambda m: (m.get("occurred_start") or "", m.get("mentioned_at") or ""))
        total = len(matched)
        return {
            "client_name": client_name,
            "total": total,
            "items": matched[offset: offset + limit],
        }

    # -- bank administration ------------------------------------------------
    async def bank_exists(self) -> bool:
        """False when the bank has never been written to.

        Reads against a non-existent bank return 404 by design, so this is the
        reliable way to tell "no bank" apart from "empty bank".
        """
        try:
            await self._client.alist_memories(bank_id=self.bank_id, limit=1)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def create_bank(self, **kwargs: Any) -> None:
        """Explicitly create the bank.

        Not required - banks auto-create on first write - and not available on
        every deployment, so callers should tolerate failure.
        """
        await self._client.acreate_bank(bank_id=self.bank_id, **kwargs)

    async def apply_bank_config(
        self,
        *,
        retain_mission: Optional[str] = None,
        reflect_mission: Optional[str] = None,
        observations_mission: Optional[str] = None,
        retain_extraction_mode: Optional[str] = None,
        skepticism: Optional[int] = None,
        literalism: Optional[int] = None,
        empathy: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upsert bank missions and disposition traits (all 1-5 scales)."""
        return await self._client.aupdate_bank_config(
            bank_id=self.bank_id,
            retain_mission=retain_mission,
            reflect_mission=reflect_mission,
            observations_mission=observations_mission,
            retain_extraction_mode=retain_extraction_mode,
            disposition_skepticism=skepticism,
            disposition_literalism=literalism,
            disposition_empathy=empathy,
        )

    async def list_directives(self) -> List[Any]:
        response = await self._client.alist_directives(self.bank_id)
        return list(response or [])

    async def create_directive(
        self, *, name: str, content: str, priority: int = 0
    ) -> None:
        await self._client.acreate_directive(
            bank_id=self.bank_id, name=name, content=content, priority=priority
        )

    # -- reason -----------------------------------------------------------
    async def generate_brief(self, *, client_name: str) -> Dict[str, Any]:
        """Structured pre-engagement brief, with the memories it cited."""
        self._require_config()
        response = await self._client.areflect(
            bank_id=self.bank_id,
            query=_BRIEF_PROMPT.format(client_name=client_name),
            budget="high",
            tags=[client_tag(client_name)],
            tags_match="all_strict",
            response_schema=BRIEF_SCHEMA,
            include_facts=True,
            max_tokens=2000,
        )
        return self._shape_reflect(response, fallback_key="payment_behavior")

    async def evaluate_nudge(
        self, *, client_name: str, interaction_text: str
    ) -> Dict[str, Any]:
        """Decide whether a fresh interaction matches a known risky pattern."""
        self._require_config()
        response = await self._client.areflect(
            bank_id=self.bank_id,
            query=_NUDGE_PROMPT.format(
                client_name=client_name,
                interaction_text=interaction_text,
            ),
            budget="mid",
            tags=[client_tag(client_name)],
            tags_match="all_strict",
            response_schema=NUDGE_SCHEMA,
            include_facts=True,
            max_tokens=1200,
        )
        return self._shape_reflect(response, fallback_key="message")

    @staticmethod
    def _shape_reflect(response: Any, *, fallback_key: str) -> Dict[str, Any]:
        """Normalise a ReflectResponse into dicts the API layer can return."""
        structured = getattr(response, "structured_output", None)
        cited = []
        based_on = getattr(response, "based_on", None)
        for fact in (getattr(based_on, "memories", None) or []):
            cited.append(
                {
                    "id": getattr(fact, "id", None),
                    "text": getattr(fact, "text", "") or "",
                    "type": getattr(fact, "type", None),
                    "occurred_start": getattr(fact, "occurred_start", None),
                }
            )

        error = getattr(response, "structured_output_error", None)
        if error:
            # Reflect succeeded; only the JSON projection failed. Surface the
            # markdown so the caller can still show something useful.
            logger.warning("reflect structured_output failed: %s", error)

        return {
            "text": getattr(response, "text", "") or "",
            "structured": structured,
            "cited": cited,
            "structured_output_error": error,
            "fallback_key": fallback_key,
        }


#: Shared instance used by the FastAPI app and the CLI scripts.
memory = HindsightService()
