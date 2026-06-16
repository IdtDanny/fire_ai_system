### Working when the mock hardware is running and publishing to MQTT topics. The dashboard updates in real-time with fire status, temperature, gas levels, and recent alerts.

"""
FastAPI Dashboard with WebSockets for live updates.
- When MOCK_HARDWARE = True in config.py, the dashboard shows simulated sensor data (no real GPIO needed).
- When MOCK_HARDWARE = False, it subscribes to the real MQTT broker for actual system status.
"""

import json
import asyncio
import random
import time
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import paho.mqtt.client as mqtt
from config import CONFIG

app = FastAPI()

# Global state that the WebSocket broadcasts
state = {
    "fire": False,
    "temperature": "--",
    "gas": "--",
    "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
    "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
    "camera_active": True,
    "alerts": []
}

MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)

# ------------------------------------------------------------------
# Mock Data Generator (used when MOCK_HARDWARE = True)
# ------------------------------------------------------------------
def mock_data_worker():
    """Simulate sensor readings and occasional fire alerts."""
    global state
    last_alert_time = 0
    while True:
        # Simulate temperature around 22°C ± 3°, occasionally spike to >60°C for fire
        if state["fire"]:
            # After fire, temperature may stay high for a while
            temp = random.uniform(55, 80)
            gas = random.randint(700, 1023)
        else:
            # Normal: temp 18-28°C, gas 50-300
            temp = random.uniform(18, 28)
            gas = random.randint(50, 300)
            # 3% chance to trigger fire (for testing the dashboard)
            if random.random() < 0.03 and time.time() - last_alert_time > 10:
                state["fire"] = True
                alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
                alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
                state["alerts"].insert(0, alert_msg)
                state["alerts"] = state["alerts"][:10]  # keep last 10
                last_alert_time = time.time()
                # Keep fire true for 5 seconds then auto-reset
                threading.Timer(5.0, lambda: state.update({"fire": False})).start()

        state["temperature"] = round(temp, 1)
        state["gas"] = gas
        time.sleep(2)   # update every 2 seconds

# ------------------------------------------------------------------
# MQTT Worker (used when MOCK_HARDWARE = False)
# ------------------------------------------------------------------
def mqtt_worker():
    """Subscribe to MQTT broker for real sensor data."""
    global state
    client = mqtt.Client()
    client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
    client.on_message = on_message
    client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
    client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
    client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
    client.loop_forever()

def on_message(client, userdata, msg):
    global state
    payload = msg.payload.decode()
    if msg.topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
        was = state["fire"]
        state["fire"] = (payload == "FIRE_DETECTED")
        if state["fire"] and not was:
            alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            state["alerts"].insert(0, alert_msg)
            state["alerts"] = state["alerts"][:10]
    elif msg.topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
        try:
            data = json.loads(payload)
            state["temperature"] = data.get("temperature", "--")
            state["gas"] = data.get("gas", "--")
        except:
            pass

# ------------------------------------------------------------------
# Start the appropriate background thread based on MOCK_HARDWARE
# ------------------------------------------------------------------
if MOCK_HARDWARE:
    threading.Thread(target=mock_data_worker, daemon=True).start()
else:
    threading.Thread(target=mqtt_worker, daemon=True).start()

# ------------------------------------------------------------------
# WebSocket endpoint – pushes current state to clients every 0.5s
# ------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps({
                "fire": state["fire"],
                "temperature": state["temperature"],
                "gas": state["gas"],
                "alerts": state["alerts"]
            }))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass

# ------------------------------------------------------------------
# HTML Dashboard (embedded for simplicity)
# ------------------------------------------------------------------
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Fire System Dashboard (FastAPI)</title>
    <style>
        body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
        .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
        .safe { background: #10b981; }
        .danger { background: #ef4444; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
        .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
        .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
        .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
    </style>
</head>
<body>
    <h1>🔥 AI Fire Suppression System (FastAPI + WebSockets)</h1>
    <div id="fireStatus" class="status safe">SYSTEM SAFE</div>
    <div class="grid">
        <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
        <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
        <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
        <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
    </div>
    <div><h3>🚨 Recent Alerts</h3><div id="alerts"></div></div>
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            const statusDiv = document.getElementById('fireStatus');
            if (data.fire) {
                statusDiv.className = 'status danger';
                statusDiv.innerHTML = '🚨 FIRE DETECTED! 🚨';
            } else {
                statusDiv.className = 'status safe';
                statusDiv.innerHTML = 'SYSTEM SAFE';
            }
            document.getElementById('temp').innerText = data.temperature;
            document.getElementById('gas').innerText = data.gas;
            const alertsDiv = document.getElementById('alerts');
            if (data.alerts.length === 0) {
                alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
            } else {
                alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
            }
        };
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content)

# ------------------------------------------------------------------
# Run the server (if executed directly)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # You can change host/port here or read from config
    uvicorn.run(app, host="0.0.0.0", port=8001)