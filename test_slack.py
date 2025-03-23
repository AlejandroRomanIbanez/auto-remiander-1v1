import os

from slack_sdk import WebClient

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_BOT_TOKEN)

response = client.chat_postMessage(channel="U047Q9B9DB2", text="Test message from bot")
print(response)
