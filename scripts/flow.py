#!/usr/bin/env python3
"""Extract an agent's claims from a session transcript and check each one for
adjacent evidence.

The premise: a claim is cheap and a tool call is not. If an agent wrote "the
embedder is wired" and made no tool call between that sentence and its previous
claim, nothing in the session grounds it — the sentence came from the model's
prior, not from the repository. That is checkable with no model at all.

Writes, into <workdir>:
  events, total, unsupported   counts (denominators — rule 6)
  ask                          the first human request, for the drift query
  unsupported.txt              the ungrounded claims, verbatim
  claims/NNN.md                one file per claim, a corpus for `physis-core chain`

ponytail: cue-list extraction, not NLU. It over-matches ("this fixes nothing"
reads as a claim) and under-matches hedged assertions. Deliberately: the output
is a list to read, and the denominator is printed so an empty list is visibly
an empty list rather than a clean bill of health.
"""
import json
import re
import sys
from pathlib import Path

# Words that turn a sentence into an assertion about the world that could be
# false. Kept narrow: every addition here trades precision for recall, and a
# noisy list gets skimmed.
CUE = re.compile(
    r"\b(works?|working|wired|fixed|passes|passed|complete[ds]?|done|verified|"
    r"confirmed|implemented|now \w+s|successful(ly)?|resolved|ready|"
    r"is correct|are correct|no longer|all tests?)\b",
    re.I,
)
# The completion words above are only half of what an agent asserts. Measured
# against tests/claims-fixture.tsv, that half alone caught 2 of 30 hand-labelled
# claims — recall 0.07 at precision 1.00, which is a detector that agrees with
# you rather than one that checks you. The two patterns below carry most of the
# rest: a quantity about the repository, and a verb that reports what some part
# of it does.
MEASUREMENT = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:tokens?|files?|lines?|bytes?|nodes?|records?|"
    r"modules?|tests?|commits?|ms\b|%|x\b)|"          # 43 tokens, 11 files, 1.8x
    r"\b\d+\s*/\s*\d+\b|"                          # 11/11, 3/6
    r"\b\d+(?:[.,]\d+)?\s*(?:vs\.?|against)\s*\d+|"  # 6051 vs 14179
    r"\b\d+\s*(?:->|→|to)\s*\d+\b",                   # 4648 to 1507
    re.I,
)
# Third person, indicative: a report about behaviour, not an intention to act.
# Deliberately excludes the first person ("I ran …") and the imperative ("run
# …"), which are narration and instruction rather than claims.
REPORTS = re.compile(
    r"\b(costs?|returns?|prints?|reports?|records?|ranks?|skips?|hides?|"
    r"contains?|holds?|beats?|loses?|exceeds?|outranks?|blocked|refuses?|"
    r"produced|repeats?|requires?|means?|became|flipped|bought|"
    r"renders?|shows?|fails?|breaks?|drops?|misses?|recorded|rewritten|"
    r"is (?:a|an|the|not|still)|are (?:a|an|the|not|still)|"
    r"was (?:a|an|the|not|still)|"
    r"has \d|have \d|had \d)\b",
    re.I,
)
# Sentences that are plans or questions, not claims about what is.
NOT_CLAIM = re.compile(
    r"^(let me|i'?ll|i will|should i|next\b|todo|plan\b|will |"
    # Imperatives. "Take the neighbour", "Verify at …", "Run the benchmark" are
    # instructions to someone, and an instruction cannot be false.
    r"(take|verify|run|use|see|add|keep|consider|check|install|read|open|try)\s)",
    re.I,
)
# Markup, not prose: table rows, headings, bullets, code fences. A results table
# is evidence being reported, not a claim being made, and letting it through
# floods the list with `| Stage | Result |`. It did, on the first real run.
# Table rows, headings, quotes and fences are evidence being displayed, not
# claims being made. A *bullet* is different: most of what an agent asserts
# about a repository it asserts in a list, and dropping every line starting `-`
# cost 12 of the 30 fixture claims on its own. Bullets are kept; their marker is
# stripped before the cue match so `- costs 43 tokens` reads as prose.
# A single backtick starts *inline code*, and an agent's claims routinely start
# with the thing they are about: "`list --limit 100` went from 4648 to 1735
# tokens" was dropped as markup. Only a real fence (three backticks) is markup.
MARKUP = re.compile(r"^\s*([|>#]|```|\d+\.\s)")
BULLET = re.compile(r"^\s*[-*+]\s+")
EVIDENCE_TOOLS = {  # tools whose result is evidence about this repo
    "Bash", "Read", "Grep", "Glob", "Edit", "Write", "NotebookEdit", "Task", "Agent",
}


