import os
from typing import Any  # ← THIS WAS MISSING!
from discord_webhook import DiscordWebhook

def send_signal(embed: str) -> Any:
    """Send Discord webhook."""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("WARNING: DISCORD_WEBHOOK not set (dry-run mode)")
        return None
    
    webhook = DiscordWebhook(url=webhook_url, content=embed)
    response = webhook.execute()
    return response
