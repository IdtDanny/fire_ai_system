import time
import logging
from control.actuator import ActuatorController

logging.basicConfig(level=logging.INFO)

# Force mock=False manually
actuator = ActuatorController(pump_pin=18, buzzer_pin=23, mock=False)
actuator.trigger_buzzer()
time.sleep(3)
actuator.stop_buzzer()
actuator.cleanup()