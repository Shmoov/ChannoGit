#!/bin/bash

# Create service file
sudo tee /etc/systemd/system/channobot.service << 'EOF'
[Unit]
Description=ChannoBot Discord Bot
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/ChannoBot
Environment=PATH=/home/pi/ChannoBot/venv/bin:$PATH
ExecStart=/home/pi/ChannoBot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/ChannoBot/data/logs/channobot.log
StandardError=append:/home/pi/ChannoBot/data/logs/channobot.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and restart service
sudo systemctl daemon-reload
sudo systemctl restart channobot.service
sudo systemctl status channobot.service 