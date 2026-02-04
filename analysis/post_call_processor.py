from analysis.intent_extractor import extract_intent_and_summary
from agent.utils.email_utils import send_support_summary_email
from datetime import datetime

def build_post_call_payload(
    *,
    merchant,
    call_result: dict,
    transcript: str
) -> dict:

    intent_data = extract_intent_and_summary(transcript)

    post_call_data = {
        "merchant_id": merchant.id,
        "merchant_name": getattr(merchant, "name", None),
        "merchant_phone": merchant.phone,
        "call_id": call_result.get("call_id"),
        "call_time": datetime.utcnow().isoformat(),
        "duration": call_result.get("duration", 0),
        "agent_connected": call_result.get("agent_connected", False),
        "call_result": call_result.get("result"),
        "intent": intent_data["intent"],
        "summary": intent_data["summary"]
    }

    # Previous behavior (kept for reference):
    # return {
    #     "merchant_id": merchant.id,
    #     "merchant_name": getattr(merchant, "name", None),
    #     "merchant_phone": merchant.phone,
    #     "call_id": call_result.get("call_id"),
    #     "call_time": datetime.utcnow().isoformat(),
    #     "duration": call_result.get("duration", 0),
    #     "agent_connected": call_result.get("agent_connected", False),
    #     "call_result": call_result.get("result"),
    #     "intent": intent_data["intent"],
    #     "summary": intent_data["summary"]
    # }

    # Send summary email after every call
    send_support_summary_email(post_call_data)

    return post_call_data
