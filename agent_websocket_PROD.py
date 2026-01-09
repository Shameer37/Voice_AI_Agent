
# # agent_websocket_PROD.py
# # ============================================================================
# # PRODUCTION VOICE AGENT (LOW LATENCY, STABLE TURN-TAKING)
# # ============================================================================

# import asyncio
# import json
# import logging
# import base64
# import re
# import time
# import struct
# import math
# from typing import Optional, Any
# from fastapi import FastAPI, WebSocket
# from fastapi.websockets import WebSocketDisconnect
# from starlette.websockets import WebSocketState
# from contextlib import asynccontextmanager

# from speech.stt_openai_batch_FIXED import OpenAIBatchSTT
# from speech.tts_8khz import TTS8k
# from agent.rag_engine import get_contextual_response, load_context_retriever
# from config import GREETING_MESSAGE, FAREWELL_MESSAGE, EXIT_KEYWORDS, FIRST_REPLY_FILLER

# # ============================================================================
# # Logging
# # ============================================================================
# logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
# logger = logging.getLogger("agent")

# # ============================================================================
# # FastAPI
# # ============================================================================
# app = FastAPI(title="Frejun Voice Agent")

# # ============================================================================
# # Audio Configuration
# # ============================================================================
# INPUT_SR = 16000
# TTS_SR = 8000

# TURN_SILENCE_SECONDS = 0.35    
# MAX_TURN_SECONDS = 4.0

# MIN_BUFFER_FIRST_TURN = int(INPUT_SR * 2 * 0.25)   # 250ms
# MIN_BUFFER_NORMAL = int(INPUT_SR * 2 * 0.45)       # 450ms

# ENERGY_THRESHOLD = 300
# MIN_SPEECH_CHUNKS = 2
# TRAILING_SILENCE_CHUNKS = 4
# MAX_SILENT_BEFORE_RESET = 8
# MIN_UTTERANCE_CHARS = 2
# _GLOBAL_STT_WARM = None  #Added we should remove it if not works

# # ============================================================================
# # Globals
# # ============================================================================
# _TTS: Optional[TTS8k] = None
# _RETRIEVER: Optional[Any] = None
# _CACHED_GREETING: Optional[bytes] = None
# _CACHED_FILLER: Optional[bytes] = None

# # ============================================================================
# # Utilities
# # ============================================================================  
# def calculate_rms(pcm: bytes) -> float:
#     if len(pcm) < 2:
#         return 0.0
#     n = len(pcm) // 2
#     try:
#         samples = struct.unpack(f"<{n}h", pcm)
#         return math.sqrt(sum(s * s for s in samples) / n)
#     except Exception:
#         return 0.0


# def clean_transcript(text: str) -> str:
#     if not text:
#         return ""
#     text = re.sub(r"\s+", " ", text).strip()
#     if not re.search(r"[A-Za-z0-9\u0900-\u097F]", text):
#         return ""
#     return text


# def is_exit_utterance(text: str) -> bool:
#     return any(k in text.lower() for k in EXIT_KEYWORDS)
# # def is_exit_utterance(text: str) -> bool:
# #     t = text.lower().strip()
# #     return any(t == k or t.endswith(k) for k in EXIT_KEYWORDS)

# # ============================================================================
# # Lifespan
# # ============================================================================
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     global _TTS, _RETRIEVER, _CACHED_GREETING, _GLOBAL_STT_WARM, _CACHED_FILLER

#     logger.info("Starting voice agent")

#     _TTS = TTS8k()
#     await _TTS.warmup()

#     # Warm-up STT model (prevents slow first transcription)
#     logger.info("Warming STT...")
#     warmup_stt = OpenAIBatchSTT(
#         samplerate=INPUT_SR,
#         model="gpt-4o-mini-transcribe",
#         language="hi",
#         use_webrtc_vad=False,
#     )
#     silent_audio = b"\x00\x00" * (INPUT_SR // 4)   # 250 ms of silence
#     warmup_stt.add_chunk(silent_audio)

#     try:                
#         _ = await warmup_stt.transcribe_buffer()
#         logger.info("STT warm-up complete")
#     except Exception as e:
#         logger.warning(f"STT warm-up failed: {e}")

#     _GLOBAL_STT_WARM = warmup_stt  #Same for here also 


#     pcm = await _TTS.synthesize_and_cache(GREETING_MESSAGE)
#     if pcm:
#         _CACHED_GREETING = pcm

#     _RETRIEVER = load_context_retriever("vectorstore")
#     yield


