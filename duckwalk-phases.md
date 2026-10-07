# Duckwalk: Development Phases

This plan splits the build into ten phases, starting from project structure and setup. Each phase ends with **deliverables** and an **exit gate**. Do not start the next phase until every item in the gate is checked. The ordering is deliberate: each phase builds on a verified foundation, so a failure is always isolated to the newest layer.

## Phase map

| Phase | Name | Core outcome | Est. |
|-------|------|--------------|------|
| 0 | Structure and setup | Repo, environments and every service running | 2 h |
| 1 | Local intelligence | Gemma produces a breadcrumb summary and a nudge | 2 h |
| 2 | Signals and stuck detector | TabPFN returns P(stuck) from real work signals | 3 h |
| 3 | Durable workflow | `WalkSession` runs end to end with fake inputs | 3 h |
| 4 | Voice loop | Spoken Socratic conversation, fully local | 3 h |
| 5 | Fine-tuning | Tuned Gemma beats the base model on a benchmark | 4 h |
| 6 | Phone client | Nudge, walking screen and return brief on a real phone | 3 h |
| 7 | Closed loop and smart features | Auto-labeling, flow protection, walk modes | 3 h |
| 8 | Observability and hardening | Sentry traces, failure drills, one debugged bottleneck | 2 h |
| 9 | Demo and submission | Recorded demo, write-up, prize mapping | 3 h |

Total is about 28 hours. If time is short, the first cut candidates are the Flutter app in Phase 6 (replace it with an ntfy.sh push) and the P2 features. Do not cut Phases 1 to 5, since they are the core of the project.

---

## Phase 0: Project structure and setup

**Goal:** a repo where every component has a home and every external service runs on your machine.

**Context:** hackathon projects fail at integration, not at algorithms. Getting Ollama, Temporal, Sentry and Python tooling running before writing logic means later bugs are yours, not environment bugs.

### Repo layout

```
duckwalk/
├── daemon/               # signal collectors and detector loop
│   ├── collectors/       # git, editor, build, terminal
│   └── detector.py
├── workflows/            # Temporal workflows and worker
│   ├── walk_session.py
│   └── worker.py
├── activities/           # LLM, voice, push, breadcrumb activities
├── voice/                # whisper.cpp + Piper wrappers
├── ml/                   # TabPFN training, Tinker scripts, datasets
│   ├── data/
│   └── tinker/
├── phone/                # Flutter client
├── eval/                 # benchmark harness and results
├── scripts/              # setup, seed data, demo helpers
├── docs/                 # architecture, write-up, traces
├── pyproject.toml
├── .env.example
└── README.md
```

### Tasks

1. Create the repo, `pyproject.toml` (Python 3.11+), and a virtual environment.
2. Install and verify **Ollama**, then pull a Gemma model (`ollama pull gemma4:e4b` for local, or `gemma4:31b-cloud` for Ollama cloud; chosen with `OLLAMA_MODEL`).
3. Install **Temporal** (dev server via the Temporal CLI) and confirm the UI loads.
4. Build **whisper.cpp** and download a small model. Install **Piper** with one voice.
5. Install the Python dependencies: `temporalio`, `tabpfn`, `sentry-sdk`, `pandas`, `httpx`, `astral`.
6. Create a Sentry project and call `sentry_sdk.init(...)` once in a shared module.
7. Create the Flutter project in `phone/` and run the default app on a device.
8. Write `scripts/doctor.py` that checks every service and prints a pass/fail table.
9. Add `.env.example` (Ollama URL, Sentry DSN, Temporal address, ntfy topic).

### Deliverables

- Repo with the structure above, committed.
- `scripts/doctor.py` that reports all services healthy.
- README with a one-command setup section.

### Exit gate

- [ ] `doctor.py` shows Ollama, Temporal, whisper.cpp, Piper and Sentry all passing.
- [ ] A hardcoded prompt to Gemma returns a response through Ollama.
- [ ] The Flutter default app runs on a physical phone.
- [ ] A test error appears in the Sentry dashboard.

---

## Phase 1: Local intelligence

**Goal:** prove the AI half of the core idea: capture working state, compress it, and write a good nudge.

**Context:** the breadcrumb is the feature that makes leaving the desk free, and it needs no phone, voice or workflow engine. If it isn't compelling here, nothing built on top will rescue it.

### Tasks

