#!/usr/bin/env python3
"""Score `flow.py`'s claim detector against hand-labelled sentences.

Rule 7 is only as good as what it calls a claim, and that was never measured —
the detector was tuned by reading its output, which is how a narrow cue list
stays narrow. This fixture is 50 sentences taken from real Claude Code
transcripts and labelled by hand: `claim` = an assertion about the repository
that could be false and needs evidence; `not` = a plan, instruction, question,
heading, markup, or change-list entry.

    python3 tests/score-extractor.py            # precision / recall / F1
    python3 tests/score-extractor.py --misses    # also list what it got wrong
    python3 tests/score-extractor.py --holdout   # sentences from another session,
                                                 # labelled after the tuning stopped

The fixture is a sample of one project's sentences, labelled by one judge. It
measures whether a change to the cue list moves the detector; it is not a
population estimate.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.dont_write_bytecode = True
import flow  # noqa: E402


def detects(sentence: str) -> bool:
    """The detector under test is `flow.is_claim` itself — not a copy of it."""
    return flow.is_claim(sentence)


def main() -> int:
    name = "claims-holdout.tsv" if "--holdout" in sys.argv else "claims-fixture.tsv"
    rows = []
    for line in (HERE / name).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        label, sentence = line.split("\t", 1)
        rows.append((label == "claim", sentence))
    if not rows:
        print("0 labelled sentences: nothing was measured")
        return 2

    tp = sum(1 for want, s in rows if want and detects(s))
    fp = sum(1 for want, s in rows if not want and detects(s))
    fn = sum(1 for want, s in rows if want and not detects(s))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    claims = sum(1 for want, _ in rows if want)
    print(f"{len(rows)} labelled sentences ({claims} claims, {len(rows) - claims} not)")
    print(f"precision {precision:.2f}  recall {recall:.2f}  F1 {f1:.2f}   (tp {tp} · fp {fp} · fn {fn})")

    if "--misses" in sys.argv:
        for want, s in rows:
            got = detects(s)
            if want != got:
                print(f"  {'MISSED ' if want else 'FALSE +'} {s[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
