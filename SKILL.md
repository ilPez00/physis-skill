---
name: physis
description: Judge your own work before claiming it is done. Use when working in physis-pro/physis-core, or any time you are about to (a) claim a capability exists, (b) summarise what a system is, (c) quote a benchmark number as evidence, or (d) report a task complete. Also use when the user says "physis", "check yourself", "did you verify", or pushes back on a claim you made.
---

# Physis: judge your own work

Four failure modes, each observed repeatedly, each with a mechanical check.
Run the check. Do not reason about whether the check is needed.

## 1. Declared ≠ called

**A module that compiles and exports is not a module that runs.**

Observed four times in one session, same shape every time:

| symbol | looked like | actually |
|---|---|---|
| `OnnxEmbedder` | production ONNX embedder, exported from `lib.rs` | called by nothing — every benchmark number came from a lexical hash |
| `FitnessShifted`, `OutcomeObserved` | audit event types | emitted by no code path; `replay` disagreed with `list` |
| structural classifier | classified into `DOMAIN×MODE` | built its own random-projection embedder — symbol sequences were noise with a schema |
| `build_structural` ← `ledger` | trace-fed n-gram tables | both halves exist, join absent |

**Before writing "X works" / "X is wired" / "the system does X":**

```bash
grep -rn "SymbolName" --include='*.rs' <src dirs> | grep -v "src/<defining_file>"
```

Zero hits outside the defining file ⇒ **it does not run.** Say so.

Repo-wide sweep (ships with this skill):

```bash
~/.claude/skills/physis/scripts/declared-never-called.sh [dirs]
```

Its output is a list of questions, not verdicts — trait dispatch and macros are
invisible to it. Written for Rust; the pattern generalises, the regex does not.

## 2. Does the measurement discriminate?

**A benchmark whose score does not move when the thing it measures moves is not
a benchmark.**

`physis-core/benchmarks/ground-truth` scores *identically* under a random
projection hash and a real ONNX model: repeat 100%, anomaly 100%, contradiction
50%, compression ~24% either way. It cannot fail, so it is not evidence.

**Before quoting any number as evidence:** name the arm it would lose to. Run
both arms. If the difference is ~0, the number says nothing.

Working instrument (in the physis-pro tree): `benchmarks/retrieval/run.py
--arms rp,semantic` — prints `DISCRIMINATION: semantic - rp` and says outright
when it is zero. Outside that tree, build the two arms by hand; the discipline
is the point, not the script.

Standing rule, earned seven times in this repo's research track:
**treat any positive as an artifact until a construction-matched control says
otherwise.**

## 3. Do not compress a system to one noun

Three attempts in one session reduced physis to a single noun. All three wrong:
"context compiler" (one operation of six), "epistemic ledger" (a second of six),
"70-symbol vocabulary" (it is **70 tables with subtables**).

Each sounded sharper than the last. Sharpness is not correctness.

**Before summarising any large system:** generate its module map
(`~/.claude/skills/physis/scripts/gen-wiki.sh`) and read that. Describe the
system **structurally** — its coordinate system and the operations over it —
never as one noun. In a physis tree, `docs/WHAT_PHYSIS_IS.md` is the canonical
version.

Specific trap: **`judge` is not `propose`.** The research track refuted
*certification* (does this belong here → chance). It did **not** refute
*proposal* (which few should a person look at → top-3 0.712 vs null 0.136).
Writing "the grid is not a discovery mechanism" is the error this rule exists
to prevent.

## 4. Read before grepping; recall before working

A module map — one line per module, taken from each module's own `//!` header —
answers "which module does X" in one read. Three separate times an agent rebuilt
that inventory by hand at real token cost because it was not on disk.
**Generate it once, read it first:**

```bash
~/.claude/skills/physis/scripts/gen-wiki.sh
```

Measured on physis-pro: the map is ~4.4k tokens and pays for itself immediately.
A full *symbol* index was also built and measured — 3996 lines, ~26k tokens —
and deliberately discarded: it answers exactly what `grep -rn "fn foo"` answers
for ~50 tokens against fresher data. **A wiki page earns its keep only when
reading it is cheaper than the search it replaces.**

Then recall before working — has this been tried and already failed?

```bash
physis-core node-search "<task>"       # verdict -1 = tried, failed. Read it first.
# ... work ...
physis-core note "<outcome>" --verdict -1|0|1
```

In a physis-pro tree these are `just recall` / `just dev-loop`
(`docs/PHYSIS_DEV_LOOP.md`).

MCP (30 tools, `.mcp.json`): `physis_recall` → `physis_pack` / `physis_find` →
`physis_classify` → `physis_remember` + `physis_serve`.

Needs a dev licence signed for *this* build — the gate verifies signatures even
in dev builds:

```bash
(cd physis-dev-license && cargo run -q) > "$PHYSIS_DATA_DIR/license.key"
```

## 5. Register claims that can be wrong

A claim worth making is worth recording so it can be refuted later:

```bash
physis-core hypothesis create "<claim>" --confidence 0.6
physis-core hypothesis evidence <id> "<measurement>" --polarity contradicting --weight 0.9
physis-core hypothesis transition <id> Contradicted --reason "<control that killed it>"
physis-core replay --subject <full-uuid> --at <ISO8601>   # belief state at T
physis-core hypothesis open                                # predictions never resolved
```

This is how a 7-day-old hypothesis about retrieval was found already predicting
a finding being independently rediscovered from scratch.

**Known defect:** `list`/`explain` report a status *derived* from fitness while
`replay` reconstructs it from the event log, and they disagree. See
`packets/PH-017`. Do not cite `replay` as authoritative until that closes.

## The checklist

Before reporting work done:

- [ ] Every capability I claimed — grepped for call sites?
- [ ] Every number I quoted — does its benchmark discriminate?
- [ ] Every summary I wrote — structural, not one noun?
- [ ] `judge` vs `propose` kept distinct?
- [ ] Anything I could not verify — labelled `NOT MEASURED`, not implied?
- [ ] Outcome recorded with a verdict?
