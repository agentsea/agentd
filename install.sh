#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (or with sudo). Exiting..."
   exit 1
fi

echo "creating user..."
adduser --disabled-password --gecos '' agentsea
touch /home/agentsea/.bashrc
touch /home/agentsea/.Xauthority
chown -R agentsea:agentsea /home/agentsea
echo 'agentsea ALL=(ALL) NOPASSWD:ALL' | tee /etc/sudoers.d/agentsea

echo "installing base packages..."
add-apt-repository universe
apt-get update
apt-get install -y xvfb x11vnc websockify python3-pip python3-dev python3-venv python3-tk software-properties-common ntp dbus-x11 lxqt sddm
snap install chromium

# Since LXQt doesn't use GDM, we configure SDDM (Simple Desktop Display Manager) for automatic login if needed.
mkdir -p /etc/sddm.conf.d
echo "[Autologin]" > /etc/sddm.conf.d/autologin.conf
echo "User=agentsea" >> /etc/sddm.conf.d/autologin.conf
echo "Session=lxqt.desktop" >> /etc/sddm.conf.d/autologin.conf

su agentsea -c "xauth generate :99 . trusted"
su agentsea -c "bash install_deps.sh"

echo "copying services..."
# Note: Copying the service files as before. Ensure these services are correctly configured for LXQt.
cp ./conf/agentd.service /etc/systemd/system/agentd.service
cp ./conf/websockify.service /etc/systemd/system/websockify.service
cp ./conf/x11vnc.service /lib/systemd/system/x11vnc.service
cp ./conf/xvfb.service /lib/systemd/system/xvfb.service
cp ./conf/lxqt.service /lib/systemd/system/lxqt.service

echo "enabling services..."
systemctl daemon-reload
systemctl enable agentd.service
systemctl enable websockify.service
systemctl enable x11vnc.service
systemctl enable xvfb.service
systemctl enable lxqt.service
systemctl enable ntp

echo "restarting services..."
systemctl restart agentd.service
systemctl restart websockify.service
systemctl restart x11vnc.service
systemctl restart xvfb.service
systemctl restart lxqt.service
systemctl restart ntp

echo "setting up firewall..."
ufw_status=$(ufw status | grep -o "inactive")
if [ "$ufw_status" == "inactive" ]; then
    echo "UFW is inactive. Enabling..."
    ufw enable
fi
# Configuring firewall rules as before
ufw allow 22/tcp # SSH
# Add other rules as necessary
ufw reload
