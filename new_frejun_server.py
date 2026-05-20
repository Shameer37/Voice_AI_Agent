# import logging
# import json
# import base64

# from fastapi import APIRouter, HTTPException, WebSocket, status
# from fastapi.responses import JSONResponse
# from new_config import settings
# from pydantic import BaseModel
# from typing import Optional, Any
# # from agent.utils.time_utils import parse_utc_iso, format_ist

# from teler.streams import StreamConnector, StreamType, StreamOp
# from teler import AsyncClient
# ## Previous import (kept for reference):
# # from agent.utils.email_utils import send_support_summary_email

# logger = logging.getLogger(__name__)
# router = APIRouter()
# from itertools import count
# _chunk_counter = count(1)
# CALL_CONTEXT = {} 

# # ────────────────────────────────────────────────
# # Models
# # ────────────────────────────────────────────────
# class CallFlowRequest(BaseModel):
#     call_id: str
#     account_id: str
#     from_number: str
#     to_number: str
#     data: Optional[dict] = None
#     direction_v2: Optional[str] = None


# class CallRequest(BaseModel):
#     from_number: str
#     to_number: str


# # ────────────────────────────────────────────────
# # Helpers
# # ────────────────────────────────────────────────
# def _fmt_bytes(n: int) -> str:
#     # 8kHz * 2 bytes/sample (pcm16 mono)
#     secs = n / (16000 * 2) if n else 0.0
#     return f"{n} bytes (~{secs:.2f}s @8kHz pcm16 mono)"


# # ────────────────────────────────────────────────
# # Stream Handlers
# # ────────────────────────────────────────────────
# async def call_stream_handler(message: str):
#     """
#     Handle incoming websocket messages from Teler.
#     """
#     try:
#         logger.debug(f"[Teler->Bridge] raw message: {message[:200]}{'...' if len(message) > 200 else ''}")
#         msg = json.loads(message)

#         # #1) Teler will always send a "start" first
#         # if msg.get("type") == "start":
#         #     data = msg.get("data", {}) or {}
#         #     logger.info(
#         #         f"[Teler->Bridge] start: encoding={data.get('encoding')} "
#         #         f"sr={data.get('sample_rate')} ch={data.get('channels')} "
#         #         f"stream_id={msg.get('stream_id')} message_id={msg.get('message_id')}"
#         #     )
#         #     return ({}, StreamOp.PASS)
#         if msg.get("type") == "start":
#             stream_id = msg.get("stream_id")

#             logger.info(
#                 f"[Teler->Bridge] start stream_id={stream_id} "
#                 f"encoding={msg.get('data', {}).get('encoding')} "
#                 f"sr={msg.get('data', {}).get('sample_rate')}"
#             )

#             # 🔑 Lookup call context populated via webhook
#             call_ctx = next(
#                 (v for v in CALL_CONTEXT.values() if v.get("stream_id") == stream_id),
#                 {}
#             )

#             meta_payload = {
#                 "type": "meta",
#                 "call_id": call_ctx.get("call_id"),
#                 "to_number": call_ctx.get("to_number"),
#             }

#             logger.info(f"[Bridge->Agent] META injected: {meta_payload}")

#             return (json.dumps(meta_payload), StreamOp.RELAY)

#         if msg.get("type") == "audio":
#             data = msg.get("data") or {}
#             audio_b64 = data.get("audio_b64")
#             if audio_b64:
#                 logger.info(
#                     f"[Teler->Bridge] audio in b64_len={len(audio_b64)} "
#                     f"stream_id={msg.get('stream_id')} message_id={msg.get('message_id')}"
#                 )
#                 payload = json.dumps({"user_audio_chunk": audio_b64})
#                 return (payload, StreamOp.RELAY)
#             else:
#                 logger.warning(
#                     f"[Teler->Bridge] audio message without audio_b64 "
#                     f"(stream_id={msg.get('stream_id')} message_id={msg.get('message_id')})"
#                 )

