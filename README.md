# ChannoPoints Discord Bot

A Discord bot that manages a points-based betting system for League of Legends matches and other games.

## Features

### League of Legends Betting
- **League Match Betting**: Users can bet on their own League matches using `!leaguebet`
- **Automatic Verification**: Uses Riot API to verify match results
- **Point Management**: Tracks and manages user points for betting

### General Betting
- **Coin Flip Betting**: Users can create coin flip bets with `!flip`
- **Custom Descriptions**: Add descriptions to bets for clarity
- **Point System**: Fair and transparent point distribution

## Commands

### League Betting
- `!leaguebet @opponent (w/l) amount summoner_name` - Bet on your next League match
  - Example: `!leaguebet @Friend w 100 MyGameName`

### General Betting
- `!flip amount "description"` - Create a coin flip bet
  - Example: `!flip 100 "First Blood"`

### Points
- Points are awarded for winning bets
- Double or nothing system
- Points are checked before bet acceptance

## Privacy & Security
- Uses Riot API for match verification
- No personal data is stored
- Only tracks Discord IDs and point balances

## Technical Details
- Written in Python using discord.py
- Uses Riot Games API for League match verification
- Runs on a Raspberry Pi for 24/7 uptime
- Open source and freely available

## Support
For support or questions, contact the bot maintainer on Discord.

# ChannoBot Setup Instructions

## Initial Setup

1. Transfer files to Raspberry Pi:
```bash
scp bot.py betting.py blackjack.py rewards.py requirements.txt .env channobot.service backup.sh README.md pi@192.168.0.171:/home/pi/ChannoBot/
```

2. SSH into the Raspberry Pi:
```bash
ssh pi@192.168.0.171
```

3. Set up the bot environment:
```bash
cd /home/pi/ChannoBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Service Setup

1. Make the backup script executable:
```bash
chmod +x backup.sh
```

2. Set up the systemd service:
```bash
sudo cp channobot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable channobot
sudo systemctl start channobot
```

3. Check service status:
```bash
sudo systemctl status channobot
```

## Backup Setup

1. Create a cron job for daily backups (runs at 3 AM):
```bash
(crontab -l 2>/dev/null; echo "0 3 * * * /home/pi/ChannoBot/backup.sh") | crontab -
```

## File Locations

- Bot files: `/home/pi/ChannoBot/`
- Database: `/home/pi/ChannoBot/channobot.db`
- Logs: `/home/pi/ChannoBot/logs/channobot.log`
- Backups: `/home/pi/ChannoBot/backups/`

## Useful Commands

- View logs: `tail -f /home/pi/ChannoBot/logs/channobot.log`
- Manual backup: `./backup.sh`
- Restart bot: `sudo systemctl restart channobot`
- Stop bot: `sudo systemctl stop channobot`
- Start bot: `sudo systemctl start channobot`

## Maintenance

- Logs are automatically rotated (5 files, 1MB each)
- Database backups are kept for 7 days
- Older backups are automatically compressed
- The service will automatically restart if the bot crashes 