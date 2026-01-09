# # speech/tts_16khz.py
# import asyncio
# import base64
# import logging
# import os
# import time
# import hashlib
# from collections import OrderedDict
# from typing import AsyncGenerator, Optional
# import contextlib
# from dotenv import load_dotenv
# load_dotenv()

# import httpx

# logger = logging.getLogger(__name__)

# # ---------- small utility: apply fade in/out to raw PCM16 @ 16k ----------
# def apply_fade_pcm16(pcm_bytes: bytes, sr: int = 16000, fade_ms: int = 12) -> bytes:
#     """
#     Apply short linear fade-in/out to raw PCM16 little-endian bytes.
#     Helps remove clicks/edge artifacts on concatenated/cached audio.
#     """
#     try:
#         import numpy as _np
#         if not pcm_bytes:
#             return pcm_bytes
#         arr = _np.frombuffer(pcm_bytes, dtype=_np.int16).astype(_np.float32)
#         n_fade = int(sr * fade_ms / 1000)
#         if n_fade <= 0 or n_fade * 2 >= arr.size:
#             return pcm_bytes
#         ramp = _np.linspace(0.0, 1.0, n_fade, dtype=_np.float32)
#         arr[:n_fade] *= ramp
#         arr[-n_fade:] *= ramp[::-1]
#         return arr.astype(_np.int16).tobytes()
#     except Exception:
#         return pcm_bytes


# DEFAULT_OPENAI_MODEL = "gpt-4o-mini-tts"
# DEFAULT_OPENAI_VOICE = "sage"
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# # 16000 samples/sec * 2 bytes/sample = 32000 bytes/sec -> 32 bytes/ms
# BYTES_PER_MS_16K_PCM16 = 32

# class TTS16k:
#     """
#     OpenAI TTS -> ffmpeg -> raw PCM16 mono @ 16kHz streaming and full-synth APIs.

#     Public methods (used by agent_websocket_server):
#       - warmup()
#       - generate_frejun_audio_chunks(text, chunk_ms, stop_event) -> async gen of {"type":"audio","audio_b64":...}
#       - synthesize_pcm16_16k(text) -> returns bytes of full PCM16 mono @ 16kHz
#       - synthesize_and_cache(text)
#       - get_cached_pcm(text)
#     """

#     def __init__(
#         self,
#         openai_model: str = DEFAULT_OPENAI_MODEL,
#         openai_voice: str = DEFAULT_OPENAI_VOICE,
#         response_format: str = "pcm",  # raw pcm (likely 24000Hz s16le from OpenAI)
#         cache_max_bytes: int = 8 * 1024 * 1024,
#         cache_ttl: int = 60 * 60,
#     ):
#         self.openai_model = openai_model
#         self.openai_voice = openai_voice
#         self.openai_response_format = response_format
#         self._client: Optional[httpx.AsyncClient] = None
#         self._client_lock = asyncio.Lock()
#         self._warmed = False

#         # in-memory cache: key -> (bytes, ts, size)
#         self._pcm_cache = OrderedDict()
#         self._cache_max_bytes = cache_max_bytes
#         self._cache_ttl = cache_ttl
#         self._cache_current_bytes = 0
#         self._cache_lock = asyncio.Lock()

#     # ---------------- cache helpers ----------------
#     def _text_to_key(self, text: str) -> str:
#         return hashlib.sha256(text.encode("utf-8")).hexdigest()

#     async def _cache_put(self, key: str, pcm_bytes: bytes):
#         async with self._cache_lock:
#             now = time.time()
#             if key in self._pcm_cache:
#                 _, _, old_size = self._pcm_cache.pop(key)
#                 self._cache_current_bytes -= old_size
#             size = len(pcm_bytes)
#             while self._cache_current_bytes + size > self._cache_max_bytes and len(self._pcm_cache) > 0:
#                 k_old, (b_old, ts_old, s_old) = self._pcm_cache.popitem(last=False)
#                 self._cache_current_bytes -= s_old
#             self._pcm_cache[key] = (pcm_bytes, now, size)
#             self._cache_current_bytes += size

#     async def _cache_get(self, key: str):
#         async with self._cache_lock:
#             val = self._pcm_cache.get(key)
#             if not val:
#                 return None
#             pcm_bytes, ts, size = val
#             if (time.time() - ts) > self._cache_ttl:
#                 del self._pcm_cache[key]
#                 self._cache_current_bytes -= size
#                 return None
#             del self._pcm_cache[key]
#             self._pcm_cache[key] = (pcm_bytes, ts, size)
#             return pcm_bytes