#         # Unexpected type fallback log
#         logger.debug(f"[Teler->Bridge] non-audio message type={msg.get('type')}")
#         return ({}, StreamOp.PASS)

#     except Exception as e:
#         logger.error(f"Error in call stream handler: {e}")
#         return ({}, StreamOp.PASS)



# def remote_stream_handler():
#     async def handler(message: str):
#         try:
#             logger.debug(f"[Agent->Bridge] raw message: {message[:200]}{'...' if len(message) > 200 else ''}")
#             msg = json.loads(message)

#             # Forward agent audio to Teler in the exact schema Teler expects
#             if msg.get("type") == "audio" and msg.get("audio_b64"):
#                 chunk_id = next(_chunk_counter)
#                 out = {
#                     "type": "audio",
#                     "audio_b64": msg["audio_b64"],
#                     "chunk_id": chunk_id
#                 }
#                 logger.info(
#                     f"[Bridge->Teler] audio out chunk_id={chunk_id} b64_len={len(msg['audio_b64'])}"
#                 )
#                 return (json.dumps(out), StreamOp.RELAY)

#             # Optional: support agent-driven interrupt/clear passthrough
#             if msg.get("type") == "interrupt" and "chunk_id" in msg:
#                 logger.info(f"[Bridge->Teler] interrupt chunk_id={msg['chunk_id']}")
#                 return (json.dumps({"type": "interrupt", "chunk_id": msg["chunk_id"]}), StreamOp.RELAY)

#             if msg.get("type") == "clear":
#                 logger.info("[Bridge->Teler] clear (wipe playback buffer)")
#                 return (json.dumps({"type": "clear"}), StreamOp.RELAY)

#             logger.debug(f"[Agent->Bridge] non-audio message type={msg.get('type')}")
#             return ({}, StreamOp.PASS)

#         except Exception as e:
#             logger.error(f"Error in remote stream handler: {e}")
#             return ({}, StreamOp.PASS)
#     return handler



# # ────────────────────────────────────────────────
# # Connector
# # ────────────────────────────────────────────────
# connector = StreamConnector(
#     stream_type=StreamType.BIDIRECTIONAL,
#     remote_url=settings.local_agent_websocket_url,
#     call_stream_handler=call_stream_handler,
#     remote_stream_handler=remote_stream_handler()  # try 400–2000 as needed
# )


# # GREETING
# # Routes
# # ────────────────────────────────────────────────
# @router.post("/calls/flow", status_code=status.HTTP_200_OK, include_in_schema=False)
# async def stream_flow(payload: CallFlowRequest):
#     logger.info(
#         f"Call Flow for call_id={payload.call_id} from={payload.from_number} to={payload.to_number} "
#         f"account_id={payload.account_id}"
#     )
#     stream_flow = {
#         "action": "stream",
#         "ws_url": f"wss://{settings.server_domain}/api/v1/calls/media-stream",
#         "chunk_size": 1000,          # align with our aggregator (try 400 or 2000 if needed)
#         "sample_rate": "16k", # Previously it was about 8khz 
#         "record": True
#     }
#     logger.info(f"Stream flow response: {stream_flow}")
#     return JSONResponse(stream_flow)
# # @router.post("/calls/flow", status_code=200, include_in_schema=False)
# # async def stream_flow(payload: CallFlowRequest):
# #     """
# #     Call flow entrypoint.

# #     HARD RULE:
# #     - Only OUTBOUND campaign calls are allowed
# #     - ALL inbound calls are rejected immediately
# #     """

# #     # Previous behavior (kept for reference):
# #     # direction = payload.data.get("direction") if hasattr(payload, "data") else None

# #     # Safely extract direction from either nested data or top-level field
# #     direction = None
# #     if payload.data and isinstance(payload.data, dict):
# #         direction = payload.data.get("direction")
# #     if direction is None:
# #         direction = payload.direction

