# """
# Complete FastAPI Dashboard with:
# - Live MJPEG video stream (supports USB or Pi Camera)
# - WebSocket for real‑time sensor & fire status
# - Mock mode when MOCK_HARDWARE = True (displays test pattern)
# - Uses OpenCV for camera capture
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import cv2
# import numpy as np
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import HTMLResponse, StreamingResponse
# from config import CONFIG

# app = FastAPI()

# # ------------------------------------------------------------------
# # Global state (shared with WebSocket clients)
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
# CAMERA_INDEX = CONFIG.get("CAMERA_INDEX", 0)

# # ------------------------------------------------------------------
# # Camera handling (real or mock)
# # ------------------------------------------------------------------
# def get_camera():
#     """Return an OpenCV VideoCapture object or None if mock mode."""
#     if MOCK_HARDWARE:
#         return None
#     cap = cv2.VideoCapture(CAMERA_INDEX)
#     if not cap.isOpened():
#         print(f"Warning: Could not open camera index {CAMERA_INDEX}")
#         return None
#     return cap

# def generate_mock_frame():
#     """Generate a dummy test pattern for mock mode."""
#     frame = np.zeros((480, 640, 3), dtype=np.uint8)
#     # Draw some moving pattern to show "live"
#     t = int(time.time() * 2) % 100
#     cv2.putText(frame, f"MOCK MODE - No Camera", (50, 200),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
#     cv2.putText(frame, f"Time: {time.strftime('%H:%M:%S')}", (50, 300),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
#     # Add a moving square
#     x = (t * 10) % 590
#     cv2.rectangle(frame, (x, 400), (x+50, 450), (0, 255, 0), -1)
#     return frame

# def generate_frames():
#     """Generator for MJPEG stream."""
#     cap = get_camera()
#     try:
#         while True:
#             if MOCK_HARDWARE or cap is None:
#                 frame = generate_mock_frame()
#                 ret = True
#             else:
#                 ret, frame = cap.read()
#                 if not ret:
#                     # If camera fails, fallback to mock
#                     frame = generate_mock_frame()
#             # Encode frame as JPEG
#             ret, buffer = cv2.imencode('.jpg', frame)
#             if not ret:
#                 continue
#             frame_bytes = buffer.tobytes()
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
#             time.sleep(0.05)  # ~20 fps
#     finally:
#         if cap is not None:
#             cap.release()

# @app.get("/video_feed")
# async def video_feed():
#     """MJPEG streaming endpoint."""
#     return StreamingResponse(generate_frames(),
#                              media_type="multipart/x-mixed-replace; boundary=frame")

# # ------------------------------------------------------------------
# # Data source: Mock or MQTT
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
#             # 3% chance to trigger fire (for testing dashboard)
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 alert_time = time.strftime('%Y-%m-%d %H:%M:%S')
#                 alert_msg = f"🔥 MOCK FIRE DETECTED at {alert_time}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:10]
#                 last_alert_time = time.time()
#                 # Auto‑reset after 5 seconds
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# def mqtt_worker():
#     """Subscribe to MQTT broker for real sensor data."""
#     import paho.mqtt.client as mqtt
#     global state
#     def on_message(client, userdata, msg):
#         nonlocal state
#         payload = msg.payload.decode()
#         if msg.topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#             was = state["fire"]
#             state["fire"] = (payload == "FIRE_DETECTED")
#             if state["fire"] and not was:
#                 alert_msg = f"🔥 FIRE DETECTED at {time.strftime('%Y-%m-%d %H:%M:%S')}"
#                 state["alerts"].insert(0, alert_msg)
#                 state["alerts"] = state["alerts"][:10]
#         elif msg.topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#             try:
#                 data = json.loads(payload)
#                 state["temperature"] = data.get("temperature", "--")
#                 state["gas"] = data.get("gas", "--")
#             except:
#                 pass
#     client = mqtt.Client()
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     client.loop_forever()

