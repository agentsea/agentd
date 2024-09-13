#!/bin/sh
cd /config/agentd
VENV_PATH=$(poetry env info -p)
source "$VENV_PATH/bin/activate"
exec uvicorn agentd.server:app --host 0.0.0.0 --port 8000