#     async def synthesize_and_cache(self, text: str, *, force: bool = False) -> Optional[bytes]:
#         key = self._text_to_key(text)
#         if not force:
#             existing = await self._cache_get(key)
#             if existing is not None:
#                 return existing
#         try:
#             pcm = await self.synthesize_pcm16_16k(text)
#         except Exception as e:
#             logger.exception(f"[TTS16k] synth failed for caching: {e}")
#             pcm = None
#         if pcm:
#             # optional fade to make concatenation safe
#             pcm = apply_fade_pcm16(pcm, sr=16000)
#             await self._cache_put(key, pcm)
#             return pcm
#         return None

#     async def get_cached_pcm(self, text: str):
#         return await self._cache_get(self._text_to_key(text))

#     # ---------------- client init ----------------
#     async def _init_client(self) -> httpx.AsyncClient:
#         async with self._client_lock:
#             if self._client is not None:
#                 return self._client

#             api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY") or os.getenv("OPENAI_TOKEN")
#             if not api_key:
#                 logger.error("[TTS16k] OPENAI_API_KEY not found in environment")
#                 raise RuntimeError("OPENAI_API_KEY not found in environment")

#             headers = {
#                 "Authorization": f"Bearer {api_key}",
#                 "Accept": "*/*",
#             }

#             self._client = httpx.AsyncClient(timeout=None, headers=headers)
#             logger.info("[TTS16k] OpenAI Async HTTP client initialized")
#             return self._client

#     # ---------------- ffmpeg (convert input -> pcm_s16le @16k) ----------------
#     async def _spawn_ffmpeg(self, in_rate: int = 24000, in_format: str = "s16le"):
#         """
#         Launch ffmpeg to convert raw input (OpenAI's raw PCM) -> PCM16 LE 16kHz mono.
#         in_rate: sampling rate of incoming bytes from OpenAI (commonly 24000)
#         """
#         return await asyncio.create_subprocess_exec(
#             "ffmpeg",
#             "-hide_banner",
#             "-loglevel", "error",
#             "-f",
#             in_format,
#             "-ar",
#             str(in_rate),
#             "-ac",
#             "1",
#             "-i",
#             "pipe:0",
#             # output: signed 16-bit little-endian, mono, 16000Hz
#             "-f",
#             "s16le",
#             "-acodec",
#             "pcm_s16le",
#             "-ac",
#             "1",
#             "-ar",
#             "16000",
#             "pipe:1",
#             stdin=asyncio.subprocess.PIPE,
#             stdout=asyncio.subprocess.PIPE,
#             stderr=asyncio.subprocess.PIPE,
#         )

#     # ---------------- warmup ----------------
#     async def warmup(self) -> None:
#         if self._warmed:
#             return
#         try:
#             text = "Hello"
#             client = await self._init_client()
#             url = "https://api.openai.com/v1/audio/speech"
#             payload = {
#                 "model": self.openai_model,
#                 "voice": self.openai_voice,
#                 "input": text,
#                 "response_format": self.openai_response_format,
#             }
#             r = await client.post(url, json=payload, timeout=30.0)
#             if r.status_code == 200:
#                 logger.info("[TTS16k] warmed OpenAI pipeline")
#             else:
#                 logger.warning(f"[TTS16k] warmup returned status {r.status_code}")
#             self._warmed = True
#         except Exception as e:
#             logger.warning(f"[TTS16k] warmup failed: {e}")

#     # ---------------- generator: stream to frejun ----------------
#     async def generate_frejun_audio_chunks(
#         self,
#         text: str,
#         *,
#         chunk_ms: int = 500,
#         stop_event: Optional[asyncio.Event] = None,
#         retries: int = 1,
#     ) -> AsyncGenerator[dict, None]:
#         """
#         Stream base64(PCM16/16k/mono) chunks in ~chunk_ms slices.
#         Yields dicts: {"type":"audio", "audio_b64": "..."}

#         Process:
#          - Call OpenAI speech endpoint (response_format=pcm)
#          - Pipe raw bytes into ffmpeg stdin (in_rate default 24000 s16le)
#          - Read ffmpeg stdout (PCM16 s16le @ 16000) and emit base64 frames
#         """
#         await self.warmup()
#         client = await self._init_client()
#         url = "https://api.openai.com/v1/audio/speech"

