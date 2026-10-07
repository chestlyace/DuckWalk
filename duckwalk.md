# Duckwalk

> A local-first AI companion that notices when a developer is stuck, gets them away from the screen, and helps them think out loud while they walk. The screen is the shortest part of the experience.

---

## 1. Concept

Most developers don't skip breaks because of willpower. They skip them because they fear losing their mental context. Duckwalk removes that cost:

1. A laptop daemon watches local work signals and detects a "stuck loop".
2. It snapshots where you are (a **breadcrumb**), so leaving costs nothing.
3. Your phone nudges you outside with one line.
4. You rubber-duck the problem by voice while walking, with no screen.
5. When you return, one screen shows what you worked out and what to try next.

**Design rule:** success means minimal time in the app. Every feature either pushes work to the AI or is cut.

**Privacy:** local-first. By default all inference runs locally on open-weight models (Gemma via Ollama), and no code or transcripts leave the machine. The same open-weight models can optionally be served from Ollama's cloud (e.g. `gemma4:31b-cloud`) on machines that can't run them locally. The write-up states which mode each demo and measurement used. The only telemetry sent out is Sentry trace metadata (stage timings, model names, token counts), never code, diffs, prompts or transcripts.

---

## 2. Features

### P0: Core demo loop

| # | Feature | What it does |
|---|---------|--------------|
| 1 | **Stuck detector** | Classifies each 5-minute window of work as "stuck" or "flow" from local signals (time since break, failed builds, repeated edits to one file, undo ratio, commits, hour of day). |
| 2 | **Breadcrumb snapshot** | On nudge, captures branch, `git diff --stat`, last terminal error and open files. The LLM compresses it into a 60-word "where you were / what's failing / next thing to try" note. |
| 3 | **Flow protection** | Never nudges during high typing cadence with low failure rate. Tracks a *false-nudge rate* (nudges dismissed within 10 seconds) as the honest quality metric. |
| 4 | **Walk nudge** | One-line push notification to the phone, written by the local LLM from the current context. |
| 5 | **Voice duck** | Hands-free Socratic rubber-ducking over earbuds: speech-to-text, LLM asks questions (never gives direct answers), text-to-speech. |
| 6 | **Return brief** | One screen, readable in about 10 seconds: hypotheses you voiced, the next three actions, one ready-to-run command. |

### P1: Makes it smart

| # | Feature | What it does |
|---|---------|--------------|
| 7 | **Walk modes** | The LLM picks a mode from context: *Think walk* (Socratic questions), *Reset walk* (silent, at most one sensory prompt), *Vent walk* (duck only listens, then summarizes). |
| 8 | **Automatic outcome labeling** | After you return, a passing test or landed commit within 30 minutes labels the walk "worked". No manual tapping. Feeds weekly retraining of the detector. |
| 9 | **Natural-break timing** | Prefers nudging right after a commit or green test run rather than mid-thought. |
| 10 | **Daylight-aware walk length** | Computes sunset locally and caps walk length accordingly. Short walks for a stuck bug, longer for a long grind. |
| 11 | **Voice-to-artifact** | Turns the walk transcript into a ticket draft, commit message or TODO list, exported as markdown to the repo. |

### P2: Stretch

- Weekly passive digest (one notification, for example "4 walks, 3 preceded fixes").
- Outdoor-flavored "eyes up" micro-prompts (birding, foliage, gardening) to match the hackathon theme.
- Local-discovery walk-and-talk pairing with nearby developers.

### Explicitly cut

Accounts, social feed, leaderboards, photo verification, and any dashboard that invites more phone time.

---

## 3. Architecture

