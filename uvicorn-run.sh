#!/bin/sh
source /config/agentd/.venv/bin/activate  # Activate the virtual environment
exec uvicorn app.main:app --host 0.0.0.0 --port 8000