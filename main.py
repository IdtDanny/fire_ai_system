#!/usr/bin/env python3
"""
Main AI Fire Detection & Suppression System.
- Subscribes to MQTT commands from the dashboard.
- Differentiates between auto (hidden) and manual suppression alerts.
"""

import cv2
import time
import logging
import os
import json
import threading
from config import CONFIG
from camera.camera_stream import CameraStream
from ai.inference import InferencePipeline
from sensors.temp_sensor import TemperatureSensor
from sensors.gas_sensor import GasSensor
from fusion.decision_engine import DecisionEngine
from control.actuator import ActuatorController
from utils.alerter import Alerter
from utils.rgb_indicator import RGBIndicator
from utils.mqtt_publisher import MQTTPublisher
import paho.mqtt.client as mqtt

# ------------------------------------------------------------------
# Setup logging
# ------------------------------------------------------------------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("fire_system.log"),
            logging.StreamHandler()
        ]
    )

# ------------------------------------------------------------------
# Global state for manual suppression
# ------------------------------------------------------------------
manual_suppression_active = False
manual_suppression_lock = threading.Lock()

# ------------------------------------------------------------------
# MQTT command callback (for manual suppression) - NEW API V2
# ------------------------------------------------------------------
def on_command_message(client, userdata, message):
    """Callback when a command is received on fire_detection/command."""
    global manual_suppression_active
    try:
        payload = message.payload.decode()
        cmd = json.loads(payload)
        action = cmd.get("action")
        source = cmd.get("source", "unknown")
        logging.info(f"Received MQTT command: {action} from {source}")

        if action == "suppress":
            logging.critical("Suppression activated via MQTT")
            if hasattr(on_command_message, 'actuator') and on_command_message.actuator:
                actuator = on_command_message.actuator
                # Set RGB to fire state (red blink) immediately
                if hasattr(on_command_message, 'rgb') and on_command_message.rgb:
                    on_command_message.rgb.set_state("fire")
                actuator.trigger_buzzer()
                actuator.actuate_linear(duration_forward=1, duration_reverse=1)

                # Publish alert based on source
                mqtt_pub = on_command_message.mqtt_pub if hasattr(on_command_message, 'mqtt_pub') else None
                if mqtt_pub:
                    if source == "auto":
                        # Hidden trigger: pretend it's a real fire detection
                        alert_msg = "FIRE CONFIRMED: Fire detected by vision/sensors (auto suppression triggered)"
                        mqtt_pub.publish_alert(alert_msg, 2)
                        # Also publish fire status to keep subscribers in sync
                        mqtt_pub.publish_fire_status(True)
                    else:
                        # Manual button or any other source
                        alert_msg = "Manual suppression activated"
                        mqtt_pub.publish_alert(alert_msg, 2)

                # Clear manual flag after 12 seconds (suppression done)
                def clear_manual_flag():
                    global manual_suppression_active
                    with manual_suppression_lock:
                        manual_suppression_active = False
                    logging.info("Manual suppression flag cleared")
                threading.Timer(12.0, clear_manual_flag).start()

                # Publish response
                client.publish("fire_detection/command/response", "Suppression activated")
            else:
                logging.warning("Actuator or RGB not available for command")
        elif action == "reset":
            logging.info("Reset command received (ignored for now)")
        else:
            logging.warning(f"Unknown command action: {action}")
    except Exception as e:
        logging.error(f"Error processing MQTT command: {e}")

