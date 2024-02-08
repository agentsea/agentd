#!/bin/bash

if [ "$(whoami)" != "agentsea" ]; then
    echo "This script must be run as the user 'agentsea'. Exiting..."
    exit 1
fi

# Define the path to be added
PATH_TO_ADD="/home/agentsea/.local/bin"

# Define the profile file
PROFILE_FILE="/home/agentsea/.bashrc"

# Check if the path is already in the PATH variable within the profile file
if ! grep -qxF "export PATH=\"\$PATH:$PATH_TO_ADD\"" $PROFILE_FILE; then
  # If the path is not in the file, append the export command to the profile file
  echo "export PATH=\"\$PATH:$PATH_TO_ADD\"" >> $PROFILE_FILE
  echo "Path $PATH_TO_ADD added to PATH permanently for user agentsea."
else
  echo "Path $PATH_TO_ADD is already in PATH for user agentsea."
fi

export PATH="$PATH:$PATH_TO_ADD"

python3 -m pip install mss "fastapi[all]" pyautogui pynput "uvicorn[standard]" psutil