# # Start the appropriate background thread
# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket for real‑time state updates
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
# # Embedded HTML Dashboard (with live video)
# # ------------------------------------------------------------------
# html_content = """
# <!DOCTYPE html>
# <html>
# <head>
#     <title>Fire System Dashboard (FastAPI)</title>
#     <style>
#         body { background: #0f172a; color: white; font-family: system-ui; padding: 2rem; }
#         .status { padding: 2rem; border-radius: 2rem; text-align: center; font-size: 2rem; margin-bottom: 2rem; }
#         .safe { background: #10b981; }
#         .danger { background: #ef4444; animation: pulse 1s infinite; }
#         @keyframes pulse { 0% { opacity:1; } 50% { opacity:0.8; } 100% { opacity:1; } }
#         .grid { display: flex; gap: 1.5rem; flex-wrap: wrap; }
#         .card { background: #1e293b; padding: 1.5rem; border-radius: 1.5rem; flex:1; min-width:200px; }
#         .video-card { background: #1e293b; padding: 1rem; border-radius: 1.5rem; margin-top: 1.5rem; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         img { width: 100%; border-radius: 1rem; }
#     </style>
# </head>
# <body>
#     <h1>🔥 AI Fire Suppression System (FastAPI + WebSockets)</h1>
#     <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
#     <div class="grid">
#         <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
#         <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
#         <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
#         <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
#     </div>
#     <div class="video-card">
#         <h3>📹 Live Video Feed</h3>
#         <img src="/video_feed" alt="Live Stream">
#     </div>
#     <div><h3>🚨 Recent Alerts</h3><div id="alerts"></div></div>
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
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def get():
#     return HTMLResponse(html_content)

# # ------------------------------------------------------------------
# # Run the server (if executed directly)
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8001)

# """
# Complete FastAPI Dashboard fulfilling all requirements:
# - /dashboard (HTML)
# - /video_feed (MJPEG with YOLOv8 bounding boxes)
# - /logs (JSON alert history)
# - /status (JSON sensor readings)
# - /suppress (POST manual override)
# - Background MQTT or mock data thread
# """

# import json
# import asyncio
# import random
# import time
# import threading
# import cv2
# import numpy as np
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
# from pydantic import BaseModel
# from config import CONFIG

# # Optional: YOLO import (ensure ultralytics is installed)
# try:
#     from ultralytics import YOLO
#     YOLO_AVAILABLE = True
# except ImportError:
#     YOLO_AVAILABLE = False
#     print("Warning: ultralytics not installed. Video feed will not have YOLO boxes.")

# app = FastAPI()

# # ------------------------------------------------------------------
# # Global state & alert history
# # ------------------------------------------------------------------
# state = {
#     "fire": False,
#     "temperature": "--",
#     "gas": "--",
#     "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
#     "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
#     "camera_active": True,
# }
# alert_history = []  # list of dicts: {"timestamp": "...", "level": 2, "message": "..."}
# ALERT_HISTORY_MAX = 50

# # Manual override flag (if True, system suppresses even without fire)
# manual_override_active = False

# MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
# CAMERA_INDEX = CONFIG.get("CAMERA_INDEX", 0)

# # ------------------------------------------------------------------
# # YOLO Model (load once)
# # ------------------------------------------------------------------
# yolo_model = None
# if YOLO_AVAILABLE and not MOCK_HARDWARE:
#     try:
#         yolo_model = YOLO(CONFIG.get("MODEL_PATH", "yolov8n.pt"))
#         print("YOLO model loaded for video stream.")
#     except Exception as e:
#         print(f"Failed to load YOLO model: {e}")

# def add_alert(level, message):
#     """Add an alert to history (in-memory)."""
#     alert = {
#         "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
#         "level": level,
#         "message": message
#     }
#     alert_history.insert(0, alert)
#     # Keep only last N alerts
#     while len(alert_history) > ALERT_HISTORY_MAX:
#         alert_history.pop()

# # ------------------------------------------------------------------
# # Camera & YOLO frame generation
# # ------------------------------------------------------------------
# def get_camera():
#     if MOCK_HARDWARE:
#         return None
#     cap = cv2.VideoCapture(CAMERA_INDEX)
#     if not cap.isOpened():
#         print(f"Warning: Could not open camera index {CAMERA_INDEX}")
#         return None
#     return cap

# def process_frame_with_yolo(frame):
#     """Run YOLO inference and draw bounding boxes on frame."""
#     if yolo_model is None:
#         return frame
#     # Run inference
#     results = yolo_model(frame, conf=CONFIG.get("CONFIDENCE_THRESHOLD", 0.5))
#     # Annotate frame
#     annotated = results[0].plot()  # returns BGR numpy array
#     return annotated

