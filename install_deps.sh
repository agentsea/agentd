#!/bin/bash

if [ "$(whoami)" != "agentsea" ]; then
    echo "This script must be run as the user 'agentsea'. Exiting..."
    exit 1
fi

pip install mss "fastapi[all]" pyautogui pynput uvicorn
