#!/usr/bin/env bash
#
# Script to create a Python 3.12 virtual environment for the project and
# install its dependencies.

set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3.12}
ENV_DIR=${ENV_DIR:-.venv}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN not found. Please install Python 3.12 or adjust PYTHON_BIN." >&2
  exit 1
fi

echo "Creating virtual environment in '$ENV_DIR' using '$PYTHON_BIN'."
"$PYTHON_BIN" -m venv "$ENV_DIR"

echo "Activating virtual environment."
# shellcheck source=/dev/null
source "$ENV_DIR/bin/activate"

echo "Upgrading pip."
pip install --upgrade pip

echo "Installing project dependencies from requirements.txt."
pip install -r requirements.txt

echo "Environment setup complete."
