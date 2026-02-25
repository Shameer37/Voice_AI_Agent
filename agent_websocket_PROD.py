# agent_websocket_PROD.py
# ============================================================================
# PRODUCTION VOICE AGENT (LOW LATENCY, FREJUN SAFE, HALF-DUPLEX)
# ============================================================================

import asyncio
import json
import logging
import base64
import re
import time
import struct
import math
from agent.utils.time_utils import utc_now, parse_utc_iso, format_ist
from typing import Optional, Any
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from starlette.websockets import WebSocketState
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo
from datetime import timezone

from speech.stt_openai_batch_FIXED import OpenAIBatchSTT
from speech.tts_8khz import TTS8k
from agent.rag_engine import get_contextual_response, load_context_retriever
from analysis.intent_extractor import extract_intent_and_summary
from config import GREETING_MESSAGE, FAREWELL_MESSAGE, EXIT_KEYWORDS, FIRST_REPLY_FILLER
from agent.utils.email_utils import send_support_summary_email
from analysis.hinglish_normalizer import normalize_hinglish
from dotenv import load_dotenv
load_dotenv()
# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("agent")

# ----------------------------------------------------------------------------
# FastAPI
# ----------------------------------------------------------------------------
app = FastAPI(title="Frejun Voice Agent")

# ----------------------------------------------------------------------------
# Audio config
# ----------------------------------------------------------------------------
INPUT_SR = 16000
TTS_SR = 8000

TURN_SILENCE_SECONDS = 0.4
MAX_TURN_SECONDS = 4.0

MIN_BUFFER_FIRST_TURN = int(INPUT_SR * 2 * 0.25)
MIN_BUFFER_NORMAL = int(INPUT_SR * 2 * 0.45)

ENERGY_THRESHOLD = 300
MIN_SPEECH_CHUNKS = 2
MAX_SILENT_BEFORE_RESET = 8
MIN_UTTERANCE_CHARS = 2


# ----------------------------------------------------------------------------
# Globals
# ----------------------------------------------------------------------------
_TTS: Optional[TTS8k] = None
_RETRIEVER: Optional[Any] = None
_CACHED_GREETING: Optional[bytes] = None
_CACHED_FILLER: Optional[bytes] = None
_GLOBAL_STT_WARM: Optional[OpenAIBatchSTT] = None
_CACHED_FAREWELL: Optional[bytes] = None


# ----------------------------------------------------------------------------
# Utils
# ----------------------------------------------------------------------------
def calculate_rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    n = len(pcm) // 2
    samples = struct.unpack(f"<{n}h", pcm)
    return math.sqrt(sum(s * s for s in samples) / n)

