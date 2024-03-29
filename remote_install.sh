#!/bin/bash

# Define where to clone the repository
INSTALL_DIR="/home/agentsea/agentd"
if [ -d "$INSTALL_DIR" ]; then
    echo "$INSTALL_DIR already exists. Consider removing it first if you want a fresh install."
    exit 1
fi

# Clone the repository
echo "Cloning repository into $INSTALL_DIR..."
git clone https://github.com/agentsea/agentd.git "$INSTALL_DIR"

# Check if git clone was successful
if [ $? -ne 0 ]; then
    echo "Failed to clone the repository. Please check your internet connection and repository URL."
    exit 1
fi

# Change directory to the cloned repository
cd "$INSTALL_DIR"

# Assuming your script uses other scripts or configurations from the repo
# Execute a specific script from the cloned repository
echo "Running installation script from the cloned repository..."
bash install.sh

echo "Installation completed."