# def generate_mock_frame():
#     """Test pattern for mock mode."""
#     frame = np.zeros((480, 640, 3), dtype=np.uint8)
#     t = int(time.time() * 2) % 100
#     cv2.putText(frame, f"MOCK MODE - No Camera", (50, 200),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
#     cv2.putText(frame, f"Time: {time.strftime('%H:%M:%S')}", (50, 300),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
#     x = (t * 10) % 590
#     cv2.rectangle(frame, (x, 400), (x+50, 450), (0, 255, 0), -1)
#     return frame

# def generate_frames():
#     """Generator for MJPEG stream with YOLO bounding boxes."""
#     cap = get_camera()
#     try:
#         while True:
#             if MOCK_HARDWARE or cap is None:
#                 frame = generate_mock_frame()
#             else:
#                 ret, frame = cap.read()
#                 if not ret:
#                     frame = generate_mock_frame()
#                 else:
#                     # Apply YOLO detection if available
#                     frame = process_frame_with_yolo(frame)
#             ret, buffer = cv2.imencode('.jpg', frame)
#             if not ret:
#                 continue
#             frame_bytes = buffer.tobytes()
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
#             time.sleep(0.05)  # ~20 fps
#     finally:
#         if cap is not None:
#             cap.release()

# @app.get("/video_feed")
# async def video_feed():
#     return StreamingResponse(generate_frames(),
#                              media_type="multipart/x-mixed-replace; boundary=frame")

# # ------------------------------------------------------------------
# # Data source: Mock or MQTT (same as before)
# # ------------------------------------------------------------------
# def mock_data_worker():
#     global state
#     last_alert_time = 0
#     while True:
#         if state["fire"] or manual_override_active:
#             temp = random.uniform(55, 80)
#             gas = random.randint(700, 1023)
#         else:
#             temp = random.uniform(18, 28)
#             gas = random.randint(50, 300)
#             if random.random() < 0.03 and time.time() - last_alert_time > 10:
#                 state["fire"] = True
#                 add_alert(2, "🔥 MOCK FIRE DETECTED")
#                 last_alert_time = time.time()
#                 threading.Timer(5.0, lambda: state.update({"fire": False})).start()
#         state["temperature"] = round(temp, 1)
#         state["gas"] = gas
#         time.sleep(2)

# def mqtt_worker():
#     import paho.mqtt.client as mqtt
#     global state
#     def on_message(client, userdata, msg):
#         nonlocal state
#         payload = msg.payload.decode()
#         if msg.topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
#             was = state["fire"]
#             state["fire"] = (payload == "FIRE_DETECTED")
#             if state["fire"] and not was:
#                 add_alert(2, "🔥 REAL FIRE DETECTED via MQTT")
#         elif msg.topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
#             try:
#                 data = json.loads(payload)
#                 state["temperature"] = data.get("temperature", "--")
#                 state["gas"] = data.get("gas", "--")
#             except:
#                 pass
#     client = mqtt.Client()
#     client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
#     client.on_message = on_message
#     client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
#     client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
#     client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
#     client.loop_forever()

# if MOCK_HARDWARE:
#     threading.Thread(target=mock_data_worker, daemon=True).start()
# else:
#     threading.Thread(target=mqtt_worker, daemon=True).start()

# # ------------------------------------------------------------------
# # WebSocket for real-time UI updates
# # ------------------------------------------------------------------
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     try:
#         while True:
#             await websocket.send_text(json.dumps({
#                 "fire": state["fire"] or manual_override_active,
#                 "temperature": state["temperature"],
#                 "gas": state["gas"],
#                 "manual_override": manual_override_active
#             }))
#             await asyncio.sleep(0.5)
#     except WebSocketDisconnect:
#         pass

# # ------------------------------------------------------------------
# # REST API endpoints (required)
# # ------------------------------------------------------------------
# @app.get("/status")
# async def get_status():
#     """JSON endpoint for current sensor readings and fire status."""
#     return {
#         "fire": state["fire"] or manual_override_active,
#         "temperature": state["temperature"],
#         "gas": state["gas"],
#         "manual_override": manual_override_active,
#         "timestamp": time.time()
#     }

# @app.get("/logs")
# async def get_logs():
#     """JSON endpoint for alert history."""
#     return {"alerts": alert_history}

# class SuppressRequest(BaseModel):
#     action: str  # "activate" or "reset"

