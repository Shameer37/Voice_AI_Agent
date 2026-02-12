# campaign/post_call_processor.py

from analysis.intent_extractor import extract_intent_and_summary
from agent.utils.time_utils import parse_utc_iso, iso_ist
from typing import Optional
import logging

logger = logging.getLogger("post_call")


def build_post_call_payload(
    *,
    merchant,
    call_result: dict,
    transcript: Optional[str] = None,
) -> dict:
    """
    Build normalized post-call payload.
    NO side effects (no email, no DB writes).
    """

    # -----------------------------
    # Intent extraction (safe)
    # -----------------------------
    if transcript and transcript.strip():
        try:
            intent_data = extract_intent_and_summary(transcript)
            intent = intent_data.get("intent", "unknown")
            summary = intent_data.get("summary", "Summary unavailable.")
        except Exception:
            logger.exception("Intent extraction failed")
            intent = "unknown"
            summary = "Intent extraction failed."
    else:
        intent = "unknown"
        summary = "No transcript available."

    # -----------------------------
    # Time normalization (FreJun → IST)
    # -----------------------------
    start_time_utc = parse_utc_iso(call_result.get("start_time"))
    answer_time_utc = parse_utc_iso(call_result.get("answer_time"))
    hangup_time_utc = parse_utc_iso(call_result.get("hangup_time"))

    payload = {
        "merchant_id": getattr(merchant, "id", None),
        "merchant_name": getattr(merchant, "name", None),
        "merchant_phone": getattr(merchant, "phone", None),

        "call_id": call_result.get("call_id"),

        # Provider-aligned times (ISO, IST)
        "call_start_time": iso_ist(start_time_utc),
        "answer_time": iso_ist(answer_time_utc),
        "hangup_time": iso_ist(hangup_time_utc),

        "duration": call_result.get("duration", 0),
        "agent_connected": bool(call_result.get("agent_connected")),

        "call_result": call_result.get("result", "unknown"),

        "intent": intent,
        "summary": summary,
    }

    return payload
