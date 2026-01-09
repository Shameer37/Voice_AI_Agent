# import logging
# import asyncio
# import edge_tts

# class TTS:
#     def __init__(self, voice="en-US-JennyNeural", rate="+0%"):
#         self.voice = voice
#         self.rate = rate
#         self.logger = logging.getLogger("TTS")
#         self.logger.setLevel(logging.INFO)

#     async def synthesize_speech(self, text, output_path="output.wav"):
#         try:
#             self.logger.info(f"Synthesizing speech: {text[:30]}...")
#             communicate = edge_tts.Communicate(text, self.voice)
#             await communicate.save(output_path)
#             self.logger.info(f"Saved synthesized speech to {output_path}")
#         except Exception as e:
#             self.logger.error(f"Error in TTS: {e}")



#---------------------------------------------------------------------------



# import os
# import logging
# # import asyncio
# import edge_tts
# from datetime import datetime

# class TTS:
#     def __init__(self, voice="hi-IN-SwaraNeural", rate="+0%"):
#         self.voice = voice
#         self.rate = rate
#         os.makedirs("recordings", exist_ok=True)
#         self.logger = logging.getLogger("TTS")
#         self.logger.setLevel(logging.INFO)

#     async def synthesize_speech(self, text, session_id="default", output_path=None):
#         try:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             if not output_path:
#                 filename = f"agent_{session_id}_{timestamp}.wav"
#                 output_path = os.path.join("recordings", filename)

#             communicate = edge_tts.Communicate(text, self.voice)
#             await communicate.save(output_path)
#             self.logger.info(f"[TTS] ✅ Saved agent speech to: {output_path}")
#             return output_path
#         except Exception as e:
#             self.logger.error(f"[TTS ❌ ERROR] Failed to synthesize: {e}")
#             return None


#---------------------------------------------------------------------------


# import os
# import logging
# import edge_tts
# from datetime import datetime

# class TTS:
#     def __init__(self, voice="en-IN-NeerjaNeural", rate="+0%"):
#         self.voice = voice
#         self.rate = rate
#         os.makedirs("recordings", exist_ok=True)
#         self.logger = logging.getLogger("TTS")
#         self.logger.setLevel(logging.INFO)

#     async def synthesize_speech(self, text, session_id="default", output_path=None):
#         try:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             if not output_path:
#                 filename = f"agent_{session_id}_{timestamp}.wav"
#                 output_path = os.path.join("recordings", filename)

#             communicate = edge_tts.Communicate(
#                 text=text,
#                 voice=self.voice,
#                 rate=self.rate
#             )
#             await communicate.save(output_path)
#             self.logger.info(f"[TTS] ✅ Saved agent speech to: {output_path}")
#             return output_path
#         except Exception as e:
#             self.logger.error(f"[TTS ❌ ERROR] Failed to synthesize: {e}")
#             return None

#---------------------------------------------------------------------------



#import os
#import edge_tts
#from datetime import datetime

#class TTS:
#    def __init__(self):
#        self.voice = "hi-IN-SwaraNeural"  # Only Hindi

#    async def synthesize_speech(self, text, session_id, language="hi"):
#        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#        os.makedirs("recordings", exist_ok=True)
#        audio_path = f"recordings/agent_{session_id}_{timestamp}.wav"

#        communicate = edge_tts.Communicate(text=text, voice=self.voice)
#        await communicate.save(audio_path)
#        return audio_path


#Updated code
# speech/tts.py
#import os
#import io
#import base64
#import asyncio
#import logging
#from datetime import datetime
#from typing import AsyncGenerator

#import edge_tts
#import numpy as np
#import soundfile as sf
#import librosa
#import wave

#logger = logging.getLogger(__name__)


#class TTS:
#    """
#    Edge TTS streamer tailored for FreJun/Teler.

#    NOTE:
#    - We do NOT pass `output_format` because the installed `edge-tts` version
#      on your machine doesn’t support it.
#    - We stream Edge bytes, decode the container with soundfile, resample to 8k,
#      convert to PCM16 mono, then either:
#        * yield FreJun-ready base64 chunks, or
#        * yield raw PCM16 bytes, or
#        * save a proper 8k WAV for local sanity checks.
#    """

#    def __init__(self, voice: str = "hi-IN-SwaraNeural", rate: str = "+0%", pitch: str = "+0Hz"):
#        self.voice = voice
#        self.rate = rate
#        self.pitch = pitch

    # ──────────────────────────────────────────────────────────────────────────
    # Internal: get full audio payload from Edge (compressed container)
    # ──────────────────────────────────────────────────────────────────────────
