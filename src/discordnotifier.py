from discord_webhook import DiscordWebhook
import os

def send_signal(embed: str):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    webhook = DiscordWebhook(url=webhook_url, content=embed)
    response = webhook.execute()
    return response
