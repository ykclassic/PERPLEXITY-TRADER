import os
from discord_webhook import DiscordWebhook

def send_signal(embed: str) -> Any:
    """Send Discord webhook."""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK env var required")
    
    webhook = DiscordWebhook(url=webhook_url, content=embed)
    response = webhook.execute()
    return response
