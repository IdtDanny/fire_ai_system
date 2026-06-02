# import logging
# import requests

# class Alerter:
#     def __init__(self, slack_webhook_url=None, sms_api_key=None, phone_number=None):
#         self.slack_webhook_url = slack_webhook_url
#         self.sms_api_key = sms_api_key
#         self.phone_number = phone_number

#     def send_log_alert(self, message):
#         """Standard log alert"""
#         logging.critical(f"ALERT DISPATCHED: {message}")

#     def send_http_alert(self, message):
#         """Optional HTTP/Slack Webhook Alert"""
#         if not self.slack_webhook_url:
#             return
            
#         try:
#             payload = {"text": f"🔥 FIRE ALARM ALERT 🔥\n{message}"}
#             requests.post(self.slack_webhook_url, json=payload, timeout=5)
#             logging.info("Sent HTTP alert successfully.")
#         except Exception as e:
#             logging.error(f"Failed to send HTTP alert: {e}")

#     def trigger_all(self, level, details=""):
#         """
#         Trigger configured alerts
#         level: 1 (Warning), 2 (Critical Fire)
#         """
#         if level == 1:
#             msg = f"WARNING! Potentially hazardous conditions detected. {details}"
#             self.send_log_alert(msg)
#             # Maybe don't send SMS for warnings to save money, but do HTTP
#             self.send_http_alert(msg)
            
#         elif level == 2:
#             msg = f"CRITICAL FIRE CONFIRMED! Suppression system engaged. {details}"
#             self.send_log_alert(msg)
#             self.send_http_alert(msg)

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     alerter = Alerter()
#     alerter.trigger_all(2, "High temperature and fire bounding box detected.")


### For alerting on email or SMS, you would typically integrate with an email service (like SMTP) or an SMS gateway (like Twilio). Below is a simplified example of how you might implement email alerts using Python's built-in `smtplib`. Note that for real applications, you should handle credentials securely and consider using environment variables or a secrets manager.

import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class Alerter:
    def __init__(self, slack_webhook_url=None, telegram_token=None, telegram_chat_id=None, smtp_config=None):
        """
        slack_webhook_url: Slack incoming webhook URL (optional)
        telegram_token: Bot token from @BotFather (optional)
        telegram_chat_id: Your Telegram chat ID (optional)
        smtp_config: dict with keys: server, port, user, password, from_addr, to_addr (optional)
        """
        self.slack_webhook_url = slack_webhook_url
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.smtp_config = smtp_config

    def send_log_alert(self, message):
        """Standard log alert (always sent)"""
        logging.critical(f"ALERT DISPATCHED: {message}")

    def send_slack_alert(self, message):
        """Slack webhook alert"""
        if not self.slack_webhook_url:
            return
        try:
            payload = {"text": f"🔥 FIRE ALARM 🔥\n{message}"}
            requests.post(self.slack_webhook_url, json=payload, timeout=5)
            logging.info("Slack alert sent successfully.")
        except Exception as e:
            logging.error(f"Failed to send Slack alert: {e}")

    def send_telegram_alert(self, message):
        """Telegram bot alert"""
        if not self.telegram_token or not self.telegram_chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=5)
            logging.info("Telegram alert sent successfully.")
        except Exception as e:
            logging.error(f"Failed to send Telegram alert: {e}")

    def send_email_alert(self, subject, body):
        """SMTP email alert"""
        if not self.smtp_config:
            return
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['from_addr']
            msg['To'] = self.smtp_config['to_addr']
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP_SSL(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.login(self.smtp_config['user'], self.smtp_config['password'])
                server.send_message(msg)
            logging.info("Email alert sent successfully.")
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")

    def trigger_all(self, level, details=""):
        """
        Trigger all configured alerts.
        level: 1 (Warning), 2 (Critical Fire)
        """
        if level == 1:
            msg = f"⚠️ WARNING! Potentially hazardous conditions detected. {details}"
            self.send_log_alert(msg)
            self.send_slack_alert(msg)
            self.send_telegram_alert(msg)
            # Email only for critical alerts? You can change this.
            # self.send_email_alert("Fire Alert (Warning)", msg)

        elif level == 2:
            msg = f"🔥 CRITICAL FIRE CONFIRMED! Suppression system engaged. {details}"
            self.send_log_alert(msg)
            self.send_slack_alert(msg)
            self.send_telegram_alert(msg)
            self.send_email_alert("🚨 CRITICAL FIRE ALERT 🚨", msg)

        else:
            logging.warning(f"Unknown alert level: {level}")


if __name__ == "__main__":
    # Quick test (use mock credentials)
    logging.basicConfig(level=logging.INFO)
    alerter = Alerter()
    alerter.trigger_all(2, "Test – high temperature and flame detected.")