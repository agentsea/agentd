#!/bin/bash

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