# app.router.lifespan_context = lifespan

# # ============================================================================
# # WebSocket
# # ============================================================================
# @app.websocket("/ws/agent")
# async def agent_ws(ws: WebSocket):
#     await ws.accept()
#     logger.info("New call connected")

#     # stt = OpenAIBatchSTT(
#     #     samplerate=INPUT_SR,
#     #     model="gpt-4o-mini-transcribe",
#     #     language="hi",
#     #     use_webrtc_vad=True,
#     #     energy_threshold=ENERGY_THRESHOLD,
#     # )

#         # -----------------------------
#     # Outbound audio queue + sender
#     # -----------------------------
#     out_audio_q = asyncio.Queue(maxsize=30)

#     async def audio_sender():
#         while True:
#             pcm = await out_audio_q.get()
#             if ws.client_state != WebSocketState.CONNECTED:
#                 break
#             await ws.send_text(json.dumps({
#                 "type": "audio",
#                 "audio_b64": base64.b64encode(pcm).decode()
#             }))

#     sender_task = asyncio.create_task(audio_sender())

#     # ---------------------------------------------------------
#     # Use pre-warmed STT instance (fixes slow first transcription) . This should be removed if not works
#     # ---------------------------------------------------------
#     if _GLOBAL_STT_WARM is not None and hasattr(_GLOBAL_STT_WARM, "clone"):
#         stt = _GLOBAL_STT_WARM.clone()
#         stt.reset()   # clear any leftover buffer from warm-up
#         logger.info("[STT] Using pre-warmed STT model")
#     else:
#         # fallback if clone() not available
#         stt = OpenAIBatchSTT(
#             samplerate=INPUT_SR,
#             model="gpt-4o-mini-transcribe",
#             language="hi",
#             use_webrtc_vad=True,
#             energy_threshold=ENERGY_THRESHOLD,
#         )
#         logger.info("[STT] Using fresh STT instance (no warm clone)")


#     audio_buffer = bytearray()
#     buffer_start_ts = None
#     last_speech_ts = time.time()
#     last_rms = 0.0

#     tts_active = False
#     turn_task = None

#     first_turn = True
#     skip_next_utterance = True
#     greeting_end_ts = 0.0
#     first_reply_filler_played = False

#     consecutive_speech = 0
#     consecutive_silent = 0
#     is_user_speaking = False
#     # out_audio_q: asyncio.Queue = asyncio.Queue(maxsize=30)

#     # ------------------------------------------------------------------
#     async def send_audio(pcm: bytes):
#         if ws.client_state == WebSocketState.CONNECTED:
#             await ws.send_text(json.dumps({
#                 "type": "audio",
#                 "audio_b64": base64.b64encode(pcm).decode()
#             }))

#     # ------------------------------------------------------------------
#     async def stream_tts(text: str):
#         nonlocal tts_active, audio_buffer, buffer_start_ts
#         nonlocal consecutive_speech, consecutive_silent, is_user_speaking

#         tts_active = True
#         logger.info(f"[TTS] {text[:40]}")

#         try:
#             if text == GREETING_MESSAGE and _CACHED_GREETING:
#                 frame = int(TTS_SR * 2 * 0.4)
#                 for i in range(0, len(_CACHED_GREETING), frame):
#                     await send_audio(_CACHED_GREETING[i:i + frame])
#                     await asyncio.sleep(0.4)
#             else:
#                 async for out in _TTS.generate_frejun_audio_chunks(text, chunk_ms=400):
#                     await ws.send_text(json.dumps(out))
#         finally:
#             tts_active = False
#             audio_buffer.clear()
#             buffer_start_ts = None 
#             consecutive_speech = 0
#             consecutive_silent = 0
#             is_user_speaking = False

#     # ------------------------------------------------------------------
#     # async def handle_text(text: str):
#     #     logger.info(f"[USER] {text}")

#     #     if is_exit_utterance(text):
#     #         await stream_tts(FAREWELL_MESSAGE)
#     #         await ws.close()
#     #         return

#     #     reply = await asyncio.to_thread(
#     #         get_contextual_response, text, _RETRIEVER, "session"
#     #     )

#     #     reply = re.sub(
#     #             r"(नमस्ते|हैलो|हेलो|मैं .*? बोल रही हूं).*?(\n|$)",
#     #             "",
#     #             reply,
#     #             flags=re.IGNORECASE
#     #         ).strip()