# @app.post("/suppress")
# async def manual_suppress(request: SuppressRequest):
#     """Manual override: activate suppression or reset."""
#     global manual_override_active
#     if request.action == "activate":
#         manual_override_active = True
#         add_alert(1, "Manual suppression activated by administrator")
#         # Optionally, trigger the actual actuator here (call your ActuatorController)
#         return {"status": "suppression_activated", "manual_override": True}
#     elif request.action == "reset":
#         manual_override_active = False
#         add_alert(1, "Manual suppression reset by administrator")
#         return {"status": "suppression_reset", "manual_override": False}
#     else:
#         raise HTTPException(status_code=400, detail="Action must be 'activate' or 'reset'")

# # ------------------------------------------------------------------
# # HTML Dashboard (includes manual suppression button)
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
#         .video-card { background: #1e293b; padding: 1rem; border-radius: 1.5rem; margin-top: 1.5rem; }
#         .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
#         img { width: 100%; border-radius: 1rem; }
#         button { background: #ef4444; border: none; color: white; padding: 1rem 2rem; font-size: 1.2rem; border-radius: 2rem; cursor: pointer; margin-top: 1rem; }
#         button.reset { background: #3b82f6; }
#         .override-active { background: #f59e0b; }
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
#     <div style="text-align: center; margin: 1rem;">
#         <button id="suppressBtn" style="background: #ef4444;">🧯 MANUAL SUPPRESSION</button>
#         <button id="resetSuppressBtn" class="reset" style="background: #3b82f6;">↺ RESET MANUAL</button>
#     </div>
#     <div class="video-card">
#         <h3>📹 Live Video Feed (YOLO detections)</h3>
#         <img src="/video_feed" alt="Live Stream">
#     </div>
#     <div><h3>🚨 Alert Log</h3><div id="alerts"></div></div>
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
#             // Update alert log via separate fetch (or keep WebSocket only for status; but we also need logs)
#         };
#         // Fetch alert logs every 5 seconds
#         async function fetchLogs() {
#             const res = await fetch('/logs');
#             const data = await res.json();
#             const alertsDiv = document.getElementById('alerts');
#             if (data.alerts.length === 0) {
#                 alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
#             } else {
#                 alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a.timestamp} [Level ${a.level}] ${a.message}</div>`).join('');
#             }
#         }
#         fetchLogs();
#         setInterval(fetchLogs, 5000);
#         // Manual suppression buttons
#         document.getElementById('suppressBtn').onclick = async () => {
#             const res = await fetch('/suppress', {
#                 method: 'POST',
#                 headers: { 'Content-Type': 'application/json' },
#                 body: JSON.stringify({ action: 'activate' })
#             });
#             const data = await res.json();
#             alert('Manual suppression activated');
#         };
#         document.getElementById('resetSuppressBtn').onclick = async () => {
#             const res = await fetch('/suppress', {
#                 method: 'POST',
#                 headers: { 'Content-Type': 'application/json' },
#                 body: JSON.stringify({ action: 'reset' })
#             });
#             const data = await res.json();
#             alert('Manual suppression reset');
#         };
#     </script>
# </body>
# </html>
# """

# @app.get("/")
# async def dashboard():
#     return HTMLResponse(html_content)

# # ------------------------------------------------------------------
# # Run with Gunicorn? (for production, see instructions)
# # ------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8001)

#!/usr/bin/env python3
"""
FastAPI Dashboard for AI Fire Suppression System
Implements:
- / (HTML dashboard)
- /video_feed (MJPEG stream with YOLO detections)
- /logs (JSON alert history)
- /status (JSON sensor readings)
- /suppress (POST manual override)
- WebSocket /ws for live status updates
"""

import json
import asyncio
import random
import time
import threading
import cv2
import numpy as np
import subprocess
import socket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from config import CONFIG

# Optional YOLO (if available)
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: ultralytics not installed. Video feed will not have YOLO boxes.")

app = FastAPI()

# ------------------------------------------------------------------
# Global state & alert history
# ------------------------------------------------------------------
state = {
    "fire": False,
    "temperature": "--",
    "gas": "--",
    "model": CONFIG.get("MODEL_PATH", "yolov8n.pt"),
    "confidence": CONFIG.get("CONFIDENCE_THRESHOLD", 0.5),
    "camera_active": True,
}
alert_history = []          # list of dict: {"timestamp": str, "level": int, "message": str}
ALERT_HISTORY_MAX = 50
manual_override_active = False

MOCK_HARDWARE = CONFIG.get("MOCK_HARDWARE", False)
CAMERA_INDEX = CONFIG.get("CAMERA_INDEX", 0)

