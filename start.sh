#!/usr/bin/env bash
set -e
export WARTUNG_HOST="${WARTUNG_HOST:-0.0.0.0}"
export WARTUNG_PORT="${PORT:-${WARTUNG_PORT:-8080}}"
python run.py