#    async def _edge_stream_to_bytes(self, text: str) -> bytes:
#        """
#        Collects the entire Edge stream into a single bytes payload.
#        (Edge returns compressed container frames; we decode after.)
#        """
#        logger.info(f"🎤 Edge TTS streaming (container bytes): {text[:60]}...")
#        comm = edge_tts.Communicate(text=text, voice=self.voice, rate=self.rate, pitch=self.pitch)

#        buf = io.BytesIO()
#        total = 0
#        async for chunk in comm.stream():
#            if chunk["type"] == "audio":
#                buf.write(chunk["data"])
#                total += len(chunk["data"])

#        logger.info(f"✅ Edge delivered {total} bytes of container audio")
#        return buf.getvalue()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal: decode to float32 mono, resample to 8k, convert to int16 PCM
    # ──────────────────────────────────────────────────────────────────────────
#    def _decode_resample_to_pcm16_8k(self, container_bytes: bytes) -> np.ndarray:
#        """
#        Decodes (mp3/wav/etc) → float32 mono → resample to 8k → int16 PCM.
#        Returns a 1-D np.ndarray(dtype=int16).
#        """
#        if not container_bytes:
#            raise RuntimeError("Edge TTS returned no audio data")

#        bio = io.BytesIO(container_bytes)
#        data_f32, sr = sf.read(bio, dtype="float32")  # auto-decodes
#        if data_f32.ndim > 1:
#            data_f32 = data_f32.mean(axis=1)  # mono

#        if sr != 8000:
#            data_f32 = librosa.resample(data_f32, orig_sr=sr, target_sr=8000)

#        data_i16 = np.int16(np.clip(data_f32, -1.0, 1.0) * 32767)
#        logger.info(f"🧰 Decoded+resampled to 8k PCM16: {data_i16.size} samples (~{data_i16.size/8000:.2f}s)")
#        return data_i16

    # ──────────────────────────────────────────────────────────────────────────
    # 1) Raw PCM stream (bytes) @ 8kHz mono 16-bit (simulated streaming)
    # ──────────────────────────────────────────────────────────────────────────
#    async def stream_audio_chunks_8k_pcm(self, text: str) -> AsyncGenerator[bytes, None]:
#        """
#        Yields raw PCM16 8kHz mono bytes. We decode the full TTS first, then
#        stream out in small slices to simulate live streaming.
#        """
#        container = await self._edge_stream_to_bytes(text)
#        pcm_i16 = self._decode_resample_to_pcm16_8k(container)
#        pcm_bytes = pcm_i16.tobytes()

#        chunk_bytes = 4096  # ~256ms at 8kHz (2 bytes/sample)
#        total = 0
#        for i in range(0, len(pcm_bytes), chunk_bytes):
#            chunk = pcm_bytes[i:i + chunk_bytes]
#            if not chunk:
#                continue
#            total += len(chunk)
#            yield chunk
#            await asyncio.sleep(0)  # cooperative yield

#        logger.info(f"✅ Streamed {total} bytes (~{total/(8000*2):.2f}s @8kHz pcm16 mono)")

    # ──────────────────────────────────────────────────────────────────────────
    # 2) FreJun-ready base64 chunks @ 8kHz mono 16-bit
    # ──────────────────────────────────────────────────────────────────────────
#    async def generate_frejun_audio_chunks(self, text: str, chunk_ms: int = 1000):
#        """
#        Yields dicts like:
#         { "type": "audio", "chunk_id": N, "audio_b64": "..." }
#        where audio_b64 is base64(PCM16 mono @ 8kHz). Each chunk ≈ chunk_ms.
#        """
#        logger.info(f"🎧 Generating FreJun chunks @ {chunk_ms} ms")
#        container = await self._edge_stream_to_bytes(text)
#        pcm_i16 = self._decode_resample_to_pcm16_8k(container)

#        bytes_per_ms = 8000 * 2 / 1000.0  # 16 bytes/ms
#        target_bytes = int(bytes_per_ms * chunk_ms)
#        pcm_bytes = pcm_i16.tobytes()

#        chunk_id = 0
#        total_out = 0

#        for start in range(0, len(pcm_bytes), target_bytes):
#            frame = pcm_bytes[start:start + target_bytes]
#            if not frame:
#                continue
#            b64 = base64.b64encode(frame).decode("utf-8")
#            chunk_id += 1
#            total_out += len(frame)
#            logger.info(f"[TTS->FreJun] chunk_id={chunk_id} {len(frame)} bytes (~{len(frame)/(8000*2):.2f}s)")
#            yield {"type": "audio", "chunk_id": chunk_id, "audio_b64": b64}

