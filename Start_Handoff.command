#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then
  TASK_PYTHON="${HANDOFF_PYTHON:-python3}"
  if ! "$TASK_PYTHON" -c 'import sys; assert sys.version_info >= (3,11)' 2>/dev/null; then
    TASK_BUNDLED_PYTHON="/Users/$(id -un)/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
    if [ -x "$TASK_BUNDLED_PYTHON" ]; then
      TASK_PYTHON="$TASK_BUNDLED_PYTHON"
    else
      echo 'Python 3.11 or newer is required. See README.md for setup.'
      read -r -p 'Press Return to close.'
      exit 1
    fi
  fi
  "$TASK_PYTHON" -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python -m handoff init
echo 'Open http://127.0.0.1:5055 in your browser. Keep this window open.'
echo 'To stop the app, press Control-C.'
.venv/bin/python -m handoff run