#         attempt = 0
#         while True:
#             attempt += 1
#             proc = await self._spawn_ffmpeg(in_rate=24000, in_format="s16le")
#             any_audio_out = False
#             pcm_buffer = bytearray()
#             stop_writer = asyncio.Event()

#             async def _writer():
#                 nonlocal any_audio_out
#                 try:
#                     payload = {
#                         "model": self.openai_model,
#                         "voice": self.openai_voice,
#                         "input": text,
#                         "response_format": self.openai_response_format,
#                     }
#                     async with client.stream("POST", url, json=payload, timeout=None) as response:
#                         if response.status_code != 200:
#                             body = await response.aread()
#                             logger.error(f"[TTS16k writer] OpenAI returned status {response.status_code}: {body[:1024]!r}")
#                             return

#                         ctype = response.headers.get("content-type", "")
#                         if "application/json" in ctype.lower():
#                             body = await response.aread()
#                             logger.error(f"[TTS16k writer] OpenAI returned JSON unexpectedly: {body[:1024]!r}")
#                             return

#                         async for chunk in response.aiter_bytes():
#                             if stop_event and stop_event.is_set():
#                                 logger.debug("[TTS16k writer] stop_event set, breaking writer loop")
#                                 break
#                             if not chunk:
#                                 continue
#                             try:
#                                 if proc.stdin is None:
#                                     logger.error("[TTS16k writer] ffmpeg stdin is None, aborting writer")
#                                     break
#                                 proc.stdin.write(chunk)
#                                 await proc.stdin.drain()
#                             except (BrokenPipeError, ConnectionResetError) as e:
#                                 logger.error(f"[TTS16k writer] broken pipe/connection to ffmpeg stdin: {e}")
#                                 break
#                             except Exception as e:
#                                 logger.exception(f"[TTS16k writer] failed writing to ffmpeg stdin: {e}")
#                                 break
#                 except asyncio.CancelledError:
#                     raise
#                 except Exception as e:
#                     logger.exception(f"[TTS16k writer] OpenAI streaming error: {e}")
#                 finally:
#                     try:
#                         if proc.stdin:
#                             try:
#                                 proc.stdin.close()
#                             except Exception:
#                                 pass
#                     except Exception:
#                         pass
#                     stop_writer.set()

#             async def _reader():
#                 nonlocal pcm_buffer, any_audio_out
#                 try:
#                     flush_threshold = max(200, chunk_ms) * BYTES_PER_MS_16K_PCM16
#                     while True:
#                         if stop_event and stop_event.is_set():
#                             break
#                         chunk = await proc.stdout.read(8192)
#                         if not chunk:
#                             break
#                         pcm_buffer.extend(chunk)
#                         while len(pcm_buffer) >= flush_threshold:
#                             out = bytes(pcm_buffer[:flush_threshold])
#                             del pcm_buffer[:flush_threshold]
#                             any_audio_out = True
#                             yield {"type": "audio", "audio_b64": base64.b64encode(out).decode("ascii")}
#                     if pcm_buffer:
#                         out = bytes(pcm_buffer)
#                         pcm_buffer.clear()
#                         if out:
#                             any_audio_out = True
#                             yield {"type": "audio", "audio_b64": base64.b64encode(out).decode("ascii")}
#                 except asyncio.CancelledError:
#                     raise
#                 except Exception as e:
#                     logger.exception(f"[TTS16k reader] error: {e}")

#             async def _drain_stderr():
#                 try:
#                     while True:
#                         line = await proc.stderr.readline()
#                         if not line:
#                             break
#                         logger.debug(f"[ffmpeg-stderr] {line.decode('utf-8', 'ignore').strip()}")
#                 except asyncio.CancelledError:
#                     raise
#                 except Exception:
#                     pass

#             writer_task = asyncio.create_task(_writer())
#             stderr_task = asyncio.create_task(_drain_stderr())

#             try:
#                 async for pkt in _reader():
#                     yield pkt
#                 await stop_writer.wait()
#             except asyncio.CancelledError:
#                 raise
#             finally:
#                 if writer_task and not writer_task.done():
#                     writer_task.cancel()
#                     with contextlib.suppress(Exception):
#                         await writer_task
#                 if stderr_task and not stderr_task.done():
#                     stderr_task.cancel()
#                     with contextlib.suppress(Exception):
#                         await stderr_task
#                 with contextlib.suppress(Exception):
#                     if proc.stdin:
#                         try:
#                             proc.stdin.close()
#                         except Exception:
#                             pass
#                 with contextlib.suppress(Exception):
#                     proc.kill()
#                 with contextlib.suppress(Exception):
#                     await proc.wait()

