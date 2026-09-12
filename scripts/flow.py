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
# Sentences that are plans or questions, not claims about what is.
NOT_CLAIM = re.compile(r"^(let me|i'?ll|i will|should i|next|todo|plan\b|will )", re.I)
# Markup, not prose: table rows, headings, bullets, code fences. A results table
# is evidence being reported, not a claim being made, and letting it through
# floods the list with `| Stage | Result |`. It did, on the first real run.
MARKUP = re.compile(r"^\s*([|>#`\-*]|\d+\.\s)")
EVIDENCE_TOOLS = {  # tools whose result is evidence about this repo
    "Bash", "Read", "Grep", "Glob", "Edit", "Write", "NotebookEdit", "Task", "Agent",
}


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
                for sent in re.split(r"(?<=[.!?\n])\s+", b.get("text", "")):
                    s = sent.strip()
                    if len(s) < 20 or NOT_CLAIM.match(s) or MARKUP.match(s):
                        continue
                    if not CUE.search(s):
                        continue
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