# def clean_transcript(text: str) -> str:
#     if not text:
#         return ""
#     text = re.sub(r"\s+", " ", text).strip()
#     if not re.search(r"[A-Za-z0-9\u0900-\u097F]", text):
#         return ""
#     return text
def clean_transcript(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()

    # Allow pure digits (serial numbers, phone numbers)
    if re.fullmatch(r"[0-9]{4,}", text):
        return text

    # Allow Hindi / English mixed speech
    if not re.search(r"[A-Za-z\u0900-\u097F]", text):
        return ""

    return text

def is_exit_utterance(text: str) -> bool:
    return any(k in text.lower() for k in EXIT_KEYWORDS)



# ----------------------------------------------------------------------------
# Lifespan
# ----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _TTS, _RETRIEVER, _CACHED_GREETING, _CACHED_FILLER, _GLOBAL_STT_WARM, _CACHED_FAREWELL

    logger.info("Starting voice agent")

    _TTS = TTS8k()
    await _TTS.warmup()

    warm = OpenAIBatchSTT(
        samplerate=INPUT_SR,
        model="gpt-4o-mini-transcribe",
        language="hi",
        use_webrtc_vad=False,
    )
    warm.add_chunk(b"\x00\x00" * (INPUT_SR // 4))
    try:
        await warm.transcribe_buffer()
    except Exception:
        pass

    _GLOBAL_STT_WARM = warm

    _CACHED_GREETING = await _TTS.synthesize_and_cache(GREETING_MESSAGE)
    _CACHED_FILLER = await _TTS.synthesize_and_cache(FIRST_REPLY_FILLER)
    _CACHED_FAREWELL = await _TTS.synthesize_and_cache(FAREWELL_MESSAGE)

    _RETRIEVER = load_context_retriever("vectorstore")
    logger.info("Agent ready")

    yield

app.router.lifespan_context = lifespan

# ----------------------------------------------------------------------------
# WebSocket
# ----------------------------------------------------------------------------
@app.websocket("/ws/agent")
async def agent_ws(ws: WebSocket):
    await ws.accept()
    logger.info("New call connected")
    #call_start_ts = datetime.utcnow()
    call_start_ts = utc_now()
    call_id = None
    to_number = None
    transcript_lines = []

    # ---------------------------
    # Audio sender (ONLY writer)
    # ---------------------------
    out_audio_q = asyncio.Queue(maxsize=40)

    async def audio_sender():
        while ws.client_state == WebSocketState.CONNECTED:
            pcm = await out_audio_q.get()
            await ws.send_text(json.dumps({
                "type": "audio",
                "audio_b64": base64.b64encode(pcm).decode()
            }))

    sender_task = asyncio.create_task(audio_sender())

    # ---------------------------
    # STT
    # ---------------------------
    stt = _GLOBAL_STT_WARM.clone()
    stt.reset()

    # ---------------------------
    # State
    # ---------------------------
    audio_buffer = bytearray()
    last_speech_ts = time.time()
    last_rms = 0.0

    tts_active = False
    first_turn = True
    skip_next_utterance = True
    greeting_end_ts = 0.0
    first_reply_filler_played = False

    consecutive_speech = 0
    consecutive_silent = 0
    is_user_speaking = False

    
    last_turn_end_ts = 0.0
    TURN_COOLDOWN_SECONDS = 0.8
    call_active = True

    # Semantic turn buffer (per call)
    semantic_buffer = []
    semantic_last_ts = time.time()
    SEMANTIC_SILENCE = 0.6   # slightly longer than acoustic silence
    MAX_SEMANTIC_LEN = 200

    # ---------------------------
    # Greeting (BLOCKING INPUT)
    # ---------------------------
    logger.info("Playing greeting")
    tts_active = True
    frame = int(TTS_SR * 2 * 0.4)
    for i in range(0, len(_CACHED_GREETING), frame):
        await out_audio_q.put(_CACHED_GREETING[i:i + frame])
        await asyncio.sleep(0.4)
    tts_active = False
    greeting_end_ts = time.time()

    # ---------------------------
    # async def process_turn():
    #     nonlocal first_reply_filler_played, first_turn, skip_next_utterance

    #     audio = bytes(audio_buffer)
    #     audio_buffer.clear()

    #     if not stt.add_chunk(audio):
    #         return

    #     # Play filler ONCE, instantly
    #     if not first_reply_filler_played:
    #         first_reply_filler_played = True
    #         frame = int(TTS_SR * 2 * 0.16)
    #         for i in range(0, len(_CACHED_FILLER), frame):
    #             await out_audio_q.put(_CACHED_FILLER[i:i + frame])

    #     asyncio.create_task(background_intelligence())


    # background_task: Optional[asyncio.Task] = None
    # async def process_turn():
    #     nonlocal first_reply_filler_played, first_turn, skip_next_utterance
    #     nonlocal background_task

    #     audio = bytes(audio_buffer)
    #     audio_buffer.clear()

    #     max_bytes = int(MAX_TURN_SECONDS * INPUT_SR * 2)
    #     if len(audio) > max_bytes:
    #         audio = audio[-max_bytes:]

    #     if len(audio) < int(INPUT_SR * 2 * 0.4):
    #         return

    #     if not stt.add_chunk(audio):
    #         return

    #     # Filler: delayed, once, no cancellation
    #     if not first_reply_filler_played and _CACHED_FILLER:
    #         first_reply_filler_played = True

    #         async def delayed_filler():
    #             await asyncio.sleep(0.3)
    #             frame = int(TTS_SR * 2 * 0.16)
    #             for i in range(0, len(_CACHED_FILLER), frame):
    #                 await out_audio_q.put(_CACHED_FILLER[i:i + frame])

    #         asyncio.create_task(delayed_filler())

    #     if background_task and not background_task.done():
    #         background_task.cancel()
    #         try: 
    #             await background_task
    #         except asyncio.CancelledError:
    #             pass
    #             background_task = asyncio.create_task(background_intelligence())

    #         async def background_intelligence():
    #             nonlocal skip_next_utterance, first_turn, tts_active

    background_task: Optional[asyncio.Task] = None

    async def background_intelligence():
        nonlocal skip_next_utterance, first_turn, tts_active, call_active, semantic_last_ts

        # -------------------------------
        # 1) Get final transcript
        # -------------------------------
        text = clean_transcript(await stt.transcribe_buffer())
        text = normalize_hinglish(text)                   #This line is added for that intent extractor can work better on hinglish inputs. It normalizes common hinglish words to a more standard form. If the output gets worse then we should  remove this line.
        if len(text) < MIN_UTTERANCE_CHARS:
            return

        # -------------------------------
        # 🧠 SEMANTIC CHUNKING START
        # -------------------------------
        now = time.time()

        # semantic_pause must be measured before updating semantic_last_ts
        semantic_pause = (now - semantic_last_ts) > SEMANTIC_SILENCE

        semantic_buffer.append(text)
        semantic_last_ts = now

        # Join what user has said so far
        merged_text = " ".join(semantic_buffer).strip()

        # Stop conditions (VERY IMPORTANT)
        SEMANTIC_STOP_WORDS = [
            "haan", "haan ji", "bas", "itna hi",
            "yehi problem", "ho gaya", "nahi aur"
        ]

        has_stop_word = any(w in merged_text.lower() for w in SEMANTIC_STOP_WORDS)
        too_long = len(merged_text) >= MAX_SEMANTIC_LEN

        # Decide whether meaning is complete
        if not (has_stop_word or too_long or semantic_pause):
            logger.info(f"[SEMANTIC BUFFERING] {merged_text}")
            return

        # FINAL semantic utterance
        final_text = merged_text
        semantic_buffer.clear()

        logger.info(f"[SEMANTIC FINAL] {final_text}")

        logger.info(f"[USER] {final_text}")
        # CHANGE: capture user text for post-call summary
        transcript_lines.append(f"USER: {final_text}")

        # -------------------------------
        # 2) Greeting-only skip (first turn protection)
        # -------------------------------
        if skip_next_utterance and any(
            w in final_text.lower() for w in ["hello", "hi", "hey", "à¤¹à¥‡à¤²à¥‹", "à¤¹à¤²à¥‹", "à¤¨à¤®à¤¸à¥à¤¤à¥‡"]
        ):
            logger.info("[STT] Greeting-only utterance skipped")
            skip_next_utterance = False
            return

        skip_next_utterance = False
        first_turn = False

        # -------------------------------
        # 3) EXIT INTENT (HIGHEST PRIORITY)
        # -------------------------------
        if is_exit_utterance(final_text):
            logger.info("[CALL] Exit intent detected")

            if _CACHED_FAREWELL:
                tts_active = True
                frame = int(TTS_SR * 2 * 0.30)  # 300 ms frames
                for i in range(0, len(_CACHED_FAREWELL), frame):
                    await out_audio_q.put(_CACHED_FAREWELL[i:i + frame])
                    await asyncio.sleep(0.30)
                tts_active = False

            call_active = False
            return

        # -------------------------------
        # 4) NORMAL RAG + LLM FLOW
        # -------------------------------
        reply = await asyncio.to_thread(
            get_contextual_response, final_text, _RETRIEVER, "session"
        )

        logger.info(f"[AGENT] {reply}")
        # CHANGE: capture agent reply for post-call summary
        transcript_lines.append(f"AGENT: {reply}")

        # -------------------------------
        # 5) Speak reply
        # -------------------------------
        tts_active = True
        async for pkt in _TTS.generate_frejun_audio_chunks(reply, chunk_ms=120):
            await out_audio_q.put(base64.b64decode(pkt["audio_b64"]))
        tts_active = False

    async def process_turn():
        nonlocal first_reply_filler_played, background_task

        audio = bytes(audio_buffer)
        audio_buffer.clear()

        # limit turn size
        max_bytes = int(MAX_TURN_SECONDS * INPUT_SR * 2)
        if len(audio) > max_bytes:
            audio = audio[-max_bytes:]

        # drop super short turns
        if len(audio) < int(INPUT_SR * 2 * 0.4):
            return

        if not stt.add_chunk(audio):
            return

        # Play filler ONCE, delayed
        if not first_reply_filler_played and _CACHED_FILLER:
            first_reply_filler_played = True

            async def delayed_filler():
                await asyncio.sleep(0.3)
                frame = int(TTS_SR * 2 * 0.16)
                for i in range(0, len(_CACHED_FILLER), frame):
                    await out_audio_q.put(_CACHED_FILLER[i:i + frame])

            asyncio.create_task(delayed_filler())

        # Cancel previous background task (prevents overlap)
        if background_task and not background_task.done():
            background_task.cancel()
            try:
                await background_task
            except asyncio.CancelledError:
                pass 

        # âœ… Only background_intelligence does STTâ†’LLMâ†’TTS
        background_task = asyncio.create_task(background_intelligence())


    # ---------------------------
    # Main receive loop                 
    # ---------------------------
    try:
        # while True:
        while call_active:
            msg = await ws.receive_text()
            data = json.loads(msg)
            # Handle optional metadata message
            if data.get("type") == "meta":
                # Previous behavior (kept for reference):
                # (No metadata handling)

                call_id = data.get("call_id") or call_id
                to_number = data.get("to_number") or to_number
                logger.info(f"[META] call_id={call_id} to_number={to_number}")
                continue
            if "user_audio_chunk" not in data:
                continue

            if tts_active:
                continue  # HARD GATE â€” REQUIRED

            chunk = base64.b64decode(data["user_audio_chunk"])
            rms = calculate_rms(chunk)
            last_rms = rms

            if rms > ENERGY_THRESHOLD:
                last_speech_ts = time.time()
                consecutive_speech += 1
                consecutive_silent = 0
                if consecutive_speech >= MIN_SPEECH_CHUNKS:
                    is_user_speaking = True
            else:
                consecutive_silent += 1

            if is_user_speaking:
                audio_buffer.extend(chunk)

            silence = time.time() - last_speech_ts
            min_buf = MIN_BUFFER_FIRST_TURN if first_turn else MIN_BUFFER_NORMAL

            # if (
            #     is_user_speaking
            #     and silence > TURN_SILENCE_SECONDS
            #     and len(audio_buffer) >= int(INPUT_SR * 2 * 0.6)
            # ):
            #     is_user_speaking = False
            #     consecutive_speech = 0
            #     await process_turn()

            now = time.time()

            if (
                is_user_speaking
                and silence > TURN_SILENCE_SECONDS
                and len(audio_buffer) >= int(INPUT_SR * 2 * 0.6)
                and (now - last_turn_end_ts) > TURN_COOLDOWN_SECONDS
            ):
                last_turn_end_ts = now
                is_user_speaking = False
                consecutive_speech = 0
                await process_turn()

    except WebSocketDisconnect:
        pass
    # finally:
    #     sender_task.cancel()
    #     logger.info("Call ended")
    finally:
        call_active = False

        sender_task.cancel()

        try:
            await ws.close()
        except Exception:
            pass

        # Previous behavior (kept for reference):
        # logger.info("Call ended")

        # NEW: send summary email after call ends
        call_end_ts = utc_now()
        duration = int((call_end_ts - call_start_ts).total_seconds())
        # Previous behavior (kept for reference):
        # post_call_data = {
        #     "merchant_id": None,
        #     "merchant_name": None,
        #     "merchant_phone": to_number,
        #     "call_id": call_id,
        #     "call_time": call_start_ts.isoformat(),
        #     "duration": duration,
        #     "agent_connected": True,
        #     "call_result": "completed",
        #     "intent": "unknown",
        #     "summary": "Call completed via agent websocket (no transcript attached)."
        # }

        # CHANGE: build short summary from transcript
        transcript_text = "\n".join(transcript_lines).strip()
        if transcript_text:
            intent_data = await asyncio.to_thread(
                extract_intent_and_summary, transcript_text
            )
            intent = intent_data.get("intent", "unknown")
            summary = intent_data.get("summary", "Summary unavailable.")
        else:
            intent = "unknown"
            summary = "No transcript captured."

        post_call_data = {
            "merchant_id": None,
            "merchant_name": None,
            "merchant_phone": to_number,
            "call_id": call_id,
            "call_time": format_ist(call_start_ts),
            "duration": duration,
            "agent_connected": True,
            "call_result": "completed",
            "intent": intent,
            "summary": summary
        }
        send_support_summary_email(post_call_data)

        logger.info("Call ended")

# ============================================================================
# Main 
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_websocket_PROD:app", host="0.0.0.0", port=8001)