1. Implement `capture_breadcrumb(repo)`: branch, `git diff --stat`, last terminal error (tail of a log), open files (a stub is fine for now).
2. Write the summary prompt (max 60 words: what you were doing, what's failing, next thing to try).
3. Write the nudge prompt (one line, no lecture, references the real context).
4. Create an Ollama client wrapper with timeouts and a clean error type.
5. Create 5 realistic fixture states (failing test, merge conflict, flaky build, and so on) in `eval/fixtures/`.
6. Add Sentry spans around every LLM call, tagging model name and token counts from the first call onward.

### Deliverables

- `activities/breadcrumb.py` and `activities/llm.py`.
- Prompt files versioned in the repo.
- A CLI: `python -m duckwalk.breadcrumb --repo .` that prints the summary and nudge.
- Output for all 5 fixtures saved to `eval/fixtures/outputs.md`.

### Exit gate

- [ ] The CLI works on a real repo you have open.
- [ ] You would genuinely act on at least 4 of the 5 fixture summaries.
- [ ] Summaries stay under the word limit and never give direct fixes.
- [ ] Every LLM call shows up as a span in Sentry.

---

## Phase 2: Signals and the stuck detector

**Goal:** a daemon that turns raw work signals into a P(stuck) score using TabPFN.

**Context:** TabPFN needs no hyperparameter tuning and works with very small tables, which is why a hand-labeled starter dataset is enough. The model is only as good as the features, so define them carefully.

### Features per 5-minute window

`mins_since_break`, `failed_builds`, `same_file_edits`, `undo_ratio`, `commits`, `hour`

### Tasks

1. Implement collectors: git (commits, edit counts per file), build/test exit codes (a wrapper or log watcher), editor undo/redo counts (via the editor's log or extension), and last-input time for break detection.
2. Write windows to a SQLite `windows` table (schema in the project doc).
3. Build a labeling script: a one-key CLI to mark past windows as stuck or flow.
4. Hand-label 30 to 50 windows from your own real work.
5. Train `TabPFNClassifier` and expose `p_stuck(window)`.
6. Evaluate with a held-out split; record precision and recall at several training sizes (10, 20, 30, 50).
7. Add a threshold setting (start at 0.7).

### Deliverables

- `daemon/collectors/*`, `daemon/detector.py`, a populated `windows.db`.
- `ml/train_detector.py` and a metrics file in `ml/data/`.
- A learning-curve chart of detector quality versus labeled examples.

### Exit gate

- [ ] The daemon runs for 30+ minutes without crashing and records windows.
- [ ] At least 30 labeled windows exist, with both classes represented.
- [ ] Held-out metrics are recorded, even if modest. Report them honestly.
- [ ] Triggering a synthetic "stuck" window returns P(stuck) above threshold.

---

## Phase 3: Durable workflow

**Goal:** the `WalkSession` Temporal workflow runs the whole sequence with fake phone and voice inputs.

**Context:** doing the orchestration before the voice loop and the phone means those parts later plug into a skeleton that already handles failure. Durability is also a demo moment you can prove here.

### Tasks

1. Define activities: `capture_breadcrumb`, `gemma_nudge`, `push_to_phone` (print to console for now), `voice_loop` (stub that returns a canned transcript), `gemma_brief`.
2. Define `WalkSession` with a `phone_moving` signal and a 10-minute wait condition.
3. Set retry policies and timeouts per activity (LLM: 5 attempts, 30 s).
4. Write the worker and a starter that the detector calls when P(stuck) crosses the threshold.
5. Handle the timeout path: if the user never moves, the workflow ends gracefully and records `walked=false`.
6. Persist workflow outcomes to the `windows` table.
7. Write a failure drill script: kill Ollama mid-run, restart it, confirm the workflow finishes.

### Deliverables

- `workflows/walk_session.py`, `workflows/worker.py`, all activities.
- `scripts/drill_ollama_kill.sh`.
- Screenshot or recording of the workflow in the Temporal UI surviving the drill.

### Exit gate

- [ ] A full run completes: detector trigger, nudge, signal, brief.
- [ ] The no-movement timeout path works.
- [ ] The Ollama kill drill ends with a completed workflow, with retries visible.
- [ ] Restarting the worker mid-run resumes the workflow.

---

## Phase 4: Voice loop

**Goal:** a real spoken conversation, fully local, replacing the stub `voice_loop` activity.

**Context:** this is the highest-latency, highest-risk phase. Use the base Gemma model now. Fine-tuning comes next, and you need the baseline you are about to beat.

### Tasks

1. Implement audio capture from the laptop mic as a test harness (the phone mic comes in Phase 6).
2. Add voice activity detection so the loop knows when you've finished speaking.
3. Transcribe with whisper.cpp, send to Gemma with a Socratic system prompt (questions only, never direct answers), speak the reply with Piper.
4. Stream the LLM output into TTS sentence by sentence to cut perceived latency.
5. Add session limits (max duration, "stop" phrase) and save the full transcript.
6. Record per-turn latency for each stage (STT, LLM, TTS) and log it as spans.
7. Add the opt-in ElevenLabs TTS path behind a flag, with Piper as the default.

### Deliverables

- `voice/` package and the real `voice_loop` activity.
- Transcript files for at least 3 test conversations.
- A latency table for each stage, per turn.

### Exit gate

- [ ] A 5-turn spoken conversation works with no screen interaction.
- [ ] The duck asks questions and does not hand out solutions in the test conversations.
- [ ] Median time from end-of-speech to start-of-reply is measured and written down.
- [ ] The workflow still completes end to end with the real voice loop.

---

## Phase 5: Fine-tuning with Tinker

**Goal:** a small fine-tuned Gemma that is measurably better than the base model at being a Socratic debugging duck.

**Context:** the prize requires a clear improvement in quality, latency or cost over a baseline, so the benchmark matters as much as the model. Build the evaluation before you train, so you can't unconsciously fit the test.

### Tasks

1. Write the rubric: asks a question (not a statement), refers to the stated problem, no direct fix, under N words.
2. Create 50 held-out debugging prompts and freeze them. Never train on these.
3. Generate about 500 synthetic training dialogues with a larger model, then filter them with the rubric.
4. Run the baseline: base Gemma on the 50 prompts, recording rubric score, latency per response and tokens per response.
5. Fine-tune with Tinker (check its current supported-model list and pick a small Gemma if available, otherwise the closest small open model).
6. Re-run the same 50 prompts on the tuned model.
7. Serve the tuned model locally if the export allows it. If not, document the serving path you used and what that means for the offline claim.
8. Swap the tuned model into the voice loop and run a regression test.

### Deliverables

- `ml/tinker/` scripts, the frozen eval set, the filtered training set.
- `eval/results.md` with a baseline vs. tuned comparison table.
- Updated model setting in `.env`.

### Exit gate

- [ ] A frozen eval set exists and was never used for training.
- [ ] The comparison table shows a real improvement on at least one metric. If there is none, document that honestly and iterate on data quality.
- [ ] The voice loop works with the tuned model.
- [ ] The write-up states exactly where the tuned model runs.

---

## Phase 6: Phone client

**Goal:** the three-screen Flutter app, wired to the workflow.

**Context:** the app's job is to disappear. Three screens, no navigation, nothing that invites scrolling. If the timeline is tight, replace the app with ntfy.sh notifications and a tiny web page, and keep the rest of the phase's gate.

### Screens

1. **Nudge:** the notification and a single "Walk" button.
2. **Walking:** a black screen with one stop button. The only job is to emit movement signals.
3. **Return brief:** hypotheses, next three actions, one command.

### Tasks

1. Receive pushes (ntfy topic or FCM-free local approach) and open the nudge screen.
2. Emit movement via `pedometer` and `geolocator`, and send the `phone_moving` signal to the workflow through a small local API endpoint.
3. Stream phone mic audio to the laptop for the voice loop, and play the TTS audio back (or use the laptop with Bluetooth earbuds if streaming proves too costly).
4. Implement the return brief screen from the workflow result.
5. Handle disconnects: the workflow must tolerate the phone dropping off the network.

### Deliverables

- `phone/` app, a small `daemon/api.py` for signals, and a screen recording.

### Exit gate

- [ ] A real walk triggers the movement signal with the phone in a pocket.
- [ ] The full loop works with a physical phone: nudge, walk, voice, brief.
- [ ] Total phone screen-on time for one full session is measured and under 30 seconds.
- [ ] Turning off Wi-Fi mid-walk and back on doesn't break the session.

---

## Phase 7: Closed loop and smart features

**Goal:** the system learns from outcomes and behaves with judgment.

**Context:** this phase turns a demo into a product. It adds the features that make the system trustworthy: it stays quiet during flow, adapts to the situation, and measures whether walks actually help.

### Tasks

1. **Auto-labeling:** after a session, watch for a passing test or a landed commit within 30 minutes and set `resolved_30m`.
2. **Retraining:** a script that retrains TabPFN on the accumulated labels.
3. **Flow protection:** suppress nudges when typing cadence is high and failures are low. Track the false-nudge rate.
4. **Natural-break timing:** hold a pending nudge until the next commit or green test run (with a maximum delay).
5. **Walk modes:** Gemma picks Think, Reset or Vent from the context, and the voice loop behaves accordingly.
6. **Daylight cap:** compute sunset with `astral` and cap the walk length.
7. **Voice-to-artifact:** export the transcript as a markdown ticket draft or commit message.

### Deliverables

- Working versions of the features above, each behind a config flag.
- A stats script that prints fix rate (walked vs. skipped) and the false-nudge rate.

### Exit gate

- [ ] Auto-labels are written without any manual step.
- [ ] Flow protection suppresses a nudge in a simulated high-flow window.
- [ ] Each walk mode produces visibly different behavior in a test run.
- [ ] The stats script runs. Note the sample size and any limits when reporting numbers.

---

## Phase 8: Observability and hardening

**Goal:** show the agent's work in Sentry, and prove the system survives bad conditions.

**Context:** the Sentry prize rewards how you set up tracing, what you found, and how you debugged it. A single well-explained bottleneck is worth more than dashboards full of screenshots.

### Tasks

1. Verify that every stage emits a span: `classify`, `breadcrumb`, `nudge`, `stt`, `llm`, `tts`, `brief`, with model and token tags.
2. Collect 20+ real traces and find the slowest stage.
3. Fix one real bottleneck (for example sentence-level TTS streaming, a smaller quantization, or a warm model keep-alive) and capture before and after traces.
4. Run the failure drills: Ollama killed, worker restarted, phone offline, TabPFN input malformed.
5. Add graceful degradation: if the LLM is unavailable, fall back to a canned nudge instead of failing silently.
6. Run the whole system for a continuous 2-hour session.

### Deliverables

- `docs/traces/` with screenshots and a before/after latency table.
- A drill log recording what broke and what you fixed.

### Exit gate

- [ ] One documented debugging story with before and after traces.
- [ ] All four failure drills pass.
- [ ] The 2-hour soak test finishes without manual intervention.

---

## Phase 9: Demo and submission

**Goal:** a short demo and a write-up that makes the case clearly and honestly.

**Context:** the strongest demo shows the screen as the shortest part of the experience. Film the real thing outside, and keep the claims tied to your measured numbers.

### Tasks

1. Script a 2 to 3 minute demo: the stuck moment, nudge, step outside, voice duck, return brief. Include the Temporal failure drill as a short beat.
2. Record outdoors with a real walk. Optionally use ElevenLabs for demo narration.
3. Write the README and the write-up: problem, architecture, results (detector curve, fine-tune table, fix rates), the offline claim (state exactly what runs locally), limitations.
4. Map evidence to each prize you are entering (Gemma, TabPFN, Tinker, Temporal, Sentry, ElevenLabs if used). Link the proof for each.
5. If you want the Render prize, deploy the landing page or demo site there and mention it as the only hosted piece.
6. Clean the repo: remove secrets, confirm `.env.example`, test the setup steps on a clean machine or fresh clone.

### Deliverables

- Demo video, final README, write-up with traces and tables, and a public repo.

### Exit gate

- [ ] A fresh clone follows the README and reaches a working `doctor.py`.
- [ ] Every claim in the write-up links to a number, trace or file.
- [ ] The demo shows the real outdoor flow, not a mock.
- [ ] Prize mapping table is complete.

---

## Rules that apply to every phase

1. **Gate discipline:** unfinished deliverables don't carry forward.
2. **Commit at each gate** with a tag (`phase-0-done`, `phase-1-done`, and so on) so you can always roll back to a known good state.
3. **Instrument from Phase 1**, so you never retrofit tracing.
4. **Measure before claiming:** every number in the write-up comes from a script in the repo.
5. **Cut scope, not gates:** if you run out of time, drop features from Phase 7 or the Flutter app in Phase 6, never a phase's verification step.
