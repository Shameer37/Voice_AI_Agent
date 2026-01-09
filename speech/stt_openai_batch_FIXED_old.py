# speech/stt_openai_batch.py - FIXED VERSION

import asyncio
import io
import wave
import logging
import struct
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
import os

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger("openai_batch_stt")


class OpenAIBatchSTT:
    def __init__(self, samplerate: int, model: str, language: str = "hi"):
        self.sr = samplerate
        self.model = model
        self.language = language
        self._buffer = bytearray()
        self.client = OpenAI()

    def validate_pcm16_format(self, data: bytes) -> bool:
        """
        Validate that data looks like valid PCM16 mono audio.
        PCM16 = 16-bit samples, so data length should be even.
        """
        if len(data) == 0:
            return False
        if len(data) % 2 != 0:
            logger.warning(f"[STT] Invalid PCM16: odd byte count {len(data)}")
            return False
        return True

    def estimate_audio_properties(self, data: bytes) -> dict:
        """
        Estimate audio properties from raw PCM16 data.
        """
        if len(data) < 2:
            return {"samples": 0, "duration_sec": 0, "estimated_sr": None}

        num_samples = len(data) // 2
        duration_sec = num_samples / self.sr
        
        return {
            "samples": num_samples,
            "duration_sec": duration_sec,
            "estimated_sr": self.sr,
            "byte_count": len(data)
        }

    def add_chunk(self, pcm16: bytes) -> bool:
        """
        Add audio chunk to buffer with validation.
        Returns True if successfully added, False otherwise.
        """
        if not self.validate_pcm16_format(pcm16):
            logger.error(f"[STT] Rejected invalid PCM16 chunk: {len(pcm16)} bytes")
            return False

        self._buffer.extend(pcm16)
        props = self.estimate_audio_properties(self._buffer)
        logger.debug(
            f"[STT] buffered_audio: {props['samples']} samples, "
            f"{props['duration_sec']:.2f}s @ {props['estimated_sr']}Hz, "
            f"{props['byte_count']} bytes"
        )
        return True

    def reset_transcript(self):
        """Clear the audio buffer."""
        old_size = len(self._buffer)
        self._buffer.clear()
        logger.info(f"[STT] buffer reset ({old_size} bytes cleared)")

    async def transcribe_buffer(self) -> str:
        """
        Transcribe accumulated audio buffer using OpenAI Whisper API.
        """
        if not self._buffer:
            logger.info("[STT] transcribe called with empty buffer")
            return ""

        # Validate before sending
        if not self.validate_pcm16_format(bytes(self._buffer)):
            logger.error(f"[STT] Buffer validation failed: {len(self._buffer)} bytes")
            return ""

        props = self.estimate_audio_properties(bytes(self._buffer))
        logger.info(
            f"[STT] sending audio to OpenAI "
            f"(samples={props['samples']}, duration={props['duration_sec']:.2f}s, "
            f"sr={props['estimated_sr']}Hz, bytes={props['byte_count']})"
        )

        # Create WAV file with proper headers
        wav_io = io.BytesIO()
        try:
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # PCM16 = 2 bytes
                wf.setframerate(self.sr)  # Sample rate
                wf.writeframes(self._buffer)
            
            wav_io.seek(0)
            wav_bytes = wav_io.getvalue()
            logger.debug(f"[STT] Created WAV file: {len(wav_bytes)} bytes")

        except Exception as e:
            logger.error(f"[STT] Failed to create WAV: {e}")
            return ""

        # Send to OpenAI
        try:
            result = await asyncio.to_thread(
                self.client.audio.transcriptions.create,
                model=self.model,
                file=("speech.wav", wav_bytes),
                language=self.language,
                response_format="text",
            )

            # Handle response
            if isinstance(result, str):
                text = result.strip()
            else:
                text = str(result).strip()

            logger.info(f"[STT] transcription='{text}'")
            self.reset_transcript()
            return text

        except Exception as e:
            logger.error(f"[STT] Transcription failed: {e}")
            return ""
