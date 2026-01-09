# import os
# import wave
# import pyaudio
# import tempfile
# from faster_whisper import WhisperModel

# class STT:
#     def __init__(self, model_size="base", device_index=21, samplerate=16000):
#         self.device_index = device_index
#         self.samplerate = samplerate
#         self.channels = 1
#         self.chunk = 1024
#         self.format = pyaudio.paInt16
#         self.model = WhisperModel(model_size, compute_type="auto")

#     def listen_and_transcribe(self, max_seconds=10):
#         print(f"[STT] 🎙️ Listening on device {self.device_index} for up to {max_seconds} seconds...")

#         # Create temp WAV file
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
#             filename = tmpfile.name

#         p = pyaudio.PyAudio()
#         try:
#             stream = p.open(format=self.format,
#                             channels=self.channels,
#                             rate=self.samplerate,
#                             input=True,
#                             input_device_index=self.device_index,
#                             frames_per_buffer=self.chunk)
#         except Exception as e:
#             print(f"[STT ERROR] ❌ Could not open input device: {e}")
#             return None

#         frames = []
#         try:
#             for _ in range(0, int(self.samplerate / self.chunk * max_seconds)):
#                 data = stream.read(self.chunk, exception_on_overflow=False)
#                 frames.append(data)
#         except Exception as e:
#             print(f"[STT ERROR] ❌ Recording failed: {e}")
#             return None
#         finally:
#             stream.stop_stream()
#             stream.close()
#             p.terminate()

#         # Save audio to WAV
#         with wave.open(filename, 'wb') as wf:
#             wf.setnchannels(self.channels)
#             wf.setsampwidth(p.get_sample_size(self.format))
#             wf.setframerate(self.samplerate)
#             wf.writeframes(b''.join(frames))

#         print(f"[STT] ✅ Audio recorded to temp file: {filename}")

#         # Transcribe using Whisper
#         try:
#             segments, _ = self.model.transcribe(filename)
#             result_text = " ".join(segment.text for segment in segments).strip()
#             print(f"[STT] 📝 Transcription: {result_text}")
#             return result_text if result_text else None
#         except Exception as e:
#             print(f"[STT ERROR] ❌ Transcription failed: {e}")
#             return None
#         finally:
#             os.remove(filename)  # Clean up


#---------------------------------------------------------------




# from faster_whisper import WhisperModel
# import sounddevice as sd
# import soundfile as sf
# from datetime import datetime
# import os

# class STT:
#     def __init__(self):
#         self.model = WhisperModel("base", device="cpu", compute_type="int8")

#     def listen_and_transcribe(self, session_id=None, duration=7):
#         print("🎤 Listening... Speak now.")
#         samplerate = 16000
#         recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1)
#         sd.wait()

#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         audio_file = f"recordings/user_{session_id}_{timestamp}.wav"
#         sf.write(audio_file, recording, samplerate)
#         print(f"[STT] 🎧 Saved mic input to: {audio_file}")

#         segments, _ = self.model.transcribe(audio_file)
#         text = "".join(segment.text for segment in segments)
#         return text.strip() if text else None


#-----------------------------------------------------------------------------



# from faster_whisper import WhisperModel
# import sounddevice as sd
# import soundfile as sf
# from datetime import datetime
# import os

# class STT:
#     def __init__(self):
#         self.model = WhisperModel("large-v2", device="cpu", compute_type="int8")
#         self.device_id = 1  
#         self.samplerate = 16000
#         self.channels = 1
#         self.duration = 7  

#     def listen_and_transcribe(self, session_id=None):
#         print("🎤 Listening... Speak now.")

#         # Record audio
#         recording = sd.rec(
#             int(self.duration * self.samplerate),
#             samplerate=self.samplerate,
#             channels=self.channels,
#             dtype='int16',
#             device=self.device_id
#         )
#         sd.wait()

#         # Save recording
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         audio_file = f"recordings/user_{session_id}_{timestamp}.wav"
#         sf.write(audio_file, recording, self.samplerate)
#         print(f"[STT] 🎧 Saved mic input to: {audio_file}")

#         # Transcribe using Whisper
#         segments, _ = self.model.transcribe(audio_file, language="hi")
#         text = "".join(segment.text for segment in segments)
#         return text.strip() if text else None