def sentences(text):
    """Split a text block the way both the detector and its control must."""
    return re.split(r"(?<=[.!?\n])\s+", text or "")


def is_claim(sentence: str) -> bool:
    """One definition of a claim, shared by `flow.py`, `flow-null.py` and the
    scorer.

    It lived in three places and drifted twice: the control once counted user
    text the arm never saw (10 claims against 5), and a later widening of the
    cues reached the arm only (55 against 18). A control that scores a different
    population is not a control, so there is exactly one function now.
    """
    s = BULLET.sub("", (sentence or "").strip())
    if len(s) < 20 or NOT_CLAIM.match(s) or MARKUP.match(s):
        return False
    if s.endswith(":"):
        return False
    return bool(CUE.search(s) or MEASUREMENT.search(s) or REPORTS.search(s))


def blocks(msg):
    c = (msg or {}).get("content")
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return c if isinstance(c, list) else []


def main() -> int:
    tx, work = Path(sys.argv[1]), Path(sys.argv[2])
    (work / "claims").mkdir(parents=True, exist_ok=True)

    events = 0
    first_ask = ""
    tools_since_claim = 0
    claims = []  # (text, tools_seen_before_it)

    for line in tx.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = rec.get("type")
        if kind not in ("user", "assistant"):
            continue
        events += 1
        msg = rec.get("message", {})

        if kind == "user":
            for b in blocks(msg):
                if b.get("type") == "tool_result":
                    tools_since_claim += 1
                elif b.get("type") == "text" and not first_ask:
                    # origin.kind == human excludes tool output replayed as user turns
                    if rec.get("origin", {}).get("kind", "human") == "human":
                        first_ask = b["text"].strip()
            if isinstance(msg.get("content"), str) and not first_ask:
                first_ask = msg["content"].strip()
            continue

        for b in blocks(msg):
            if b.get("type") == "tool_use":
                if b.get("name") in EVIDENCE_TOOLS:
                    tools_since_claim += 1
            elif b.get("type") == "text":
                for sent in sentences(b.get("text", "")):
                    if not is_claim(sent):
                        continue
                    s = BULLET.sub("", sent.strip())
                    claims.append((s, tools_since_claim))
                    tools_since_claim = 0

    unsupported = [s for s, n in claims if n == 0]
    for i, (s, n) in enumerate(claims):
        # >40 chars or physis-core's corpus loader skips the file.
        (work / "claims" / f"{i:04d}.md").write_text(
            f"# claim {i} (evidence events before it: {n})\n\n{s}\n", encoding="utf-8"
        )
    (work / "events").write_text(str(events))
    (work / "total").write_text(str(len(claims)))
    (work / "unsupported").write_text(str(len(unsupported)))
    (work / "ask").write_text(first_ask.replace("\n", " ")[:200])
    (work / "unsupported.txt").write_text("\n".join(unsupported), encoding="utf-8")
    return 0


def demo():
    """Self-check: a grounded claim and an ungrounded one, one of each."""
    import tempfile

    rows = [
        {"type": "user", "message": {"role": "user", "content": "make the embedder real"}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Let me look at the file first."},          # plan, not claim
            {"type": "tool_use", "name": "Bash", "input": {}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "The ONNX embedder is wired and every call site resolves."}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "The benchmark passes on all four arms as well."},
            {"type": "text", "text": "| stage | PASSED |"}]}},   # markup, not a claim
    ]
    with tempfile.TemporaryDirectory() as d:
        tx = Path(d) / "t.jsonl"
        tx.write_text("\n".join(json.dumps(r) for r in rows))
        w = Path(d) / "w"
        sys.argv = ["flow.py", str(tx), str(w)]
        main()
        assert (w / "total").read_text() == "2", (w / "total").read_text()
        # first claim had a tool_use + tool_result behind it; second had nothing
        assert (w / "unsupported").read_text() == "1", (w / "unsupported").read_text()
        assert "benchmark passes" in (w / "unsupported.txt").read_text()
        assert (w / "ask").read_text() == "make the embedder real"
        assert len(list((w / "claims").glob("*.md"))) == 2
    print("flow.py self-check OK")


if __name__ == "__main__":
    sys.exit(demo() if "--demo" in sys.argv else main())