# ------------------------------------------------------------------
# YOLO model (load once)
# ------------------------------------------------------------------
yolo_model = None
if YOLO_AVAILABLE and not MOCK_HARDWARE:
    try:
        yolo_model = YOLO(CONFIG.get("MODEL_PATH", "yolov8n.pt"))
        print("YOLO model loaded for video stream.")
    except Exception as e:
        print(f"Failed to load YOLO model: {e}")

def add_alert(level, message):
    """Add an alert to the in‑memory history."""
    alert = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": message
    }
    alert_history.insert(0, alert)
    while len(alert_history) > ALERT_HISTORY_MAX:
        alert_history.pop()

# ------------------------------------------------------------------
# Camera & video feed with YOLO
# ------------------------------------------------------------------
def get_camera():
    if MOCK_HARDWARE:
        return None
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)  # force V4L2 backend
    if not cap.isOpened():
        print(f"Warning: Could not open camera index {CAMERA_INDEX}")
        return None
    return cap

def process_frame_with_yolo(frame):
    """Run YOLO inference and return annotated frame (BGR)."""
    if yolo_model is None:
        return frame
    results = yolo_model(frame, conf=CONFIG.get("CONFIDENCE_THRESHOLD", 0.5))
    annotated = results[0].plot()
    return annotated

