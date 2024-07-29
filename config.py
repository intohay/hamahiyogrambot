from dotenv import load_dotenv
load_dotenv()

import os
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

USER_ID = os.getenv('USER_ID')
PASSWD = os.getenv('PASSWD')