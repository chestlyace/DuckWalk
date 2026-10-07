"""Microphone sources for the voice loop: the live mic, or a scripted stand-in for tests."""

import queue
import time
from collections import deque

import numpy as np
import sounddevice as sd

from duckwalk import config

SAMPLE_RATE = 16000
FRAME = 512  # samples per frame (32 ms), the size Silero VAD expects at 16 kHz


class EndOfScript(Exception):
    """A scripted mic has no more utterances to say."""


def _device(setting: str):
    if not setting:
        return None
    return int(setting) if setting.isdigit() else setting


class LiveMic:
    """16 kHz mono int16 frames from the system (or configured) input device."""

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME,
            device=_device(config.AUDIO_INPUT), callback=self._on_audio,
        )

    def _on_audio(self, indata, frames, time_info, status) -> None:
        self._q.put(indata[:, 0].copy())

    def start(self) -> None:
        self._stream.start()

    def stop(self) -> None:
        self._stream.stop()
        self._stream.close()

    def flush(self) -> None:
        """Drop buffered audio, e.g. the duck's own voice picked up while it was speaking."""
        time.sleep(0.3)  # let the room's echo of the duck's last word die away
        while not self._q.empty():
            self._q.get_nowait()

    def read(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None


class ScriptedMic:
    """Says pre-written utterances (synthesized with Piper) so the loop can be tested without a human.

    Frames are delivered as fast as they are read, so tests run quicker than real time.
    The next utterance is released when the loop starts listening (`flush`).
    """

    def __init__(self, utterances: list[str], lead_s: float = 0.4, tail_s: float = 1.5) -> None:
        self._utterances = deque(utterances)
        self._frames: deque = deque()
        self._lead, self._tail = lead_s, tail_s

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def flush(self) -> None:
        self._frames.clear()
        if not self._utterances:
            raise EndOfScript
        audio = _synthesize_16k(self._utterances.popleft())
        pad = lambda s: np.zeros(int(s * SAMPLE_RATE), dtype=np.int16)  # noqa: E731
        audio = np.concatenate([pad(self._lead), audio, pad(self._tail)])
        audio = audio[: len(audio) // FRAME * FRAME]
        self._frames.extend(audio.reshape(-1, FRAME))

    def read(self, timeout: float = 1.0) -> np.ndarray | None:
        return self._frames.popleft() if self._frames else np.zeros(FRAME, dtype=np.int16)


def _synthesize_16k(text: str) -> np.ndarray:
    from scipy.signal import resample_poly

    from duckwalk.voice.tts import PiperTTS

    tts = PiperTTS()
    pcm = np.frombuffer(b"".join(tts.stream(text)), dtype=np.int16).astype(np.float32)
    return resample_poly(pcm, SAMPLE_RATE, tts.sample_rate).astype(np.int16)
