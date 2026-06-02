from config import CONFIG
from utils.alerter import Alerter

alerter = Alerter(
    slack_webhook_url=CONFIG.get("SLACK_WEBHOOK"),
    telegram_token=CONFIG.get("TELEGRAM_BOT_TOKEN"),
    telegram_chat_id=CONFIG.get("TELEGRAM_CHAT_ID"),
    smtp_config=CONFIG.get("SMTP_CONFIG")
)
alerter.trigger_all(2, "Test alert – everything works!")