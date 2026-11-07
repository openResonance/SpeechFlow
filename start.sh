#!/bin/sh
# speechflow – startet das Skript (Doppelklick oder ./start.sh im Terminal)
cd "$(dirname "$0")" || exit 1
exec uv run ./speechflow-start.py "$@"
