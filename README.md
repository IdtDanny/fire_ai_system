# 🔥 AI Fire Detection & Suppression System

A real-time fire and smoke detection system using YOLOv8 computer vision, designed for indoor/warehouse environments. Runs on a laptop for development/testing and deploys to Raspberry Pi for production.

---

## 📁 Project Structure

```
fire_ai_system/
├── main.py                  # Entry point
├── config.py                # Central configuration
├── requirements.txt         # Python dependencies
├── ai/
│   ├── model.py             # YOLOv8 model wrapper
│   └── inference.py         # Frame processing & annotation
├── camera/
│   └── camera_stream.py     # Camera capture (OpenCV)
├── sensors/
│   ├── temp_sensor.py       # Temperature sensor (real or mocked)
│   └── gas_sensor.py        # Gas sensor (real or mocked)
├── fusion/
│   └── decision_engine.py   # Multi-modal fire decision logic
├── control/
│   └── actuator.py          # Pump & buzzer control (real or mocked)
└── utils/
    └── alerter.py           # Logging + Slack webhook alerts
```

---

## ⚙️ Setup

### 1. Create and activate a virtual environment

```bash
cd fire_ai_system
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The Raspberry Pi hardware libs (`gpiozero`, `Adafruit-DHT`) are commented out in `requirements.txt`. Only install them on the RPi.

---

## 🚀 Running the System

### Option A — Run with default COCO model (no fire training)

This runs immediately out of the box. The model won't detect fire yet, but you can verify the camera, pipeline, and decision engine all work.

```bash
cd fire_ai_system
source venv/bin/activate
python main.py
```

- A window opens showing your **laptop camera feed**
- Sensors are **automatically mocked** (temp ≈ 22°C, gas ≈ normal) — no hardware needed
- Press **`Q`** to quit
- Logs are written to `fire_system.log`

---

### Option B — Run with a pre-trained fire detection model

Download a fire/smoke detection `best.pt` from [Roboflow Universe](https://universe.roboflow.com/search?q=fire+smoke), then:

1. Place `best.pt` in the `fire_ai_system/` directory
2. Update `config.py`:

```python
"MODEL_PATH": "best.pt",
"CONFIDENCE_THRESHOLD": 0.45,   # Good starting point for indoor scenes
```

3. Run:

```bash
python main.py
```

The system will now detect fire and smoke in real time from your camera.

#### Downloading via Roboflow Python SDK

```bash
pip install roboflow
```

```python
from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_API_KEY")   # Free key from roboflow.com
project = rf.workspace("YOUR_WORKSPACE").project("YOUR_PROJECT")
version = project.version(1)
dataset = version.download("yolov8")
```

Your API key is found at **roboflow.com → top right menu → API Key**.

---

### Option C — Run using a video file instead of camera

Great for testing against fire footage without a live camera or real fire.

1. Download or record a fire/smoke test video
2. In `config.py`, change:

```python
"CAMERA_INDEX": "/absolute/path/to/fire_test_video.mp4",
```

3. Run as normal:

```bash
python main.py
```

---

## 🏋️ Training Your Own Model

Use this path when you want a model trained specifically on your warehouse environment.

### Step 1 — Download a fire/smoke dataset from Roboflow

```python
from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_API_KEY")
project = rf.workspace("WORKSPACE").project("PROJECT_NAME")
version = project.version(1)
dataset = version.download("yolov8")  # or "yolov5"
```

This creates a folder like `fire-detection-1/` with:
- `data.yaml` — class definitions and paths
- `train/`, `valid/`, `test/` — images and labels

### Step 2 — Train

```bash
yolo train \
  model=yolov8n.pt \         # Start from pretrained COCO weights
  data=fire-detection-1/data.yaml \
  epochs=50 \
  imgsz=640 \
  batch=16
```

> - Use `yolov8n.pt` (nano) for speed on laptop/RPi  
> - Use `yolov8m.pt` (medium) for better accuracy if GPU is available  
> - Training outputs are saved to `runs/detect/train/`

### Step 3 — Use your trained model

```bash
cp runs/detect/train/weights/best.pt fire_ai_system/best.pt
```

Update `config.py`:
```python
"MODEL_PATH": "best.pt",
```

Run the system — it will now use your custom-trained model.

---

## 🧪 Testing Tips

| Scenario | How to test |
|---|---|
| Fire detected (visual only) | Show a fire video/image to the camera → expect `WARNING` in logs |
| Fire + sensors alert | Edit `config.py`: lower `TEMP_THRESHOLD` to`21.0` to trigger mock sensor → expect `CRITICAL` |
| Full suppression trigger | Lower both temp threshold and fire confidence → expect pump + buzzer logs |
| Camera not found | Change `CAMERA_INDEX` to `1` or `2` if laptop has external camera |
| Video file input | Set `CAMERA_INDEX` to the video file path |

### Simulate a fire via sensors only (no camera)

In `config.py`, temporarily lower the threshold below the mock sensor value (~22°C):

```python
"TEMP_THRESHOLD": 20.0,   # Mock returns ~22°C, this will trigger sensor alert
```

---

## 🍓 Raspberry Pi Deployment

1. Uncomment RPi libs in `requirements.txt`:
   ```
   gpiozero
   Adafruit-DHT
   ```

2. Install on Pi:
   ```bash
   pip install -r requirements.txt
   ```

3. Set `MOCK_HARDWARE` to `False` in `config.py`:
   ```python
   "MOCK_HARDWARE": False,
   ```

4. Wire hardware to the correct GPIO pins as defined in `config.py`:
   - `TEMP_PIN`: DHT sensor data pin
   - `GAS_PIN`: Analog gas sensor pin
   - `PUMP_PIN`: Relay for water pump
   - `BUZZER_PIN`: Buzzer

5. Run:
   ```bash
   python main.py
   ```

---

## 🔔 Optional: Slack Alerts

To receive Slack notifications when fire is detected:

1. Create a Slack Incoming Webhook URL at [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)
2. Set it in `config.py`:

```python
"SLACK_WEBHOOK": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

---

## 📊 Decision Logic Summary

| Visual Detection | Sensor Reading | Decision |
|---|---|---|
| No fire/smoke | Normal | ✅ Normal (0) |
| Smoke detected | Normal | ⚠️ Alert (1) |
| Fire detected | Normal | ⚠️ Alert (1) |
| No fire | Temp/Gas high | ⚠️ Alert (1) |
| Fire detected | Temp/Gas high | 🚨 Suppression (2) |
| High conf fire | Extreme gas | 🚨 Suppression (2) |

- **Alert (1)** → Buzzer activated  
- **Suppression (2)** → Buzzer + water pump (30s cooldown between activations)