# ------------------------------------------------------------------
# Main function
# ------------------------------------------------------------------
def main():
    global manual_suppression_active
    setup_logging()
    logging.info("Starting AI Fire Detection & Suppression System...")

    # Initialize modules
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

        actuator = ActuatorController(
            pump_pin=CONFIG["PUMP_PIN"],
            buzzer_pin=CONFIG["BUZZER_PIN"],
            pump_back=CONFIG["PUMP_BACK"],
            mock=CONFIG["MOCK_HARDWARE"]
        )

        alerter = Alerter(
            slack_webhook_url=CONFIG.get("SLACK_WEBHOOK"),
            telegram_token=CONFIG.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=CONFIG.get("TELEGRAM_CHAT_ID"),
            smtp_config=CONFIG.get("SMTP_CONFIG"),
            gsm_phone_number=CONFIG.get("GSM_PHONE_NUMBER"),
            gsm_port=CONFIG.get("GSM_PORT", "/dev/ttyS0")
        )

        rgb = RGBIndicator(
            red_pin=CONFIG.get("RGB_RED_PIN", 13),
            green_pin=CONFIG.get("RGB_GREEN_PIN", 26),
            blue_pin=CONFIG.get("RGB_BLUE_PIN", 19),
            mock=CONFIG["MOCK_HARDWARE"]
        )

        # MQTT Publisher
        mqtt_pub = MQTTPublisher()
        mqtt_pub.connect()

        # MQTT Command Subscriber (new API)
        cmd_client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="fire_main_cmd"
        )
        cmd_client.username_pw_set(CONFIG.get("MQTT_USER"), CONFIG.get("MQTT_PASSWORD"))
        # Attach objects to callback
        on_command_message.actuator = actuator
        on_command_message.rgb = rgb
        on_command_message.mqtt_pub = mqtt_pub
        cmd_client.on_message = on_command_message
        cmd_client.connect(CONFIG.get("MQTT_BROKER", "localhost"), CONFIG.get("MQTT_PORT", 1883), 60)
        cmd_client.subscribe("fire_detection/command")
        cmd_thread = threading.Thread(target=cmd_client.loop_forever, daemon=True)
        cmd_thread.start()
        logging.info("MQTT command subscriber started")

    except Exception as e:
        logging.error(f"Initialization Failed: {e}")
        return

    logging.info("System Initialized and Running.")

    # State tracking
    cooldown_time = 0
    last_sensor_publish = 0
    last_fire_state = False
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

            # MQTT: Publish sensor data every 5 seconds
            if time.time() - last_sensor_publish >= 5:
                mqtt_pub.publish_sensor_data(avg_temp, gas_val)
                last_sensor_publish = time.time()

            # MQTT: Publish fire status only on change
            fire_detected = (decision == 2)
            if fire_detected != last_fire_state:
                mqtt_pub.publish_fire_status(fire_detected)
                last_fire_state = fire_detected

            # RGB control
            with manual_suppression_lock:
                if manual_suppression_active:
                    rgb.set_state("fire")
                else:
                    if decision == 1:
                        rgb.set_state("warning")
                    elif decision == 2:
                        rgb.set_state("fire")
                    else:
                        rgb.set_state("normal")

            # Actions
            if decision > 0:
                details = f"Temp: {avg_temp:.1f}C, Gas: {gas_val}, Vis: {len(detections)} detection(s)"
                alerter.trigger_all(decision, details)

                if decision == 1:   # Warning
                    mqtt_pub.publish_alert(f"WARNING: {details}", 1)
                    actuator.trigger_buzzer()
                elif decision == 2: # Fire
                    mqtt_pub.publish_alert(f"FIRE CONFIRMED: {details}", 2)
                    if time.time() > cooldown_time:
                        actuator.trigger_buzzer()
                        actuator.actuate_linear(duration_forward=1, duration_reverse=1)
                        cooldown_time = time.time() + 30
                    else:
                        logging.info("Suppression on cooldown...")
            else:
                actuator.stop_buzzer()

            # Headless GUI
            if not headless:
                annotated_frame = ai_pipeline.annotate_frame(frame, detections)
                cv2.imshow('AI Fire Detection (Press Q to exit)', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logging.info("Shutdown signal received.")
                    break
            else:
                pass

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
        rgb.cleanup()
        mqtt_pub.disconnect()
        cmd_client.disconnect()
        logging.info("System Shutdown Complete.")

if __name__ == "__main__":
    main()

# ## For Headless - No manual intervation or control from dashboard ###

# import cv2
# import time
# import logging
# import os
# from config import CONFIG
# from camera.camera_stream import CameraStream
# from ai.inference import InferencePipeline
# from sensors.temp_sensor import TemperatureSensor
# from sensors.gas_sensor import GasSensor
# from fusion.decision_engine import DecisionEngine
# from control.actuator import ActuatorController
# from utils.alerter import Alerter
# import RPi.GPIO as GPIO
# #from control.stepper_controller import StepperController
# from utils.rgb_indicator import RGBIndicator

# GPIO.setmode(GPIO.BCM)

# def setup_logging():
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s [%(levelname)s] %(message)s',
#         handlers=[
#             logging.FileHandler("fire_system.log"),
#             logging.StreamHandler()
#         ]
#     )

# def main():
#     setup_logging()
#     logging.info("Starting AI Fire Detection & Suppression System...")

#     # Initialize Modules
#     try:
#         camera = CameraStream(CONFIG["CAMERA_INDEX"], CONFIG["FRAME_WIDTH"], CONFIG["FRAME_HEIGHT"])
#         ai_pipeline = InferencePipeline(CONFIG["MODEL_PATH"], CONFIG["CONFIDENCE_THRESHOLD"])
        
#         temp_sensor = TemperatureSensor(pin=CONFIG["TEMP_PIN"], mock=CONFIG["MOCK_HARDWARE"])
#         gas_sensor = GasSensor(pin=CONFIG["GAS_PIN"], mock=CONFIG["MOCK_HARDWARE"], threshold=CONFIG["GAS_THRESHOLD"])
        
#         decision_engine = DecisionEngine(
#             temp_threshold=CONFIG["TEMP_THRESHOLD"], 
#             gas_threshold=CONFIG["GAS_THRESHOLD"],
#             fire_conf_threshold=CONFIG["CONFIDENCE_THRESHOLD"],
#             high_fire_conf=CONFIG["HIGH_FIRE_CONF"]
#         )
        
#         actuator = ActuatorController(pump_pin=CONFIG["PUMP_PIN"], buzzer_pin=CONFIG["BUZZER_PIN"], pump_back=CONFIG["PUMP_BACK"], mock=CONFIG["MOCK_HARDWARE"])
#         # alerter = Alerter(slack_webhook_url=CONFIG["SLACK_WEBHOOK"])
#         alerter = Alerter(
#             slack_webhook_url=CONFIG.get("SLACK_WEBHOOK"),
#             telegram_token=CONFIG.get("TELEGRAM_BOT_TOKEN"),
#             telegram_chat_id=CONFIG.get("TELEGRAM_CHAT_ID"),
#             smtp_config=CONFIG.get("SMTP_CONFIG"),
#             gsm_phone_number=CONFIG.get("GSM_PHONE_NUMBER"),
#             gsm_port=CONFIG.get("GSM_PORT", "/dev/ttyS0")
#         )

#         rgb = RGBIndicator(
#             red_pin=CONFIG.get("RGB_RED_PIN", 13),
#             green_pin=CONFIG.get("RGB_GREEN_PIN", 26),
#             blue_pin=CONFIG.get("RGB_BLUE_PIN", 19),
#             mock=CONFIG["MOCK_HARDWARE"]
#         )

#         #stepper = StepperController(step_pin=5, dir_pin=6, enable_pin=13, mock=CONFIG["MOCK_HARDWARE"])
#         #stepper = StepperController()
        
#     except Exception as e:
#         logging.error(f"Initialization Failed: {e}")
#         return

#     logging.info("System Initialized and Running.")
    
#     # State tracking
#     cooldown_time = 0

#     # Optional: set HEADLESS=1 in environment to disable all GUI
#     headless = os.environ.get('HEADLESS', '1') == '1'  # default headless

#     try:
#         while True:
#             start_time = time.time()
            
#             # 1. Capture Frame
#             frame = camera.read_frame()
#             if frame is None:
#                 logging.warning("Skipping empty frame...")
#                 time.sleep(0.1)
#                 continue
                
#             # 2. Sensor Readings
#             temp = temp_sensor.read_temperature()
#             avg_temp = temp_sensor.get_rolling_average()
#             gas_val = gas_sensor.read_value()
            
#             # 3. Vision Inference
#             detections = ai_pipeline.process_frame(frame)
            
#             # 4. Sensor Fusion Decision
#             decision = decision_engine.evaluate(detections, avg_temp, gas_val)
            
#             # 5. Take Action
#             if decision > 0:
#                 details = f"Temp: {avg_temp:.1f}C, Gas: {gas_val}, Vis: {len(detections)} detection(s)"
#                 alerter.trigger_all(decision, details)
                
#                 if decision == 1:
#                     rgb.set_state("warning")
#                     actuator.trigger_buzzer()
#                 elif decision == 2:
#                     rgb.set_state("fire")
#                     if time.time() > cooldown_time:
#                         actuator.trigger_buzzer()
#                         actuator.actuate_linear(duration_forward=5, duration_reverse=5)
#                         # actuator.trigger_pump(duration=5)
#                         #if stepper.available:
#                         #    stepper.activate()
#                         cooldown_time = time.time() + 30  # 30 second cooldown before spraying again
#                     else:
#                         logging.info("Suppression on cooldown...")
#             else:
#                 rgb.set_state("normal")
#                 actuator.stop_buzzer()

#             # --- HEADLESS MODE: No GUI calls ---
#             if not headless:
#                 # For demo purposes, visualize frame (only if display available)
#                 annotated_frame = ai_pipeline.annotate_frame(frame, detections)
#                 cv2.imshow('AI Fire Detection (Press Q to exit)', annotated_frame)
#                 # Cap FPS slightly to allow sensors to breathe and UI to update
#                 if cv2.waitKey(1) & 0xFF == ord('q'):
#                     logging.info("Shutdown signal received.")
#                     break
#             else:
#                 # Optional: save a debug frame every N iterations
#                 # if int(start_time) % 300 == 0:   # every ~30 seconds
#                 #     cv2.imwrite("debug_frame.jpg", frame)
#                 pass

#             # Keep loop under 10 FPS to simulate a real Raspberry Pi processing constraint,
#             # wait up to 100ms
#             elapsed = time.time() - start_time
#             if elapsed < 0.1:
#                 time.sleep(0.1 - elapsed)

#     except KeyboardInterrupt:
#         logging.info("Interrupted by user.")
#     except Exception as e:
#         logging.error(f"Runtime error: {e}")
#     finally:
#         camera.release()
#         if not headless:
#             cv2.destroyAllWindows()
#         actuator.stop_buzzer()
#         actuator.stop_pump()
#         rgb.cleanup()
#         logging.info("System Shutdown Complete.")

# if __name__ == "__main__":
#     main()

#----------------------------------

### For windows ###

# import cv2
# import time
# import logging
# from config import CONFIG
# from camera.camera_stream import CameraStream
# from ai.inference import InferencePipeline
# from sensors.temp_sensor import TemperatureSensor
# from sensors.gas_sensor import GasSensor
# from fusion.decision_engine import DecisionEngine
# from control.actuator import ActuatorController
# from utils.alerter import Alerter

# def setup_logging():
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s [%(levelname)s] %(message)s',
#         handlers=[
#             logging.FileHandler("fire_system.log"),
#             logging.StreamHandler()
#         ]
#     )

# def main():
#     setup_logging()
#     logging.info("Starting AI Fire Detection & Suppression System...")

#     # Initialize Modules
#     try:
#         camera = CameraStream(CONFIG["CAMERA_INDEX"], CONFIG["FRAME_WIDTH"], CONFIG["FRAME_HEIGHT"])
#         ai_pipeline = InferencePipeline(CONFIG["MODEL_PATH"], CONFIG["CONFIDENCE_THRESHOLD"])
        
#         temp_sensor = TemperatureSensor(pin=CONFIG["TEMP_PIN"], mock=CONFIG["MOCK_HARDWARE"])
#         gas_sensor = GasSensor(pin=CONFIG["GAS_PIN"], mock=CONFIG["MOCK_HARDWARE"], threshold=CONFIG["GAS_THRESHOLD"])
        
#         decision_engine = DecisionEngine(
#             temp_threshold=CONFIG["TEMP_THRESHOLD"], 
#             gas_threshold=CONFIG["GAS_THRESHOLD"],
#             fire_conf_threshold=CONFIG["CONFIDENCE_THRESHOLD"],
#             high_fire_conf=CONFIG["HIGH_FIRE_CONF"]
#         )
        
#         actuator = ActuatorController(pump_pin=CONFIG["PUMP_PIN"], buzzer_pin=CONFIG["BUZZER_PIN"], mock=CONFIG["MOCK_HARDWARE"])
#         alerter = Alerter(slack_webhook_url=CONFIG["SLACK_WEBHOOK"])
        
#     except Exception as e:
#         logging.error(f"Initialization Failed: {e}")
#         return

#     logging.info("System Initialized and Running.")
    
#     # State tracking
#     cooldown_time = 0

#     try:
#         while True:
#             start_time = time.time()
            
#             # 1. Capture Frame
#             frame = camera.read_frame()
#             if frame is None:
#                 logging.warning("Skipping empty frame...")
#                 time.sleep(0.1)
#                 continue
                
#             # 2. Sensor Readings
#             temp = temp_sensor.read_temperature()
#             avg_temp = temp_sensor.get_rolling_average()
#             gas_val = gas_sensor.read_value()
            
#             # 3. Vision Inference
#             detections = ai_pipeline.process_frame(frame)
            
#             # 4. Sensor Fusion Decision
#             decision = decision_engine.evaluate(detections, avg_temp, gas_val)
            
#             # 5. Take Action
#             if decision > 0:
#                 details = f"Temp: {avg_temp:.1f}C, Gas: {gas_val}, Vis: {len(detections)} detection(s)"
#                 alerter.trigger_all(decision, details)
                
#                 if decision == 1:
#                     actuator.trigger_buzzer()
#                 elif decision == 2:
#                     if time.time() > cooldown_time:
#                         actuator.trigger_buzzer()
#                         actuator.trigger_pump(duration=5)
#                         cooldown_time = time.time() + 30 # 30 second cooldown before spraying again
#                     else:
#                         logging.info("Suppression on cooldown...")
#             else:
#                 actuator.stop_buzzer()

#             # For demo purposes, visualize frame
#             annotated_frame = ai_pipeline.annotate_frame(frame, detections)
#             cv2.imshow('AI Fire Detection (Press Q to exit)', annotated_frame)

#             # Cap FPS slightly to allow sensors to breathe and UI to update
#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 logging.info("Shutdown signal received.")
#                 break
                
#             # Keep loop under 10 FPS to simulate a real Raspberry Pi processing constraint,
#             # wait up to 100ms
#             elapsed = time.time() - start_time
#             if elapsed < 0.1:
#                 time.sleep(0.1 - elapsed)

#     except KeyboardInterrupt:
#         logging.info("Interrupted by user.")
#     except Exception as e:
#         logging.error(f"Runtime error: {e}")
#     finally:
#         camera.release()
#         cv2.destroyAllWindows()
#         actuator.stop_buzzer()
#         actuator.stop_pump()
#         logging.info("System Shutdown Complete.")

# if __name__ == "__main__":
#     main()