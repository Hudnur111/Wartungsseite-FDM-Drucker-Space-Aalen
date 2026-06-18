#!/usr/bin/env bash
set -e
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port "${PORT:-8501}"