#             if not any_audio_out and attempt <= (1 + retries):
#                 logger.info(f"[TTS16k] No audio emitted (attempt {attempt}); retrying...")
#                 await asyncio.sleep(0.05)
#                 continue

#             break

#     # ---------------- one-shot synth ----------------
#     async def synthesize_pcm16_16k(self, text: str, *, timeout: float = 30.0) -> bytes:
#         """
#         Produce a single byte string with full PCM16 mono @ 16k (resampled by ffmpeg).
#         Accumulates streaming generator output.
#         """
#         full = bytearray()
#         stop_event = asyncio.Event()
#         try:
#             async for pkt in self.generate_frejun_audio_chunks(text, chunk_ms=320, stop_event=stop_event, retries=1):
#                 b64 = pkt.get("audio_b64")
#                 if not b64:
#                     continue
#                 try:
#                     full.extend(base64.b64decode(b64))
#                 except Exception as e:
#                     logger.warning(f"[TTS16k] decode error while accumulating synth: {e}")
#         except asyncio.CancelledError:
#             logger.info("[TTS16k] synth cancelled")
#         except Exception as e:
#             logger.exception(f"[TTS16k] synth error: {e}")
#         return bytes(full)

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

# ---- fade helper ----
def apply_fade_pcm16(pcm_bytes: bytes, sr: int = 8000, fade_ms: int = 12) -> bytes:
    try:
        import numpy as _np
        if not pcm_bytes:
            return pcm_bytes
        arr = _np.frombuffer(pcm_bytes, dtype=_np.int16).astype(_np.float32)
        n_fade = int(sr * fade_ms / 1000)
        if n_fade <= 0 or n_fade * 2 >= arr.size:
            return pcm_bytes
        ramp = _np.linspace(0.0, 1.0, n_fade, dtype=_np.float32)
        arr[:n_fade] *= ramp
        arr[-n_fade:] *= ramp[::-1]
        return arr.astype(_np.int16).tobytes()
    except Exception:
        return pcm_bytes


DEFAULT_OPENAI_MODEL = "gpt-4o-mini-tts"
DEFAULT_OPENAI_VOICE = "sage"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ---- 8 kHz bytes/ms ----
BYTES_PER_MS_8K_PCM16 = 16     # 8000 Hz * 2 bytes = 16 bytes/ms