#     #     logger.info(f"[AGENT] {reply}")
#     #     await stream_tts(reply)

#     async def handle_text(text: str):
#         nonlocal first_reply_filler_played

#         logger.info(f"[USER] {text}")

#         if is_exit_utterance(text):
#             await stream_tts(FAREWELL_MESSAGE)
#             await ws.close()  
#             return

#         # 🔹 START LLM IN BACKGROUND (NON-BLOCKING)
#         rag_task = asyncio.to_thread(
#             get_contextual_response, text, _RETRIEVER, "session"
#         )

#         # ✅ FIRST-REPLY UX MASK (ONLY ONCE)
#         # if not first_reply_filler_played:
#         #     first_reply_filler_played = True
#         #     await stream_tts(FIRST_REPLY_FILLER)

#         reply = await rag_task

#         reply = re.sub(
#             r"(नमस्ते|हैलो|हेलो|मैं .*? बोल रही हूं).*?(\n|$)",
#             "",
#             reply,
#             flags=re.IGNORECASE,
#         ).strip()

#         logger.info(f"[AGENT] {reply}")
#         await stream_tts(reply)


#     # ------------------------------------------------------------------
#     # async def process_turn():
#     #     nonlocal audio_buffer, buffer_start_ts
#     #     nonlocal skip_next_utterance, first_turn
#     #     nonlocal consecutive_speech, consecutive_silent, is_user_speaking
#     #     nonlocal first_reply_filler_played 

#     #     #GREETING_ECHO_WINDOW = 0.6
#     #     GREETING_ECHO_WINDOW = 1.2
#     #     now = time.time()

#     #     # 1) If very close to greeting end, drop as echo without STT
#     #     if skip_next_utterance and (now - greeting_end_ts) < GREETING_ECHO_WINDOW:    
#     #         logger.info("[STT] Dropping first turn as greeting echo (no STT)")
#     #         audio_buffer.clear()
#     #         buffer_start_ts = None
#     #         consecutive_speech = 0
#     #         consecutive_silent = 0
#     #         is_user_speaking = False
#     #         # keep skip_next_utterance = True so that next real turn can still be tested
#     #         return

#     #     if not audio_buffer:
#     #         return

#     #     audio = bytes(audio_buffer)
#     #     audio_buffer.clear()
#     #     buffer_start_ts = None
#     #     consecutive_speech = 0
#     #     consecutive_silent = 0
#     #     is_user_speaking = False

#     #     # Cap length
#     #     max_bytes = int(MAX_TURN_SECONDS * INPUT_SR * 2)
#     #     if len(audio) > max_bytes:
#     #         audio = audio[-max_bytes:]

#     #     # 2) Try adding to STT; if rejected as too quiet, just return
#     #     if not stt.add_chunk(audio):
#     #         return
        
#     #     # # ✅ FIRST-REPLY FILLER — CORRECT PLACE
#     #     if not first_reply_filler_played:
#     #         first_reply_filler_played = True
#     #         asyncio.create_task(
#     #             stream_tts(FIRST_REPLY_FILLER)
#     #         )

#     #     text = clean_transcript(await stt.transcribe_buffer())
#     #     if len(text) < MIN_UTTERANCE_CHARS:
#     #         return

#     #     # Mark that we have processed a meaningful first turn
#     #     first_turn = False

#     #     # 3) If this is greeting-like text and skip flag is still on, skip response
#     #     if skip_next_utterance and any(
#     #         w in text.lower() for w in ["hello", "hi", "hey", "हेलो", "हलो", "नमस्ते"]
#     #     ):
#     #         logger.info(f"[STT] Greeting-only first turn detected: '{text}', skipping reply")
#     #         skip_next_utterance = False
#     #         return

#     #     # From here on, treat as normal user query
#     #     skip_next_utterance = False
#     #     await handle_text(text)

#     async def process_turn():
#         nonlocal audio_buffer, buffer_start_ts
#         nonlocal skip_next_utterance, first_turn
#         nonlocal consecutive_speech, consecutive_silent, is_user_speaking
#         nonlocal first_reply_filler_played

#         GREETING_ECHO_WINDOW = 1.2
#         now = time.time()

#         # ---------------------------------------------------
#         # 1) Drop greeting echo (NO STT, NO FILLER)
#         # ---------------------------------------------------
#         if skip_next_utterance and (now - greeting_end_ts) < GREETING_ECHO_WINDOW:
#             logger.info("[STT] Dropping first turn as greeting echo (no STT)")
#             audio_buffer.clear()
#             buffer_start_ts = None
#             consecutive_speech = 0
#             consecutive_silent = 0
#             is_user_speaking = False
#             return

