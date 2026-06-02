# #!/usr/bin/env python3
# import RPi.GPIO as GPIO
# from config import CONFIG
# from sensors.temp_sensor import TemperatureSensor
# from sensors.gas_sensor import GasSensor
# import cv2

# GPIO.setmode(GPIO.BCM)
# GPIO.setwarnings(False)

# print("Testing Temperature Sensor...")
# temp = TemperatureSensor(pin=CONFIG["TEMP_PIN"], mock=False)
# t = temp.read_temperature()
# print(f"Temp: {t}°C, avg: {temp.get_rolling_average():.1f}")

# print("Testing Gas Sensor...")
# gas = GasSensor(pin=CONFIG["GAS_PIN"], mock=False, threshold=CONFIG["GAS_THRESHOLD"])
# val = gas.read_value()
# print(f"Gas value: {val}")

# print("Testing Camera...")
# cap = cv2.VideoCapture(CONFIG["CAMERA_INDEX"])
# ret, frame = cap.read()
# print(f"Camera OK: {ret}, frame shape: {frame.shape if ret else None}")
# cap.release()

# print("Testing Actuator Pins (pump, buzzer) – will toggle for 1 sec")
# GPIO.setup(CONFIG["PUMP_PIN"], GPIO.OUT)
# GPIO.setup(CONFIG["BUZZER_PIN"], GPIO.OUT)
# GPIO.output(CONFIG["PUMP_PIN"], 1)
# GPIO.output(CONFIG["BUZZER_PIN"], 1)
# time.sleep(1)
# GPIO.output(CONFIG["PUMP_PIN"], 0)
# GPIO.output(CONFIG["BUZZER_PIN"], 0)
# GPIO.cleanup()
# print("Done.")

### Headless AI fire ###

#!/usr/bin/env python3
# """
# Headless sensor test script for AI Fire Detection System.
# Run on Raspberry Pi (or any PC) without GUI dependencies.
# """
import time
import sys
from config import CONFIG

# ------------------------------------------------------------------
# 1. Handle GPIO gracefully (optional)
# ------------------------------------------------------------------
GPIO = None
try:
    if not CONFIG.get("MOCK_HARDWARE", False):
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        print("GPIO: Using real hardware mode")
    else:
        print("GPIO: Mock mode (no real pins)")
except ImportError:
    print("GPIO: RPi.GPIO not installed – running in simulation mode")
    CONFIG["MOCK_HARDWARE"] = True

# ------------------------------------------------------------------
# 2. Import sensors (they support mock mode)
# ------------------------------------------------------------------
from sensors.temp_sensor import TemperatureSensor
from sensors.gas_sensor import GasSensor

# ------------------------------------------------------------------
# 3. Camera test (headless OpenCV)
# ------------------------------------------------------------------
def test_camera():
    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV not installed. Run: pip install opencv-python-headless")
        return False

    cap = cv2.VideoCapture(CONFIG["CAMERA_INDEX"])
    if not cap.isOpened():
        print(f"ERROR: Cannot open camera index {CONFIG['CAMERA_INDEX']}")
        return False

    ret, frame = cap.read()
    cap.release()

    if ret:
        h, w = frame.shape[:2]
        print(f"Camera OK: {w}x{h} pixels")
        return True
    else:
        print("ERROR: Camera read failed – check connection")
        return False

# ------------------------------------------------------------------
# 4. Temperature sensor test
# ------------------------------------------------------------------
def test_temperature():
    try:
        temp = TemperatureSensor(
            pin=CONFIG["TEMP_PIN"],
            mock=CONFIG.get("MOCK_HARDWARE", False)
        )
        t = temp.read_temperature()
        avg = temp.get_rolling_average()
        print(f"Temperature: {t}°C (rolling avg: {avg:.1f}°C)")
        return t is not None
    except Exception as e:
        print(f"Temperature sensor error: {e}")
        return False

# ------------------------------------------------------------------
# 5. Gas sensor test
# ------------------------------------------------------------------
def test_gas():
    try:
        gas = GasSensor(
            pin=CONFIG["GAS_PIN"],
            mock=CONFIG.get("MOCK_HARDWARE", False),
            threshold=CONFIG["GAS_THRESHOLD"]
        )
        val = gas.read_value()
        print(f"Gas sensor value: {val}")
        return val is not None
    except Exception as e:
        print(f"Gas sensor error: {e}")
        return False

# ------------------------------------------------------------------
# 6. Actuator test (only if real GPIO available and not mock)
# ------------------------------------------------------------------
def test_actuators():
    if CONFIG.get("MOCK_HARDWARE", False) or GPIO is None:
        print("Actuator test skipped (mock mode or no GPIO)")
        return True

    try:
        pump_pin = CONFIG["PUMP_PIN"]
        buzzer_pin = CONFIG["BUZZER_PIN"]

        GPIO.setup(pump_pin, GPIO.OUT)
        GPIO.setup(buzzer_pin, GPIO.OUT)

        print("Testing buzzer (1 sec)...")
        GPIO.output(buzzer_pin, 1)
        time.sleep(1)
        GPIO.output(buzzer_pin, 0)

        print("Testing pump relay (1 sec)...")
        GPIO.output(pump_pin, 1)
        time.sleep(1)
        GPIO.output(pump_pin, 0)

        print("Actuators OK")
        return True
    except Exception as e:
        print(f"Actuator test error: {e}")
        return False
    finally:
        if GPIO:
            GPIO.cleanup()

# ------------------------------------------------------------------
# 7. Main test runner
# ------------------------------------------------------------------
def main():
    print("\n=== AI Fire System Hardware Test (Headless) ===\n")
    
    results = []
    
    # Camera
    print("[1/4] Testing Camera...")
    results.append(("Camera", test_camera()))
    
    # Temperature sensor
    print("\n[2/4] Testing Temperature Sensor...")
    results.append(("Temperature", test_temperature()))
    
    # Gas sensor
    print("\n[3/4] Testing Gas Sensor...")
    results.append(("Gas", test_gas()))
    
    # Actuators
    print("\n[4/4] Testing Actuators...")
    results.append(("Actuators", test_actuators()))
    
    # Summary
    print("\n=== RESULTS ===")
    all_ok = True
    for name, status in results:
        print(f"{name:15} : {'✓ PASS' if status else '✗ FAIL'}")
        if not status:
            all_ok = False
    
    if all_ok:
        print("\n✅ All tests passed. System is ready.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check connections and configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()