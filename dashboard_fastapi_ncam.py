#!/usr/bin/env python3
"""
FastAPI Dashboard (no camera) with alert support.
- Displays last 5 alerts.
- Hidden Model‑card trigger simulates a real fire (auto‑suppression, no manual reference).
- Visible Manual Suppression and Reset Alarm buttons.
"""

import json
import asyncio
import random
import time
import threading
import socket
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
import paho.mqtt.client as mqtt
from config import CONFIG

app = FastAPI()

# ------------------------------------------------------------------
# Global state
# ------------------------------------------------------------------
state = {
    "fire": False,
    "temperature": "--",
    "gas": "--",
    "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
    "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
    "camera_active": True,
    "alerts": []   # max 5
}

MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
MQTT_CLIENT = None

# ------------------------------------------------------------------
# Helper: Get local IP address
# ------------------------------------------------------------------
def get_local_ip():
    try:
        output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()
        if output:
            return output[0]
    except:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

SERVER_IP = get_local_ip()

# ------------------------------------------------------------------
# Mock data worker
# ------------------------------------------------------------------
def mock_data_worker():
    global state
    last_alert_time = 0
    while True:
        if state["fire"]:
            temp = random.uniform(55, 80)
            gas = random.randint(700, 1023)
        else:
            temp = random.uniform(18, 28)
            gas = random.randint(50, 300)
            if random.random() < 0.03 and time.time() - last_alert_time > 10:
                state["fire"] = True
                alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
                alert_msg = f"🔥 FIRE DETECTED at {alert_time}"
                state["alerts"].insert(0, alert_msg)
                state["alerts"] = state["alerts"][:5]
                last_alert_time = time.time()
                threading.Timer(5.0, lambda: state.update({"fire": False})).start()
        state["temperature"] = round(temp, 1)
        state["gas"] = gas
        time.sleep(2)

# ------------------------------------------------------------------
# MQTT worker
# ------------------------------------------------------------------
def on_mqtt_message(client, userdata, message):
    global state
    payload = message.payload.decode()
    topic = message.topic
    if topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
        was = state["fire"]
        state["fire"] = (payload == "FIRE_DETECTED")
        if state["fire"] and not was:
            alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            state["alerts"].insert(0, alert_msg)
            state["alerts"] = state["alerts"][:5]
    elif topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
        try:
            data = json.loads(payload)
            state["temperature"] = data.get("temperature", "--")
            state["gas"] = data.get("gas", "--")
        except:
            pass
    elif topic == "fire_detection/command/response":
        state["alerts"].insert(0, f"📢 {payload}")
        state["alerts"] = state["alerts"][:5]
    elif topic == "fire_detection/alerts":
        try:
            data = json.loads(payload)
            timestamp = data.get("timestamp", time.strftime('%Y-%m-%d %H:%M:%S'))
            level = data.get("level", 0)
            msg = data.get("message", "")
            if level == 1:
                alert_str = f"⚠️ WARNING: {msg}"
            elif level == 2:
                alert_str = f"🔥 FIRE: {msg}"
            else:
                alert_str = f"ℹ️ INFO: {msg}"
            alert_display = f"{timestamp} - {alert_str}"
            state["alerts"].insert(0, alert_display)
            state["alerts"] = state["alerts"][:5]
        except Exception as e:
            print(f"Error processing alert: {e}")

def mqtt_worker():
    global MQTT_CLIENT
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="dashboard_ncam"
    )
    client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
    client.on_message = on_mqtt_message
    client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
    client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
    client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
    client.subscribe("fire_detection/command/response")
    client.subscribe("fire_detection/alerts")
    MQTT_CLIENT = client
    client.loop_forever()

if MOCK_HARDWARE:
    threading.Thread(target=mock_data_worker, daemon=True).start()
else:
    threading.Thread(target=mqtt_worker, daemon=True).start()

# ------------------------------------------------------------------
# WebSocket
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
# HTTP endpoints
# ------------------------------------------------------------------
@app.post("/suppress")
async def manual_suppress():
    global state
    alert_msg = f"🧯 Manual suppression requested at {time.strftime('%Y-%m-%d %H:%M:%S')}"
    state["alerts"].insert(0, alert_msg)
    state["alerts"] = state["alerts"][:5]

    if MOCK_HARDWARE:
        state["fire"] = True
        def clear_fire():
            state["fire"] = False
            state["alerts"].insert(0, "🧯 Suppression simulation completed (mock)")
            state["alerts"] = state["alerts"][:5]
        threading.Timer(3.0, clear_fire).start()
        return {"status": "suppression_triggered (mock)"}
    else:
        if MQTT_CLIENT:
            cmd = json.dumps({"action": "suppress", "source": "dashboard"})
            MQTT_CLIENT.publish("fire_detection/command", cmd)
            return {"status": "suppression_command_sent"}
        else:
            raise HTTPException(status_code=503, detail="MQTT client not available")

@app.post("/reset_alarm")
async def reset_alarm():
    global state
    if state["fire"]:
        state["fire"] = False
        alert_msg = f"🔄 Alarm reset manually at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        state["alerts"].insert(0, alert_msg)
        state["alerts"] = state["alerts"][:5]
        if not MOCK_HARDWARE and MQTT_CLIENT:
            MQTT_CLIENT.publish("fire_detection/command", json.dumps({"action": "reset"}))
        return {"status": "alarm_reset"}
    else:
        return {"status": "no_active_alarm"}

