"""Voice activity detection with Silero: collect one utterance, and know when it has ended."""

import time
import warnings
from collections import deque
from dataclasses import dataclass
from typing import Callable

import numpy as np

from duckwalk.voice.audio import FRAME, SAMPLE_RATE

MIN_SILENCE_MS = 700  # silence that ends an utterance
MIN_SPEECH_S = 0.3  # shorter blips (coughs, footsteps) are ignored
MAX_UTTERANCE_S = 60
PRE_ROLL_FRAMES = 10  # ~320 ms of audio kept from before speech was detected

_model = None


def _load():
    global _model
    if _model is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # torch.jit deprecation noise from silero's bundled model
            from silero_vad import load_silero_vad

            _model = load_silero_vad()
    return _model


@dataclass
class Utterance:
    audio: np.ndarray  # int16, 16 kHz
    speech_s: float
    decided_at: float  # time.monotonic() when the VAD decided the speaker had finished
    hangover_s: float = MIN_SILENCE_MS / 1000  # trailing silence that had to pass before deciding


class Listener:
    def __init__(self, mic, on_tick: Callable[[], None] = lambda: None) -> None:
        import torch
        from silero_vad import VADIterator

        self._torch = torch
        self.mic = mic
        self.on_tick = on_tick
        self._it = VADIterator(_load(), threshold=0.5, sampling_rate=SAMPLE_RATE,
                               min_silence_duration_ms=MIN_SILENCE_MS, speech_pad_ms=100)

    def hear(self, silence_timeout_s: float = 90.0) -> Utterance | None:
        """Block until one utterance ends. Returns None if nobody speaks for `silence_timeout_s`."""
        self.mic.flush()
        self._it.reset_states()
        pre: deque = deque(maxlen=PRE_ROLL_FRAMES)
        frames: list = []
        speaking = False
        began = time.monotonic()
        last_tick = began
        while True:
            now = time.monotonic()
            if now - last_tick > 5:
                self.on_tick()
                last_tick = now
            if not speaking and now - began > silence_timeout_s:
                return None
            if speaking and len(frames) * FRAME / SAMPLE_RATE > MAX_UTTERANCE_S:
                return self._finish(frames)
            frame = self.mic.read()
            if frame is None:
                continue
            event = self._it(self._torch.from_numpy(frame.astype(np.float32) / 32768.0))
            if not speaking:
                pre.append(frame)
            else:
                frames.append(frame)
            if event and "start" in event and not speaking:
                speaking = True
                frames = list(pre)
            elif event and "end" in event and speaking:
                utt = self._finish(frames)
                if utt.speech_s >= MIN_SPEECH_S:
                    return utt
                speaking, frames = False, []  # a blip, not speech: keep listening
                self._it.reset_states()

    def _finish(self, frames: list) -> Utterance:
        audio = np.concatenate(frames)
        speech_s = max(0.0, len(audio) / SAMPLE_RATE - MIN_SILENCE_MS / 1000)
        return Utterance(audio=audio, speech_s=speech_s, decided_at=time.monotonic())
