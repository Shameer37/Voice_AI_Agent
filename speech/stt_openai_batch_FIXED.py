# speech/stt_openai_batch_FIXED.py
# ============================================================================
# PRODUCTION STT MODULE WITH VAD & NOISE FILTERING
# Tuned for Frejun Telephony (16kHz input)
# ============================================================================

import asyncio
import io
import wave
import logging
import struct
import math
from typing import Tuple
from openai import OpenAI
from dotenv import load_dotenv
import os
import re

load_dotenv()

logger = logging.getLogger("stt")

# ============================================================================
# CONFIGURATION - TUNED FOR FREJUN TELEPHONY
# ============================================================================

# Energy threshold (RMS) - audio below this is considered silence
# Frejun telephony has higher noise floor than typical systems
RMS_SILENCE_THRESHOLD = 300

# Minimum percentage of frames that must have speech
MIN_SPEECH_RATIO = 0.15

# Minimum audio duration (seconds) to attempt transcription
MIN_AUDIO_DURATION_SEC = 0.5

# Common noise transcriptions to filter out
NOISE_TRANSCRIPTIONS = {
    # Empty/whitespace
    "", " ", "  ", "   ",
    # English noise artifacts
    ".", "..", "...", "uh", "um", "hmm", "hm", "ah", "eh", "oh",
    "bye.", "okay.", "ok.", "yes.", "no.",
    # Hindi noise artifacts  
    "ह", "अ", "उ", "ओ", "हम्म", "हूं", "हूँ",
    "आ", "ई", "ऊ", "ए", "ऐ", "औ",
    "।", "।।", "॥",
    "अच्छा", "ठीक", "हंहं",
    # Single characters
    "a", "i", "e", "o", "u", "m", "n", "s", "h",
    # Background detection
    "[music]", "[music playing]", "[background noise]", "[silence]",
    "(music)", "(silence)", "music", "silence",
    # Common short words that appear as noise
    "the", "a", "an", "is", "it", "to", "and",
    "hello", "hi", "हैलो", "हेलो",
    "क्या", "क्यों", "क्योंकि", "क्योंकि।",
}

MAX_NOISE_LENGTH = 20


# ============================================================================
# AUDIO ANALYSIS FUNCTIONS
# ============================================================================

def calculate_rms(pcm_data: bytes) -> float:
    """Calculate Root Mean Square (RMS) energy of PCM16 audio."""
    if len(pcm_data) < 2:
        return 0.0
    
    num_samples = len(pcm_data) // 2
    try:
        samples = struct.unpack(f"<{num_samples}h", pcm_data)
        if not samples:
            return 0.0
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / num_samples)
    except Exception as e:
        logger.error(f"[STT] RMS calculation error: {e}")
        return 0.0


def analyze_audio_energy(pcm_data: bytes, frame_size_ms: int = 20, sample_rate: int = 16000) -> dict:
    """Analyze audio energy frame by frame."""
    if len(pcm_data) < 2:
        return {"speech_ratio": 0.0, "avg_rms": 0.0, "peak_rms": 0.0, "frames": 0}
    
    frame_size_bytes = int(sample_rate * 2 * frame_size_ms / 1000)
    
    frames_with_speech = 0
    total_frames = 0
    rms_values = []
    
    for i in range(0, len(pcm_data) - frame_size_bytes, frame_size_bytes):
        frame = pcm_data[i:i + frame_size_bytes]
        rms = calculate_rms(frame)
        rms_values.append(rms)
        total_frames += 1
        
        if rms > RMS_SILENCE_THRESHOLD:
            frames_with_speech += 1
    
    speech_ratio = frames_with_speech / total_frames if total_frames > 0 else 0.0
    avg_rms = sum(rms_values) / len(rms_values) if rms_values else 0.0
    peak_rms = max(rms_values) if rms_values else 0.0
    
    return {
        "speech_ratio": speech_ratio,
        "avg_rms": avg_rms,
        "peak_rms": peak_rms,
        "frames": total_frames,
        "frames_with_speech": frames_with_speech
    }

# def is_supported_language(text: str) -> bool:
#     #Previous behavior (kept for reference):
#     # Hindi (Devanagari) OR English letters
#     return bool(
#         re.search(r"[\u0900-\u097F]", text)  # Hindi
#         or re.search(r"[A-Za-z]", text)      # English
#     )
def is_supported_language(text: str) -> bool:
    # Must contain Hindi OR English
    if not re.search(r"[\u0900-\u097F]|[A-Za-z]", text):
        return False

    # HARD reject Arabic / Urdu
    if re.search(r"[\u0600-\u06FF]", text):
        return False

    return True


