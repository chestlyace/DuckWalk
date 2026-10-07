"""The duck: a hands-free Socratic conversation. Mic -> VAD -> whisper.cpp -> Gemma -> TTS -> speaker.

Each turn runs inside a Sentry span with child spans for `stt`, the LLM call and `tts`.
Spans carry timings and counts only, never what was said.
"""

import json
import re
import time
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator

import sentry_sdk

from duckwalk import config
from duckwalk.activities import llm
from duckwalk.voice import stt
from duckwalk.voice.audio import EndOfScript
from duckwalk.voice.vad import Listener

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "duck.txt"
GOODBYE = "Okay, ending the walk. Nice thinking out there."
STILL_HERE = "Take your time. I'm here whenever you're ready."
RESUMED = "Sorry, I lost you for a moment. Where were we?"
OPENER_CUE = "(The walk has just started. Open with one short question about where they were.)"
SILENCE_PROMPT_AFTER_S = 90

_SENTENCE = re.compile(r"(.+?[.!?])\s+", re.S)
_NOT_SPOKEN = re.compile(r"[*_`#>]+")


def sentences(chunks: Iterable[str]) -> Iterator[str]:
    """Complete sentences from a stream of text chunks (the last one is flushed when the stream ends)."""
    buf = ""
    for chunk in chunks:
        buf += chunk
        while m := _SENTENCE.match(buf):
            yield m.group(1)
            buf = buf[m.end():]
    if buf.strip():
        yield buf.strip()


def is_stop_phrase(text: str) -> bool:
    """True if a short utterance contains the stop phrase, allowing for how whisper mishears it
    ("and walk" for "end walk"). Longer utterances must contain it exactly, so talking about
    ending a walk doesn't end the conversation."""
    words = re.sub(r"[^a-z ]", "", text.lower()).split()
    phrase = config.STOP_PHRASE.split()
    if " ".join(phrase) in " ".join(words):
        return True
    if len(words) > len(phrase) + 2:
        return False
    n = len(phrase)
    return any(SequenceMatcher(None, " ".join(words[i:i + n]), " ".join(phrase)).ratio() >= 0.8
               for i in range(len(words) - n + 1))


@dataclass
class TurnMetrics:
    turn: int  # 0 is the duck's opening question
    speech_s: float = 0.0  # how long the person spoke
    hangover_s: float = 0.0  # silence the VAD waited for before deciding they had finished
    stt_s: float = 0.0
    llm_first_token_s: float | None = None
    tts_first_synth_s: float | None = None  # first sentence queued -> first audio ready
    reply_latency_s: float | None = None  # VAD decision -> first audio at the speaker
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def perceived_latency_s(self) -> float | None:
        """What the person waits after their last word: the VAD hangover plus the pipeline."""
        return None if self.reply_latency_s is None else self.hangover_s + self.reply_latency_s


