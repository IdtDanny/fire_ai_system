# Configuration file for AI Fire Detection System

CONFIG = {
    # Camera settings
    "CAMERA_INDEX": 0,
    "FRAME_WIDTH": 640,
    "FRAME_HEIGHT": 480,

    # AI Model path
    "MODEL_PATH": "yolov8n.pt", # You can replace with best.pt after training
    "CONFIDENCE_THRESHOLD": 0.5,

    # Sensor Mocking (set to False when deploying on RPi hardware)
    "MOCK_HARDWARE": True,

    # Thresholds
    "TEMP_THRESHOLD": 45.0,     # Celsius
    "GAS_THRESHOLD": 600,       # Analog 0-1023
    "HIGH_FIRE_CONF": 0.85,     # Confidence level considered "definite" visual fire

    # Hardware Pins
    "TEMP_PIN": 4,
    "GAS_PIN": 17,
    "PUMP_PIN": 18,
    "BUZZER_PIN": 23,

    # Alert Webhook (Optional)
    "SLACK_WEBHOOK": None,  # e.g., "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

    # Telegram Bot (optional)
    "TELEGRAM_BOT_TOKEN": None, # e.g., "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    "TELEGRAM_CHAT_ID": None,   # e.g., "-1001234567890"

    # Email (SMTP) – e.g., Gmail (optional)
    "SMTP_CONFIG": {
        "server": "smtp.gmail.com",
        "port": 465,
        "user": "maglobalrw@gmail.com",
        "password": "Mere1Liebe",        # Use Gmail App Password, not your regular password
        "from_addr": "maglobalrw@gmail.com",
        "to_addr": "idtbusy@gmail.com"
    },  # or None to disable email

    # GSM Module (optional)
    "GSM_PHONE_NUMBER": "+250788984609",   # Recipient phone number
    "GSM_PORT": "/dev/ttyS0",            # Serial port

    # --- MQTT Broker Settings ---
    "MQTT_BROKER": "localhost",        # Pi is the broker
    "MQTT_PORT": 1883,
    "MQTT_USER": "fireuser",
    "MQTT_PASSWORD": "your_chosen_password",
    "MQTT_FIRE_TOPIC": "fire_detection/status",
    "MQTT_SENSOR_TOPIC": "fire_detection/sensors",
}