#        logger.info(f"✅ Completed FreJun chunking: {total_out} bytes total (~{total_out/(8000*2):.2f}s)")

    # ──────────────────────────────────────────────────────────────────────────
    # 3) Save to proper WAV @ 8kHz PCM16 mono (for local sanity checks)
    # ──────────────────────────────────────────────────────────────────────────
#    async def synthesize_to_wav_8k_pcm(self, text: str, session_id: str = "frejun") -> str:
#        """
#        Writes a proper WAV (8kHz/16-bit/mono) for local playback/testing.
#        """
#        os.makedirs("recordings", exist_ok=True)
#        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#        path = f"recordings/agent_{session_id}_{timestamp}.wav"

#        container = await self._edge_stream_to_bytes(text)
#        pcm_i16 = self._decode_resample_to_pcm16_8k(container)
#        raw = pcm_i16.tobytes()

#        with wave.open(path, "wb") as wf:
#            wf.setnchannels(1)
#            wf.setsampwidth(2)  # 16-bit
#            wf.setframerate(8000)
#            wf.writeframes(raw)

#        logger.info(f"✅ Saved WAV (8kHz pcm16 mono): {path} ({len(raw)} bytes)")
#        return path


# ─────────────────────────────────────────────────────────────────────────────
# Optional synchronous helper (if you really need a sync API)
# ─────────────────────────────────────────────────────────────────────────────
#def synthesize_speech(text: str) -> bytes:
#    """
#    Synchronous wrapper that returns 8kHz PCM16 mono bytes for the given text.
#    """
#    async def _run() -> bytes:
#        tts = TTS()
#        container = await tts._edge_stream_to_bytes(text)
#        pcm_i16 = tts._decode_resample_to_pcm16_8k(container)
#        return pcm_i16.tobytes()

#    return asyncio.run(_run())

# speech/tts.py
#import asyncio
#import base64
#import logging
#import contextlib
#from typing import AsyncGenerator, Optional

#import edge_tts  
#import numpy as np
#from collections import OrderedDict
#import hashlib
#import asyncio
#import time


#logger = logging.getLogger(__name__)

#HI_VOICE = "hi-IN-SwaraNeural"
#BYTES_PER_MS_8K_PCM16 = 16  # 8000 samples/sec * 2 bytes = 16000 bytes/sec = 16 bytes/ms


#class TTS:
#    """
#    Edge TTS -> ffmpeg -> raw PCM16 mono @ 8kHz streaming and full-synth APIs.

#    Methods:
#      - warmup() : warm edge_tts pipeline (removes cold start)
#      - generate_frejun_audio_chunks(text, chunk_ms, stop_event) -> async gen of {"type":"audio","audio_b64":...}
#      - synthesize_pcm16_8k(text) -> returns bytes of full PCM16 mono @ 8kHz
#    """

#    def __init__(self, voice: str = HI_VOICE, rate: str = "+0%", pitch: str = "+0Hz"):
#        self.voice = voice
#        self.rate = rate
#        self.pitch = pitch
#        self._warmed = False
#        self._pcm_cache = OrderedDict()
#        self._cache_max_bytes = 8 * 1024 * 1024 
#        self._cache_ttl = 60 * 60 
#        self._cache_current_bytes = 0 
#        self._cache_lock = asyncio.Lock()

        # ---------- cache helpers ----------
#    def _text_to_key(self, text: str) -> str:
#        """Deterministic short key for text."""
#        return hashlib.sha256(text.encode("utf-8")).hexdigest()

#    async def _cache_put(self, key: str, pcm_bytes: bytes):
#        async with self._cache_lock:
#            now = time.time()
#            if key in self._pcm_cache:
#                old_bytes, old_ts, old_size = self._pcm_cache.pop(key)
#                self._cache_current_bytes -= old_size
#            size = len(pcm_bytes)
            # evict until fits
#            while self._cache_current_bytes + size > self._cache_max_bytes and len(self._pcm_cache) > 0:
#                k_old, (b_old, ts_old, s_old) = self._pcm_cache.popitem(last=False)
#                self._cache_current_bytes -= s_old
#            self._pcm_cache[key] = (pcm_bytes, now, size)
#            self._cache_current_bytes += size

