#!/bin/sh
cd /config/agentd
source /config/agentd/.venv/bin/activate  # Activate the virtual environment
exec uvicorn agentd.server:app --host 0.0.0.0 --port 8000