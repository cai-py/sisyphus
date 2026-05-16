#!/usr/bin/env bash
set -euo pipefail

# Start the Sisyphus server from the project root.
# If the virtual environment does not exist, create it and install requirements.

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python server.py