# #     # 🚨 HARD BLOCK INBOUND CALLS
# #       if direction in {"incoming", "inbound"}:
# #         logger.warning(
# #             f"[SECURITY] Inbound call blocked | from={payload.from_number}"
# #         )
# #         return {
# #             "action": "hangup"
# #         }

# #     # ✅ OUTBOUND ONLY
# #     logger.info(
# #         f"[FLOW] Outbound call allowed | call_id={payload.call_id}"
# #     )

# #     return {
# #         "action": "stream",
# #         "ws_url": f"wss://{settings.server_domain}/api/v1/calls/media-stream",
# #         "chunk_size": 1000,
# #         "sample_rate": "16k",
# #         "record": True
# #     }


# @router.post("/initiate-call", status_code=status.HTTP_200_OK)
# async def initiate_call(call_request: CallRequest):
#     """
#     Initiate a call using Teler SDK.
#     """
#     try:

#         logger.info(f"Initiating call from {call_request.from_number} to {call_request.to_number}")
#         async with AsyncClient(api_key=settings.teler_api_key, timeout=10) as client:
#             call = await client.calls.create(
#                 from_number=call_request.from_number,
#                 to_number=call_request.to_number,
#                 flow_url=f"https://{settings.server_domain}/api/v1/calls/flow",
#                 status_callback_url=f"https://{settings.server_domain}/api/v1/webhooks/receiver",
#                 record=True,
#             )
#             logger.info(f"Call created successfully: {call}")
#         return JSONResponse(content={"success": True, "call_id": call.id})
#     except Exception as e:
#         logger.error(f"Failed to create call: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to create call."
#         )


# # @router.post("/webhooks/receiver", status_code=status.HTTP_200_OK, include_in_schema=False)
# # async def webhook_receiver(data: dict):
# #     """
# #     Log webhook payload from Teler.
# #     """
# #     logger.info(f"--------Webhook Payload-------- {data}")
# #     return JSONResponse(content={"status": "received"})
# @router.post("/webhooks/receiver", status_code=200, include_in_schema=False)
# async def webhook_receiver(payload: dict):
#     logger.info(f"--------Webhook Payload-------- {payload}")

#     event = payload.get("event")
#     data = payload.get("data", {}) or {}

#     call_id = data.get("call_id")
#     if not call_id:
#         return {"status": "ignored"}

#     ctx = CALL_CONTEXT.setdefault(call_id, {})

#     if event == "call.initiated":
#         ctx.update({
#             "call_id": call_id,
#             "from_number": data.get("from"),
#             "to_number": data.get("to"),
#             "start_time": data.get("startTime"),
#         })

#     elif event == "call.answered":
#         ctx["answer_time"] = data.get("answer_time")

#     elif event == "call.completed":
#         ctx["hangup_time"] = data.get("hangup_time")

#     elif event == "stream.initiated":
#         ctx["stream_id"] = data.get("stream_id")

#     return {"status": "ok"}



# @router.websocket("/calls/media-stream")
# async def handle_media_stream(websocket: WebSocket):
#     await websocket.accept()
#     logger.info("WebSocket connected.")
#     logger.info("Starting bridge_stream with StreamConnector…")
#     await connector.bridge_stream(websocket)
#     logger.info("WebSocket disconnected.")

#     # Previous behavior with email (kept for reference):
#     # start_ts = datetime.utcnow()
#     # try:
#     #     await connector.bridge_stream(websocket)
#     # finally:
#     #     end_ts = datetime.utcnow()
#     #     duration = int((end_ts - start_ts).total_seconds())
#     #
#     #     post_call_data = {
#     #         "merchant_id": None,
#     #         "merchant_name": None,
#     #         "merchant_phone": None,
#     #         "call_id": None,
#     #         "call_time": start_ts.isoformat(),
#     #         "duration": duration,
#     #         "agent_connected": True,
#     #         "call_result": "completed",
#     #         "intent": "unknown",
#     #         "summary": "Call completed via FreJun bridge (no transcript attached)."
#     #     }
#     #
#     #     # Send email after call ends
#     #     send_support_summary_email(post_call_data)
#     #
#     #     logger.info("WebSocket disconnected.")
import logging
import json
import base64

