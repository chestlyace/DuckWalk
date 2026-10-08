"""The rubric for a good Socratic duck reply. Written before any training data or eval run existed.

Eight pass/fail criteria per reply. Six are deterministic code. Two come from an LLM judge,
because "does this hand over a solution?" can't be decided by regex.

    asks_question      the reply ends with a question mark
    one_question       exactly one question mark
    concise            at most 30 words (the prompt asks for 25, so a little slack)
    plain_speech       nothing that can't be spoken: no backticks, markdown, lists, URLs
    no_fix_phrasing    no "you should", "try X", "the problem is", "the fix is" and similar
    refers_to_problem  shares at least one content word with what the developer just said or the summary
    no_direct_fix      judge: the reply does not state a cause or tell them what to change
    not_leading        judge: the question is not a fix in disguise ("What if you added a retry?")

Scoring: score = criteria passed / 8. all_pass = every criterion passed.
Limitation: the judge is an LLM from the same family as the teacher that writes the training data,
so it may be lenient toward that style. The six deterministic criteria carry no such bias.
"""

import json
import re
from dataclasses import dataclass

CRITERIA = ["asks_question", "one_question", "concise", "plain_speech", "no_fix_phrasing",
            "refers_to_problem", "no_direct_fix", "not_leading"]
DETERMINISTIC = CRITERIA[:6]
MAX_WORDS = 30

_STOPWORDS = set("""about above after again against also because been before being below between both could does doing down during each
from further have having here into just more most only other over same should some such than that their them then there these they this those
through under until very were what when where which while will with would your you're it's don't that's i'm i've i'd""".split())
_FIX_OPENERS = re.compile(r"^\s*(try|use|change|add|replace|set|make sure|just|simply|run|install|update|remove|delete|check that you)\b", re.I)
_FIX_PHRASES = re.compile(
    r"\b(you should|you need to|you must|you could just|you can just|the fix is|the problem is|the issue is|the cause is|"
    r"it'?s because|this is because|that'?s because|the solution is|what you want is|you have to)\b", re.I)
_NOT_SPEAKABLE = re.compile(r"[`*#>_|]|https?://|\n\s*[-\d]+[.)]?\s|\w+\(\)|\w+\.\w+\(")


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def content_words(text: str) -> set[str]:
    return {w for w in words(text) if len(w) >= 4 and w not in _STOPWORDS}


def check_deterministic(reply: str, context: str) -> dict[str, bool]:
    """`context` is the developer's latest message plus the summary the duck was given."""
    reply = reply.strip()
    return {
        "asks_question": reply.endswith("?"),
        "one_question": reply.count("?") == 1,
        "concise": len(words(reply)) <= MAX_WORDS,
        "plain_speech": not _NOT_SPEAKABLE.search(reply),
        "no_fix_phrasing": not (_FIX_OPENERS.search(reply) or _FIX_PHRASES.search(reply)),
        "refers_to_problem": bool(content_words(reply) & content_words(context)),
    }


JUDGE_PROMPT = """You are grading a rubber-duck debugging assistant. A developer is talking through a bug out loud. The duck must only ask questions that help the developer think. It must never hand over a solution.

Classify the duck's reply as exactly one of:
- "asks_only": it asks a genuinely open question about what the developer knows, saw, expected, ruled out, or could test. It names no cause and suggests no change.
- "leading": it is phrased as a question but effectively proposes the cause or the fix. Example: "What happens if you wrap that call in a retry?" or "Could the float discount be introducing the precision error?" when the developer never suggested that.
- "gives_fix": it states a cause, a fix, a command, or tells the developer what to do.

Asking the developer which of THEIR OWN stated ideas to test first is "asks_only". Repeating their idea back as a question is "asks_only". Introducing a new idea of the duck's own is "leading".

Developer's problem summary:
{summary}

Conversation so far:
{conversation}

Duck's reply to grade:
{reply}

Answer with JSON only: {{"verdict": "asks_only" | "leading" | "gives_fix", "reason": "<one short sentence>"}}"""


@dataclass
class Grade:
    passed: dict[str, bool]
    verdict: str
    reason: str

    @property
    def score(self) -> float:
        return sum(self.passed.values()) / len(CRITERIA)

    @property
    def all_pass(self) -> bool:
        return all(self.passed.values())


def parse_verdict(text: str) -> tuple[str, str]:
    """Pull the judge's JSON out of its answer, which may be wrapped in code fences. Unparseable = gives_fix (fail safe)."""
    match = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(match.group(0))
        verdict = data.get("verdict", "")
        if verdict in ("asks_only", "leading", "gives_fix"):
            return verdict, str(data.get("reason", ""))[:200]
    except (AttributeError, json.JSONDecodeError):
        pass
    return "gives_fix", "judge answer could not be parsed"


def format_conversation(turns: list[dict]) -> str:
    return "\n".join(f"{'Duck' if t['role'] == 'duck' else 'Developer'}: {t['text']}" for t in turns) or "(walk just started)"


def grade(reply: str, turns: list[dict], summary: str, judge, always_judge: bool = False) -> Grade:
    """Grade one duck reply. `judge(prompt) -> str` calls the judge model.

    Data generation (always_judge=False) skips the judge once a deterministic criterion has failed, since such a
    reply is rejected anyway; its two judge criteria then count as failed. Evaluation uses always_judge=True so a
    single flaw (say, two question marks) is not also counted against the two judge criteria."""
    last_user = next((t["text"] for t in reversed(turns) if t["role"] == "you"), "")
    passed = check_deterministic(reply, f"{last_user} {summary}")
    if always_judge or all(passed.values()):
        prompt = JUDGE_PROMPT.format(summary=summary, conversation=format_conversation(turns), reply=reply)
        verdict, reason = parse_verdict(judge(prompt))
    else:
        verdict, reason = "not_judged", "failed a deterministic criterion"
    passed["no_direct_fix"] = verdict in ("asks_only", "leading")
    passed["not_leading"] = verdict == "asks_only"
    return Grade(passed=passed, verdict=verdict, reason=reason)
