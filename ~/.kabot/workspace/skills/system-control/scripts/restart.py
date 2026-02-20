import sys
import time

# Ensure UTF-8 output for emojis on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("🔄 Initiating restart sequence...")
time.sleep(1)
sys.exit(42)