def trim_silence(pcm_data: bytes, sample_rate: int = 16000, threshold: float = None) -> bytes:
    """Trim leading and trailing silence from audio."""
    if len(pcm_data) < 100:
        return pcm_data
    
    if threshold is None:
        threshold = RMS_SILENCE_THRESHOLD
    
    frame_size = int(sample_rate * 2 * 0.02)  # 20ms frames
    
    # Find start of speech
    start_idx = 0
    for i in range(0, len(pcm_data) - frame_size, frame_size):
        frame = pcm_data[i:i + frame_size]
        if calculate_rms(frame) > threshold:
            start_idx = max(0, i - frame_size)
            break
    
    # Find end of speech
    end_idx = len(pcm_data)
    for i in range(len(pcm_data) - frame_size, frame_size, -frame_size):
        frame = pcm_data[i:i + frame_size]
        if calculate_rms(frame) > threshold:
            end_idx = min(len(pcm_data), i + frame_size * 2)
            break
    
    if start_idx >= end_idx:
        return b''
    
    return pcm_data[start_idx:end_idx]


def is_noise_transcription(text: str) -> bool:
    """Check if transcription is likely noise rather than real speech."""
    if not text:
        return True
    
    cleaned = text.strip().lower()
    
    if cleaned in NOISE_TRANSCRIPTIONS:
        return True
    
    if len(cleaned) <= 2:
        return True
    
    if len(set(cleaned.replace(" ", ""))) <= 2 and len(cleaned) < MAX_NOISE_LENGTH:
        return True
    
    if all(c in '.,!?;:\'"()-[]{}।॥' for c in cleaned):
        return True
    
    return False


# ============================================================================
# SIMPLE VAD (Voice Activity Detection)
# ============================================================================

class SimpleVAD:
    """Energy-based Voice Activity Detection."""
    
    def __init__(self, sample_rate: int = 16000, energy_threshold: float = None):
        self.sample_rate = sample_rate
        self.frame_duration_ms = 20
        self.frame_size = int(sample_rate * 2 * self.frame_duration_ms / 1000)
        self.energy_threshold = energy_threshold or RMS_SILENCE_THRESHOLD
        
    def process_audio(self, pcm_data: bytes) -> Tuple[bool, float]:
        """Process audio and determine if it contains speech."""
        if len(pcm_data) < self.frame_size:
            return False, 0.0
        
        speech_frames = 0
        total_frames = 0
        
        for i in range(0, len(pcm_data) - self.frame_size, self.frame_size):
            frame = pcm_data[i:i + self.frame_size]
            total_frames += 1
            if calculate_rms(frame) > self.energy_threshold:
                speech_frames += 1
        
        if total_frames == 0:
            return False, 0.0
        
        speech_ratio = speech_frames / total_frames
        has_speech = speech_ratio >= MIN_SPEECH_RATIO
        
        return has_speech, speech_ratio


# ============================================================================
# WEBRTC VAD (Optional - More Accurate)
# ============================================================================

class WebRTCVAD:
    """WebRTC-based VAD. Requires: pip install webrtcvad"""
    
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        self.sample_rate = sample_rate
        self.vad = None
        self.frame_duration_ms = 20
        self.frame_size = int(sample_rate * 2 * self.frame_duration_ms / 1000)
        
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
            logger.info("[STT] WebRTC VAD initialized")
        except ImportError:
            logger.info("[STT] webrtcvad not installed, using SimpleVAD")
    
    @property
    def is_available(self) -> bool:
        return self.vad is not None
    
    def process_audio(self, pcm_data: bytes) -> Tuple[bool, float]:
        if not self.vad:
            return True, 1.0
        
        speech_frames = 0
        total_frames = 0
        
        for i in range(0, len(pcm_data) - self.frame_size, self.frame_size):
            frame = pcm_data[i:i + self.frame_size]
            total_frames += 1
            try:
                if self.vad.is_speech(frame, self.sample_rate):
                    speech_frames += 1
            except Exception:
                pass
        
        if total_frames == 0:
            return False, 0.0
        
        speech_ratio = speech_frames / total_frames
        has_speech = speech_ratio >= MIN_SPEECH_RATIO
        
        return has_speech, speech_ratio


# ============================================================================
# MAIN STT CLASS
# ============================================================================

