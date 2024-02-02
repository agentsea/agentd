#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (or with sudo). Exiting..."
   exit 1
fi

echo "creating user..."
adduser --disabled-password --gecos '' agentsea
touch /home/agentsea/.bashrc
chown -R agentsea:agentsea /home/agentsea
echo 'agentsea ALL=(ALL) NOPASSWD:ALL' | tee /etc/sudoers.d/agentsea
su agentsea -c "xauth generate :99 . trusted"

echo "installing base packages..."
apt-get update
apt-get install -y xvfb ubuntu-desktop x11vnc websockify python3-pip python3-dev python3-venv
snap install chromium

su agentsea -c "bash install_deps.sh"

echo "copying services..."
cp ./conf/agentd.service /etc/systemd/system/agentd.service
cp ./conf/websockify.service /etc/systemd/system/websockify.service
cp ./conf/x11vnc.service /lib/systemd/system/x11vnc.service
cp ./conf/xvfb.service /lib/systemd/system/xvfb.service

echo "enabling services..."
systemctl daemon-reload
systemctl enable agentd.service
systemctl enable websockify.service
systemctl enable x11vnc.service
systemctl enable xvfb.service

echo "restarting services..."
systemctl restart agentd.service
systemctl restart websockify.service
systemctl restart x11vnc.service
systemctl restart xvfb.service

echo "setting up firewall..."
ufw_status=$(ufw status | grep -o "inactive")
if [ "$ufw_status" == "inactive" ]; then
    echo "UFW is inactive. Enabling..."
    ufw enable
fi
# agentd
# NOTE: currently only allowing SSH tunneling
# ufw allow 8000/tcp

# websockify
# ufw allow 6080/tcp

# vnc
#ufw allow 5090/tcp

# ssh
ufw allow 22/tcp
ufw reload