#-----------------------------------
#Previous code with soundfile and sounddevice usage . Audio files are first saved and then processed. No audio streaming

#from faster_whisper import WhisperModel
#import os
#from datetime import datetime

#class STT:
#    def __init__(self):
#        self.env = os.getenv("ENV", "local")
#        self.model = WhisperModel("large-v2", device="cpu", compute_type="int8")
#        self.device_id = 15 #1
#        self.samplerate = 48000   #16000
#        self.channels = 1
#        self.duration = 7

        # Only import sounddevice/soundfile if not on cloud
#        if self.env != "cloud":
#            import sounddevice as sd
#            import soundfile as sf
#            self.sd = sd
#            self.sf = sf 
#        else:
#            self.sd = None
#            self.sf = None

#    def listen_and_transcribe(self, session_id=None):
#        if self.env == "cloud":
#            print("[STT] ❌ Audio recording not supported in cloud.")
#            return "Audio recording not available in cloud environment."

#        print("🎤 Listening... Speak now.")

        # Record audio
#        recording = self.sd.rec(
#            int(self.duration * self.samplerate),
#            samplerate=self.samplerate,
#            channels=self.channels,
#            dtype='int16',
#            device=self.device_id
#        )
#        self.sd.wait()

        # Save audio
#        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#        audio_file = f"recordings/user_{session_id}_{timestamp}.wav"
#        self.sf.write(audio_file, recording, self.samplerate)
#        print(f"[STT] 🎧 Saved mic input to: {audio_file}")

        # Transcribe
#        segments, _ = self.model.transcribe(audio_file, language="hi")
#        text = "".join(segment.text for segment in segments)
#        return text.strip() if text else None

#Streaming Voice to STT 
# speech/stt.py
"""
High-accuracy STT for telephony audio (PCM16, 8 kHz → 16 kHz).
Optimized for Hindi customer-care conversations.

Key points:
- Input from Frejun/Teler: 8 kHz, mono, PCM16 bytes.
- We preprocess (DC removal, pre-emphasis, normalization), resample → 16 kHz.
- VAD-driven buffering with silence-based flush.
- Forced Hindi decoding (no language auto-detect).
- Aggressive cleaning to reduce hallucinations / noise-only transcripts.
"""

import numpy as np
import webrtcvad
import logging
import re
import unicodedata
from collections import deque
from typing import Dict, Any, Tuple

from faster_whisper import WhisperModel
import librosa

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ============================================================
# UTILITIES
# ============================================================

def rms_energy_i16(i16: np.ndarray) -> float:
    if i16.size == 0:
        return 0.0
    x = i16.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(x * x)) + 1e-12)


_re_any_letter = re.compile(r"[A-Za-z0-9\u0900-\u097F]")


def smart_clean_transcript(raw: str) -> str:
    """
    Very aggressive hallucination removal + Hindi normalization.
    """
    if not raw:
        return ""

    txt = unicodedata.normalize("NFC", raw)
    txt = txt.replace("\u200c", "").replace("\u200d", "")  # zero-width

    # collapse whitespace
    txt = re.sub(r"\s+", " ", txt).strip()

    # remove repeated punctuation
    txt = re.sub(r"(\.\s*){2,}", ".", txt)

    # remove repeated characters (e.g., AAAA → AAA)
    txt = re.sub(r"(.)\1{3,}", r"\1\1\1", txt)

    # remove repeating words
    words = txt.split(" ")
    result = []
    prev = None
    for w in words:
        if w != prev:
            result.append(w)
        prev = w
    txt = " ".join(result)

    # trim leading/trailing punctuation
    txt = txt.strip(".,;:!?\u0964\u0965-–—[](){}\"'|/")

    # if Whisper hallucinated junk with no letters/digits/Devanagari, fall back
    if not _re_any_letter.search(txt):
        txt2 = re.sub(r"\s+", " ", raw).strip()
        return txt2[:200] if txt2 else ""

    return txt


# ============================================================
# FASTER-WHISPER DECODER CONFIG
# ============================================================

DECODER_KW: Dict[str, Any] = dict(
    temperature=0.0,
    beam_size=5,
    best_of=1,
    compression_ratio_threshold=2.6,
    log_prob_threshold=-1.2,
    no_speech_threshold=0.35,
    condition_on_previous_text=False,
    vad_filter=False,
)


