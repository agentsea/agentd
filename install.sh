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
apt-get install -y xvfb x11vnc websockify python3-pip python3-dev python3-venv python3-tk software-properties-common ntp dbus-x11 openbox menu lxqt sddm lxqt-session

echo "installing chromium"
snap install chromium
update-alternatives --install /usr/bin/x-www-browser x-www-browser /snap/bin/chromium 200
update-alternatives --set x-www-browser /snap/bin/chromium

echo "configuring lxqt"
mkdir -p /etc/sddm.conf.d
echo "[Autologin]" > /etc/sddm.conf.d/autologin.conf
echo "User=agentsea" >> /etc/sddm.conf.d/autologin.conf
echo "Session=lxqt.desktop" >> /etc/sddm.conf.d/autologin.conf

mkdir -p /home/agentsea/.config/lxqt
echo -e "[Session]\nwindow_manager=openbox" > /home/agentsea/.config/lxqt/session.conf
chown -R agentsea:agentsea /home/agentsea/.config

mkdir -p /home/agentsea/.config/openbox
cp /etc/xdg/openbox/rc.xml /home/agentsea/.config/openbox/

su agentsea -c "xauth generate :99 . trusted"
su agentsea -c "bash install_deps.sh"

echo "copying services..."
cp ./conf/agentd.service /etc/systemd/system/agentd.service
cp ./conf/websockify.service /etc/systemd/system/websockify.service
cp ./conf/x11vnc.service /lib/systemd/system/x11vnc.service
cp ./conf/xvfb.service /lib/systemd/system/xvfb.service
cp ./conf/openbox.service /lib/systemd/system/openbox.service
cp ./conf/lxqt.service /lib/systemd/system/lxqt.service

loginctl enable-linger agentsea

echo "enabling services..."
systemctl daemon-reload
systemctl enable agentd.service
systemctl enable websockify.service
systemctl enable x11vnc.service
systemctl enable xvfb.service
systemctl enable openbox.service
systemctl enable lxqt.service
systemctl enable ntp
# systemctl enable sddm

restart_service_and_log() {
  local service_name="$1"
  echo "Restarting $service_name..."
  if systemctl restart "$service_name"; then
    echo "$service_name restarted successfully."
  else
    echo "Failed to restart $service_name. Here are the last 20 log lines:"
    journalctl -u "$service_name" --no-pager -n 20
  fi
}

echo "restarting services..."
restart_service_and_log agentd.service
restart_service_and_log websockify.service
restart_service_and_log x11vnc.service
restart_service_and_log xvfb.service
restart_service_and_log openbox.service
restart_service_and_log lxqt.service
restart_service_and_log ntp

echo "setting up firewall..."
ufw disable
# ufw enable
# ufw allow 22/tcp
# ufw reload
