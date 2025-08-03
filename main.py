from telethon.sync import TelegramClient
from pathlib import Path

# Replace these with your actual details
api_id = 29872536
api_hash = '65e1f714a47c0879734553dc460e98d6'

# Define the base directory (where main.py is located)
base_dir = Path(__file__).parent

# Path to the 'sessions' directory
sessions_dir = base_dir / 'sessions'

# Automatically get the first .session file from the 'sessions' directory
session_files = list(sessions_dir.glob('*.session'))
if not session_files:
    raise FileNotFoundError(f"No .session file found in {sessions_dir}")

# Pick the first session file found (if you have multiple, choose accordingly)
session_file_path = session_files[0]

# Telethon expects the session name without the '.session' extension
session_name = session_file_path.stem

with TelegramClient(str(sessions_dir / session_name), api_id, api_hash) as client:
    client.send_message('me', 'hi')
    print('Message sent to saved messages.')
