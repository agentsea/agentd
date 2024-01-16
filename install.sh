#!/bin/bash

echo "copying services..."
cp ./conf/agentd.service /etc/systemd/system/agentd.service
cp ./conf/websockify.service /etc/systemd/system/websockify.service
cp ./conf/x11vnc.service /lib/systemd/system/x11vnc.service

echo "enabling services..."
systemctl daemon-reload
systemctl enable agentd.service
systemctl enable websockify.service
systemctl enable x11vnc.service

echo "restarting services..."
systemctl restart agentd.service
systemctl restart websockify.service
systemctl restart x11vnc.service

echo "setting up firewall..."
# agentd
ufw allow 8000/tcp

# websockify
ufw allow 6080/tcp

# vnc
ufw allow 5090/tcp
ufw reload