#    async def _cache_get(self, key: str):
#        async with self._cache_lock:
#            val = self._pcm_cache.get(key)
#            if not val:
#                return None
#            pcm_bytes, ts, size = val
#            if (time.time() - ts) > self._cache_ttl:
                # expired
#                del self._pcm_cache[key]
#                self._cache_current_bytes -= size
#                return None
            # promote to MRU
#            del self._pcm_cache[key]
#            self._pcm_cache[key] = (pcm_bytes, ts, size)
#            return pcm_bytes

#    async def synthesize_and_cache(self, text: str, *, force: bool = False) -> bytes:
#        """
#        Synthesize full PCM16@8k bytes and cache in-memory.
#        Returns PCM bytes (or None on failure).
#        """
#        key = self._text_to_key(text)
#        if not force:
#            existing = await self._cache_get(key)
#            if existing is not None:
#                return existing
#        try:
#            pcm = await self.synthesize_pcm16_8k(text)
#        except Exception:
#            pcm = None
#        if pcm:
#            await self._cache_put(key, pcm)
#            return pcm
#        return None

#    async def get_cached_pcm(self, text: str):
#        return await self._cache_get(self._text_to_key(text))


#    async def warmup(self) -> None:
#        """Prime Edge once to remove cold-start lag."""
#        if self._warmed:
#            return
#        try:
#            comm = edge_tts.Communicate(text="Hello", voice=self.voice, rate=self.rate, pitch=self.pitch)
#            async for ev in comm.stream():
                # first audio event is enough to warm
#                if ev.get("type") == "audio" and ev.get("data"):
#                    break
#            self._warmed = True
#            logger.info("[TTS] Warmed Edge TTS pipeline.")
#        except Exception as e:
#            logger.warning(f"[TTS] Warmup failed (continuing): {e}")

#    async def _spawn_ffmpeg(self):
#        """
#        Launch ffmpeg to convert incoming audio container bytes -> raw PCM16 (8kHz mono).
#        NOTE: ffmpeg must be installed and in PATH.
#        """
#        return await asyncio.create_subprocess_exec(
#            "ffmpeg",
#            "-hide_banner",
#            "-loglevel", "error",
#            "-i", "pipe:0",
#            "-f", "s16le",
#            "-acodec", "pcm_s16le",
#            "-ac", "1",
#            "-ar", "8000",
#            "pipe:1",
#            stdin=asyncio.subprocess.PIPE,
#            stdout=asyncio.subprocess.PIPE,
#            stderr=asyncio.subprocess.PIPE,
#        )

#    async def generate_frejun_audio_chunks(
#        self,
#        text: str,
#        *,
#        chunk_ms: int = 500,
#        rate: Optional[str] = None,
#        pitch: Optional[str] = None,
#        stop_event: Optional[asyncio.Event] = None,
#        retries: int = 1,
#    ) -> AsyncGenerator[dict, None]:
#        """
#        Stream base64(PCM16/8k/mono) chunks in ~chunk_ms slices.
#        Yields dicts: {"type":"audio", "audio_b64": "..."}.

#        Arguments:
#          stop_event - optional asyncio.Event that, when set, forces generator to stop (barge-in).
#          retries - retry count for the case Edge emits no audio at all.

#        Important: caller should cancel the generator or set stop_event to halt streaming early.
#        """
#        await self.warmup()
#        rate = rate or self.rate
#        pitch = pitch or self.pitch

#        attempt = 0
#        while True:
#            attempt += 1
#            proc = await self._spawn_ffmpeg()
#            comm = edge_tts.Communicate(text=text, voice=self.voice, rate=rate, pitch=pitch)

#            flush_threshold = max(1, chunk_ms) * BYTES_PER_MS_8K_PCM16
#            pcm_buffer = bytearray()
#            stop_writer = asyncio.Event()
#            any_audio_out = False

#            async def _writer():
#                """Feed edge_tts bytes -> ffmpeg stdin."""
#                try:
#                    async for ev in comm.stream():
#                        if stop_event and stop_event.is_set():
#                            break
#                        if ev.get("type") == "audio" and ev.get("data"):
#                            try:
                                # ev["data"] is raw audio bytes from edge container (streamed)
#                                proc.stdin.write(ev["data"])
#                                await proc.stdin.drain()
#                            except Exception as e:
#                                logger.error(f"[TTS] failed writing to ffmpeg stdin: {e}")
#                                break
#                except asyncio.CancelledError:
#                    raise
#                except Exception as e:
#                    logger.error(f"[TTS] writer loop error: {e}")
#                finally:
                    # close stdin so ffmpeg can finish
