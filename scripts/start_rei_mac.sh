#!/usr/bin/env bash
# REI local-first Apple Silicon launcher.
# Run from a cloned REI repository: bash scripts/start_rei_mac.sh
# No remote installation scripts, public ports, sudo, accounts or API keys.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This launcher is for macOS. On Linux use STANDALONE_AI.md." >&2
  exit 2
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Warning: This shell reports $(uname -m), not arm64. For Apple Silicon, use a native Terminal rather than Rosetta." >&2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
REI_MODEL="${REI_MODEL:-qwen3:4b-instruct}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install it from https://www.python.org/downloads/macos/." >&2
  exit 2
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
  echo "Your python3 is older than 3.10. Install Python 3.10+ and reopen Terminal." >&2
  exit 2
fi
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required. Install https://ollama.com/download/mac, open it, and rerun." >&2
  exit 2
fi
if [[ ! -f pyproject.toml || ! -d rei0 ]]; then
  echo "Expected REI repository files are missing. Reclone the research branch." >&2
  exit 2
fi

echo "[1/4] Checking local Ollama (no cloud API)..."
if ! ollama list >/dev/null 2>&1; then
  if [[ -d /Applications/Ollama.app ]]; then
    echo "Starting the local Ollama application..."
    open -a Ollama
    for _ in $(seq 1 20); do
      if ollama list >/dev/null 2>&1; then break; fi
      sleep 2
    done
  fi
fi
if ! ollama list >/dev/null 2>&1; then
  echo "Ollama is not running. Open the Ollama app and rerun this script." >&2
  exit 2
fi

echo "[2/4] Checking model: $REI_MODEL"
if ! ollama show "$REI_MODEL" >/dev/null 2>&1; then
  echo "Downloading this model into Ollama's local model store (first run only)..."
  ollama pull "$REI_MODEL"
fi

echo "[3/4] Preparing an isolated REI Python environment..."
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -e .
echo "[4/4] Checking the model and starting REI..."
REI_MODEL="$REI_MODEL" .venv/bin/python -m rei0.local_ai_cli doctor

echo "Open http://127.0.0.1:7861/ in Safari once the server starts."
echo "Keep this Terminal window running. Press Ctrl+C to stop REI."
exec env REI_MODEL="$REI_MODEL" .venv/bin/python -m rei0.local_ai_cli serve
