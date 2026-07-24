#!/usr/bin/env bash
# PostToolUse verify hook: lint + test backend Python right after an edit.
#
# Wired in .claude/settings.json for Edit|Write. Reads the tool payload on stdin,
# does nothing unless the edited file is a .py under backend/.
#
# Exit codes: 0 = nothing to say. 2 = failure, stderr goes back to the model so it
# can fix its own edit in-loop. Never fails the session for a missing toolchain —
# an unconfigured machine gets silence, not noise.
set -u

payload=$(cat)

# Pull "file_path" out of the payload without assuming jq is installed.
file=$(printf '%s' "$payload" \
  | tr -d '\n' \
  | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
  | head -1)
[ -n "$file" ] || exit 0

# JSON-escaped Windows paths arrive as c:\\Projects\\... — normalise to forward slashes.
file=$(printf '%s' "$file" | sed 's|\\\\|/|g; s|\\|/|g')

case "$file" in
  */backend/*.py|backend/*.py) ;;
  *) exit 0 ;;
esac

root="${CLAUDE_PROJECT_DIR:-.}"
cd "$root/backend" 2>/dev/null || exit 0

py=""
for candidate in ".venv/Scripts/python.exe" ".venv/bin/python"; do
  [ -x "$candidate" ] && py="$candidate" && break
done
if [ -z "$py" ]; then
  for candidate in python3 python; do
    command -v "$candidate" >/dev/null 2>&1 && py="$candidate" && break
  done
fi
[ -n "$py" ] || exit 0

out=""
status=0

# Path relative to backend/, so ruff gets something it can resolve.
# Handles both absolute (c:/…/backend/app/x.py) and repo-relative (backend/app/x.py).
case "$file" in
  */backend/*) rel="${file##*/backend/}" ;;
  backend/*)   rel="${file#backend/}" ;;
  *)           rel="$file" ;;
esac

if "$py" -m ruff --version >/dev/null 2>&1; then
  if ! ruff_out=$("$py" -m ruff check --fix "$rel" 2>&1); then
    out="${out}ruff:
${ruff_out}
"
    status=2
  fi
fi

if "$py" -m pytest --version >/dev/null 2>&1; then
  if ! test_out=$("$py" -m pytest -q 2>&1); then
    out="${out}pytest:
$(printf '%s' "$test_out" | tail -40)
"
    status=2
  fi
fi

if [ "$status" -ne 0 ]; then
  printf '%s' "$out" >&2
  printf 'Backend verify failed after editing %s — fix before continuing.\n' "$rel" >&2
  exit 2
fi

exit 0