#                    try:
#                        if proc.stdin and not proc.stdin.is_closing():
#                            proc.stdin.close()
#                    except Exception:
#                        pass
#                    stop_writer.set()

#            async def _reader():
#                """Read converted PCM from ffmpeg stdout and yield b64 chunks."""
#                nonlocal pcm_buffer, any_audio_out
#                try:
#                    while True:
#                        if stop_event and stop_event.is_set():
#                            break
#                        chunk = await proc.stdout.read(8192)
#                        if not chunk:
#                            break
#                        pcm_buffer.extend(chunk)
#                        while len(pcm_buffer) >= flush_threshold:
#                            out = bytes(pcm_buffer[:flush_threshold])
#                            del pcm_buffer[:flush_threshold]
#                            any_audio_out = True
#                            yield {"type": "audio", "audio_b64": base64.b64encode(out).decode("ascii")}
                    # flush tail
#                    if pcm_buffer:
#                        out = bytes(pcm_buffer)
#                        pcm_buffer.clear()
#                        if out:
#                            any_audio_out = True
#                            yield {"type": "audio", "audio_b64": base64.b64encode(out).decode("ascii")}
#                except asyncio.CancelledError:
#                    raise
#                except Exception as e:
#                    logger.error(f"[TTS] reader error: {e}")

#            async def _drain_stderr():
#                """Log ffmpeg stderr lines (useful in dev; can remove in prod)."""
#                try:
#                    while True:
#                        line = await proc.stderr.readline()
#                        if not line:
#                            break
                        # keep this as warning in dev; remove/quiet in production
#                        logger.warning(f"[ffmpeg-stderr] {line.decode('utf-8', 'ignore').strip()}")
#                except asyncio.CancelledError:
#                    raise
#                except Exception:
#                    pass

#            writer_task = asyncio.create_task(_writer())
#            stderr_task = asyncio.create_task(_drain_stderr())

#            try:
                # iterate reader (yields chunks to caller)
#                async for packet in _reader():
#                    yield packet

                # wait for writer to close / finish
#                await stop_writer.wait()

#            except asyncio.CancelledError:
                # propagate cancellation for barge-in
#                raise
#            finally:
                # cleanup tasks and process
#                if writer_task and not writer_task.done():
#                    writer_task.cancel()
#                    with contextlib.suppress(Exception):
#                        await writer_task
#                if stderr_task and not stderr_task.done():
#                    stderr_task.cancel()
#                    with contextlib.suppress(Exception):
#                        await stderr_task

                # ensure ffmpeg terminated
#                with contextlib.suppress(Exception):
#                    if proc.stdin and not proc.stdin.is_closing():
#                        proc.stdin.close()
#                with contextlib.suppress(Exception):
#                    proc.kill()
#                with contextlib.suppress(Exception):
#                    await proc.wait()

#            # Retry if no audio produced by this attempt
#            if not any_audio_out and attempt <= (1 + retries):
#                logger.info(f"[TTS] No audio emitted (attempt {attempt}); retrying...")
#                await asyncio.sleep(0.05)
#                continue

#            break

#    async def synthesize_pcm16_8k(self, text: str, *, timeout: float = 30.0) -> bytes:
#        """
#        One-shot synthesize full PCM16 mono @ 8k and return bytes.

#        This uses the streaming generator internally and accumulates the produced
#        PCM chunks (already PCM16@8k) into a single bytes object.
#        """
#        full = bytearray()
#        stop_event = asyncio.Event()

#        try:
#            async for pkt in self.generate_frejun_audio_chunks(text, chunk_ms=320, stop_event=stop_event, retries=1):
#                b64 = pkt.get("audio_b64")
#                if not b64:
#                    continue
#                try:
#                    full.extend(base64.b64decode(b64))
#                except Exception as e:
#                    logger.warning(f"[TTS] decode error while accumulating synth: {e}")
#        except asyncio.CancelledError:
#            logger.info("[TTS] synth cancelled")
#        except Exception as e:
#            logger.warning(f"[TTS] synth error: {e}")

#        return bytes(full)

# end of file

# speech/tts.py
# speech/tts.py
import asyncio
import base64
import logging
import os
import time
import hashlib
from collections import OrderedDict
from typing import AsyncGenerator, Optional
import contextlib
from dotenv import load_dotenv
load_dotenv()

import httpx

logger = logging.getLogger(__name__)