from fastapi import APIRouter, HTTPException, WebSocket, status
from fastapi.responses import JSONResponse
from new_config import settings
from pydantic import BaseModel
from typing import Optional, Any

from teler.streams import StreamConnector, StreamType, StreamOp
from teler import AsyncClient
from agent.utils.time_utils import parse_utc_iso, format_ist

logger = logging.getLogger(__name__)
router = APIRouter()

# -----------------------------------------------------------------------------
# GLOBAL STATE (per call lifecycle)
# -----------------------------------------------------------------------------
CALL_CONTEXT: dict[str, dict] = {}
from itertools import count
_chunk_counter = count(1)

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class CallFlowRequest(BaseModel):
    call_id: str
    account_id: str
    from_number: str
    to_number: str
    data: Optional[dict] = None
    direction: Optional[str] = None
    direction_v2: Optional[str] = None


class CallRequest(BaseModel):
    from_number: str
    to_number: str


def normalize_direction(direction: Optional[str]) -> Optional[str]:
    if not direction:
        return None

    return {
        "incoming": "inbound",
        "outgoing": "outbound",
    }.get(direction.strip().lower(), direction.strip().lower())


def extract_direction(*sources: Any) -> Optional[str]:
    for source in sources:
        if not source:
            continue

        if isinstance(source, dict):
            direction = normalize_direction(
                source.get("direction") or source.get("direction_v2")
            )
        else:
            direction = normalize_direction(source)

        if direction:
            return direction

    return None


# -----------------------------------------------------------------------------
# Stream Handlers
# -----------------------------------------------------------------------------
async def call_stream_handler(message: str):
    try:
        msg = json.loads(message)

        # --------------------------------------------------
        # STREAM START
        # --------------------------------------------------
        if msg.get("type") == "start":
            stream_id = msg.get("stream_id")
            logger.info(f"[Teler] stream.start stream_id={stream_id}")

            # Match stream_id → call context
            call_ctx = next(
                (v for v in CALL_CONTEXT.values() if v.get("stream_id") == stream_id),
                None
            )

            if not call_ctx:
                logger.warning("[Bridge] Stream started without call context")
                return ({}, StreamOp.PASS)

            meta_payload = {
                "type": "meta",
                "call_id": call_ctx["call_id"],
                "to_number": call_ctx["to_number"],
            }

            logger.info(f"[Bridge] META injected {meta_payload}")
            return (json.dumps(meta_payload), StreamOp.RELAY)

        # --------------------------------------------------
        # AUDIO
        # --------------------------------------------------
        if msg.get("type") == "audio":
            audio_b64 = msg.get("data", {}).get("audio_b64")
            if audio_b64:
                return (json.dumps({"user_audio_chunk": audio_b64}), StreamOp.RELAY)

        return ({}, StreamOp.PASS)

    except Exception:
        logger.exception("[Bridge] call_stream_handler error")
        return ({}, StreamOp.PASS)


def remote_stream_handler():
    async def handler(message: str):
        try:
            msg = json.loads(message)

            if msg.get("type") == "audio" and msg.get("audio_b64"):
                return (json.dumps({
                    "type": "audio",
                    "audio_b64": msg["audio_b64"],
                    "chunk_id": next(_chunk_counter),
                }), StreamOp.RELAY)

            return ({}, StreamOp.PASS)

        except Exception:
            logger.exception("[Bridge] remote_stream_handler error")
            return ({}, StreamOp.PASS)

    return handler


# -----------------------------------------------------------------------------
# Stream Connector
# -----------------------------------------------------------------------------
connector = StreamConnector(
    stream_type=StreamType.BIDIRECTIONAL,
    remote_url=settings.local_agent_websocket_url,
    call_stream_handler=call_stream_handler,
    remote_stream_handler=remote_stream_handler(),
)


