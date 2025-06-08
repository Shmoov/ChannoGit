# Configuration
$RemoteHost = "pi@192.168.0.171"
$RemotePath = "/home/pi/ChannoBot"
$ServiceName = "channobot.service"

Write-Host "🚀 Starting ChannoBot Deployment..." -ForegroundColor Cyan

# 1. Create backup of remote database
Write-Host "📦 Creating database backup..." -ForegroundColor Yellow
ssh $RemoteHost "cd $RemotePath && python3 backup_db.py"

# 2. Copy systemd service file if it doesn't exist or has changed
Write-Host "🔧 Updating service configuration..." -ForegroundColor Yellow
scp channobot.service ${RemoteHost}:/tmp/channobot.service
ssh $RemoteHost "sudo mv /tmp/channobot.service /etc/systemd/system/channobot.service && sudo systemctl daemon-reload"

# 3. Sync code changes
Write-Host "📤 Syncing code changes..." -ForegroundColor Yellow
# Exclude sensitive files and data
$RsyncExcludes = @(
    "--exclude", ".git",
    "--exclude", ".env",
    "--exclude", "data/*.db",
    "--exclude", "data/backups",
    "--exclude", "data/logs",
    "--exclude", "deploy.ps1",
    "--exclude", "__pycache__"
)
rsync -av --progress $RsyncExcludes ./ ${RemoteHost}:${RemotePath}/

# 4. Install/update dependencies
Write-Host "📚 Updating dependencies..." -ForegroundColor Yellow
ssh $RemoteHost @"
cd $RemotePath
pip3 install -r requirements.txt --user
"@

# 5. Restart the service
Write-Host "🔄 Restarting bot..." -ForegroundColor Yellow
ssh $RemoteHost "sudo systemctl restart $ServiceName"

# 6. Check service status
Write-Host "🔍 Checking service status..." -ForegroundColor Yellow
ssh $RemoteHost @"
sudo systemctl status $ServiceName
echo 'Recent logs:'
tail -n 10 $RemotePath/data/logs/channobot.log
"@

Write-Host "✅ Deployment completed!" -ForegroundColor Green
Write-Host @"

To manage the bot, use these commands:
- Check status: ssh $RemoteHost "sudo systemctl status $ServiceName"
- View logs: ssh $RemoteHost "tail -f $RemotePath/data/logs/channobot.log"
- Stop bot: ssh $RemoteHost "sudo systemctl stop $ServiceName"
- Start bot: ssh $RemoteHost "sudo systemctl start $ServiceName"
- Restart bot: ssh $RemoteHost "sudo systemctl restart $ServiceName"
"@ -ForegroundColor Cyan 