```
┌────────────────────────── Laptop ──────────────────────────┐
│ Signal collectors (git, editor, build, terminal)            │
│        │                                                    │
│        ▼                                                    │
│ TabPFN classifier → P(stuck)                                │
│        │ > threshold                                        │
│        ▼                                                    │
│ Temporal workflow: WalkSession                              │
│   1. capture_breadcrumb                                     │
│   2. Gemma nudge → push to phone                            │
│   3. wait for movement signal (timeout 10 min)              │
│   4. voice loop: whisper.cpp → fine-tuned Gemma → TTS       │
│   5. Gemma return brief                                     │
│        │                                                    │
│ Ollama (local models)        Sentry spans on every step     │
└───────────────┬─────────────────────────────────────────────┘
                │ LAN / ntfy push
        ┌───────▼────────┐
        │ Flutter phone  │  3 screens: nudge, walking (black + stop), return brief
        │ pedometer/GPS  │
        └────────────────┘
```

---

## 4. Tools and where each is used

| Tool | Role | Used for features | Notes |
|------|------|-------------------|-------|
| **Gemma** (via **Ollama**) | LLM | 2, 4, 5, 6, 7, 11 | Local by default (`gemma4:e4b`, fully offline); optional Ollama cloud (`gemma4:31b-cloud`). Set with `OLLAMA_MODEL`. Base model for nudges and briefs. |
| **Tinker** (Thinking Machines) | Fine-tuning | 5 | Fine-tune a small Gemma on Socratic debugging dialogues. Verify the current supported-model list before committing. |
| **TabPFN** (Prior Labs) | Tabular classifier | 1, 8, 9 | Works with tiny datasets (30-50 labeled windows). Retrained weekly on auto-labeled outcomes. |
| **Temporal** | Durable workflow engine | 4, 5, 6 | `WalkSession` survives laptop sleep, Ollama crashes and dropped phone connections. Retries activities. |
| **Sentry Agent Tracing** | Observability | All | Spans per stage (`classify`, `nudge`, `stt`, `llm`, `tts`, `brief`) tagged with model name and token counts. |
| **ElevenLabs** (optional) | Higher-quality TTS | 5 | Requires internet. Keep **Piper** as the offline default and treat ElevenLabs as an opt-in upgrade. |
| **whisper.cpp** | Local speech-to-text | 5, 11 | Runs offline. |
| **Piper** | Local text-to-speech | 5 | Offline fallback voice. |
| **Flutter** (`pedometer`, `geolocator`) | Phone client | 4, 6, 10 | Three screens only. Movement signals sent to Temporal. |
| **ntfy.sh** (or self-hosted) | Push transport | 4 | Simple fallback if the Flutter app doesn't fit the timeline. |
| **astral** (Python) | Sunrise/sunset | 10 | Offline computation. |
| **SQLite** | Local storage | 8 | Window history and outcome labels. |
| **Render** (optional) | Static hosting | Demo only | Host the landing page or demo site. Not part of the runtime, since local-first is the point. |

### Deliberately not used

MongoDB Atlas, Tiger Data, SerpApi, Backboard and Mastra: each would add a cloud dependency or overlap with Temporal without improving the local-first story.

---

## 5. Data model

```sql
CREATE TABLE windows (
  id               INTEGER PRIMARY KEY,
  ts               TIMESTAMP,
  repo             TEXT,     -- watched repo of the most-edited file, if any
  mins_since_break REAL,
  failed_builds    INT,
  same_file_edits  INT,
  undo_ratio       REAL,
  commits          INT,
  hour             INT,
  nudged           BOOL,
  walked           BOOL,
  dismissed_fast   BOOL,   -- dismissed within 10s => false nudge
  resolved_30m     BOOL,   -- auto-labeled: test passed or commit landed
  stuck            BOOL    -- hand label: 1 stuck, 0 flow, NULL unlabeled
);
```

---

## 6. Key code sketches

### Stuck detector (TabPFN)

```python
from tabpfn import TabPFNClassifier
import pandas as pd

df = pd.read_csv("windows.csv")
X, y = df.drop(columns="stuck"), df["stuck"]

clf = TabPFNClassifier()
clf.fit(X, y)

p_stuck = clf.predict_proba(latest_window)[0][1]
if p_stuck > 0.7:
    start_walk_workflow()
```

