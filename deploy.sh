#!/bin/bash

# Configuration
PI_USER="pi"
PI_HOST="192.168.0.171"  # Pi's IP address
PI_DIR="/home/pi/ChannoBot"

# Files to copy
FILES=(
    "blackjack.py"
    "bot.py"
    "betting.py"
    "rewards.py"
    "requirements.txt"
)

echo "Deploying to Raspberry Pi..."

# Copy each file
for file in "${FILES[@]}"; do
    echo "Copying $file..."
    scp "$file" "$PI_USER@$PI_HOST:$PI_DIR/"
done

# Restart the bot service
echo "Restarting ChannoBot service..."
ssh "$PI_USER@$PI_HOST" "sudo systemctl restart channobot.service"

echo "Deployment complete!"

# Optional: Check service status
echo "Checking service status..."
ssh "$PI_USER@$PI_HOST" "sudo systemctl status channobot.service" 