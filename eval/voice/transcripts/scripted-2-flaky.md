# Walk conversation scripted-2-flaky

Started 2026-10-07T13:50:43. Model `gemma4:31b-cloud`, TTS `piper`, STT `ggml-base.en.bin`.

**Duck:** You were looking into that timeout in the order sync retries test. Why are you only seeing two events instead of three?

**You:** I've got an integration test and go that times out sometimes and passes other times. It waits for three sync events but only gets two.

**Duck:** Intermittent failures. Since it passes sometimes, what's different about the runs that fail?

**You:** It fails maybe one run in three, I changed the retry logic and the worker just before it started.

**Duck:** You changed the retry logic and the worker. What specific part of that logic controls when a sync event is emitted?

**You:** I haven't looked at ordering, the test might be checking before the third event has been sent.

**Duck:** The test might be checking too early. If you increased the wait time, would the third event eventually arrive?

**You:** I suppose I could add a log line with timestamps when each event is sent and when the test checks.

**Duck:** Adding timestamps for the events and the check. What would those logs prove about the timing?

**You:** Okay, so if the check happens first it's a race and the test, and if not it's the worker dropping an event.

**Duck:** A race or a dropped event. Which of those two possibilities would you try to rule out first?

**You:** and walk.

**Duck:** Okay, ending the walk. Nice thinking out there.
