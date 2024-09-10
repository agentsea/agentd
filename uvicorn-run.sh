#!/bin/sh

cd /config/agentd

exec poetry run uvicorn app:app --host 0.0.0.0 --port 8000 > /config/agentd/agentd.log 2>&1