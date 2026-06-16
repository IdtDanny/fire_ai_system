"""
Installing GUNICORN and Flask for the dashboard:
pip install gunicorn flask paho-mqtt

fire_ai_system/
├── dashboard_sse.py
├── templates/
│   └── dashboard_sse.html
├── static/
│   └── style.css (optional, but we'll embed CSS in HTML)

"""

import json
import threading
import time
from flask import Flask, render_template, Response, jsonify
import paho.mqtt.client as mqtt
from config import CONFIG

app = Flask(__name__)

# Global state
state = {
    "fire": False,
    "temperature": "--",
    "gas": "--",
    "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
    "confidence_threshold": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
    "camera_active": True,   # assume camera is active; could be updated from MQTT
    "last_alert": None,
    "alerts": []   # store last 10 alerts
}

# MQTT settings
MQTT_BROKER = CONFIG.get("MQTT_BROKER", "localhost")
MQTT_PORT = CONFIG.get("MQTT_PORT", 1883)
MQTT_USER = CONFIG.get("MQTT_USER")
MQTT_PASSWORD = CONFIG.get("MQTT_PASSWORD")
FIRE_TOPIC = CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status")
SENSOR_TOPIC = CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors")

def on_message(client, userdata, msg):
    global state
    payload = msg.payload.decode()
    if msg.topic == FIRE_TOPIC:
        was_fire = state["fire"]
        state["fire"] = (payload == "FIRE_DETECTED")
        if state["fire"] and not was_fire:
            alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            state["alerts"].insert(0, alert_msg)
            state["alerts"] = state["alerts"][:10]  # keep last 10
            state["last_alert"] = alert_msg
    elif msg.topic == SENSOR_TOPIC:
        try:
            data = json.loads(payload)
            state["temperature"] = data.get("temperature", "--")
            state["gas"] = data.get("gas", "--")
        except:
            pass

def mqtt_loop():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(FIRE_TOPIC)
    client.subscribe(SENSOR_TOPIC)
    client.loop_forever()

# Start MQTT thread
threading.Thread(target=mqtt_loop, daemon=True).start()

# SSE stream
@app.route('/stream')
def stream():
    def event_stream():
        last_fire = state["fire"]
        last_temp = state["temperature"]
        last_gas = state["gas"]
        while True:
            if (state["fire"] != last_fire or 
                state["temperature"] != last_temp or 
                state["gas"] != last_gas):
                last_fire = state["fire"]
                last_temp = state["temperature"]
                last_gas = state["gas"]
                yield f"data: {json.dumps({'fire': state['fire'], 'temperature': state['temperature'], 'gas': state['gas']})}\n\n"
            time.sleep(0.5)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/alerts')
def get_alerts():
    return jsonify(state["alerts"])

@app.route('/status')
def get_status():
    return jsonify({
        "fire": state["fire"],
        "temperature": state["temperature"],
        "gas": state["gas"],
        "model": state["model"],
        "confidence": state["confidence_threshold"],
        "camera_active": state["camera_active"]
    })

@app.route('/')
def dashboard():
    return render_template('dashboard_sse.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)