#!/usr/bin/env bash
# Install the physis self-judgement skill, and the physis-core engine it uses.
#
#   curl -fsSL https://raw.githubusercontent.com/ilPez00/physis-skill/main/install.sh | bash
#   # or, from a clone:
#   ./install.sh [--skill-only] [--rev <git-rev>]
set -Eeuo pipefail

REPO_URL="https://github.com/ilPez00/physis-core"
# master now carries `embed::select` (fast-forwarded 2026-09-12). Before that it
# was 43 commits behind, and a build from it resolved the embedder to a lexical
# hash unconditionally — the exact defect this skill teaches you to check for.
# Override with PHYSIS_CORE_REV to pin a branch or sha.
REV="${PHYSIS_CORE_REV:-master}"
SKILL_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/physis"
SKILL_ONLY=0

while (($#)); do
  case "$1" in
    --skill-only) SKILL_ONLY=1; shift ;;
    --rev) REV="$2"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1. the skill ────────────────────────────────────────────────────────────
say "installing skill to $SKILL_DIR"
mkdir -p "$SKILL_DIR/scripts"
if [ -f "$SRC/SKILL.md" ]; then
  cp "$SRC/SKILL.md" "$SKILL_DIR/SKILL.md"
  cp "$SRC"/scripts/*.sh "$SRC"/scripts/*.py "$SKILL_DIR/scripts/"
else
  # curl|bash path: no clone on disk, fetch the files directly.
  RAW="https://raw.githubusercontent.com/ilPez00/physis-skill/main"
  curl -fsSL "$RAW/SKILL.md" -o "$SKILL_DIR/SKILL.md"
  for f in declared-never-called.sh gen-wiki.sh physis-check.sh flow.py flow-null.py; do
    curl -fsSL "$RAW/scripts/$f" -o "$SKILL_DIR/scripts/$f"
  done
fi
chmod +x "$SKILL_DIR"/scripts/*.sh "$SKILL_DIR"/scripts/*.py

# SKILL.md writes every check as `physis-check <sub>`, so that has to BE a
# command. Without this the skill documents 16 invocations of something that
# answers "command not found" — a capability declared and never callable, which
# is the defect the skill's own rule 1 exists to catch.
BIN_DIR="${PHYSIS_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"
ln -sf "$SKILL_DIR/scripts/physis-check.sh" "$BIN_DIR/physis-check"
case ":$PATH:" in
  *":$BIN_DIR:"*) say "physis-check -> $BIN_DIR/physis-check" ;;
  *) echo "note: $BIN_DIR is not on PATH; run the checks as $SKILL_DIR/scripts/physis-check.sh" >&2 ;;
esac
# Rule 6: prove what was installed runs, rather than trusting that cp exited 0.
if python3 "$SKILL_DIR/scripts/flow.py" --demo >/dev/null 2>&1; then
  say "skill installed ($(find "$SKILL_DIR"/scripts -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) | wc -l | tr -d ' ') scripts, self-check passed)"
else
  echo "warning: flow.py self-check failed — 'physis-check flow' will not work" >&2
fi

if [ "$SKILL_ONLY" = "1" ]; then
  say "done (--skill-only). The checks that need the engine will not run."
  exit 0
fi

# ── 2. the engine ───────────────────────────────────────────────────────────
if ! command -v cargo >/dev/null 2>&1; then
  cat >&2 <<'EOF'
cargo not found. physis-core is a Rust crate; install a toolchain first:
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
Then re-run, or re-run with --skill-only to take the rules without the engine.
EOF
  exit 1
fi

say "installing physis-core from $REPO_URL @ $REV"
say "(a release build of an ONNX-linking crate takes a while; this is normal)"
# `embed-onnx` is NOT a default feature. Without it `embed::select` has no ONNX
# candidates to try and always resolves to random projection — a lexical hash
# that fails the semantic self-test by design. Installing without this flag
# would ship the exact defect rule 1 exists to catch.
#
# The feature only adds the *capability*: with no model weights on disk the
# cascade still falls back to random projection, and says so on stderr.
FEATURES="cli,embed-onnx"

# `--branch` for a branch, `--rev` for a sha. Try branch, fall back to rev.
if ! cargo install --git "$REPO_URL" --branch "$REV" --features "$FEATURES" --locked physis-core 2>/dev/null; then
  cargo install --git "$REPO_URL" --rev "$REV" --features "$FEATURES" --locked physis-core
fi

say "verifying"
if command -v physis-core >/dev/null 2>&1; then
  physis-core --version || true
  # The skill's own rule 1: check that what you installed actually runs.
  if physis-core hypothesis list >/dev/null 2>&1; then
    say "physis-core responds. Graph lives in \${PHYSIS_CORE_DIR:-~/.physis-core}"
  else
    echo "warning: physis-core installed but 'hypothesis list' failed" >&2
  fi
else
  echo "physis-core not on PATH — add ~/.cargo/bin to it" >&2
  exit 1
fi

cat <<EOF

Installed:
  skill    $SKILL_DIR/SKILL.md
  scripts  $SKILL_DIR/scripts/
  engine   \$(command -v physis-core)

In Claude Code the skill loads on its own description, or type /physis.
First thing it will tell you to do: check that a thing you are about to claim
works actually has call sites.
EOF