# ---------- small utility: apply fade in/out to raw PCM16 @ 8k ----------
def apply_fade_pcm16(pcm_bytes: bytes, sr: int = 8000, fade_ms: int = 12) -> bytes:
    """
    Apply short linear fade-in/out to raw PCM16 little-endian bytes.
    Helps remove clicks/edge artifacts on concatenated/cached audio.
    """
    try:
        import numpy as _np
        if not pcm_bytes:
            return pcm_bytes
        arr = _np.frombuffer(pcm_bytes, dtype=_np.int16).astype(_np.float32)
        n_fade = int(sr * fade_ms / 1000)
        if n_fade <= 0 or n_fade * 2 >= arr.size:
            return pcm_bytes
        # linear fade window
        ramp = _np.linspace(0.0, 1.0, n_fade, dtype=_np.float32)
        arr[:n_fade] *= ramp
        arr[-n_fade:] *= ramp[::-1]
        return arr.astype(_np.int16).tobytes()
    except Exception:
        # if numpy or anything fails, return original to avoid breaking synth path
        return pcm_bytes


# Default Hindi-ish voice name provided as example. Change to "sage" or any OpenAI voice you prefer.
DEFAULT_OPENAI_MODEL = "gpt-4o-mini-tts"
DEFAULT_OPENAI_VOICE = "sage"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# 8000 samples/sec * 2 bytes/sample = 16000 bytes/sec -> 16 bytes/ms
BYTES_PER_MS_8K_PCM16 = 16

