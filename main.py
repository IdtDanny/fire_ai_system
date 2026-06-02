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

### For Headless ###

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
        
        actuator = ActuatorController(pump_pin=CONFIG["PUMP_PIN"], buzzer_pin=CONFIG["BUZZER_PIN"], mock=CONFIG["MOCK_HARDWARE"])
        # alerter = Alerter(slack_webhook_url=CONFIG["SLACK_WEBHOOK"])
        alerter = Alerter(
            slack_webhook_url=CONFIG.get("SLACK_WEBHOOK"),
            telegram_token=CONFIG.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=CONFIG.get("TELEGRAM_CHAT_ID"),
            smtp_config=CONFIG.get("SMTP_CONFIG")
        )

        #stepper = StepperController(step_pin=5, dir_pin=6, enable_pin=13, mock=CONFIG["MOCK_HARDWARE"])
        stepper = StepperController()
        
    except Exception as e:
        logging.error(f"Initialization Failed: {e}")
        return

    logging.info("System Initialized and Running.")
    
    # State tracking
    cooldown_time = 0

    # Optional: set HEADLESS=1 in environment to disable all GUI
    headless = os.environ.get('HEADLESS', '1') == '1'  # default headless

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
            
            # 5. Take Action
            if decision > 0:
                details = f"Temp: {avg_temp:.1f}C, Gas: {gas_val}, Vis: {len(detections)} detection(s)"
                alerter.trigger_all(decision, details)
                
                if decision == 1:
                    actuator.trigger_buzzer()
                elif decision == 2:
                    if time.time() > cooldown_time:
                        actuator.trigger_buzzer()
                        actuator.trigger_pump(duration=5)
                        if stepper.available:
                            stepper.activate()
                        cooldown_time = time.time() + 30  # 30 second cooldown before spraying again
                    else:
                        logging.info("Suppression on cooldown...")
            else:
                actuator.stop_buzzer()

            # --- HEADLESS MODE: No GUI calls ---
            if not headless:
                # For demo purposes, visualize frame (only if display available)
                annotated_frame = ai_pipeline.annotate_frame(frame, detections)
                cv2.imshow('AI Fire Detection (Press Q to exit)', annotated_frame)
                # Cap FPS slightly to allow sensors to breathe and UI to update
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logging.info("Shutdown signal received.")
                    break
            else:
                # Optional: save a debug frame every N iterations
                # if int(start_time) % 300 == 0:   # every ~30 seconds
                #     cv2.imwrite("debug_frame.jpg", frame)
                pass

            # Keep loop under 10 FPS to simulate a real Raspberry Pi processing constraint,
            # wait up to 100ms
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
        logging.info("System Shutdown Complete.")

if __name__ == "__main__":
    main()