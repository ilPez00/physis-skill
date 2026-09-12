#!/usr/bin/env bash
# Find public items that are declared, exported, and called by nothing.
#
# This defect class bit four times in one session, every time the same shape:
#   - OnnxEmbedder          exported from lib.rs, called by nothing.
#                           Every benchmark number came from a lexical hash.
#   - FitnessShifted        declared in the event enum, emitted by no path.
#     OutcomeObserved       replay disagreed with `hypothesis list` (PH-017).
#   - structural classifier built its own RandomProjectionEmbedder::new(64),
#                           so DOMAIN×MODE sequences were noise with a schema.
#   - build_structural      never joined to ledger.rs — both halves, no join.
#
# A module that compiles and exports is not a module that runs. Run this before
# claiming a capability exists.
#
# Usage: declared-never-called.sh [dir ...]        (default: the current tree)
#        LANGS=rust,python ... to restrict the languages scanned.
#
# ponytail: textual, not a compiler pass. It counts `name` occurrences outside
# the defining file, so trait-method dispatch, macro use, decorator registries,
# and dynamic dispatch read as calls it cannot see. Deliberately: it must never
# be trusted as proof a thing IS used — only as a list of things to go look at.
# Zero hits is a question, not a verdict.
set -Eeuo pipefail

DIRS=("${@:-.}")

# One row per language: ext-glob | declaration regex | field holding the name.
# Keep these conservative. A regex that over-matches produces a long list of
# false questions, and a long list of questions gets skimmed, which is the same
# as not running the check at all.
langs_rust='*.rs|^[[:space:]]*pub (fn|struct|enum|trait|const) [A-Za-z_][A-Za-z0-9_]*'
langs_python='*.py|^(def|class) [A-Za-z_][A-Za-z0-9_]*'
langs_ts='*.ts|^export (default )?(async )?(function|class|const|interface|type) [A-Za-z_][A-Za-z0-9_]*'
langs_tsx='*.tsx|^export (default )?(async )?(function|class|const|interface|type) [A-Za-z_][A-Za-z0-9_]*'
langs_js='*.js|^export (default )?(async )?(function|class|const) [A-Za-z_][A-Za-z0-9_]*'
langs_go='*.go|^(func|type) [A-Z][A-Za-z0-9_]*'

WANT="${LANGS:-rust,python,ts,tsx,js,go}"

# Names too generic to be evidence of anything, or conventionally called by the
# language/framework rather than by our code.
# Test functions are invoked by the runner by name, so they are uncalled by
# construction — the same category as `main`. Measured on a 390-file Go tree:
# 1180 of 1235 findings were `TestXxx` in `_test.go`. A list that is 96% noise
# gets skimmed, which is the same as not running the check.
SKIP='^(new|default|from|fmt|len|is_empty|clone|get|set|run|id|next|into|drop|main|init|setup|test|__init__|toString|render|index|type|Props|State|String|Error|Config|Options|Result|Test.*|Benchmark.*|Fuzz.*|Example.*)$'

TMP="$(mktemp)"; SCANNED="$(mktemp)"; trap 'rm -f "$TMP" "$SCANNED"' EXIT

for lang in ${WANT//,/ }; do
  eval "row=\${langs_${lang}:-}"
  [ -n "$row" ] || { echo "unknown language: $lang" >&2; continue; }
  glob="${row%%|*}"; decl="${row#*|}"

  files=$(find "${DIRS[@]}" \( -name node_modules -o -name target -o -name .git \
          -o -name dist -o -name build -o -name vendor -o -name __pycache__ \
          -o -name .venv -o -name tests -o -name __tests__ -o -name spec \) -prune \
          -o -name "$glob" -type f -print 2>/dev/null \
          | grep -vE '_test\.|\.test\.|\.spec\.|(^|/)test_[^/]*$' | sort) || true
  [ -n "$files" ] || continue
  echo "-- $lang ($(printf '%s\n' "$files" | wc -l | tr -d ' ') files)"
  printf '%s\n' "$files" >> "$SCANNED"

  printf '%s\n' "$files" | while read -r f; do
    # Every stage needs `|| true`: grep exits 1 on no match, and under
    # `set -e` + `pipefail` the first header-less or symbol-less file ends the
    # whole sweep silently. It did — the first run stopped at `batch_csv.rs`
    # and looked like a complete result.
    { grep -hoE "$decl" "$f" 2>/dev/null \
      | awk '{print $NF}' | sort -u | grep -Ev "$SKIP" || true; } | while read -r sym; do
      [ -z "$sym" ] && continue
      # `--include` MUST precede `--`, or `--` ends option parsing and the flag
      # is taken as a filename — which silently makes every symbol look
      # uncalled. This check reported 15 false positives that way.
      hits=$(grep -rlF --include="$glob" -- "$sym" "${DIRS[@]}" 2>/dev/null \
             | grep -vxF -- "$f" | wc -l | tr -d ' ') || hits=0
      if [ "${hits:-0}" = "0" ]; then
        printf '  %-34s %s\n' "$sym" "$f"
        echo x >> "$TMP"
      fi
    done
  done
done

echo
# Rule 6: print the denominator. An empty result and a result that never ran
# look identical otherwise — and both exit 0.
files_seen=$(wc -l < "$SCANNED" | tr -d ' ')
if [ "$files_seen" = "0" ]; then
  echo "NO FILES SCANNED in: ${DIRS[*]} (langs: $WANT)"
  echo "This is not a clean result. Check the paths and LANGS before believing it."
  exit 2
fi
if [ -s "$TMP" ]; then
  echo "$(wc -l < "$TMP" | tr -d ' ') item(s) over $files_seen file(s). Each line is a"
  echo "QUESTION, not a defect: confirm by reading before acting. Trait dispatch,"
  echo "macros, decorators and dynamic imports are invisible here, so a listed"
  echo "item may still be reached."
else
  echo "no declared-never-called items found over $files_seen file(s)"
fi