class OpenAIBatchSTT:
    """OpenAI Batch STT with VAD and noise filtering."""
    
    def __init__(
        self,
        samplerate: int = 16000,
        model: str = "gpt-4o-mini-transcribe",
        language: str = "hi",
        use_webrtc_vad: bool = True,
        energy_threshold: float = None
    ):
        self.sr = samplerate
        self.model = model
        self.language = language
        self._buffer = bytearray()
        self.client = OpenAI()
        
        self.energy_threshold = energy_threshold or RMS_SILENCE_THRESHOLD
        
        # Initialize VAD
        if use_webrtc_vad:
            self.vad = WebRTCVAD(sample_rate=samplerate)
            if not self.vad.is_available:
                self.vad = SimpleVAD(sample_rate=samplerate, energy_threshold=self.energy_threshold)
        else:
            self.vad = SimpleVAD(sample_rate=samplerate, energy_threshold=self.energy_threshold)
        
        # Statistics
        self.stats = {
            "chunks_received": 0,
            "chunks_rejected_silent": 0,
            "transcriptions_filtered": 0,
            "successful_transcriptions": 0
        }
        
        logger.info(
            f"[STT] Initialized: sr={samplerate}, model={model}, "
            f"energy_threshold={self.energy_threshold}"
        )

    def check_audio_energy(self, pcm_data: bytes) -> Tuple[bool, dict]:
        """Check if audio has sufficient energy."""
        if len(pcm_data) < 100:
            return False, {"rms": 0, "reason": "too_short"}
        
        rms = calculate_rms(pcm_data)
        has_energy = rms > self.energy_threshold
        
        return has_energy, {"rms": round(rms, 2), "threshold": self.energy_threshold, "has_energy": has_energy}

    def add_chunk(self, pcm16: bytes) -> bool:
        """Add audio chunk to buffer with energy filtering."""
        self.stats["chunks_received"] += 1
        
        if len(pcm16) == 0 or len(pcm16) % 2 != 0:
            logger.error(f"[STT] Invalid PCM16 chunk: {len(pcm16)} bytes")
            return False
        
        has_energy, energy_stats = self.check_audio_energy(pcm16)
        
        if not has_energy:
            self.stats["chunks_rejected_silent"] += 1
            logger.info(
                f"[STT] Rejected silent chunk: RMS={energy_stats['rms']:.1f} "
                f"< threshold={self.energy_threshold}"
            )
            return False
        
        self._buffer.extend(pcm16)
        logger.info(
            f"[STT] Added chunk: {len(pcm16)} bytes, RMS={energy_stats['rms']:.1f}, "
            f"buffer={len(self._buffer)} bytes"
        )
        
        return True

    def reset_transcript(self):
        """Clear the audio buffer."""
        old_size = len(self._buffer)
        self._buffer.clear()
        logger.info(f"[STT] Buffer reset ({old_size} bytes cleared)")

    def get_buffer_stats(self) -> dict:
        """Get current buffer statistics."""
        buffer_bytes = len(self._buffer)
        duration = buffer_bytes / (self.sr * 2) if buffer_bytes > 0 else 0
        
        return {
            "buffer_bytes": buffer_bytes,
            "duration_sec": round(duration, 2),
            **self.stats
        }

    async def transcribe_buffer(self) -> str:
        """Transcribe accumulated audio buffer."""
        if not self._buffer:
            logger.info("[STT] Transcribe called with empty buffer")
            return ""
        
        buffer_data = bytes(self._buffer)
        duration = len(buffer_data) / (self.sr * 2)
        
        # Check minimum duration
        if duration < MIN_AUDIO_DURATION_SEC:
            logger.info(f"[STT] Buffer too short ({duration:.2f}s), skipping")
            self.reset_transcript()
            return ""
        
        # Analyze energy
        energy_analysis = analyze_audio_energy(buffer_data, sample_rate=self.sr)
        logger.info(
            f"[STT] Energy analysis: speech_ratio={energy_analysis['speech_ratio']:.1%}, "
            f"avg_rms={energy_analysis['avg_rms']:.1f}, peak_rms={energy_analysis['peak_rms']:.1f}"
        )
        
        # VAD check
        has_speech, speech_ratio = self.vad.process_audio(buffer_data)
        
        if not has_speech:
            logger.info(
                f"[STT] VAD rejected: speech_ratio={speech_ratio:.1%} < required={MIN_SPEECH_RATIO:.0%}"
            )
            self.reset_transcript()
            return ""
        
        # Trim silence
        trimmed_data = trim_silence(buffer_data, self.sr, self.energy_threshold * 0.8)
        if len(trimmed_data) < 200:
            logger.info("[STT] After trimming, buffer too short")
            self.reset_transcript()
            return ""
        
        logger.info(
            f"[STT] Sending to OpenAI: {len(trimmed_data)} bytes "
            f"({len(trimmed_data)/(self.sr*2):.2f}s)"
        )
        
        # Create WAV file
        wav_io = io.BytesIO()
        try:
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sr)
                wf.writeframes(trimmed_data)
            wav_io.seek(0)
            wav_bytes = wav_io.getvalue()
        except Exception as e:
            logger.error(f"[STT] Failed to create WAV: {e}")
            self.reset_transcript()
            return ""
        
        # Send to OpenAI
        try:
            # Previous behavior (kept for reference):
            # result = await asyncio.to_thread(
            #     self.client.audio.transcriptions.create,
            #     model=self.model,
            #     file=("speech.wav", wav_bytes),
            #     language=self.language,
            #     response_format="text",
            # )

            # RESTORED: allow Urdu/Arabic script in transcription
            # result = await asyncio.to_thread(
            #     self.client.audio.transcriptions.create,
            #     model=self.model,
            #     file=("speech.wav", wav_bytes),
            #     language="hi",  # primary hint (keeps Hindi strong, allows Urdu)
            #     prompt=(
            #         "Transcribe in Hindi (Devanagari), Urdu (Arabic script), or English. "
            #         "Do not hallucinate; if unclear, return the closest accurate text."
            #     ),
            #     response_format="text",
            # )
            result = await asyncio.to_thread(
                self.client.audio.transcriptions.create,
                model=self.model,
                file=("speech.wav", wav_bytes),
                language="hi",
                prompt=("""
                    You are transcribing a real outbound phone call with an Indian fintech merchant related to AEPS, payments, settlements, devices, and portal issues.

                    STRICT RULES:
                    - Transcribe ONLY in Hindi (Devanagari script) or English (Latin script). 
                    - DO NOT use Urdu, Arabic, or any other script.
                    - If the speech is unclear, noisy, or incomplete, return an empty string. 
                    - Do NOT guess, translate, paraphrase, or autocorrect.
                    - Preserve the merchant’s words exactly as spoken.

                    DOMAIN CONTEXT (for accuracy, not guessing):
                    Common topics may include:
                    - AEPS, Aadhaar Pay, withdrawals, settlements
                    - Device issues (Mantra, Morpho, SecuGen, Precision)
                    - Portal, app, login, KYC, biometric, transaction status
                    - Pending, failed, awaiting, balance, commission, charges

                    STYLE:
                    - Short, spoken phrases only.
                    - No punctuation unless clearly spoken.
                    

                    If you cannot confidently transcribe in Hindi or English, return an empty string."""
                ),
                response_format="text",
            )
                        
            text = result.strip() if isinstance(result, str) else str(result).strip()

            # Previous change (kept for reference):
            # (Urdu -> Hindi conversion block removed)

            if not is_supported_language(text):
                logger.info(f"[STT] Rejected unsupported script: '{text}'")
                self.reset_transcript()
                return ""
            
            # Post-transcription noise filtering
            if is_noise_transcription(text):
                self.stats["transcriptions_filtered"] += 1
                logger.info(f"[STT] Filtered noise transcription: '{text}'")
                self.reset_transcript()
                return ""
            
            self.stats["successful_transcriptions"] += 1
            logger.info(f"[STT] Transcription: '{text}'")
            self.reset_transcript()
            return text
            
        except Exception as e:
            logger.error(f"[STT] Transcription failed: {e}")
            self.reset_transcript()
            return ""
    # ============================================================================
    # CLONE & RESET — NEEDED FOR FAST FIRST-STT CALLS
    # ============================================================================
    def clone(self):
        """
        Create a new STT instance using the same model, language, thresholds,
        and VAD settings — but with a fresh clean buffer.
        """
        clone_obj = OpenAIBatchSTT(
            samplerate=self.sr,
            model=self.model,
            language=self.language,
            use_webrtc_vad=isinstance(self.vad, WebRTCVAD),
            energy_threshold=self.energy_threshold,
        )
        return clone_obj

    def reset(self):
        """Reset only the audio buffer (no re-creation of client)."""
        self._buffer.clear()
        # Reset VAD state if needed in future
        logger.info("[STT] Clone instance reset (buffer cleared)")