### Breadcrumb capture

```python
def capture_breadcrumb(repo: str) -> dict:
    return {
        "diff": run(["git", "-C", repo, "diff", "--stat"]),
        "branch": run(["git", "-C", repo, "branch", "--show-current"]),
        "last_error": tail(TERMINAL_LOG, 40),
        "open_files": editor_open_files(),
    }

PROMPT = """You are summarizing a developer's working state before they walk away.
Write: 1) what they were trying to do, 2) what's failing, 3) the single next thing to try.
Max 60 words. No advice beyond that.
State: {state}"""
```

### Durable walk session (Temporal)

```python
@workflow.defn
class WalkSession:
    def __init__(self):
        self.moving = False

    @workflow.signal
    def phone_moving(self):
        self.moving = True

    @workflow.run
    async def run(self, ctx: dict) -> str:
        nudge = await workflow.execute_activity(
            gemma_nudge, ctx, start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5))
        await workflow.execute_activity(push_to_phone, nudge,
            start_to_close_timeout=timedelta(seconds=10))
        await workflow.wait_condition(lambda: self.moving,
            timeout=timedelta(minutes=10))
        transcript = await workflow.execute_activity(
            voice_loop, ctx, start_to_close_timeout=timedelta(minutes=45))
        return await workflow.execute_activity(
            gemma_brief, transcript, start_to_close_timeout=timedelta(seconds=30))
```

### Ollama call from the phone or daemon

```dart
final res = await http.post(
  Uri.parse('http://192.168.1.20:11434/api/generate'),
  body: jsonEncode({
    'model': 'gemma4:e4b',
    'prompt': 'User stuck 90min on same file. One-line walk nudge.',
    'stream': false,
  }),
);
final nudge = jsonDecode(res.body)['response'];
```

---

## 7. Evaluation plan

| Claim | How to measure | Tool |
|-------|----------------|------|
| Fine-tuned duck beats base model | 50 held-out debugging prompts: latency per response, tokens, rubric score for "asks questions instead of answering" | Tinker + Sentry |
| Detector learns from few examples | Precision/recall on a held-out slice of labeled windows as training size grows (10, 20, 30, 50) | TabPFN |
| Walks help | Fix rate within 30 minutes after walked vs. skipped nudges. Report the sample size honestly. | SQLite |
| Nudges are well-timed | False-nudge rate (dismissed within 10 s) | SQLite |
| Pipeline is durable | Kill Ollama mid-session; show Temporal retrying and the session completing | Temporal |
| Pipeline is observable | One trace where the voice loop was slow, and the change that fixed it | Sentry |

---

## 8. Build order

| Step | Task | Est. |
|------|------|------|
| 1 | Ollama + Gemma answering a hardcoded "stuck" prompt | 1 h |
| 2 | Breadcrumb capture + Gemma summary (no phone needed) | 1 h |
| 3 | TabPFN on a hand-labeled CSV | 1 h |
| 4 | Temporal workflow with fake phone signals | 2 h |
| 5 | Voice loop: whisper.cpp + Piper | 2 h |
| 6 | Flutter notification + movement signal (or ntfy.sh fallback) | 2 h |
| 7 | Tinker dataset generation, fine-tune and benchmark table (run in parallel from step 3) | parallel |
| 8 | Sentry spans, demo recording | 1 h |

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Ollama doesn't run on phones | Laptop is the brain, phone talks over LAN. Optional on-device path via llama.cpp or MediaPipe LLM Inference with a 1-3B quantized model. |
| Too few labeled windows | TabPFN is built for small tabular data. Seed with hand-labeled history, then use auto-labeling. |
| Voice loop latency | Use small quantized models, stream TTS, trace with Sentry and tune. |
| Over-nudging annoys users | Flow protection + false-nudge rate tracking + natural-break timing. |
| ElevenLabs breaks the offline claim | Make it opt-in, default to Piper, and say so in the write-up. |
| Scope creep | Cut list in section 2. Phone app stays at three screens. |
