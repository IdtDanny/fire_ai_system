# Install Flask and Paho MQTT: pip install flask paho-mqtt
# Run this on the Raspberry Pi to serve a web dashboard at http://<pi_ip>:5000
# This dashboard subscribes to MQTT topics published by main_esp.py and displays fire status and sensor data in real-time.
# Note: This is a simple dashboard for demonstration. For production, consider using a more robust frontend framework and security measures.
# To run: python dashboard.py
# Make sure the MQTT broker is running and main_esp.py is publishing data.
# The dashboard auto-refreshes every 3 seconds to update the status. You can also add WebSocket support for real-time updates without refreshing.
# This file is separate from main_esp.py to keep the web server logic isolated and avoid any performance impact on the fire detection system. The dashboard is lightweight and should run smoothly on a Raspberry Pi.
# The dashboard displays:
# - Fire status (safe or fire detected)
# - Latest temperature reading
# - Latest gas level reading
# Test by running separately: mosquitto_sub -h localhost -p 1883 -u fireuser -P your_password -t "fire_detection/#"

#!/usr/bin/env python
from flask import Flask, render_template_string
import paho.mqtt.client as mqtt
import threading
import json
from config import CONFIG

app = Flask(__name__)

# Global status
status = {
    "fire": False,
    "temperature": "--",
    "gas": "--",
    "last_update": "Never"
}

# MQTT setup
def on_message(client, userdata, msg):
    global status
    payload = msg.payload.decode()
    if msg.topic == CONFIG["MQTT_FIRE_TOPIC"]:
        status["fire"] = (payload == "FIRE_DETECTED")
        status["last_update"] = "Just now"
    elif msg.topic == CONFIG["MQTT_SENSOR_TOPIC"]:
        try:
            data = json.loads(payload)
            status["temperature"] = data.get("temperature", "--")
            status["gas"] = data.get("gas", "--")
            status["last_update"] = "Just now"
        except:
            pass

def mqtt_listener():
    client = mqtt.Client()
    client.username_pw_set(CONFIG["MQTT_USER"], CONFIG["MQTT_PASSWORD"])
    client.on_message = on_message
    client.connect(CONFIG["MQTT_BROKER"], CONFIG["MQTT_PORT"], 60)
    client.subscribe(CONFIG["MQTT_FIRE_TOPIC"])
    client.subscribe(CONFIG["MQTT_SENSOR_TOPIC"])
    client.loop_forever()

# Start MQTT listener in background thread
threading.Thread(target=mqtt_listener, daemon=True).start()

@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fire Detection Dashboard</title>
        <meta http-equiv="refresh" content="3">
        <style>
            body { font-family: Arial; text-align: center; margin-top: 50px; }
            .status { font-size: 3em; margin: 20px; padding: 20px; border-radius: 15px; }
            .safe { background-color: #2ecc71; color: white; }
            .fire { background-color: #e74c3c; color: white; animation: blink 0.5s infinite; }
            @keyframes blink { 50% { opacity: 0.5; } }
            .data { font-size: 1.5em; margin: 10px; }
        </style>
    </head>
    <body>
        <h1>🔥 AI Fire Suppression System 🔥</h1>
        <div class="status {{ 'fire' if status.fire else 'safe' }}">
            {{ "🚨 FIRE DETECTED! 🚨" if status.fire else "✅ SYSTEM SAFE ✅" }}
        </div>
        <div class="data">🌡️ Temperature: {{ status.temperature }} °C</div>
        <div class="data">💨 Gas Level: {{ status.gas }}</div>
        <div class="data">⏱️ Last update: {{ status.last_update }}</div>
        <p>Page auto‑refreshes every 3 seconds.</p>
    </body>
    </html>
    """
    return render_template_string(html, status=status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)