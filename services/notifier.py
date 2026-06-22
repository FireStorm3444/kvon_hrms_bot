import logging
import requests
from config import Config


logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, config: Config):
        self.bot_token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        
        if self.bot_token:
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        else:
            self.base_url = None

    def send_alert(self, message: str) -> bool:
        """Pushes a Markdown-formatted message to the Telegram Chat ID."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials missing. Skipping notification push.")
            return False
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"  # Allows us to use bolding and emojis nicely
        }
        
        try:
            # We use a strict timeout so a Telegram outage doesn't hang the script
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info("🔔 Telegram notification pushed successfully.")
                return True
                
            logger.error("❌ Failed to push Telegram notification: %s", response.text)
            return False
            
        except requests.exceptions.RequestException:
            logger.exception("❌ Telegram request failed.")
            return False