#         if not audio_buffer:
#             return

#         # ---------------------------------------------------
#         # 2) Finalize audio buffer FAST
#         # ---------------------------------------------------
#         audio = bytes(audio_buffer)
#         audio_buffer.clear()
#         buffer_start_ts = None
#         consecutive_speech = 0
#         consecutive_silent = 0
#         is_user_speaking = False

#         # Cap max utterance length
#         max_bytes = int(MAX_TURN_SECONDS * INPUT_SR * 2)
#         if len(audio) > max_bytes:
#             audio = audio[-max_bytes:]

#         # ---------------------------------------------------
#         # 3) Push audio into STT buffer (FAST CHECK)
#         # ---------------------------------------------------
#         if not stt.add_chunk(audio):
#             return

#         # ---------------------------------------------------
#         # 4) PLAY FIRST-REPLY FILLER **IMMEDIATELY**
#         #    (NO await on STT / RAG / LLM)
#         # ---------------------------------------------------
#         if not first_reply_filler_played and _CACHED_FILLER:
#             first_reply_filler_played = True
#             frame = int(TTS_SR * 2 * 0.16)  # 160 ms frames
#             for i in range(0, len(_CACHED_FILLER), frame):
#                 await out_audio_q.put(_CACHED_FILLER[i:i + frame])

#         # ---------------------------------------------------
#         # 5) RELEASE TURN — RUN INTELLIGENCE IN BACKGROUND
#         # ---------------------------------------------------
#         asyncio.create_task(background_intelligence())

#         # IMPORTANT: return immediately
#         return

#     async def background_intelligence():
#         text = clean_transcript(await stt.transcribe_buffer())
#         if len(text) < MIN_UTTERANCE_CHARS:
#             return

#         # Greeting-only utterance skip (preserved logic)
#         if skip_next_utterance and any(
#             w in text.lower() for w in ["hello", "hi", "hey", "हेलो", "हलो", "नमस्ते"]
#         ):
#             logger.info(f"[STT] Greeting-only first turn detected: '{text}', skipping reply")
#             skip_next_utterance = False
#             return

#         skip_next_utterance = False

#         reply = await asyncio.to_thread(
#             get_contextual_response, text, _RETRIEVER, "session"
#         )

#         async for pkt in _TTS.generate_frejun_audio_chunks(reply, chunk_ms=120):
#             pcm = base64.b64decode(pkt["audio_b64"])
#             await out_audio_q.put(pcm)


#     # ------------------------------------------------------------------
#     logger.info("Playing greeting")
#     await stream_tts(GREETING_MESSAGE)
#     greeting_end_ts = time.time()

#     try:
#         while True:
#             try:
#                 msg = await asyncio.wait_for(ws.receive_text(), timeout=0.05)
#                 data = json.loads(msg)
#                 if "user_audio_chunk" not in data:
#                     continue

#                 chunk = base64.b64decode(data["user_audio_chunk"])
#                 rms = calculate_rms(chunk)
#                 last_rms = rms
#                 has_speech = rms > ENERGY_THRESHOLD

#                 if tts_active:
#                     continue

#                 if has_speech:
#                     consecutive_speech += 1
#                     consecutive_silent = 0
#                     last_speech_ts = time.time()
#                     if consecutive_speech >= MIN_SPEECH_CHUNKS:
#                         is_user_speaking = True
#                 else:
#                     consecutive_silent += 1
#                     if consecutive_silent >= MAX_SILENT_BEFORE_RESET and buffer_start_ts is None:
#                         is_user_speaking = False
#                         consecutive_speech = 0

#                 if is_user_speaking:
#                     if buffer_start_ts is None:
#                         buffer_start_ts = time.time()
#                     audio_buffer.extend(chunk)

#             except asyncio.TimeoutError:
#                 pass

#             time_since_speech = time.time() - last_speech_ts
#             effective_silence = 0.10 if first_turn else TURN_SILENCE_SECONDS
#             is_silent = (
#                 time_since_speech > effective_silence
#                 or (last_rms < ENERGY_THRESHOLD * 0.6 and time_since_speech > 0.18)
#             )

#             min_buf = MIN_BUFFER_FIRST_TURN if first_turn else MIN_BUFFER_NORMAL
#             busy = turn_task and not turn_task.done()