# ------------------------------------------------------------------
# Hidden fake fire endpoint – triggers auto‑suppression (looks real)
# ------------------------------------------------------------------
@app.post("/fake_fire")
async def fake_fire():
    """Simulate a real fire detection: auto‑suppression, no manual reference."""
    global state
    if state["fire"]:
        return {"status": "already_fire"}

    # Update dashboard state
    state["fire"] = True
    alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
    state["alerts"].insert(0, f"🔥 FIRE DETECTED at {alert_time}")
    state["alerts"] = state["alerts"][:5]

    # Publish to MQTT to trigger physical hardware (auto‑suppression)
    if MQTT_CLIENT is not None:
        # Fire status (so subscribers see FIRE_DETECTED)
        MQTT_CLIENT.publish(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"), "FIRE_DETECTED")
        # Send suppress command (this triggers actuator, buzzer, RGB)
        cmd = json.dumps({"action": "suppress", "source": "auto"})  # source=auto
        MQTT_CLIENT.publish("fire_detection/command", cmd)
        # Publish an alert that looks like a real automatic detection
        alert_data = {
            "timestamp": alert_time,
            "level": 2,
            "message": "FIRE CONFIRMED: Fire detected by vision/sensors (auto suppression triggered)"
        }
        MQTT_CLIENT.publish("fire_detection/alerts", json.dumps(alert_data))
    else:
        # Mock mode: just leave the state as fire; auto‑reset can be added if needed
        pass

    return {"status": "fake_fire_triggered"}

# ------------------------------------------------------------------
# HTML Dashboard (embedded)
# ------------------------------------------------------------------
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Fire System Dashboard</title>
    <style>
        body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
        .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
        .safe { background: #10b981; }
        .danger { background: #ef4444; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
        .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
        .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
        .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
        .alert-warning { border-left-color: #f59e0b; }
        .alert-info { border-left-color: #3b82f6; }
        .btn-group { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
        .btn { padding: 0.8rem 2rem; border: none; border-radius: 2rem; font-size: 1.2rem; cursor: pointer; font-weight: bold; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-secondary { background: #3b82f6; color: white; }
        .btn:hover { opacity: 0.8; }
        .footer { margin-top: 2rem; padding: 1rem; background: #1e293b; border-radius: 1rem; text-align: center; color: #94a3b8; }
    </style>
</head>
<body>
    <h1>🔥 AI Fire Suppression System</h1>
    <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
    <div class="grid">
        <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
        <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
        <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
        <!-- Hidden trigger: Model card -->
        <div class="card" id="modelCard"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
    </div>
    <div class="btn-group">
        <button class="btn btn-danger" id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
        <button class="btn btn-secondary" id="resetBtn">↺ RESET ALARM</button>
    </div>
    <div><h3>🚨 Recent Alerts (last 5)</h3><div id="alerts"></div></div>
    <div class="footer">
        🌐 Server IP: <strong>{{ server_ip }}</strong> &nbsp;|&nbsp; Dashboard v2.0
    </div>
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
                statusDiv.innerHTML = '✅ SYSTEM SAFE ✅';
            }
            document.getElementById('temp').innerText = data.temperature;
            document.getElementById('gas').innerText = data.gas;
            const alertsDiv = document.getElementById('alerts');
            if (data.alerts.length === 0) {
                alertsDiv.innerHTML = '<div class="alert-item alert-info">No alerts</div>';
            } else {
                alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
            }
        };

        // Visible manual suppression button
        document.getElementById('suppressBtn').addEventListener('click', async function() {
            const res = await fetch('/suppress', { method: 'POST' });
            const data = await res.json();
            alert('Suppression command sent: ' + data.status);
        });

        // Hidden trigger: Model card -> simulates a real fire (auto‑suppression)
        document.getElementById('modelCard').addEventListener('click', async function() {
            try {
                await fetch('/fake_fire', { method: 'POST' });
                console.log('Hidden fire simulation triggered.');
            } catch (e) {
                console.error('Hidden trigger failed:', e);
            }
        });

        // Reset alarm button
        document.getElementById('resetBtn').addEventListener('click', async function() {
            const res = await fetch('/reset_alarm', { method: 'POST' });
            const data = await res.json();
            alert('Alarm reset: ' + data.status);
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html_content.replace("{{ server_ip }}", SERVER_IP))

if __name__ == "__main__":
    import uvicorn
    print(f"\n🌐 Dashboard available at: http://{SERVER_IP}:8001\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)
    
# ------ v5 - silent but no alert -----

# #!/usr/bin/env python3
# """
# FastAPI Dashboard (no camera) with alert support.
# - Displays last 5 alerts (warnings and fires).
# - Manual suppression button (visible) and hidden trigger on Model card.
# - Real-time sensor data via WebSocket.
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import socket
# import subprocess
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import HTMLResponse
# import paho.mqtt.client as mqtt
# from config import CONFIG

# app = FastAPI()

# # ------------------------------------------------------------------
# # Global state
# # ------------------------------------------------------------------
# state = {
#     "fire": False,
#     "temperature": "--",
#     "gas": "--",
#     "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
#     "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
#     "camera_active": True,
#     "alerts": []   # will store up to 5
# }

# MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
# MQTT_CLIENT = None

# # ------------------------------------------------------------------
# # Helper: Get local IP address
# # ------------------------------------------------------------------
# def get_local_ip():
#     try:
#         output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()
#         if output:
#             return output[0]
#     except:
#         pass
#     try:
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         ip = s.getsockname()[0]
#         s.close()
#         return ip
#     except:
#         return "127.0.0.1"

# SERVER_IP = get_local_ip()

# # ------------------------------------------------------------------
# # Mock data worker (when MOCK_HARDWARE=True)
# # ------------------------------------------------------------------
# def mock_data_worker():
#     global state
#     last_alert_time = 0
#     while True:
#         if state["fire"]:
#             temp = random.uniform(55, 80)
#             gas = random.randint(700, 1023)
#         else:
#             temp = random.uniform(18, 28)
#             gas = random.randint(50, 300)
#             # 3% chance to trigger mock fire
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
#                 alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:5]
#                 last_alert_time = time.time()
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# # ------------------------------------------------------------------
# # MQTT worker (when MOCK_HARDWARE=False)
# # ------------------------------------------------------------------
# def on_mqtt_message(client, userdata, message):
#     """Callback for MQTT messages."""
#     global state
#     payload = message.payload.decode()
#     topic = message.topic
#     if topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#         was = state["fire"]
#         state["fire"] = (payload == "FIRE_DETECTED")
#         if state["fire"] and not was:
#             alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#             state["alerts"].insert(0, alert_msg)
#             state["alerts"] = state["alerts"][:5]
#     elif topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#         try:
#             data = json.loads(payload)
#             state["temperature"] = data.get("temperature", "--")
#             state["gas"] = data.get("gas", "--")
#         except:
#             pass
#     elif topic == "fire_detection/command/response":
#         state["alerts"].insert(0, f"📢 {payload}")
#         state["alerts"] = state["alerts"][:5]
#     elif topic == "fire_detection/alerts":
#         try:
#             data = json.loads(payload)
#             timestamp = data.get("timestamp", time.strftime('%Y-%m-%d %H:%M:%S'))
#             level = data.get("level", 0)
#             msg = data.get("message", "")
#             if level == 1:
#                 alert_str = f"⚠️ WARNING: {msg}"
#             elif level == 2:
#                 alert_str = f"🔥 FIRE: {msg}"
#             else:
#                 alert_str = f"ℹ️ INFO: {msg}"
#             alert_display = f"{timestamp} - {alert_str}"
#             state["alerts"].insert(0, alert_display)
#             state["alerts"] = state["alerts"][:5]
#         except Exception as e:
#             print(f"Error processing alert: {e}")

# def mqtt_worker():
#     global MQTT_CLIENT
#     client = mqtt.Client(
#         callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
#         client_id="dashboard_ncam"
#     )
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_mqtt_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     client.subscribe("fire_detection/command/response")
#     client.subscribe("fire_detection/alerts")
#     MQTT_CLIENT = client
#     client.loop_forever()

# # Start background thread
# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket endpoint
# # ------------------------------------------------------------------
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             await websocket.send_text(json.dumps({
#                 "fire": state["fire"],
#                 "temperature": state["temperature"],
#                 "gas": state["gas"],
#                 "alerts": state["alerts"]
#             }))
#             await asyncio.sleep(0.5)
#     except WebSocketDisconnect:
#         pass

# # ------------------------------------------------------------------
# # HTTP endpoints for actions
# # ------------------------------------------------------------------
# @app.post("/suppress")
# async def manual_suppress():
#     global state
#     alert_msg = f"🧯 Manual suppression requested at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#     state["alerts"].insert(0, alert_msg)
#     state["alerts"] = state["alerts"][:5]

#     if MOCK_HARDWARE:
#         state["fire"] = True
#         def clear_fire():
#             state["fire"] = False
#             state["alerts"].insert(0, "🧯 Suppression simulation completed (mock)")
#             state["alerts"] = state["alerts"][:5]
#         threading.Timer(3.0, clear_fire).start()
#         return {"status": "suppression_triggered (mock)"}
#     else:
#         if MQTT_CLIENT:
#             cmd = json.dumps({"action": "suppress", "source": "dashboard"})
#             MQTT_CLIENT.publish("fire_detection/command", cmd)
#             return {"status": "suppression_command_sent"}
#         else:
#             raise HTTPException(status_code=503, detail="MQTT client not available")

# @app.post("/reset_alarm")
# async def reset_alarm():
#     global state
#     if state["fire"]:
#         state["fire"] = False
#         alert_msg = f"🔄 Alarm reset manually at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#         state["alerts"].insert(0, alert_msg)
#         state["alerts"] = state["alerts"][:5]
#         if not MOCK_HARDWARE and MQTT_CLIENT:
#             MQTT_CLIENT.publish("fire_detection/command", json.dumps({"action": "reset"}))
#         return {"status": "alarm_reset"}
#     else:
#         return {"status": "no_active_alarm"}

# # ------------------------------------------------------------------
# # HTML Dashboard (embedded)
# # ------------------------------------------------------------------
# html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Fire System Dashboard</title>
#     <style>
#         body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
#         .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
#         .safe { background: #10b981; }
#         .danger { background: #ef4444; animation: pulse 1s infinite; }
#         @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
#         .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
#         .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         .alert-warning { border-left-color: #f59e0b; }
#         .alert-info { border-left-color: #3b82f6; }
#         .btn-group { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
#         .btn { padding: 0.8rem 2rem; border: none; border-radius: 2rem; font-size: 1.2rem; cursor: pointer; font-weight: bold; }
#         .btn-danger { background: #ef4444; color: white; }
#         .btn-secondary { background: #3b82f6; color: white; }
#         .btn:hover { opacity: 0.8; }
#         .footer { margin-top: 2rem; padding: 1rem; background: #1e293b; border-radius: 1rem; text-align: center; color: #94a3b8; }
#     </style>
# </head>
# <body>
#     <h1>🔥 AI Fire Suppression System</h1>
#     <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
#     <div class="grid">
#         <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
#         <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
#         <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
#         <!-- Hidden trigger: Model card is clickable (no visual change) -->
#         <div class="card" id="modelCard"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
#     </div>
#     <div class="btn-group">
#         <button class="btn btn-danger" id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
#         <button class="btn btn-secondary" id="resetBtn">↺ RESET ALARM</button>
#     </div>
#     <div><h3>🚨 Recent Alerts (last 5)</h3><div id="alerts"></div></div>
#     <div class="footer">
#         🌐 Server IP: <strong>{{ server_ip }}</strong> &nbsp;|&nbsp; Dashboard v2.0
#     </div>
#     <script>
#         // WebSocket for real-time updates
#         const ws = new WebSocket(`ws://${window.location.host}/ws`);
#         ws.onmessage = function(event) {
#             const data = JSON.parse(event.data);
#             const statusDiv = document.getElementById('fireStatus');
#             if (data.fire) {
#                 statusDiv.className = 'status danger';
#                 statusDiv.innerHTML = '🚨 FIRE DETECTED! 🚨';
#             } else {
#                 statusDiv.className = 'status safe';
#                 statusDiv.innerHTML = '✅ SYSTEM SAFE ✅';
#             }
#             document.getElementById('temp').innerText = data.temperature;
#             document.getElementById('gas').innerText = data.gas;
#             const alertsDiv = document.getElementById('alerts');
#             if (data.alerts.length === 0) {
#                 alertsDiv.innerHTML = '<div class="alert-item alert-info">No alerts</div>';
#             } else {
#                 alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
#             }
#         };

#         // Visible manual suppression button
#         document.getElementById('suppressBtn').addEventListener('click', async function() {
#             const res = await fetch('/suppress', { method: 'POST' });
#             const data = await res.json();
#             alert('Suppression command sent: ' + data.status);
#         });

#         // Hidden trigger: click on Model card sends same suppress command (no alert, no style change)
#         document.getElementById('modelCard').addEventListener('click', async function() {
#             // Silently call /suppress – no UI feedback except the system state will change
#             try {
#                 await fetch('/suppress', { method: 'POST' });
#                 // Optional: log to console (only visible to developer)
#                 console.log('Hidden manual suppression triggered via Model card.');
#             } catch (e) {
#                 console.error('Hidden suppression failed:', e);
#             }
#         });

#         // Reset alarm button
#         document.getElementById('resetBtn').addEventListener('click', async function() {
#             const res = await fetch('/reset_alarm', { method: 'POST' });
#             const data = await res.json();
#             alert('Alarm reset: ' + data.status);
#         });
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def get():
#     return HTMLResponse(html_content.replace("{{ server_ip }}", SERVER_IP))

# # ------------------------------------------------------------------
# # Run the server
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     print(f"\n🌐 Dashboard available at: http://{SERVER_IP}:8001\n")
#     uvicorn.run(app, host="0.0.0.0", port=8001)


# ---- v4 - no silent suppression -----

# #!/usr/bin/env python3
# """
# FastAPI Dashboard (no camera) with full alert support.
# - Subscribes to fire_detection/alerts for real-time warnings and fire alerts.
# - Displays alerts with timestamp and level.
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import socket
# import subprocess
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import HTMLResponse
# import paho.mqtt.client as mqtt
# from config import CONFIG

# app = FastAPI()

# # ------------------------------------------------------------------
# # Global state
# # ------------------------------------------------------------------
# state = {
#     "fire": False,
#     "temperature": "--",
#     "gas": "--",
#     "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
#     "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
#     "camera_active": True,
#     "alerts": []
# }

# MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
# MQTT_CLIENT = None

# # ------------------------------------------------------------------
# # Helper: Get local IP address
# # ------------------------------------------------------------------
# def get_local_ip():
#     try:
#         output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()
#         if output:
#             return output[0]
#     except:
#         pass
#     try:
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         ip = s.getsockname()[0]
#         s.close()
#         return ip
#     except:
#         return "127.0.0.1"

# SERVER_IP = get_local_ip()

# # ------------------------------------------------------------------
# # Mock data worker (when MOCK_HARDWARE=True)
# # ------------------------------------------------------------------
# def mock_data_worker():
#     global state
#     last_alert_time = 0
#     while True:
#         if state["fire"]:
#             temp = random.uniform(55, 80)
#             gas = random.randint(700, 1023)
#         else:
#             temp = random.uniform(18, 28)
#             gas = random.randint(50, 300)
#             # 3% chance to trigger mock fire
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
#                 alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:5]  # keep last 5
#                 last_alert_time = time.time()
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# # ------------------------------------------------------------------
# # MQTT worker (when MOCK_HARDWARE=False)
# # ------------------------------------------------------------------
# def on_mqtt_message(client, userdata, message):
#     """Callback for MQTT messages (new API v2)."""
#     global state
#     payload = message.payload.decode()
#     topic = message.topic
#     if topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#         was = state["fire"]
#         state["fire"] = (payload == "FIRE_DETECTED")
#         if state["fire"] and not was:
#             alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#             state["alerts"].insert(0, alert_msg)
#             state["alerts"] = state["alerts"][:5]
#     elif topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#         try:
#             data = json.loads(payload)
#             state["temperature"] = data.get("temperature", "--")
#             state["gas"] = data.get("gas", "--")
#         except:
#             pass
#     elif topic == "fire_detection/command/response":
#         state["alerts"].insert(0, f"📢 {payload}")
#         state["alerts"] = state["alerts"][:10]
#     elif topic == "fire_detection/alerts":
#         try:
#             data = json.loads(payload)
#             timestamp = data.get("timestamp", time.strftime('%Y-%m-%d %H:%M:%S'))
#             level = data.get("level", 0)
#             msg = data.get("message", "")
#             if level == 1:
#                 alert_str = f"⚠️ WARNING: {msg}"
#             elif level == 2:
#                 alert_str = f"🔥 FIRE: {msg}"
#             else:
#                 alert_str = f"ℹ️ INFO: {msg}"
#             alert_display = f"{timestamp} - {alert_str}"
#             state["alerts"].insert(0, alert_display)
#             state["alerts"] = state["alerts"][:10]
#         except Exception as e:
#             print(f"Error processing alert: {e}")

# def mqtt_worker():
#     """Subscribe to MQTT broker."""
#     global MQTT_CLIENT
#     client = mqtt.Client(
#         callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
#         client_id="dashboard_ncam"
#     )
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_mqtt_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     client.subscribe("fire_detection/command/response")
#     client.subscribe("fire_detection/alerts")   # NEW
#     MQTT_CLIENT = client
#     client.loop_forever()

# # Start background thread
# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket endpoint
# # ------------------------------------------------------------------
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             await websocket.send_text(json.dumps({
#                 "fire": state["fire"],
#                 "temperature": state["temperature"],
#                 "gas": state["gas"],
#                 "alerts": state["alerts"]
#             }))
#             await asyncio.sleep(0.5)
#     except WebSocketDisconnect:
#         pass

# # ------------------------------------------------------------------
# # HTTP endpoints for actions
# # ------------------------------------------------------------------
# @app.post("/suppress")
# async def manual_suppress():
#     """Send manual suppression command via MQTT."""
#     global state
#     alert_msg = f"🧯 Manual suppression requested at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#     state["alerts"].insert(0, alert_msg)
#     state["alerts"] = state["alerts"][:10]

#     if MOCK_HARDWARE:
#         state["fire"] = True
#         def clear_fire():
#             state["fire"] = False
#             state["alerts"].insert(0, "🧯 Suppression simulation completed (mock)")
#             state["alerts"] = state["alerts"][:5]
#         threading.Timer(3.0, clear_fire).start()
#         return {"status": "suppression_triggered (mock)"}
#     else:
#         if MQTT_CLIENT:
#             cmd = json.dumps({"action": "suppress", "source": "dashboard"})
#             MQTT_CLIENT.publish("fire_detection/command", cmd)
#             return {"status": "suppression_command_sent"}
#         else:
#             raise HTTPException(status_code=503, detail="MQTT client not available")

# @app.post("/reset_alarm")
# async def reset_alarm():
#     """Reset the fire alarm (clear fire state)."""
#     global state
#     if state["fire"]:
#         state["fire"] = False
#         alert_msg = f"🔄 Alarm reset manually at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#         state["alerts"].insert(0, alert_msg)
#         state["alerts"] = state["alerts"][:5]
#         if not MOCK_HARDWARE and MQTT_CLIENT:
#             MQTT_CLIENT.publish("fire_detection/command", json.dumps({"action": "reset"}))
#         return {"status": "alarm_reset"}
#     else:
#         return {"status": "no_active_alarm"}

# # ------------------------------------------------------------------
# # HTML Dashboard (embedded)
# # ------------------------------------------------------------------
# html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Fire System Dashboard</title>
#     <style>
#         body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
#         .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
#         .safe { background: #10b981; }
#         .danger { background: #ef4444; animation: pulse 1s infinite; }
#         @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
#         .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
#         .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         .alert-warning { border-left-color: #f59e0b; }
#         .alert-info { border-left-color: #3b82f6; }
#         .btn-group { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
#         .btn { padding: 0.8rem 2rem; border: none; border-radius: 2rem; font-size: 1.2rem; cursor: pointer; font-weight: bold; }
#         .btn-danger { background: #ef4444; color: white; }
#         .btn-secondary { background: #3b82f6; color: white; }
#         .btn:hover { opacity: 0.8; }
#         .footer { margin-top: 2rem; padding: 1rem; background: #1e293b; border-radius: 1rem; text-align: center; color: #94a3b8; }
#     </style>
# </head>
# <body>
#     <h1>🔥 AI Fire Suppression System</h1>
#     <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
#     <div class="grid">
#         <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
#         <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
#         <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
#         <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
#     </div>
#     <div class="btn-group">
#         <button class="btn btn-danger" id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
#         <button class="btn btn-secondary" id="resetBtn">↺ RESET ALARM</button>
#     </div>
#     <div><h3>🚨 Recent Alerts</h3><div id="alerts"></div></div>
#     <div class="footer">
#         🌐 Server IP: <strong>{{ server_ip }}</strong> &nbsp;|&nbsp; Dashboard v2.0
#     </div>
#     <script>
#         const ws = new WebSocket(`ws://${window.location.host}/ws`);
#         ws.onmessage = function(event) {
#             const data = JSON.parse(event.data);
#             const statusDiv = document.getElementById('fireStatus');
#             if (data.fire) {
#                 statusDiv.className = 'status danger';
#                 statusDiv.innerHTML = '🚨 FIRE DETECTED! 🚨';
#             } else {
#                 statusDiv.className = 'status safe';
#                 statusDiv.innerHTML = '✅ SYSTEM SAFE ✅';
#             }
#             document.getElementById('temp').innerText = data.temperature;
#             document.getElementById('gas').innerText = data.gas;
#             const alertsDiv = document.getElementById('alerts');
#             if (data.alerts.length === 0) {
#                 alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
#             } else {
#                 alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
#             }
#         };

#         document.getElementById('suppressBtn').addEventListener('click', async function() {
#             const res = await fetch('/suppress', { method: 'POST' });
#             const data = await res.json();
#             alert('Suppression command sent: ' + data.status);
#         });

#         document.getElementById('resetBtn').addEventListener('click', async function() {
#             const res = await fetch('/reset_alarm', { method: 'POST' });
#             const data = await res.json();
#             alert('Alarm reset: ' + data.status);
#         });
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def get():
#     return HTMLResponse(html_content.replace("{{ server_ip }}", SERVER_IP))

# # ------------------------------------------------------------------
# # Run the server
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     print(f"\n🌐 Dashboard available at: http://{SERVER_IP}:8001\n")
#     uvicorn.run(app, host="0.0.0.0", port=8001)

# ---------------- v3 - old depreciated --------------------------

# #!/usr/bin/env python3
# """
# FastAPI Dashboard (no camera)
# - Lightweight: no video feed.
# - Shows server IP address.
# - Manual suppression and reset buttons (send MQTT commands).
# - Real-time updates via WebSocket.
# - Works with MOCK_HARDWARE (mock data) or real MQTT.
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import socket
# import subprocess
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import HTMLResponse
# import paho.mqtt.client as mqtt
# from config import CONFIG

# app = FastAPI()

# # ------------------------------------------------------------------
# # Global state
# # ------------------------------------------------------------------
# state = {
#     "fire": False,
#     "temperature": "--",
#     "gas": "--",
#     "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
#     "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
#     "camera_active": True,
#     "alerts": []
# }

# MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
# MQTT_CLIENT = None

# # ------------------------------------------------------------------
# # Helper: Get local IP address
# # ------------------------------------------------------------------
# def get_local_ip():
#     try:
#         output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()
#         if output:
#             return output[0]
#     except:
#         pass
#     try:
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         ip = s.getsockname()[0]
#         s.close()
#         return ip
#     except:
#         return "127.0.0.1"

# SERVER_IP = get_local_ip()

# # ------------------------------------------------------------------
# # Mock data worker (when MOCK_HARDWARE=True)
# # ------------------------------------------------------------------
# def mock_data_worker():
#     global state
#     last_alert_time = 0
#     while True:
#         if state["fire"]:
#             temp = random.uniform(55, 80)
#             gas = random.randint(700, 1023)
#         else:
#             temp = random.uniform(18, 28)
#             gas = random.randint(50, 300)
#             # 3% chance to trigger mock fire
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
#                 alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:10]
#                 last_alert_time = time.time()
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# # ------------------------------------------------------------------
# # MQTT worker (when MOCK_HARDWARE=False)
# # ------------------------------------------------------------------
# def on_mqtt_message(client, userdata, message):
#     """Callback for MQTT messages (new API v2)."""
#     global state
#     payload = message.payload.decode()
#     topic = message.topic
#     if topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#         was = state["fire"]
#         state["fire"] = (payload == "FIRE_DETECTED")
#         if state["fire"] and not was:
#             alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#             state["alerts"].insert(0, alert_msg)
#             state["alerts"] = state["alerts"][:10]
#     elif topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#         try:
#             data = json.loads(payload)
#             state["temperature"] = data.get("temperature", "--")
#             state["gas"] = data.get("gas", "--")
#         except:
#             pass
#     elif topic == "fire_detection/command/response":
#         state["alerts"].insert(0, f"📢 {payload}")
#         state["alerts"] = state["alerts"][:10]

# def mqtt_worker():
#     """Subscribe to MQTT broker."""
#     global MQTT_CLIENT
#     # Use the new API version to avoid deprecation warning
#     client = mqtt.Client(
#         callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
#         client_id="dashboard_ncam"
#     )
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_mqtt_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     client.subscribe("fire_detection/command/response")
#     MQTT_CLIENT = client
#     client.loop_forever()

# # Start background thread
# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket endpoint
# # ------------------------------------------------------------------
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             await websocket.send_text(json.dumps({
#                 "fire": state["fire"],
#                 "temperature": state["temperature"],
#                 "gas": state["gas"],
#                 "alerts": state["alerts"]
#             }))
#             await asyncio.sleep(0.5)
#     except WebSocketDisconnect:
#         pass

# # ------------------------------------------------------------------
# # HTTP endpoints for actions
# # ------------------------------------------------------------------
# @app.post("/suppress")
# async def manual_suppress():
#     """Send manual suppression command via MQTT."""
#     global state
#     alert_msg = f"🧯 Manual suppression requested at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#     state["alerts"].insert(0, alert_msg)
#     state["alerts"] = state["alerts"][:10]

#     if MOCK_HARDWARE:
#         state["fire"] = True
#         def clear_fire():
#             state["fire"] = False
#             state["alerts"].insert(0, "🧯 Suppression simulation completed (mock)")
#             state["alerts"] = state["alerts"][:10]
#         threading.Timer(3.0, clear_fire).start()
#         return {"status": "suppression_triggered (mock)"}
#     else:
#         if MQTT_CLIENT:
#             cmd = json.dumps({"action": "suppress", "source": "dashboard"})
#             MQTT_CLIENT.publish("fire_detection/command", cmd)
#             return {"status": "suppression_command_sent"}
#         else:
#             raise HTTPException(status_code=503, detail="MQTT client not available")

# @app.post("/reset_alarm")
# async def reset_alarm():
#     """Reset the fire alarm (clear fire state)."""
#     global state
#     if state["fire"]:
#         state["fire"] = False
#         alert_msg = f"🔄 Alarm reset manually at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#         state["alerts"].insert(0, alert_msg)
#         state["alerts"] = state["alerts"][:10]
#         if not MOCK_HARDWARE and MQTT_CLIENT:
#             MQTT_CLIENT.publish("fire_detection/command", json.dumps({"action": "reset"}))
#         return {"status": "alarm_reset"}
#     else:
#         return {"status": "no_active_alarm"}

# # ------------------------------------------------------------------
# # HTML Dashboard (embedded)
# # ------------------------------------------------------------------
# html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Fire System Dashboard</title>
#     <style>
#         body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
#         .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
#         .safe { background: #10b981; }
#         .danger { background: #ef4444; animation: pulse 1s infinite; }
#         @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
#         .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
#         .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         .btn-group { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
#         .btn { padding: 0.8rem 2rem; border: none; border-radius: 2rem; font-size: 1.2rem; cursor: pointer; font-weight: bold; }
#         .btn-danger { background: #ef4444; color: white; }
#         .btn-secondary { background: #3b82f6; color: white; }
#         .btn:hover { opacity: 0.8; }
#         .footer { margin-top: 2rem; padding: 1rem; background: #1e293b; border-radius: 1rem; text-align: center; color: #94a3b8; }
#     </style>
# </head>
# <body>
#     <h1>🔥 AI Fire Suppression System</h1>
#     <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
#     <div class="grid">
#         <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
#         <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
#         <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
#         <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
#     </div>
#     <div class="btn-group">
#         <button class="btn btn-danger" id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
#         <button class="btn btn-secondary" id="resetBtn">↺ RESET ALARM</button>
#     </div>
#     <div><h3>🚨 Recent Alerts</h3><div id="alerts"></div></div>
#     <div class="footer">
#         🌐 Server IP: <strong>{{ server_ip }}</strong> &nbsp;|&nbsp; Dashboard v2.0
#     </div>
#     <script>
#         const ws = new WebSocket(`ws://${window.location.host}/ws`);
#         ws.onmessage = function(event) {
#             const data = JSON.parse(event.data);
#             const statusDiv = document.getElementById('fireStatus');
#             if (data.fire) {
#                 statusDiv.className = 'status danger';
#                 statusDiv.innerHTML = '🚨 FIRE DETECTED! 🚨';
#             } else {
#                 statusDiv.className = 'status safe';
#                 statusDiv.innerHTML = '✅ SYSTEM SAFE ✅';
#             }
#             document.getElementById('temp').innerText = data.temperature;
#             document.getElementById('gas').innerText = data.gas;
#             const alertsDiv = document.getElementById('alerts');
#             if (data.alerts.length === 0) {
#                 alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
#             } else {
#                 alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
#             }
#         };

#         document.getElementById('suppressBtn').addEventListener('click', async function() {
#             const res = await fetch('/suppress', { method: 'POST' });
#             const data = await res.json();
#             alert('Suppression command sent: ' + data.status);
#         });

#         document.getElementById('resetBtn').addEventListener('click', async function() {
#             const res = await fetch('/reset_alarm', { method: 'POST' });
#             const data = await res.json();
#             alert('Alarm reset: ' + data.status);
#         });
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def get():
#     return HTMLResponse(html_content.replace("{{ server_ip }}", SERVER_IP))

# # ------------------------------------------------------------------
# # Run the server
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     print(f"\n🌐 Dashboard available at: http://{SERVER_IP}:8001\n")
#     uvicorn.run(app, host="0.0.0.0", port=8001)

# ---------------- v2 - new version with IP display ----------------

# """
# FastAPI Dashboard with WebSockets for live updates.
# - Shows server IP address on the web interface.
# - No video feed – lightweight and efficient.
# - Manual suppression and reset buttons (send MQTT commands).
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import socket
# import subprocess
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
# from fastapi.responses import HTMLResponse
# import paho.mqtt.client as mqtt
# from config import CONFIG

# app = FastAPI()

# # Global state
# state = {
#     "fire": False,
#     "temperature": "--",
#     "gas": "--",
#     "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
#     "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
#     "camera_active": True,
#     "alerts": []
# }

# MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
# MQTT_CLIENT = None

# # ------------------------------------------------------------------
# # Helper: Get local IP address
# # ------------------------------------------------------------------
# def get_local_ip():
#     try:
#         # Try using hostname -I first
#         output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()
#         if output:
#             return output[0]
#     except:
#         pass
#     try:
#         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         s.connect(("8.8.8.8", 80))
#         ip = s.getsockname()[0]
#         s.close()
#         return ip
#     except:
#         return "127.0.0.1"

# SERVER_IP = get_local_ip()

# # ------------------------------------------------------------------
# # Mock data worker
# # ------------------------------------------------------------------
# def mock_data_worker():
#     global state
#     last_alert_time = 0
#     while True:
#         if state["fire"]:
#             temp = random.uniform(55, 80)
#             gas = random.randint(700, 1023)
#         else:
#             temp = random.uniform(18, 28)
#             gas = random.randint(50, 300)
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
#                 alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:10]
#                 last_alert_time = time.time()
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# # ------------------------------------------------------------------
# # MQTT worker (real mode)
# # ------------------------------------------------------------------
# def mqtt_worker():
#     global state, MQTT_CLIENT
#     client = mqtt.Client()
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     client.subscribe("fire_detection/command/response")
#     MQTT_CLIENT = client
#     client.loop_forever()

# def on_message(client, userdata, msg):
#     global state
#     payload = msg.payload.decode()
#     topic = msg.topic
#     if topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#         was = state["fire"]
#         state["fire"] = (payload == "FIRE_DETECTED")
#         if state["fire"] and not was:
#             alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#             state["alerts"].insert(0, alert_msg)
#             state["alerts"] = state["alerts"][:10]
#     elif topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#         try:
#             data = json.loads(payload)
#             state["temperature"] = data.get("temperature", "--")
#             state["gas"] = data.get("gas", "--")
#         except:
#             pass
#     elif topic == "fire_detection/command/response":
#         state["alerts"].insert(0, f"📢 {payload}")
#         state["alerts"] = state["alerts"][:10]

# # Start background thread
# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket
# # ------------------------------------------------------------------
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             await websocket.send_text(json.dumps({
#                 "fire": state["fire"],
#                 "temperature": state["temperature"],
#                 "gas": state["gas"],
#                 "alerts": state["alerts"]
#             }))
#             await asyncio.sleep(0.5)
#     except WebSocketDisconnect:
#         pass

# # ------------------------------------------------------------------
# # HTTP endpoints for actions
# # ------------------------------------------------------------------
# @app.post("/suppress")
# async def manual_suppress():
#     global state
#     alert_msg = f"🧯 Manual suppression requested at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#     state["alerts"].insert(0, alert_msg)
#     state["alerts"] = state["alerts"][:10]

#     if MOCK_HARDWARE:
#         state["fire"] = True
#         def clear_fire():
#             state["fire"] = False
#             state["alerts"].insert(0, "🧯 Suppression simulation completed (mock)")
#             state["alerts"] = state["alerts"][:10]
#         threading.Timer(3.0, clear_fire).start()
#         return {"status": "suppression_triggered (mock)"}
#     else:
#         if MQTT_CLIENT:
#             cmd = json.dumps({"action": "suppress", "source": "dashboard"})
#             MQTT_CLIENT.publish("fire_detection/command", cmd)
#             return {"status": "suppression_command_sent"}
#         else:
#             raise HTTPException(status_code=503, detail="MQTT client not available")

# @app.post("/reset_alarm")
# async def reset_alarm():
#     global state
#     if state["fire"]:
#         state["fire"] = False
#         alert_msg = f"🔄 Alarm reset manually at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#         state["alerts"].insert(0, alert_msg)
#         state["alerts"] = state["alerts"][:10]
#         if not MOCK_HARDWARE and MQTT_CLIENT:
#             MQTT_CLIENT.publish("fire_detection/command", json.dumps({"action": "reset"}))
#         return {"status": "alarm_reset"}
#     else:
#         return {"status": "no_active_alarm"}

# # ------------------------------------------------------------------
# # HTML Dashboard (with IP display)
# # ------------------------------------------------------------------
# html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Fire System Dashboard</title>
#     <style>
#         body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
#         .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
#         .safe { background: #10b981; }
#         .danger { background: #ef4444; animation: pulse 1s infinite; }
#         @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
#         .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
#         .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         .btn-group { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
#         .btn { padding: 0.8rem 2rem; border: none; border-radius: 2rem; font-size: 1.2rem; cursor: pointer; font-weight: bold; }
#         .btn-danger { background: #ef4444; color: white; }
#         .btn-warning { background: #f59e0b; color: black; }
#         .btn-secondary { background: #3b82f6; color: white; }
#         .btn:hover { opacity: 0.8; }
#         .footer { margin-top: 2rem; padding: 1rem; background: #1e293b; border-radius: 1rem; text-align: center; color: #94a3b8; }
#     </style>
# </head>
# <body>
#     <h1>🔥 AI Fire Suppression System</h1>
#     <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
#     <div class="grid">
#         <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
#         <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
#         <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
#         <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
#     </div>
#     <div class="btn-group">
#         <button class="btn btn-danger" id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
#         <button class="btn btn-secondary" id="resetBtn">↺ RESET ALARM</button>
#     </div>
#     <div><h3>🚨 Recent Alerts</h3><div id="alerts"></div></div>
#     <div class="footer">
#         🌐 Server IP: <strong>{{ server_ip }}</strong> &nbsp;|&nbsp; Dashboard v2.0
#     </div>

#     <script>
#         const ws = new WebSocket(`ws://${window.location.host}/ws`);
#         ws.onmessage = function(event) {
#             const data = JSON.parse(event.data);
#             const statusDiv = document.getElementById('fireStatus');
#             if (data.fire) {
#                 statusDiv.className = 'status danger';
#                 statusDiv.innerHTML = '🚨 FIRE DETECTED! 🚨';
#             } else {
#                 statusDiv.className = 'status safe';
#                 statusDiv.innerHTML = '✅ SYSTEM SAFE ✅';
#             }
#             document.getElementById('temp').innerText = data.temperature;
#             document.getElementById('gas').innerText = data.gas;
#             const alertsDiv = document.getElementById('alerts');
#             if (data.alerts.length === 0) {
#                 alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
#             } else {
#                 alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
#             }
#         };

#         // Manual suppression button
#         document.getElementById('suppressBtn').addEventListener('click', async function() {
#             const res = await fetch('/suppress', { method: 'POST' });
#             const data = await res.json();
#             alert('Suppression command sent: ' + data.status);
#         });

#         // Reset alarm button
#         document.getElementById('resetBtn').addEventListener('click', async function() {
#             const res = await fetch('/reset_alarm', { method: 'POST' });
#             const data = await res.json();
#             alert('Alarm reset: ' + data.status);
#         });
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def get(request: Request):
#     # Pass server IP to the template
#     return HTMLResponse(html_content.replace("{{ server_ip }}", SERVER_IP))

# # ------------------------------------------------------------------
# # Run the server
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     print(f"\n🌐 Dashboard available at: http://{SERVER_IP}:8001\n")
#     uvicorn.run(app, host="0.0.0.0", port=8001)

# --------------------------------- v1 - old ---------------------------------

# """
# FastAPI Dashboard with WebSockets for live updates.
# - When MOCK_HARDWARE = True, shows simulated sensor data.
# - When MOCK_HARDWARE = False, subscribes to the real MQTT broker.
# - Includes Manual Suppression button (sends MQTT command).
# - No video feed – lightweight and efficient.
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import subprocess
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import HTMLResponse
# import paho.mqtt.client as mqtt
# from config import CONFIG

# app = FastAPI()

# # Global state for WebSocket
# state = {
#     "fire": False,
#     "temperature": "--",
#     "gas": "--",
#     "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
#     "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
#     "camera_active": True,
#     "alerts": []
# }

# MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
# MQTT_CLIENT = None   # will be set if real mode

# # ------------------------------------------------------------------
# # Mock Data Generator (when MOCK_HARDWARE = True)
# # ------------------------------------------------------------------
# def mock_data_worker():
#     """Simulate sensor readings and occasional fire alerts."""
#     global state
#     last_alert_time = 0
#     while True:
#         if state["fire"]:
#             temp = random.uniform(55, 80)
#             gas = random.randint(700, 1023)
#         else:
#             temp = random.uniform(18, 28)
#             gas = random.randint(50, 300)
#             # 3% chance to trigger fire (for testing)
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
#                 alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:10]
#                 last_alert_time = time.time()
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# # ------------------------------------------------------------------
# # MQTT Worker (when MOCK_HARDWARE = False)
# # ------------------------------------------------------------------
# def mqtt_worker():
#     """Subscribe to MQTT broker for real sensor data and command responses."""
#     global state, MQTT_CLIENT
#     client = mqtt.Client()
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     # Also subscribe to command responses if needed
#     client.subscribe("fire_detection/command/response")
#     MQTT_CLIENT = client
#     client.loop_forever()

# def on_message(client, userdata, msg):
#     global state
#     payload = msg.payload.decode()
#     topic = msg.topic
#     if topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#         was = state["fire"]
#         state["fire"] = (payload == "FIRE_DETECTED")
#         if state["fire"] and not was:
#             alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#             state["alerts"].insert(0, alert_msg)
#             state["alerts"] = state["alerts"][:10]
#     elif topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#         try:
#             data = json.loads(payload)
#             state["temperature"] = data.get("temperature", "--")
#             state["gas"] = data.get("gas", "--")
#         except:
#             pass
#     elif topic == "fire_detection/command/response":
#         # Handle response from main system (e.g., suppression activated)
#         state["alerts"].insert(0, f"📢 {payload}")
#         state["alerts"] = state["alerts"][:10]

# # Start background thread
# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket endpoint – pushes current state every 0.5s
# # ------------------------------------------------------------------
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             await websocket.send_text(json.dumps({
#                 "fire": state["fire"],
#                 "temperature": state["temperature"],
#                 "gas": state["gas"],
#                 "alerts": state["alerts"]
#             }))
#             await asyncio.sleep(0.5)
#     except WebSocketDisconnect:
#         pass

# # ------------------------------------------------------------------
# # HTTP endpoints for manual actions
# # ------------------------------------------------------------------
# @app.post("/suppress")
# async def manual_suppress():
#     """
#     Manual suppression – sends a command via MQTT or handles locally.
#     """
#     global state
#     # Add alert
#     alert_msg = f"🧯 Manual suppression requested at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#     state["alerts"].insert(0, alert_msg)
#     state["alerts"] = state["alerts"][:10]

#     if MOCK_HARDWARE:
#         # In mock mode, simulate activation
#         state["fire"] = True  # set fire to simulate response
#         # Add a mock response after 2s
#         def clear_fire():
#             state["fire"] = False
#             state["alerts"].insert(0, "🧯 Suppression simulation completed (mock)")
#             state["alerts"] = state["alerts"][:10]
#         threading.Timer(3.0, clear_fire).start()
#         return {"status": "suppression_triggered (mock)"}
#     else:
#         # Real mode: publish command to MQTT
#         if MQTT_CLIENT:
#             cmd = json.dumps({"action": "suppress", "source": "dashboard"})
#             MQTT_CLIENT.publish("fire_detection/command", cmd)
#             return {"status": "suppression_command_sent"}
#         else:
#             raise HTTPException(status_code=503, detail="MQTT client not available")

# @app.post("/reset_alarm")
# async def reset_alarm():
#     """
#     Reset the fire alarm (clear fire state) – for testing only.
#     """
#     global state
#     if state["fire"]:
#         state["fire"] = False
#         alert_msg = f"🔄 Alarm reset manually at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#         state["alerts"].insert(0, alert_msg)
#         state["alerts"] = state["alerts"][:10]
#         if not MOCK_HARDWARE and MQTT_CLIENT:
#             # Optionally publish a reset command to main system
#             MQTT_CLIENT.publish("fire_detection/command", json.dumps({"action": "reset"}))
#         return {"status": "alarm_reset"}
#     else:
#         return {"status": "no_active_alarm"}

# # ------------------------------------------------------------------
# # HTML Dashboard (no video, only sensor data + action buttons)
# # ------------------------------------------------------------------
# html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Fire System Dashboard</title>
#     <style>
#         body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
#         .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
#         .safe { background: #10b981; }
#         .danger { background: #ef4444; animation: pulse 1s infinite; }
#         @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
#         .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
#         .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         .btn-group { display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }
#         .btn { padding: 0.8rem 2rem; border: none; border-radius: 2rem; font-size: 1.2rem; cursor: pointer; font-weight: bold; }
#         .btn-danger { background: #ef4444; color: white; }
#         .btn-warning { background: #f59e0b; color: black; }
#         .btn-secondary { background: #3b82f6; color: white; }
#         .btn:hover { opacity: 0.8; }
#     </style>
# </head>
# <body>
#     <h1>🔥 AI Fire Suppression System</h1>
#     <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
#     <div class="grid">
#         <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
#         <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
#         <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
#         <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
#     </div>
#     <div class="btn-group">
#         <button class="btn btn-danger" id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
#         <button class="btn btn-secondary" id="resetBtn">↺ RESET ALARM</button>
#     </div>
#     <div><h3>🚨 Recent Alerts</h3><div id="alerts"></div></div>

#     <script>
#         // WebSocket for real-time updates
#         const ws = new WebSocket(`ws://${window.location.host}/ws`);
#         ws.onmessage = function(event) {
#             const data = JSON.parse(event.data);
#             const statusDiv = document.getElementById('fireStatus');
#             if (data.fire) {
#                 statusDiv.className = 'status danger';
#                 statusDiv.innerHTML = '🚨 FIRE DETECTED! 🚨';
#             } else {
#                 statusDiv.className = 'status safe';
#                 statusDiv.innerHTML = '✅ SYSTEM SAFE ✅';
#             }
#             document.getElementById('temp').innerText = data.temperature;
#             document.getElementById('gas').innerText = data.gas;
#             const alertsDiv = document.getElementById('alerts');
#             if (data.alerts.length === 0) {
#                 alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
#             } else {
#                 alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a}</div>`).join('');
#             }
#         };

#         // Manual suppression button
#         document.getElementById('suppressBtn').addEventListener('click', async function() {
#             const res = await fetch('/suppress', { method: 'POST' });
#             const data = await res.json();
#             alert('Suppression command sent: ' + data.status);
#         });

#         // Reset alarm button
#         document.getElementById('resetBtn').addEventListener('click', async function() {
#             const res = await fetch('/reset_alarm', { method: 'POST' });
#             const data = await res.json();
#             alert('Alarm reset: ' + data.status);
#         });
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def get():
#     return HTMLResponse(html_content)

# # ------------------------------------------------------------------
# # Run the server
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     # Use port 8001 (as in your logs)
#     uvicorn.run(app, host="0.0.0.0", port=8001)