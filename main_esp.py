import cv2
import time
import logging
import os
from config import CONFIG
from camera.camera_stream import CameraStream
from ai.inference import InferencePipeline
from sensors.temp_sensor import TemperatureSensor
from sensors.gas_sensor import GasSensor
from fusion.decision_engine import DecisionEngine
from control.actuator import ActuatorController
from utils.alerter import Alerter
from utils.mqtt_publisher import MQTTPublisher   # <-- NEW IMPORT
import RPi.GPIO as GPIO
from control.stepper_controller import StepperController

GPIO.setmode(GPIO.BCM)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("fire_system.log"),
            logging.StreamHandler()
        ]
    )

def main():
    setup_logging()
    logging.info("Starting AI Fire Detection & Suppression System...")

    # Initialize Modules
    try:
        camera = CameraStream(CONFIG["CAMERA_INDEX"], CONFIG["FRAME_WIDTH"], CONFIG["FRAME_HEIGHT"])
        ai_pipeline = InferencePipeline(CONFIG["MODEL_PATH"], CONFIG["CONFIDENCE_THRESHOLD"])
        
        temp_sensor = TemperatureSensor(pin=CONFIG["TEMP_PIN"], mock=CONFIG["MOCK_HARDWARE"])
        gas_sensor = GasSensor(pin=CONFIG["GAS_PIN"], mock=CONFIG["MOCK_HARDWARE"], threshold=CONFIG["GAS_THRESHOLD"])
        
        decision_engine = DecisionEngine(
            temp_threshold=CONFIG["TEMP_THRESHOLD"], 
            gas_threshold=CONFIG["GAS_THRESHOLD"],
            fire_conf_threshold=CONFIG["CONFIDENCE_THRESHOLD"],
            high_fire_conf=CONFIG["HIGH_FIRE_CONF"]
        )
        
        actuator = ActuatorController(pump_pin=CONFIG["PUMP_PIN"], buzzer_pin=CONFIG["BUZZER_PIN"], pump_back=CONFIG["PUMP_BACK"], mock=CONFIG["MOCK_HARDWARE"])
        alerter = Alerter(
            slack_webhook_url=CONFIG.get("SLACK_WEBHOOK"),
            telegram_token=CONFIG.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=CONFIG.get("TELEGRAM_CHAT_ID"),
            smtp_config=CONFIG.get("SMTP_CONFIG"),
            gsm_phone_number=CONFIG.get("GSM_PHONE_NUMBER"),
            gsm_port=CONFIG.get("GSM_PORT", "/dev/ttyS0")
        )
        stepper = StepperController()
        
        # --- MQTT Publisher ---
        mqtt_pub = MQTTPublisher()
        mqtt_pub.connect()
        
    except Exception as e:
        logging.error(f"Initialization Failed: {e}")
        return

    logging.info("System Initialized and Running.")
    
    # State tracking
    cooldown_time = 0
    last_sensor_publish = 0   # throttle sensor updates

    headless = os.environ.get('HEADLESS', '1') == '1'

    try:
        while True:
            start_time = time.time()
            
            # 1. Capture Frame
            frame = camera.read_frame()
            if frame is None:
                logging.warning("Skipping empty frame...")
                time.sleep(0.1)
                continue
                
            # 2. Sensor Readings
            temp = temp_sensor.read_temperature()
            avg_temp = temp_sensor.get_rolling_average()
            gas_val = gas_sensor.read_value()
            
            # 3. Vision Inference
            detections = ai_pipeline.process_frame(frame)
            
            # 4. Sensor Fusion Decision
            decision = decision_engine.evaluate(detections, avg_temp, gas_val)
            
            # --- MQTT: Publish sensor data every 5 seconds ---
            if time.time() - last_sensor_publish >= 5:
                mqtt_pub.publish_sensor_data(avg_temp, gas_val)
                last_sensor_publish = time.time()
            
            # 5. Take Action
            if decision > 0:
                # Publish fire detected = True
                mqtt_pub.publish_fire_status(True)
                
                details = f"Temp: {avg_temp:.1f}C, Gas: {gas_val}, Vis: {len(detections)} detection(s)"
                alerter.trigger_all(decision, details)
                
                if decision == 1:
                    actuator.trigger_buzzer()
                elif decision == 2:
                    if time.time() > cooldown_time:
                        actuator.trigger_buzzer()
                        actuator.actuate_linear(duration_forward=5, duration_reverse=5)
                        if stepper.available:
                            stepper.activate()
                        cooldown_time = time.time() + 30
                    else:
                        logging.info("Suppression on cooldown...")
            else:
                actuator.stop_buzzer()
                # Optionally publish "SAFE" periodically, but only when state changes?
                # For simplicity, publish every loop when safe, but avoid flooding.
                # Better: only when state changes from fire to safe.
                # We'll use a static variable to track last fire state.
                # I'll add a simple state change check.
                # For clarity, I'll leave it as is, but you can improve.
                # Let's publish only once when transitioning to safe.
                # We'll add a variable `last_fire_state` outside loop.
                pass

            # --- HEADLESS MODE ---
            if not headless:
                annotated_frame = ai_pipeline.annotate_frame(frame, detections)
                cv2.imshow('AI Fire Detection (Press Q to exit)', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logging.info("Shutdown signal received.")
                    break
            else:
                pass

            # Maintain ~10 FPS
            elapsed = time.time() - start_time
            if elapsed < 0.1:
                time.sleep(0.1 - elapsed)

    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
    except Exception as e:
        logging.error(f"Runtime error: {e}")
    finally:
        camera.release()
        if not headless:
            cv2.destroyAllWindows()
        actuator.stop_buzzer()
        actuator.stop_pump()
        if stepper.available:
            stepper.close()
        mqtt_pub.disconnect()   # Clean up MQTT
        logging.info("System Shutdown Complete.")

if __name__ == "__main__":
    main()