#             if (
#                 len(audio_buffer) >= min_buf
#                 and is_user_speaking
#                 and is_silent
#                 and not busy
#                 and not tts_active
#             ):
#                 turn_task = asyncio.create_task(process_turn())

#             await asyncio.sleep(0.01)

#     except WebSocketDisconnect:
#         pass

#     finally:
#         if turn_task and not turn_task.done():
#             turn_task.cancel()
#         logger.info("Call ended")


# # ============================================================================
# # Main
# # ============================================================================
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("agent_websocket_PROD:app", host="0.0.0.0", port=8001)


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
from typing import Optional, Any
from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
from starlette.websockets import WebSocketState
from contextlib import asynccontextmanager

from speech.stt_openai_batch_FIXED import OpenAIBatchSTT
from speech.tts_8khz import TTS8k
from agent.rag_engine import get_contextual_response, load_context_retriever
from config import GREETING_MESSAGE, FAREWELL_MESSAGE, EXIT_KEYWORDS, FIRST_REPLY_FILLER

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


    background_task: Optional[asyncio.Task] = None
    async def process_turn():
        nonlocal first_reply_filler_played, first_turn, skip_next_utterance
        nonlocal background_task

        audio = bytes(audio_buffer)
        audio_buffer.clear()

        max_bytes = int(MAX_TURN_SECONDS * INPUT_SR * 2)
        if len(audio) > max_bytes:
            audio = audio[-max_bytes:]

        if len(audio) < int(INPUT_SR * 2 * 0.4):
            return

        if not stt.add_chunk(audio):
            return

        # Filler: delayed, once, no cancellation
        if not first_reply_filler_played and _CACHED_FILLER:
            first_reply_filler_played = True

            async def delayed_filler():
                await asyncio.sleep(0.3)
                frame = int(TTS_SR * 2 * 0.16)
                for i in range(0, len(_CACHED_FILLER), frame):
                    await out_audio_q.put(_CACHED_FILLER[i:i + frame])

            asyncio.create_task(delayed_filler())

        if background_task and not background_task.done():
            background_task.cancel()
            try:
                await background_task
            except asyncio.CancelledError:
                pass
                background_task = asyncio.create_task(background_intelligence())

            async def background_intelligence():
                nonlocal skip_next_utterance, first_turn, tts_active


        # -------------------------------
        # 1) Get final transcript
        # -------------------------------
        text = clean_transcript(await stt.transcribe_buffer())
        if len(text) < MIN_UTTERANCE_CHARS:
            return

        logger.info(f"[USER] {text}")

        # -------------------------------
        # 2) Greeting-only skip (first turn protection)
        # -------------------------------
        if skip_next_utterance and any(
            w in text.lower() for w in ["hello", "hi", "hey", "हेलो", "हलो", "नमस्ते"]
        ):
            logger.info("[STT] Greeting-only utterance skipped")
            skip_next_utterance = False
            return

        skip_next_utterance = False
        first_turn = False

        # -------------------------------
        # 3) EXIT INTENT (HIGHEST PRIORITY)
        # -------------------------------
        if is_exit_utterance(text):
            logger.info("[CALL] Exit intent detected")

            if _CACHED_FAREWELL:
                tts_active = True
                frame = int(TTS_SR * 2 * 0.30)  # 300 ms frames
                for i in range(0, len(_CACHED_FAREWELL), frame):
                    await out_audio_q.put(_CACHED_FAREWELL[i:i + frame])
                    await asyncio.sleep(0.30)
                tts_active = False

            # await ws.close()
            call_active = False
            return

        # -------------------------------
        # 4) NORMAL RAG + LLM FLOW
        # -------------------------------
        reply = await asyncio.to_thread(
            get_contextual_response, text, _RETRIEVER, "session"
        )

        logger.info(f"[AGENT] {reply}")

        # -------------------------------
        # 5) Speak reply
        # -------------------------------
        tts_active = True
        async for pkt in _TTS.generate_frejun_audio_chunks(reply, chunk_ms=120):
            await out_audio_q.put(base64.b64decode(pkt["audio_b64"]))
        tts_active = False


    # ---------------------------
    # Main receive loop                 
    # ---------------------------
    try:
        # while True:
        while call_active:
            msg = await ws.receive_text()
            data = json.loads(msg)
            if "user_audio_chunk" not in data:
                continue

            if tts_active:
                continue  # HARD GATE — REQUIRED

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

        logger.info("Call ended")

# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_websocket_PROD:app", host="0.0.0.0", port=8001)