def generate_mock_frame():
    """Generate a dummy test pattern for mock mode."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    t = int(time.time() * 2) % 100
    cv2.putText(frame, "MOCK MODE - No Camera", (50, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(frame, f"Time: {time.strftime('%H:%M:%S')}", (50, 300),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    x = (t * 10) % 590
    cv2.rectangle(frame, (x, 400), (x+50, 450), (0, 255, 0), -1)
    return frame

def generate_frames():
    """Generator for MJPEG stream with YOLO boxes (if available)."""
    cap = get_camera()
    try:
        while True:
            if MOCK_HARDWARE or cap is None:
                frame = generate_mock_frame()
            else:
                ret, frame = cap.read()
                if not ret:
                    frame = generate_mock_frame()
                else:
                    frame = process_frame_with_yolo(frame)
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.05)   # ~20 fps
    finally:
        if cap is not None:
            cap.release()

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generate_frames(),
                             media_type="multipart/x-mixed-replace; boundary=frame")

# ------------------------------------------------------------------
# Data source: Mock or MQTT
# ------------------------------------------------------------------
def mock_data_worker():
    """Simulate sensor data and random fire events."""
    global state
    last_alert_time = 0
    while True:
        if state["fire"] or manual_override_active:
            temp = random.uniform(55, 80)
            gas = random.randint(700, 1023)
        else:
            temp = random.uniform(18, 28)
            gas = random.randint(50, 300)
            # 3% chance to trigger a mock fire (only if not already)
            if not state["fire"] and random.random() < 0.03 and time.time() - last_alert_time > 10:
                state["fire"] = True
                add_alert(2, "🔥 MOCK FIRE DETECTED")
                last_alert_time = time.time()
                # Auto‑reset after 5 seconds
                threading.Timer(5.0, lambda: state.update({"fire": False})).start()
        state["temperature"] = round(temp, 1)
        state["gas"] = gas
        time.sleep(2)

def mqtt_worker():
    """Subscribe to MQTT broker for real sensor data."""
    import paho.mqtt.client as mqtt
    def on_message(client, userdata, msg):
        payload = msg.payload.decode()
        if msg.topic == CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"):
            was = state["fire"]
            state["fire"] = (payload == "FIRE_DETECTED")
            if state["fire"] and not was:
                add_alert(2, "🔥 REAL FIRE DETECTED via MQTT")
        elif msg.topic == CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"):
            try:
                data = json.loads(payload)
                state["temperature"] = data.get("temperature", "--")
                state["gas"] = data.get("gas", "--")
            except:
                pass
    client = mqtt.Client()
    client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
    client.on_message = on_message
    client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
    client.subscribe(CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status"))
    client.subscribe(CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors"))
    client.loop_forever()

if MOCK_HARDWARE:
    threading.Thread(target=mock_data_worker, daemon=True).start()
else:
    threading.Thread(target=mqtt_worker, daemon=True).start()

# ------------------------------------------------------------------
# WebSocket for real‑time UI updates
# ------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps({
                "fire": state["fire"] or manual_override_active,
                "temperature": state["temperature"],
                "gas": state["gas"],
                "manual_override": manual_override_active
            }))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass

# ------------------------------------------------------------------
# REST API endpoints
# ------------------------------------------------------------------
@app.get("/status")
async def get_status():
    return {
        "fire": state["fire"] or manual_override_active,
        "temperature": state["temperature"],
        "gas": state["gas"],
        "manual_override": manual_override_active,
        "timestamp": time.time()
    }

@app.get("/logs")
async def get_logs():
    return {"alerts": alert_history}

class SuppressRequest(BaseModel):
    action: str  # "activate" or "reset"

@app.post("/suppress")
async def manual_suppress(request: SuppressRequest):
    global manual_override_active
    if request.action == "activate":
        manual_override_active = True
        add_alert(1, "Manual suppression activated by administrator")
        return {"status": "suppression_activated", "manual_override": True}
    elif request.action == "reset":
        manual_override_active = False
        add_alert(1, "Manual suppression reset by administrator")
        return {"status": "suppression_reset", "manual_override": False}
    else:
        raise HTTPException(status_code=400, detail="Action must be 'activate' or 'reset'")

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
        .video-card { background: #1e293b; padding: 1rem; border-radius: 1.5rem; margin-top: 1.5rem; }
        .alert-item { background: #0f172a; margin: 0.5rem 0; padding: 0.8rem; border-radius: 0.8rem; border-left: 4px solid #ef4444; }
        img { width: 100%; border-radius: 1rem; }
        button { background: #ef4444; border: none; color: white; padding: 1rem 2rem; font-size: 1.2rem; border-radius: 2rem; cursor: pointer; margin-top: 1rem; margin-right: 1rem; }
        button.reset { background: #3b82f6; }
    </style>
</head>
<body>
    <h1>🔥 AI Fire Suppression System</h1>
    <div id="fireStatus" class="status safe">✅ SYSTEM SAFE</div>
    <div class="grid">
        <div class="card"><h3>🌡️ Temp</h3><span id="temp">--</span> °C</div>
        <div class="card"><h3>💨 Gas</h3><span id="gas">--</span></div>
        <div class="card"><h3>📷 Camera</h3><span id="camera">Active</span></div>
        <div class="card"><h3>🧠 Model</h3><span id="model">yolov8n.pt</span></div>
    </div>
    <div style="text-align: center; margin: 1rem;">
        <button id="suppressBtn">🧯 MANUAL SUPPRESSION</button>
        <button id="resetSuppressBtn" class="reset">↺ RESET MANUAL</button>
    </div>
    <div class="video-card">
        <h3>📹 Live Video Feed (YOLO detections)</h3>
        <img src="/video_feed" alt="Live Stream">
    </div>
    <div><h3>🚨 Alert Log</h3><div id="alerts"></div></div>
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
        };
        async function fetchLogs() {
            const res = await fetch('/logs');
            const data = await res.json();
            const alertsDiv = document.getElementById('alerts');
            if (data.alerts.length === 0) {
                alertsDiv.innerHTML = '<div class="alert-item">No alerts</div>';
            } else {
                alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-item">${a.timestamp} [Level ${a.level}] ${a.message}</div>`).join('');
            }
        }
        fetchLogs();
        setInterval(fetchLogs, 5000);
        document.getElementById('suppressBtn').onclick = async () => {
            await fetch('/suppress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'activate' })
            });
            alert('Manual suppression activated');
        };
        document.getElementById('resetSuppressBtn').onclick = async () => {
            await fetch('/suppress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'reset' })
            });
            alert('Manual suppression reset');
        };
    </script>
</body>
</html>
"""

@app.get("/")
async def dashboard():
    return HTMLResponse(html_content)

# ------------------------------------------------------------------
# Helper to get local IP address
# ------------------------------------------------------------------
def get_local_ip():
    try:
        # Use hostname -I to get the first IP
        output = subprocess.check_output(["hostname", "-I"]).decode().strip().split()
        if output:
            return output[0]
    except:
        pass
    try:
        # Fallback: connect to a public DNS to get the active interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ------------------------------------------------------------------
# Main entry point (if run directly)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    # Get local IP address
    ip = get_local_ip()
    port = 8000  # default, you can change this or read from environment

    print("\n" + "="*60)
    print(f"🌐 Dashboard available at:")
    print(f"   http://{ip}:{port}")
    print(f"   (Press Ctrl+C to stop)")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=port)