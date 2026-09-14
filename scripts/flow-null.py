"""Control for `physis-check flow`: if claim/tool adjacency in a transcript were
random, how many claims would the detector flag as ungrounded anyway?

Shuffles the sequence of (claim, tool-call) events while preserving the counts
of each, then re-runs the same adjacency rule. If the real rate does not beat
the shuffled rate, the detector is reporting sequence shape, not grounding.
"""
import json, random, re, statistics, sys
sys.dont_write_bytecode = True  # never leave __pycache__ in the installed skill dir
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import flow

tx = sys.argv[1]
kinds = []  # "C" = claim sentence, "T" = evidence tool call, in order
for line in open(tx, encoding="utf-8", errors="replace"):
    try: rec = json.loads(line)
    except Exception: continue
    kind = rec.get("type")
    if kind not in ("user", "assistant"): continue
    for b in flow.blocks(rec.get("message", {})):
        t = b.get("type")
        if t == "tool_result" or (t == "tool_use" and b.get("name") in flow.EVIDENCE_TOOLS):
            kinds.append("T")
        # Claims come from assistant text only, exactly as flow.py counts them.
        # Counting user text too gave this control twice as many claims as the
        # arm it is the control for (10 against 5 on the same transcript), and a
        # control that scores a different population is not a control.
        elif t == "text" and kind == "assistant":
            for s in re.split(r"(?<=[.!?\n])\s+", b.get("text", "")):
                s = s.strip()
                if len(s) >= 20 and not flow.NOT_CLAIM.match(s) and not flow.MARKUP.match(s) \
                   and flow.CUE.search(s):
                    kinds.append("C")

def ungrounded(seq):
    n, tools = 0, 0
    for k in seq:
        if k == "T": tools += 1
        else:
            if tools == 0: n += 1
            tools = 0
    return n

claims = kinds.count("C")
real = ungrounded(kinds)
null = []
for _ in range(200):
    s = kinds[:]; random.shuffle(s)
    null.append(ungrounded(s))
m = statistics.mean(null)
print(f"claims={claims} tools={kinds.count('T')}")
print(f"real ungrounded      = {real}/{claims} ({real/claims:.3f})")
print(f"shuffled null (n=200)= {m:.1f}/{claims} ({m/claims:.3f})  sd={statistics.stdev(null):.2f}")
print(f"DISCRIMINATION: null - real = {(m-real)/claims:+.3f}")
