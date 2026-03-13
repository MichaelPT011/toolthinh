#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  osascript -e 'display dialog "Không tìm thấy Python 3. Hãy cài Python 3.11 hoặc mới hơn rồi mở lại Tool Veo3 của Thịnh." buttons {"OK"} default button "OK"'
  exit 1
fi

"$PYTHON_BIN" bootstrap.py