# ============================================================
# MAIN CLASS
# ============================================================

class STT:
    """
    Local Whisper STT optimized for:
        - Telephony PCM16 audio (8 kHz)
        - Resample → 16 kHz for Whisper
        - Hindi ("hi") by default (no language auto-detect)
        - Stable VAD + silence flush logic
    """

    def __init__(
        self,
        model_size: str = "large-v2",
        device: str = "cuda",
        compute_type: str = "float16",
        samplerate: int = 16000,
        vad_mode: int = 2,
        frame_ms: int = 20,
        silence_seconds: float = 0.85,
        min_speech_seconds: float = 0.22,
        buffer_duration: float = 8.0,
        min_chars: int = 2,
        min_rms_before_asr: float = 0.0006,
        default_language: str = "hi",
    ):
        # Whisper model (faster-whisper)
        self.model = WhisperModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type,
        )

        self.transcript = []

        # Sampling (internal)
        self.samplerate = samplerate
        if self.samplerate != 16000:
            raise ValueError("Whisper STT requires 16 kHz input for this pipeline.")

        # VAD config
        if frame_ms not in (10, 20, 30):
            raise ValueError("frame_ms must be 10/20/30 ms")
        self.frame_ms = frame_ms
        self.frame_samples = int(self.samplerate * self.frame_ms / 1000)
        self.frame_bytes = self.frame_samples * 2
        self.vad = webrtcvad.Vad(vad_mode)

        # Buffers
        self.buffer_duration = buffer_duration
        self.max_samples = int(buffer_duration * samplerate)
        self.audio_buffer = deque(maxlen=self.max_samples)  # int16 samples
        self._vad_remainder = bytearray()

        # Silence detection
        self.silence_seconds = silence_seconds
        self.silence_frames_threshold = int(silence_seconds * 1000 / frame_ms)
        self.min_speech_frames = int(min_speech_seconds * 1000 / frame_ms)

        # STT thresholds
        self.min_chars = min_chars
        # Slightly higher min RMS than absolute noise floor for telephony
        self.min_rms_before_asr = max(min_rms_before_asr, 0.0007)
        self.default_language = default_language or "hi"

        # States
        self.speech_detected = False
        self.silence_frames = 0
        self.speech_frames_observed = 0

    # --------------------------------------------------------------
    # AUDIO INGESTION (8 kHz PCM16 → 16 kHz PCM16 with preprocessing)
    # --------------------------------------------------------------
    def add_pcm16_8k(self, raw8k: bytes):
        """
        Takes 8 kHz PCM16 audio, does telephony-oriented preprocessing and
        resamples → 16k, then feeds to add_chunk().
        """
        if not raw8k:
            return

        try:
            x = np.frombuffer(raw8k, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            return

        if x.size == 0:
            return

        # 1) Remove DC offset
        dc = float(np.mean(x))
        if abs(dc) > 1e-4:
            x = x - dc

        # 2) Pre-emphasis (boosts consonants/high-freq speech cues)
        try:
            x = librosa.effects.preemphasis(x, coef=0.97)
        except Exception:
            # if librosa.effects missing, skip
            pass

        # 3) Normalize level (avoid too quiet/too loud)
        peak = float(np.max(np.abs(x)) + 1e-7)
        target_peak = 0.9
        if peak > 0:
            x = np.clip(x * (target_peak / peak), -1.0, 1.0)

        # 4) Resample 8k → 16k
        try:
            resampled = librosa.resample(x, orig_sr=8000, target_sr=16000)
        except Exception:
            # very dumb fallback: repeat samples
            resampled = np.repeat(x, 2)

        resampled = np.clip(resampled, -1.0, 1.0)
        i16 = np.int16(resampled * 32767.0)
        self.add_chunk(i16.tobytes())

    def add_chunk(self, audio_chunk: bytes):
        """
        Accepts 16 kHz PCM16 bytes (post-resample) and updates:
          - audio_buffer (for later transcription)
          - VAD state (speech/silence frames)
        """
        if not audio_chunk:
            return

        try:
            arr_i16 = np.frombuffer(audio_chunk, dtype=np.int16)
        except Exception:
            return

        if arr_i16.size == 0:
            return

        # store raw samples
        self.audio_buffer.extend(arr_i16.tolist())

        # VAD processing (on 16k frames)
        self._vad_remainder.extend(audio_chunk)
        processed = 0

        while len(self._vad_remainder) - processed >= self.frame_bytes:
            frame = self._vad_remainder[processed:processed + self.frame_bytes]

            try:
                speech = self.vad.is_speech(bytes(frame), sample_rate=self.samplerate)
            except Exception:
                break

            if speech:
                self.speech_detected = True
                self.silence_frames = 0
                self.speech_frames_observed += 1
            else:
                if self.speech_detected:
                    self.silence_frames += 1

            processed += self.frame_bytes

        if processed:
            del self._vad_remainder[:processed]

    # --------------------------------------------------------------
    # DECISION: Should flush?
    # --------------------------------------------------------------
    def should_flush_on_silence(self) -> bool:
        """
        Returns True when:
          - We've seen enough speech frames.
          - And then enough silence frames after that.
        """
        if not self.speech_detected:
            return False
        if self.speech_frames_observed < self.min_speech_frames:
            return False
        return self.silence_frames >= self.silence_frames_threshold

    # --------------------------------------------------------------
    # TRANSCRIPTION
    # --------------------------------------------------------------
    def _buffer_to_float32(self) -> Tuple[np.ndarray, np.ndarray]:
        if not self.audio_buffer:
            return np.empty(0, dtype=np.int16), np.empty(0, dtype=np.float32)
        i16 = np.asarray(self.audio_buffer, dtype=np.int16)
        f32 = i16.astype(np.float32) / 32768.0
        return i16, f32

    def transcribe_buffer(self, lang_hint: str = "hi") -> str:
        """
        Run Whisper on the current audio_buffer and return cleaned text.
        Always forces Hindi (or default_language) for robustness in calls.
        """
        sample_count = len(self.audio_buffer)
        logger.info(f"[STT] buffer size = {sample_count} samples")

        # Require at least ~1 second of audio
        if sample_count < self.samplerate:
            return ""

        i16, f32 = self._buffer_to_float32()

        # Check energy
        rms = rms_energy_i16(i16)
        logger.info(f"[STT] RMS={rms:.6f}")
        if rms < self.min_rms_before_asr:
            logger.info(f"[STT] too quiet, skipping ASR (RMS={rms:.6f})")
            self._reset_after_flush()
            return ""

        # If audio is clipped/too loud, lightly normalize
        if rms > 0.2:
            scale = 0.15 / rms
            f32 = np.clip(f32 * scale, -1.0, 1.0)

        # Decide language: forced Hindi by default
        lang = self.default_language or lang_hint or "hi"

        try:
            segments, _info = self.model.transcribe(
                f32,
                language=lang,
                task="transcribe",
                **DECODER_KW,
            )

            raw_text = "".join(seg.text for seg in segments).strip()
            clean = smart_clean_transcript(raw_text)

            logger.info(f"[STT] RAW:   {raw_text}")
            logger.info(f"[STT] CLEAN: {clean}")

            # 🔴 NEW: hard filter junk / echo-like tiny utterances
            tokens = clean.split()
            unique_tokens = set(tokens)

            # Drop stuff like "अपर �", "नेर", "अगर अपर �", etc.
            if len(tokens) <= 2 or len(unique_tokens) <= 2:
                logger.info(f"[STT] dropping tiny/echo utterance: '{clean}'")
                self._reset_after_flush()
                return ""

            self._reset_after_flush()

            if clean and len(clean) >= self.min_chars:
                self.transcript.append(clean)
                return clean

            return ""

        except Exception as e:
            logger.exception(f"[STT] transcription failed: {e}")
            self._reset_after_flush()
            return ""


    # --------------------------------------------------------------
    # RESET
    # --------------------------------------------------------------
    def _reset_after_flush(self):
        """
        Reset internal audio/VAD state but keep accumulated transcript list.
        """
        self.audio_buffer.clear()
        self._vad_remainder.clear()
        self.speech_detected = False
        self.silence_frames = 0
        self.speech_frames_observed = 0

    def reset_transcript(self):
        """
        Clear conversation transcript and reset buffers (used after TTS playback).
        """
        self.transcript = []
        self._reset_after_flush()

    def get_full_transcript(self) -> str:
        return " ".join(self.transcript).strip()