class Duck:
    def __init__(self, summary: str, mic, speaker, *, on_tick: Callable[[], None] = lambda: None,
                 transcript_path: Path | None = None, max_seconds: float | None = None) -> None:
        self.mic, self.speaker, self.on_tick = mic, speaker, on_tick
        self.path = transcript_path
        self.max_seconds = max_seconds if max_seconds is not None else config.VOICE_MAX_MINUTES * 60
        self.system = PROMPT.read_text().replace("{summary}", summary)
        self.turns: list[dict] = []  # {"role": "duck"|"you", "text": ...}
        self.metrics: list[TurnMetrics] = []
        self.started = datetime.now().isoformat(timespec="seconds")
        self.resumed = False
        if self.path and self.path.exists():  # a retried activity picks the conversation back up
            saved = json.loads(self.path.read_text())
            self.turns, self.started, self.resumed = saved["turns"], saved["started"], bool(saved["turns"])
            self.metrics = [TurnMetrics(**m) for m in saved["metrics"]]

    def run(self) -> dict:
        began = time.monotonic()
        ended = "stop_phrase"
        self.mic.start()
        listener = Listener(self.mic, self.on_tick)
        try:
            if self.resumed:
                self._say_canned(RESUMED, "duck")
            else:
                self._reply(TurnMetrics(turn=0), opener=True)
            silent_prompts = 0
            while True:
                self.on_tick()
                if time.monotonic() - began > self.max_seconds:
                    self._say_canned(f"That's {config.VOICE_MAX_MINUTES} minutes. Let's wrap up here.", "duck")
                    ended = "time_limit"
                    break
                try:
                    utt = listener.hear(SILENCE_PROMPT_AFTER_S)
                except EndOfScript:
                    ended = "script_end"
                    break
                if utt is None:  # a long silence: say so once, then keep waiting quietly
                    if silent_prompts == 0:
                        self._say_canned(STILL_HERE, "duck")
                    silent_prompts += 1
                    continue
                silent_prompts = 0
                m = TurnMetrics(turn=sum(t["role"] == "you" for t in self.turns) + 1,
                                speech_s=utt.speech_s, hangover_s=utt.hangover_s)
                with sentry_sdk.start_span(op="duckwalk.turn", name=f"turn {m.turn}") as turn_span:
                    with sentry_sdk.start_span(op="duckwalk.stt", name="whisper.cpp") as sp:
                        t0 = time.monotonic()
                        text = stt.transcribe(utt.audio)
                        m.stt_s = time.monotonic() - t0
                        sp.set_data("stt.engine", "whisper.cpp")
                        sp.set_data("stt.model", config.WHISPER_MODEL.name)
                        sp.set_data("audio_s", round(utt.speech_s, 2))
                        sp.set_data("duration_s", round(m.stt_s, 3))
                    self.on_tick()
                    if not text:  # noise, not words
                        continue
                    self.turns.append({"role": "you", "text": text})
                    if is_stop_phrase(text):
                        self._say_canned(GOODBYE, "duck")
                        self.metrics.append(m)
                        break
                    self._reply(m, decided_at=utt.decided_at)
                    turn_span.set_data("reply_latency_s", m.reply_latency_s)
                    turn_span.set_data("perceived_latency_s", m.perceived_latency_s)
        finally:
            self.mic.stop()
            self.speaker.close()
            self._save()
        return {"ended": ended, "turns": sum(t["role"] == "you" for t in self.turns), "transcript": self.transcript_text()}

    def _messages(self, opener: bool) -> list[dict]:
        msgs = [{"role": "system", "content": self.system}]
        for t in self.turns:
            msgs.append({"role": "assistant" if t["role"] == "duck" else "user", "content": t["text"]})
        if opener:
            msgs.append({"role": "user", "content": OPENER_CUE})
        return msgs

    def _reply(self, m: TurnMetrics, opener: bool = False, decided_at: float | None = None) -> None:
        self.speaker.new_turn()
        stream = llm.ChatStream(self._messages(opener), stage="duck")
        spoken = []
        for sentence in sentences(stream):
            sentence = _NOT_SPOKEN.sub("", sentence).strip()
            if sentence:
                spoken.append(sentence)
                self.speaker.say(sentence)
                self.on_tick()
        with sentry_sdk.start_span(op="duckwalk.tts", name=self.speaker.tts.name) as sp:
            self.speaker.wait_done()
            sp.set_data("tts.engine", self.speaker.tts.name)
            sp.set_data("tts.sentences", self.speaker.sentences)
            sp.set_data("tts.first_synth_s", self.speaker.first_synth_s)
        m.llm_first_token_s = stream.first_token_s
        m.tts_first_synth_s = self.speaker.first_synth_s
        m.input_tokens, m.output_tokens = stream.input_tokens, stream.output_tokens
        if decided_at is not None and self.speaker.first_audio_at is not None:
            m.reply_latency_s = self.speaker.first_audio_at - decided_at
        self.turns.append({"role": "duck", "text": " ".join(spoken)})
        self.metrics.append(m)
        self._save()

    def _say_canned(self, text: str, role: str) -> None:
        self.speaker.new_turn()
        self.speaker.say(text)
        self.speaker.wait_done()
        self.turns.append({"role": role, "text": text})
        self._save()

    def transcript_text(self) -> str:
        return "\n".join(f"{'Duck' if t['role'] == 'duck' else 'You'}: {t['text']}" for t in self.turns)

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"started": self.started, "model": config.OLLAMA_MODEL, "tts": self.speaker.tts.name,
                "turns": self.turns, "metrics": [asdict(m) for m in self.metrics]}
        self.path.write_text(json.dumps(data, indent=2) + "\n")
        lines = [f"# Walk conversation {self.path.stem}", "",
                 f"Started {self.started}. Model `{config.OLLAMA_MODEL}`, TTS `{self.speaker.tts.name}`, STT `{config.WHISPER_MODEL.name}`.", ""]
        lines += [f"**{'Duck' if t['role'] == 'duck' else 'You'}:** {t['text']}\n" for t in self.turns]
        self.path.with_suffix(".md").write_text("\n".join(lines))
