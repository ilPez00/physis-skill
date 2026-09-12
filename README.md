# physis — an agent skill for judging your own work

An agent skill that makes an assistant check its claims before making them,
plus the [physis-core](https://github.com/ilPez00/physis-core) engine it records
those claims in.

It exists because of a measured pattern, not a theory. In one working session an
agent made four capability claims about a codebase. All four were wrong in the
same way: **the code was declared, exported, compiled — and called by nothing.**

| symbol | looked like | actually |
|---|---|---|
| `OnnxEmbedder` | production ONNX embedder, exported from `lib.rs` | called by nothing; every benchmark number came from a lexical hash |
| `FitnessShifted`, `OutcomeObserved` | audit event types | emitted by no code path; `replay` silently disagreed with `list` |
| structural classifier | classified into a 70-cell grid | built its own random-projection embedder — the symbol stream was noise with a schema |
| `build_structural` ← `ledger` | trace-fed n-gram tables | both halves present, join absent |

A module that compiles and exports is not a module that runs.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ilPez00/physis-skill/main/install.sh | bash
```

Or from a clone: `./install.sh`. Flags: `--skill-only` (rules, no engine),
`--rev <branch-or-sha>` (pin physis-core).

Installs the skill to `~/.claude/skills/physis/` and `physis-core` via
`cargo install`. Needs a Rust toolchain for the engine; `--skill-only` does not.

## What it does

Four failure modes, each with a **mechanical check** rather than an instruction
to be careful:

**1. Declared ≠ called.** Before writing "X works", grep for call sites.
Repo sweep: `~/.claude/skills/physis/scripts/declared-never-called.sh [dirs]`.

**2. Does the measurement discriminate?** A benchmark whose score does not move
when the thing it measures moves is not a benchmark. The reference case: a
structure benchmark scored *identically* under a random-projection hash and a
real sentence transformer — repeat 100%, anomaly 100%, compression ~24% either
way. It could not fail, so it was not evidence. Before quoting a number, name
the arm it would lose to, then run both.

<details>
<summary><b>Worked example — a positive, then the control that tempered it</b></summary>

A symbolic analogy engine had never been measured. Two experiments, both built
so they could lose:

**E53 — ranking.** Link prediction over a real dependency graph, top-3:

| corpus | analogy | popularity | permuted null | random |
|---|---|---|---|---|
| n=86 | **0.500** | 0.337 | 0.209 | 0.151 |
| n=294 | **0.446** | 0.303 | 0.256 | 0.061 |

The null is a *degree-preserving* shuffle: both degree sequences survive, so
popularity is unchanged by construction and only the pairing dies. Analogy beat
it by +0.291 / +0.189. The check that made it credible: on the permuted graph
analogy **lost** to popularity on both corpora — the arms behaving as designed,
rather than all drifting together the way an artifact does.

**E54 — generation, judged by a compiler.** Delete a load-bearing import, verify
the build goes red, have the method supply the missing module, run `cargo check`.
Binary, external, no partial credit:

| arm | gate passes | rate |
|---|---|---|
| analogy | 16/40 | 0.400 |
| popularity | 15/40 | 0.375 |
| permuted null | 10/40 | 0.250 |

**+0.150 over the null, +0.025 over popularity.** The structure survived the
harsher test. The advantage over the trivial baseline did not.

That +0.025 was *predictable from E53* — its headline was top-3, but its top-1
column was already thin (+0.058, +0.038). E54 scores top-1. The advantage lives
in top-3, not top-1.

The point of the example is not the engine. It is that **the second experiment
was run at all**, and that its result is recorded as PARTIAL rather than as the
first one's press release.

</details>

**3. Do not compress a system to one noun.** Three attempts in one session
reduced a 190-module system to a single noun. Each was sharper than the last and
each was wrong. Sharpness is not correctness.

**4. Read the map before grepping; recall before working.**
`scripts/gen-wiki.sh` generates a module map — one line per module from its own
`//!` header. Measured: ~4.4k tokens, and it replaced an inventory that had been
rebuilt by hand three times in one session.

A *symbol* index was also built, measured at ~26k tokens, and deliberately
discarded — it answers what `grep -rn "fn foo"` answers for ~50 tokens against
fresher data. **A wiki page earns its keep only when reading it is cheaper than
the search it replaces.**

## Recording claims so they can be refuted

```bash
physis-core hypothesis create "<claim>" --confidence 0.6
physis-core hypothesis evidence <id> "<measurement>" --polarity contradicting
physis-core hypothesis transition <id> Contradicted --reason "<the control>"
physis-core replay --subject <uuid> --at <ISO8601>   # belief state at T
physis-core hypothesis open                           # predictions never resolved
```

The point is not the storage. It is that a claim you wrote down last week comes
back with its evidence attached, so the next session does not rediscover it from
scratch — and a prediction you made comes back unresolved until you score it.

## Honest limits

- `declared-never-called.sh` is textual, not a compiler pass. Trait dispatch and
  macro use are invisible to it, so **its output is a list of questions, not
  verdicts.** It is written for Rust; the pattern generalises, the regex does not.
- It had two bugs while being written. `--include` placed after `--` made grep
  read the flag as a filename (15 false positives); a missing `|| true` under
  `set -e` ended a sweep at the first symbol-less file and reported 24 items
  where the full run finds 403 — with no sign of truncation in the output. Both
  are comments in the source now. A tool built to catch *looks-fine-but-isn't*
  was itself looks-fine-but-isn't.
- `physis-core hypothesis list` reports a status derived from fitness while
  `replay` reconstructs it from the event log, and **they can disagree.** Do not
  cite `replay` as authoritative until that is fixed.
- Installing without `--features embed-onnx`, or with no model weights on disk,
  resolves the embedder to random projection. That is a lexical hash: it fails
  the semantic self-test by design and says so on stderr. The installer sets the
  feature; the weights are yours to supply.

## Licence

Apache-2.0, matching physis-core.

## Support

If this saved you a debugging session: <https://praxisweb.xyz/me>
