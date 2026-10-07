# Voice loop latency

3 conversations, 18 measured turns. All times in seconds.

- **reply latency**: VAD decides you finished, to the first audio reaching the speaker (STT + LLM first sentence + TTS).
- **perceived**: reply latency plus the 0.7 s of silence the VAD waits for before deciding. This is what you actually wait.

| Conversation | Turn | Speech | STT | LLM first token | TTS first audio | Reply latency | Perceived |
|---|---|---|---|---|---|---|---|
| scripted-1-rounding | 1 | 7.1 | 4.01 | 0.40 | 1.06 | 5.53 | 6.23 |
| scripted-1-rounding | 2 | 5.3 | 3.73 | 0.39 | 0.57 | 4.71 | 5.41 |
| scripted-1-rounding | 3 | 6.3 | 3.95 | 0.41 | 0.82 | 5.33 | 6.03 |
| scripted-1-rounding | 4 | 5.4 | 3.70 | 0.40 | 0.57 | 4.70 | 5.40 |
| scripted-1-rounding | 5 | 5.2 | 3.86 | 0.53 | 0.50 | 5.09 | 5.79 |
| scripted-1-rounding | 6 | 1.0 | 2.87 | - | - | - | - |
| scripted-2-flaky | 1 | 7.6 | 3.90 | 0.42 | 0.37 | 4.72 | 5.42 |
| scripted-2-flaky | 2 | 5.6 | 3.60 | 0.42 | 0.98 | 5.07 | 5.77 |
| scripted-2-flaky | 3 | 4.7 | 4.26 | 0.42 | 0.63 | 5.36 | 6.06 |
| scripted-2-flaky | 4 | 5.0 | 3.83 | 0.42 | 0.70 | 5.10 | 5.80 |
| scripted-2-flaky | 5 | 5.9 | 4.75 | 0.43 | 0.45 | 5.67 | 6.37 |
| scripted-2-flaky | 6 | 0.9 | 3.02 | - | - | - | - |
| scripted-3-migration | 1 | 6.9 | 4.09 | 3.75 | 0.61 | 8.49 | 9.19 |
| scripted-3-migration | 2 | 6.3 | 3.88 | 0.43 | 0.85 | 5.24 | 5.94 |
| scripted-3-migration | 3 | 6.2 | 3.76 | 0.39 | 1.59 | 5.79 | 6.49 |
| scripted-3-migration | 4 | 5.3 | 3.69 | 0.41 | 0.78 | 4.89 | 5.59 |
| scripted-3-migration | 5 | 5.4 | 4.07 | 0.38 | 0.82 | 5.30 | 6.00 |
| scripted-3-migration | 6 | 0.9 | 3.03 | - | - | - | - |
| **median** | | 5.38 | 3.85 | 0.42 | 0.70 | **5.24** | **5.94** |

## Reply checks (the duck's LLM replies, not its fixed goodbye lines)

- Replies containing a question: 18 of 18
- Replies with code ticks or over 40 words: 0 of 18
- Whether a reply hands out a solution is a judgement call: read the transcripts.
