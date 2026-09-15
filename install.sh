#!/usr/bin/env sh
# Put `repo-cards` on PATH. The Claude Code skill ships via /plugin; this is the CLI half.
#
# The symlink is not a convenience: ${CLAUDE_PLUGIN_ROOT} is not expanded in SKILL.md prose,
# so the skill finds the command by name and falls back to the plugin root only inside bash.
set -eu

SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC="$SRC_DIR/bin/repo-cards"
BIN="${REPO_CARDS_BIN:-$HOME/.local/bin}"

[ -f "$SRC" ] || { echo "error: $SRC not found; run this from the repo-cards checkout" >&2; exit 1; }

mkdir -p "$BIN"
chmod +x "$SRC"
ln -sf "$SRC" "$BIN/repo-cards"
echo "linked $BIN/repo-cards -> $SRC"

if ! command -v uv >/dev/null 2>&1; then
  echo
  echo "warning: uv is not on PATH. repo-cards is a uv script and will not run without it."
  echo "  install:  curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

case ":${PATH}:" in
  *":$BIN:"*) ;;
  *)
    echo
    echo "warning: $BIN is not on your PATH. Add this to your shell profile:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

cat <<'NEXT'

Next:
  1. Install the skill in Claude Code:
       /plugin marketplace add ~/code/repo-cards
       /plugin install repo-cards@repo-cards
  2. Register a repo:
       repo-cards register /path/to/repo
  3. In that repo, ask Claude: "generate repo cards"
NEXT