class TTS8k:
    """
    TTS class that ALWAYS outputs PCM16 mono @ 8 kHz.
    """

    def __init__(
        self,
        openai_model: str = DEFAULT_OPENAI_MODEL,
        openai_voice: str = DEFAULT_OPENAI_VOICE,
        response_format: str = "pcm",
        cache_max_bytes: int = 8 * 1024 * 1024,
        cache_ttl: int = 3600,
    ):
        self.openai_model = openai_model
        self.openai_voice = openai_voice
        self.openai_response_format = response_format

        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

        self._warmed = False

        self._pcm_cache = OrderedDict()
        self._cache_max_bytes = cache_max_bytes
        self._cache_current_bytes = 0
        self._cache_ttl = cache_ttl
        self._cache_lock = asyncio.Lock()

    # ---------------- cache ----------------
    def _text_to_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _cache_put(self, key: str, pcm: bytes):
        async with self._cache_lock:
            now = time.time()
            if key in self._pcm_cache:
                _, _, old_size = self._pcm_cache.pop(key)
                self._cache_current_bytes -= old_size

            size = len(pcm)
            while self._cache_current_bytes + size > self._cache_max_bytes and self._pcm_cache:
                k_old, (_, _, s_old) = self._pcm_cache.popitem(last=False)
                self._cache_current_bytes -= s_old

            self._pcm_cache[key] = (pcm, now, size)
            self._cache_current_bytes += size

    async def _cache_get(self, key: str):
        async with self._cache_lock:
            val = self._pcm_cache.get(key)
            if not val:
                return None

            pcm, ts, size = val
            if (time.time() - ts) > self._cache_ttl:
                del self._pcm_cache[key]
                self._cache_current_bytes -= size
                return None

            del self._pcm_cache[key]
            self._pcm_cache[key] = (pcm, ts, size)
            return pcm

    async def synthesize_and_cache(self, text: str):
        key = self._text_to_key(text)
        existing = await self._cache_get(key)
        if existing:
            return existing

        pcm = await self.synthesize_pcm16_8k(text)
        if pcm:
            pcm = apply_fade_pcm16(pcm, sr=8000)
            await self._cache_put(key, pcm)
            return pcm
        return None

    async def get_cached_pcm(self, text: str):
        return await self._cache_get(self._text_to_key(text))

    # ---------------- httpx client ----------------
    async def _init_client(self):
        async with self._client_lock:
            if self._client:
                return self._client

            api_key = OPENAI_API_KEY
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY missing")

            self._client = httpx.AsyncClient(timeout=None, headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "*/*",
            })
            return self._client

    # ---------------- ffmpeg converter ----------------
    async def _spawn_ffmpeg(self, in_rate=24000, in_format="s16le"):
        """
        Converts OpenAI 24 kHz PCM into 8 kHz PCM16 mono.
        """
        return await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", in_format,
            "-ar", str(in_rate),
            "-ac", "1",
            "-i", "pipe:0",
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "8000",     # <<< OUTPUT AT 8 KHZ
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    # ---------------- warmup ----------------
    async def warmup(self):
        if self._warmed:
            return
        try:
            client = await self._init_client()
            url = "https://api.openai.com/v1/audio/speech"
            payload = {
                "model": self.openai_model,
                "voice": self.openai_voice,
                "input": "Hello",
                "response_format": self.openai_response_format,
                "speed": 0.9,
            }
            await client.post(url, json=payload)
            self._warmed = True
        except Exception as e:
            logger.warning(f"[TTS8k] warmup failed: {e}")

    # ---------------- streaming generator (8 kHz) ----------------
    async def generate_frejun_audio_chunks(
        self,
        text: str,
        *,
        chunk_ms: int = 500,
        stop_event: Optional[asyncio.Event] = None,
    ) -> AsyncGenerator[dict, None]:

        await self.warmup()
        client = await self._init_client()

        url = "https://api.openai.com/v1/audio/speech"
        proc = await self._spawn_ffmpeg()

        pcm_buffer = bytearray()
        flush_threshold = max(200, chunk_ms) * BYTES_PER_MS_8K_PCM16

        # ---------- internal writer ----------
        async def _writer():
            try:
                payload = {
                    "model": self.openai_model,
                    "voice": self.openai_voice,
                    "input": text,
                    "response_format": self.openai_response_format,
                    "speed" : 0.9,
                }
                async with client.stream("POST", url, json=payload) as resp:
                    async for chunk in resp.aiter_bytes():
                        if stop_event and stop_event.is_set():
                            break
                        if proc.stdin:
                            proc.stdin.write(chunk)
                            await proc.stdin.drain()
            except Exception as e:
                logger.error(f"[TTS8k writer] {e}")
            finally:
                if proc.stdin:
                    try: proc.stdin.close()
                    except: pass

        # ---------- internal reader ----------
        async def _reader():
            nonlocal pcm_buffer
            try:
                while True:
                    chunk = await proc.stdout.read(4096)
                    if not chunk:
                        break
                    pcm_buffer.extend(chunk)

                    while len(pcm_buffer) >= flush_threshold:
                        out = bytes(pcm_buffer[:flush_threshold])
                        del pcm_buffer[:flush_threshold]
                        yield {"type": "audio", "audio_b64": base64.b64encode(out).decode()}
                if pcm_buffer:
                    out = bytes(pcm_buffer)
                    pcm_buffer.clear()
                    yield {"type": "audio", "audio_b64": base64.b64encode(out).decode()}
            except Exception as e:
                logger.error(f"[TTS8k reader] {e}")

        writer_task = asyncio.create_task(_writer())

        try:
            async for pkt in _reader():
                yield pkt
        finally:
            if not writer_task.done():
                writer_task.cancel()
                with contextlib.suppress(Exception):
                    await writer_task
            try:
                proc.kill()
            except:
                pass

    # ---------------- single-shot synth ----------------
    async def synthesize_pcm16_8k(self, text: str) -> bytes:
        full = bytearray()
        async for pkt in self.generate_frejun_audio_chunks(text, chunk_ms=300):
            b64 = pkt.get("audio_b64")
            if b64:
                full.extend(base64.b64decode(b64))
        return bytes(full)