# -----------------------------------------------------------------------------
# Call Flow (Frejun → Stream)
# -----------------------------------------------------------------------------
@router.post("/calls/flow", status_code=200, include_in_schema=False)
async def stream_flow(payload: CallFlowRequest):
    direction = extract_direction(
        payload.direction,
        payload.direction_v2,
        payload.data,
    )
    logger.info(f"[FLOW] call_id={payload.call_id} direction={direction}")

    return {
        "action": "stream",
        "ws_url": f"wss://{settings.server_domain}/api/v1/calls/media-stream",
        "chunk_size": 1000,
        "sample_rate": "16k",
        "record": True,
    }


# -----------------------------------------------------------------------------
# CALL INITIATION (HARDENED)
# -----------------------------------------------------------------------------
@router.post("/initiate-call", status_code=200)
async def initiate_call(call_request: CallRequest):
    logger.info(
        f"[CALL] Initiating from={call_request.from_number} to={call_request.to_number}"
    )

    try:
        async with AsyncClient(
            api_key=settings.teler_api_key,
            timeout=15
        ) as client:

            call = await client.calls.create(
                from_number=call_request.from_number,
                to_number=call_request.to_number,
                flow_url=f"https://{settings.server_domain}/api/v1/calls/flow",
                status_callback_url=f"https://{settings.server_domain}/api/v1/webhooks/receiver",
                record=True,
            )

            # 🚨 HARD VALIDATION
            call_id = getattr(call, "id", None)
            if not call_id:
                logger.error("[CALL] No call_id returned")
                raise RuntimeError("Call creation failed")

            logger.info(f"[CALL] Created call_id={call_id}")
            return {"success": True, "call_id": call_id}

    except Exception:
        logger.exception("[CALL] Initiation failed")
        return JSONResponse(
            status_code=502,
            content={"success": False, "reason": "CALL_INIT_FAILED"},
        )


# -----------------------------------------------------------------------------
# WEBHOOK RECEIVER (CRITICAL FIX)
# -----------------------------------------------------------------------------
@router.post("/webhooks/receiver", status_code=200, include_in_schema=False)
async def webhook_receiver(payload: dict):
    data = payload.get("data", {}) or {}
    start_ist  = format_ist(parse_utc_iso(data.get("start_time")))
    hangup_ist = format_ist(parse_utc_iso(data.get("hangup_time")))
    log_payload = {**payload}
    if start_ist or hangup_ist:
        log_payload["data"] = {
            **data,
            **({"start_time": start_ist} if start_ist else {}),
            **({"hangup_time": hangup_ist} if hangup_ist else {}),
        }
    logger.info(f"[WEBHOOK] {log_payload}")

    event = payload.get("event")
    call_id = data.get("call_id")
    direction = extract_direction(data)

    if not call_id:
        return {"status": "ignored"}

    ctx = CALL_CONTEXT.setdefault(call_id, {})
    ctx["call_id"] = call_id
    if direction:
        ctx["direction"] = direction

    if event == "call.initiated":
        initiated_context = {
            "from_number": data.get("from"),
            "to_number": data.get("to"),
            "status": "initiated",
        }
        if direction:
            initiated_context["direction"] = direction
        ctx.update(initiated_context)

    elif event == "call.answered":
        ctx["status"] = "answered"

    elif event == "stream.initiated":
        ctx["stream_id"] = data.get("stream_id")
        logger.info(f"[WEBHOOK] stream bound call_id={call_id}")

    elif event == "call.failed":
        logger.error(f"[CALL FAILED] call_id={call_id}")
        CALL_CONTEXT.pop(call_id, None)

    elif event == "call.completed":
        CALL_CONTEXT.pop(call_id, None)

    return {"status": "ok"}


# -----------------------------------------------------------------------------
# MEDIA STREAM SOCKET
# -----------------------------------------------------------------------------
@router.websocket("/calls/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("[WS] media-stream connected")

    try:
        await connector.bridge_stream(websocket)
    finally:
        logger.info("[WS] media-stream disconnected")