class TTS:
    """
    OpenAI TTS -> ffmpeg -> raw PCM16 mono @ 8kHz streaming and full-synth APIs.

    Public methods (used by agent_websocket_server):
      - warmup()
      - generate_frejun_audio_chunks(text, chunk_ms, stop_event) -> async gen of {"type":"audio","audio_b64":...}
      - synthesize_pcm16_8k(text) -> returns bytes of full PCM16 mono @ 8kHz
      - synthesize_and_cache(text)
      - get_cached_pcm(text)
    """

    def __init__(
        self,
        openai_model: str = DEFAULT_OPENAI_MODEL,
        openai_voice: str = DEFAULT_OPENAI_VOICE,
        response_format: str = "pcm",  # raw pcm (24kHz 16-bit LE) is fastest per docs
        cache_max_bytes: int = 8 * 1024 * 1024,
        cache_ttl: int = 60 * 60,
    ):
        self.openai_model = openai_model
        self.openai_voice = openai_voice
        self.openai_response_format = response_format
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        self._warmed = False


        # in-memory cache: key -> (bytes, ts, size)
        self._pcm_cache = OrderedDict()
        self._cache_max_bytes = cache_max_bytes
        self._cache_ttl = cache_ttl
        self._cache_current_bytes = 0
        self._cache_lock = asyncio.Lock()

    # ---------------- cache helpers ----------------
    def _text_to_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _cache_put(self, key: str, pcm_bytes: bytes):
        async with self._cache_lock:
            now = time.time()
            if key in self._pcm_cache:
                _, _, old_size = self._pcm_cache.pop(key)
                self._cache_current_bytes -= old_size
            size = len(pcm_bytes)
            # evict until fits
            while self._cache_current_bytes + size > self._cache_max_bytes and len(self._pcm_cache) > 0:
                k_old, (b_old, ts_old, s_old) = self._pcm_cache.popitem(last=False)
                self._cache_current_bytes -= s_old
            self._pcm_cache[key] = (pcm_bytes, now, size)
            self._cache_current_bytes += size

    async def _cache_get(self, key: str):
        async with self._cache_lock:
            val = self._pcm_cache.get(key)
            if not val:
                return None
            pcm_bytes, ts, size = val
            if (time.time() - ts) > self._cache_ttl:
                # expired
                del self._pcm_cache[key]
                self._cache_current_bytes -= size
                return None
            # promote to MRU
            del self._pcm_cache[key]
            self._pcm_cache[key] = (pcm_bytes, ts, size)
            return pcm_bytes

    async def synthesize_and_cache(self, text: str, *, force: bool = False) -> Optional[bytes]:
        key = self._text_to_key(text)
        if not force:
            existing = await self._cache_get(key)
            if existing is not None:
                return existing
        try:
            pcm = await self.synthesize_pcm16_8k(text)
        except Exception as e:
            logger.exception(f"[TTS] synth failed for caching: {e}")
            pcm = None
        if pcm:
            await self._cache_put(key, pcm)
            return pcm
        return None

    async def get_cached_pcm(self, text: str):
        return await self._cache_get(self._text_to_key(text))

    # ---------------- client init ----------------
    async def _init_client(self) -> httpx.AsyncClient:
        """
        Initialize an httpx AsyncClient with OpenAI auth.
        """
        async with self._client_lock:
            if self._client is not None:
                return self._client

            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or os.getenv("OPENAI_TOKEN")
            if not api_key:
                logger.error("[TTS] OPENAI_API_KEY not found in environment")
                raise RuntimeError("OPENAI_API_KEY not found in environment")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "*/*",
                # We expect binary stream back
            }

            # Create httpx.AsyncClient with streaming
            self._client = httpx.AsyncClient(timeout=None, headers=headers)
            logger.info("[TTS] OpenAI Async HTTP client initialized")
            return self._client

    # ---------------- ffmpeg ----------------
    async def _spawn_ffmpeg(self, in_rate: int = 24000, in_format: str = "s16le"):
        """
        Launch ffmpeg to convert raw input -> PCM16 LE 8kHz mono.
        For OpenAI pcm (24kHz s16le) use in_rate=24000 in_format=s16le.
        """
        return await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            # input format (raw PCM)
            "-f",
            in_format,
            "-ar",
            str(in_rate),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            # output format: signed 16-bit little-endian, mono, 8000Hz
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "8000",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    # ---------------- warmup ----------------
    async def warmup(self) -> None:
        """Prime OpenAI TTS once to reduce cold-start latency."""
        if self._warmed:
            return
        try:
            # make a tiny request and discard result; prefer short text
            text = "Hello"
            # Attempt to create the client (will raise if key absent)
            client = await self._init_client()
            # Fire a single non-streaming request (small) to warm service:
            url = "https://api.openai.com/v1/audio/speech"
            payload = {
                "model": self.openai_model,
                "voice": self.openai_voice,
                "input": text,
                "response_format": self.openai_response_format,
            }
            # use a short timeout for the warmup
            r = await client.post(url, json=payload, timeout=30.0)
            if r.status_code == 200:
                logger.info("[TTS] warmed OpenAI pipeline")
            else:
                logger.warning(f"[TTS] warmup returned status {r.status_code}")
            self._warmed = True
        except Exception as e:
            logger.warning(f"[TTS] warmup failed: {e}")

    # ---------------- generator: stream to frejun ----------------
    async def generate_frejun_audio_chunks(
        self,
        text: str,
        *,
        chunk_ms: int = 500,
        stop_event: Optional[asyncio.Event] = None,
        retries: int = 1,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream base64(PCM16/8k/mono) chunks in ~chunk_ms slices.
        Yields dicts: {"type":"audio", "audio_b64": "..."}

        Implementation:
          - Calls OpenAI speech streaming endpoint with response_format=pcm (raw s16le @24k).
          - Pipes bytes into ffmpeg stdin (configured for 24k s16le raw input) and reads ffmpeg stdout
            which is PCM16 s16le @ 8k.
          - Emits base64 slices of the ffmpeg output roughly every chunk_ms.
        """
        await self.warmup()
        client = await self._init_client()
        url = "https://api.openai.com/v1/audio/speech"

        attempt = 0
        while True:
            attempt += 1
            proc = await self._spawn_ffmpeg(in_rate=24000, in_format="s16le")
            any_audio_out = False
            pcm_buffer = bytearray()
            stop_writer = asyncio.Event()

            async def _writer():
                """
                Stream bytes from OpenAI response into ffmpeg stdin.
                We use httpx stream() to stream the binary response body.
                """
                nonlocal any_audio_out
                try:
                    payload = {
                        "model": self.openai_model,
                        "voice": self.openai_voice,
                        "input": text,
                        "response_format": self.openai_response_format,
                    }

                    # Use streaming POST: httpx.stream yields a Response context that we can read bytes from.
                    async with client.stream("POST", url, json=payload, timeout=None) as response:
                        # If the server returned a non-200 or JSON error payload, read and log it and abort writer.
                        if response.status_code != 200:
                            body = await response.aread()
                            logger.error(f"[TTS writer] OpenAI returned status {response.status_code}: {body[:1024]!r}")
                            return

                        # If content-type indicates JSON, read it fully and abort (avoid piping JSON to ffmpeg)
                        ctype = response.headers.get("content-type", "")
                        if "application/json" in ctype.lower():
                            body = await response.aread()
                            logger.error(f"[TTS writer] OpenAI returned JSON content unexpectedly: {body[:1024]!r}")
                            return

                        # Iterate over bytes as they arrive and pipe to ffmpeg stdin
                        async for chunk in response.aiter_bytes():
                            if stop_event and stop_event.is_set():
                                logger.debug("[TTS writer] stop_event set, breaking writer loop")
                                break
                            if not chunk:
                                continue
                            try:
                                # If ffmpeg stdin was closed, this will raise
                                if proc.stdin is None:
                                    logger.error("[TTS writer] ffmpeg stdin is None, aborting writer")
                                    break
                                proc.stdin.write(chunk)
                                # drain to ensure backpressure is honored
                                await proc.stdin.drain()
                            except (BrokenPipeError, ConnectionResetError) as e:
                                logger.error(f"[TTS writer] broken pipe/connection to ffmpeg stdin: {e}")
                                break
                            except Exception as e:
                                logger.exception(f"[TTS writer] failed writing to ffmpeg stdin: {e}")
                                break
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception(f"[TTS writer] OpenAI streaming error: {e}")
                finally:
                    # close stdin so ffmpeg can finish
                    try:
                        if proc.stdin:
                            try:
                                proc.stdin.close()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    stop_writer.set()

            async def _reader():
                """
                Read ffmpeg stdout, buffer and yield base64 chunks when buffer reaches chunk size.
                """
                nonlocal pcm_buffer, any_audio_out
                try:
                    # use at least 200ms buffer to produce stable frames for telephony
                    flush_threshold = max(200, chunk_ms) * BYTES_PER_MS_8K_PCM16
                    while True:
                        if stop_event and stop_event.is_set():
                            break
                        chunk = await proc.stdout.read(8192)
                        if not chunk:
                            break
                        pcm_buffer.extend(chunk)
                        while len(pcm_buffer) >= flush_threshold:
                            out = bytes(pcm_buffer[:flush_threshold])
                            del pcm_buffer[:flush_threshold]
                            any_audio_out = True
                            yield {"type": "audio", "audio_b64": base64.b64encode(out).decode("ascii")}
                    # flush tail
                    if pcm_buffer:
                        out = bytes(pcm_buffer)
                        pcm_buffer.clear()
                        if out:
                            any_audio_out = True
                            yield {"type": "audio", "audio_b64": base64.b64encode(out).decode("ascii")}
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception(f"[TTS reader] error: {e}")

            async def _drain_stderr():
                try:
                    while True:
                        line = await proc.stderr.readline()
                        if not line:
                            break
                        logger.debug(f"[ffmpeg-stderr] {line.decode('utf-8', 'ignore').strip()}")
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

            writer_task = asyncio.create_task(_writer())
            stderr_task = asyncio.create_task(_drain_stderr())

            try:
                # iterate reader and yield to caller
                async for pkt in _reader():
                    yield pkt

                # wait until writer closed (or aborted)
                await stop_writer.wait()
            except asyncio.CancelledError:
                raise
            finally:
                # cleanup tasks and process
                if writer_task and not writer_task.done():
                    writer_task.cancel()
                    with contextlib.suppress(Exception):
                        await writer_task
                if stderr_task and not stderr_task.done():
                    stderr_task.cancel()
                    with contextlib.suppress(Exception):
                        await stderr_task

                # ensure ffmpeg terminated
                with contextlib.suppress(Exception):
                    if proc.stdin:
                        try:
                            proc.stdin.close()
                        except Exception:
                            pass
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await proc.wait()

            # Retry logic if nothing emitted
            if not any_audio_out and attempt <= (1 + retries):
                logger.info(f"[TTS] No audio emitted (attempt {attempt}); retrying...")
                await asyncio.sleep(0.05)
                continue

            break

    # ---------------- one-shot synth ----------------
    async def synthesize_pcm16_8k(self, text: str, *, timeout: float = 30.0) -> bytes:
        """
        Produce a single byte string with full PCM16 mono @ 8k (resampled).
        Internally uses the streaming generator and accumulates bytes.
        """
        full = bytearray()
        stop_event = asyncio.Event()

        try:
            async for pkt in self.generate_frejun_audio_chunks(text, chunk_ms=320, stop_event=stop_event, retries=1):
                b64 = pkt.get("audio_b64")
                if not b64:
                    continue
                try:
                    full.extend(base64.b64decode(b64))
                except Exception as e:
                    logger.warning(f"[TTS] decode error while accumulating synth: {e}")
        except asyncio.CancelledError:
            logger.info("[TTS] synth cancelled")
        except Exception as e:
            logger.exception(f"[TTS] synth error: {e}")

        return bytes(full)









