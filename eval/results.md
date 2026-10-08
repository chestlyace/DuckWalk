# Duck evaluation: baseline vs. fine-tuned

Frozen eval set: 50 held-out prompts (`ml/tinker/eval_set.jsonl`, hash in `eval_set.sha256`), never used for training.
Each reply is graded on 8 pass/fail criteria (`ml/tinker/rubric.py`): 6 deterministic checks and 2 from an LLM judge.

| Metric | gemma4:31b-cloud, deployed prompt | Qwen3.5-4B, untuned | Qwen3.5-4B, fine-tuned |
|---|---|---|---|
| **All 8 criteria pass** | **80%** | **68%** | **98%** |
| Mean rubric score (of 1.0) | 0.975 | 0.948 | 0.998 |
| &nbsp;&nbsp;asks_question | 100% | 98% | 100% |
| &nbsp;&nbsp;one_question | 80% | 98% | 100% |
| &nbsp;&nbsp;concise | 100% | 100% | 100% |
| &nbsp;&nbsp;plain_speech | 100% | 90% | 100% |
| &nbsp;&nbsp;no_fix_phrasing | 100% | 100% | 100% |
| &nbsp;&nbsp;refers_to_problem | 100% | 98% | 98% |
| &nbsp;&nbsp;no_direct_fix | 100% | 98% | 100% |
| &nbsp;&nbsp;not_leading | 100% | 76% | 100% |
| Pure question, independent judge (gpt-oss:120b) | 47/50 | 41/50 | 45/50 |
| Median time per reply | 0.63 s | 2.06 s | 2.07 s |
| Mean output tokens | 20 | 19 | 19 |
| Mean words per reply | 16.4 | 15.9 | 15.9 |

## Models

- **gemma4:31b-cloud, deployed prompt**: the duck as it runs today (Ollama cloud)
- **Qwen3.5-4B, untuned**: same model as the tuned one, before training (Tinker)
- **Qwen3.5-4B, fine-tuned**: after supervised fine-tuning on the filtered dialogues (Tinker)

## Read this before quoting the numbers

- Reply time is not like-for-like: the baseline streams from Ollama's cloud and the Qwen runs sample from Tinker's servers.
- The main judge (gemma4:31b-cloud) is the same family as the teacher that wrote the training data, so it may favor that style. A judge from another family (gpt-oss:120b, the row above) is the check. On it the fine-tuned model is level with the deployed Gemma duck within noise, not ahead. Its verdicts also vary slightly between runs.
- So the gains that hold up are: the one-question rule (a code check, no judge involved), and a large improvement over the untuned model of the same size. Against the much larger Gemma duck, the honest claim is equal quality from a 4B model, not better quality.
- One rubric change was made after seeing the baseline, before any tuned model existed: the judge now always runs, so one flaw isn't counted three times. The baseline was re-run under the final rubric.
- 50 prompts is a small sample. A difference of a few points is within noise.
