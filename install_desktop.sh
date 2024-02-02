#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (or with sudo). Exiting..."
   exit 1
fi

echo "creating user..."
adduser --disabled-password --gecos '' agentsea
chown -R agentsea:agentsea /home/agentsea
echo 'agentsea ALL=(ALL) NOPASSWD:ALL' | tee /etc/sudoers.d/agentsea

echo "installing base packages..."
apt-get update
apt-get install -y xvfb ubuntu-desktop x11vnc websockify python3-pip python3-dev python3-venv
snap install chromium

echo "setting up firewall..."
ufw_status=$(ufw status | grep -o "inactive")
if [ "$ufw_status" == "inactive" ]; then
    echo "UFW is inactive. Enabling..."
    ufw enable
fi

# ssh
ufw allow 22/tcp
ufw reload


cloud-init clean --logs
truncate -s 0 /etc/machine-id
rm /var/lib/dbus/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id