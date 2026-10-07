"""Text-to-speech engines and the speaker that plays them sentence by sentence.

Piper runs offline and is the default. ElevenLabs is opt-in (DUCKWALK_TTS=elevenlabs)
and sends the duck's replies to ElevenLabs' servers.
"""

import queue
import threading
import time
from typing import Iterator

import httpx
import numpy as np
import sounddevice as sd

from duckwalk import config
from duckwalk.voice.audio import _device


class TTSError(Exception):
    pass


class PiperTTS:
    name = "piper"

    def __init__(self) -> None:
        from piper import PiperVoice

        voice = config.PIPER_VOICE_DIR / f"{config.PIPER_VOICE}.onnx"
        if not voice.exists():
            raise TTSError(f"missing {voice.relative_to(config.ROOT)} (run scripts/setup.sh)")
        self._voice = PiperVoice.load(str(voice))
        self.sample_rate = self._voice.config.sample_rate

    def stream(self, text: str) -> Iterator[bytes]:
        for chunk in self._voice.synthesize(text):
            yield chunk.audio_int16_bytes


class ElevenLabsTTS:
    name = "elevenlabs"
    sample_rate = 22050

    def __init__(self) -> None:
        if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
            raise TTSError("DUCKWALK_TTS=elevenlabs needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env")

    def stream(self, text: str) -> Iterator[bytes]:
        try:
            with httpx.stream(
                "POST",
                f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}/stream",
                params={"output_format": "pcm_22050"},
                headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                json={"text": text, "model_id": config.ELEVENLABS_MODEL},
                timeout=30,
            ) as res:
                if res.is_error:
                    raise TTSError(f"ElevenLabs returned {res.status_code}: {res.read().decode()[:200]}")
                carry = b""
                for data in res.iter_bytes():
                    data = carry + data
                    carry = data[len(data) // 2 * 2:]  # keep int16 samples aligned
                    if len(data) >= 2:
                        yield data[: len(data) // 2 * 2]
        except httpx.HTTPError as e:
            raise TTSError(f"ElevenLabs not reachable ({e.__class__.__name__})") from None


def make_tts():
    if config.TTS_ENGINE == "elevenlabs":
        return ElevenLabsTTS()
    if config.TTS_ENGINE != "piper":
        raise TTSError(f"unknown DUCKWALK_TTS={config.TTS_ENGINE!r} (use piper or elevenlabs)")
    return PiperTTS()


class Speaker:
    """Speaks queued sentences on a worker thread, so the next sentence synthesizes while one plays.

    With play=False it still synthesizes (so TTS latency is real) but makes no sound, for tests.
    """

    def __init__(self, tts, play: bool = True) -> None:
        self.tts, self.play = tts, play
        self._q: queue.Queue = queue.Queue()
        self._out: sd.OutputStream | None = None
        self.error: Exception | None = None
        self.first_audio_at: float | None = None  # time.monotonic() when this turn's audio first reached the speaker
        self.first_synth_s: float | None = None  # first sentence: queued -> first audio chunk ready
        self.sentences = 0
        threading.Thread(target=self._run, daemon=True).start()

    def new_turn(self) -> None:
        self.first_audio_at = self.first_synth_s = None
        self.sentences = 0

    def say(self, text: str) -> None:
        self._q.put((text, time.monotonic()))

    def wait_done(self) -> None:
        self._q.join()
        if self.error:
            err, self.error = self.error, None
            raise err

    def close(self) -> None:
        if self._out:
            self._out.stop()
            self._out.close()
            self._out = None

    def _run(self) -> None:
        while True:
            text, queued_at = self._q.get()
            try:
                self.sentences += 1
                for pcm in self.tts.stream(text):
                    if self.first_audio_at is None:
                        self.first_synth_s = time.monotonic() - queued_at
                        self.first_audio_at = time.monotonic()
                    if self.play:
                        self._write(pcm)
            except Exception as e:  # surfaced to the main thread by wait_done
                self.error = e
            finally:
                self._q.task_done()

    def _write(self, pcm: bytes) -> None:
        if self._out is None:
            self._out = sd.OutputStream(samplerate=self.tts.sample_rate, channels=1, dtype="int16",
                                        device=_device(config.AUDIO_OUTPUT))
            self._out.start()
        self._out.write(np.frombuffer(pcm, dtype=np.int16))
