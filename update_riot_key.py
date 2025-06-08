import os
import sys
import subprocess

def update_key(new_key):
    # Update local .env file
    with open('.env', 'r') as f:
        lines = f.readlines()
    
    with open('.env', 'w') as f:
        for line in lines:
            if line.startswith('RIOT_API_KEY='):
                f.write(f'RIOT_API_KEY={new_key}\n')
            else:
                f.write(line)
    
    print('✅ Updated local .env file')
    
    # Copy to Pi
    try:
        result = subprocess.run(['scp', '.env', 'pi@192.168.0.171:/home/pi/ChannoBot/.env'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print('✅ Updated Pi .env file')
            
            # Restart bot on Pi
            result = subprocess.run(['ssh', 'pi@192.168.0.171', 'sudo systemctl restart channobot.service'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print('✅ Restarted bot service')
            else:
                print('❌ Failed to restart bot service')
        else:
            print('❌ Failed to copy .env to Pi')
    except Exception as e:
        print(f'❌ Error: {e}')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python update_riot_key.py RGAPI-your-new-key')
        sys.exit(1)
    
    new_key = sys.argv[1]
    if not new_key.startswith('RGAPI-'):
        print('❌ Invalid key format. Key should start with RGAPI-')
        sys.exit(1)
    
    update_key(new_key) 