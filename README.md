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

Seven failure modes, each with a **mechanical check** rather than an instruction
to be careful. Every check is a command, so an agent that ran the skill and one
that merely read it produce different output:

```bash
physis-check all [dirs]      # the whole checklist
physis-check calls Symbol    # rule 1 — non-test call sites only
physis-check sweep [dirs]    # rule 1 — whole tree (Rust/Python/TS/JS/Go)
physis-check discriminate --a '<real arm>' --b '<control arm>'   # rule 2
physis-check map [dirs]      # rule 3/4 — module map
physis-check recall "<task>" # rule 4 — already tried and failed?
physis-check claim "<x>"     # rule 5 — register something refutable
physis-check flow [tx.jsonl] # rule 7 — judge the session itself
```

Engine-backed steps print `NOT MEASURED` when physis-core is absent, rather than
passing quietly.

**1. Declared ≠ called.** Before writing "X works", check the call sites —
excluding the declaring file, and counting tests separately. `OnnxEmbedder` had
seven "call sites" and every one was its own `#[cfg(test)]` module, while every
benchmark number came from a lexical hash. `physis-check calls Symbol [dirs]`,
or `physis-check sweep [dirs]` for the whole tree.

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
column was already thin (+0.058, +0.038). So a prediction was written down
before the next arm ran: **the advantage lives in top-3, not top-1.**

**E54b — the retry regime.** One shot is not how an agent works; it emits,
compiles, retries. Same task, up to 3 compiler-checked attempts, n=15:

| arm | passes within 3 | rate | mean attempts |
|---|---|---|---|
| analogy | 12/15 | **0.800** | 1.33 |
| popularity | 10/15 | 0.667 | 1.10 |
| permuted null | 7/15 | 0.467 | 1.29 |

**+0.133 over popularity**, where one shot gave +0.025. The pre-registered
prediction held.

Honest summary of the pair: at one shot, indistinguishable from guessing the
most-imported module. Given three compiler-checked tries, 80% versus 67%, at a
mean cost of 1.33 attempts. n=15 against n=40, so the retry arm is the weaker
measurement of the two — and on most individual cases both arms emit the *same*
candidate, which is exactly why the one-shot delta was small.

The point of the example is not the engine. It is the shape: a positive, then a
control that tempered it, then a prediction written down *before* the arm that
tested it, then that arm. Each result recorded at the strength it earned —
SUPPORTED, PARTIAL, SUPPORTED-in-one-regime — rather than as the first one's
press release.

</details>

**3. Do not compress a system to one noun.** Three attempts in one session
reduced a 190-module system to a single noun. Each was sharper than the last and
each was wrong. Sharpness is not correctness.

**4. Read the map before grepping; recall before working.**
`physis-check map [dirs]` generates a module map — one line per module from its own
`//!` header. Measured: ~4.4k tokens, and it replaced an inventory that had been
rebuilt by hand three times in one session.

A *symbol* index was also built, measured at ~26k tokens, and deliberately
discarded — it answers what `grep -rn "fn foo"` answers for ~50 tokens against
fresher data. **A wiki page earns its keep only when reading it is cheaper than
the search it replaces.**

**5. Register claims that can be wrong.** `physis-check claim "<x>"`, and
`physis-check verdict "<outcome>" success|inert|failure` when it resolves.

Both halves must hit the same store. physis-pro and physis-core keep separate
graphs, and read different model-path variables (`PHYSIS_MODELS` vs
`PHYSIS_MODEL_DIR`) — so a note can be written under the fallback embedder,
stored, never recallable, and reported as a success. `physis-check` pins both.

**6. Exit 0 is not a result.** An empty result and a check that never ran look
identical. Four times while these scripts were being built: `set -e` ended a
sweep at the first symbol-less file and it read as clean; a shell alias on `ls`
starved a loop of input and it read as "nothing found"; a string-match patch
missed by one trailing space and the script ran without the new check in it; a
mining pipeline parsed 622 events, produced 0 results and exited 0. **Every
measurement prints its denominator**, and these exit 2 rather than call 0-of-0 a
pass.

**7. Judge the session, not only the artifact.** The code can be right and the
reporting still wrong. `physis-check flow [transcript.jsonl]` reads a Claude
Code session, extracts every claim, and flags the ones with no tool call between
them and the previous claim — those came from the model's prior, not from the
repository. With physis-core present it then runs the claims through `chain`,
which reports structure, coverage, drift from the original ask, **and the
label-permuted control in the same pass**.

Measured on two real sessions, against the arm it has to beat — the same rule
with event order shuffled 200 times (`scripts/flow-null.py`):

| session | claims | ungrounded | shuffled null | Δ |
|---|---:|---:|---:|---:|
| 737 events | 28 | 7 (0.250) | 1.3 (0.048) sd 1.19 | **+0.202** |
| 383 events | 13 | 9 (0.692) | 1.0 (0.080) sd 1.01 | **+0.612** |

Chance would flag about one.

The geometry half is scored separately, and on prose it keeps landing at its
null — five corpora, max Δ +0.0007 against a 0.02 bar, several identical to four
decimals. That looks like an invariant statistic but is not one: a corpus whose
topics share no content word returns **Δ +0.0655**, over the bar. The difference
between the two regimes is shared vocabulary, not corpus size. A Δ≈0 therefore
means *this corpus has no grouping the method can find* — read the ungated
halves (structure, compression, unplaced records) and leave the shortlist
alone. Read the control line first — and
the embedder line before that, because `chain` runs happily on the fallback
lexical hash and resolves its model path relative to the current directory, so
the same command is semantic in one directory and a hash in another with no
error either way. The tool that judges is subject to rule 1 too.

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

- `declared-never-called.sh` is textual, not a compiler pass. Trait dispatch,
  macros, decorators and dynamic imports are invisible to it, so **its output is
  a list of questions, not verdicts.** It covers Rust, Python, TypeScript/JS and
  Go by declaration regex; a language whose call sites are built at runtime will
  defeat it.
- **Its false positives come from scope, not from the regex.** Measured: 55/55
  Go findings true, 28/30 TypeScript findings true — and both misses were
  consumed by a sibling directory outside the swept path. Pass every tree that
  can import the code.
- `physis-check flow` extracts claims by cue list, not by understanding. It
  over-matches ("this fixes nothing" reads as a claim) and misses hedged
  assertions. It prints its denominator so an empty list is visibly an empty
  list rather than a clean bill of health.
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
