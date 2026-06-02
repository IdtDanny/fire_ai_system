# import logging
# import time

# class ActuatorController:
#     def __init__(self, pump_pin=18, buzzer_pin=23, mock=False):
#         self.pump_pin = pump_pin
#         self.buzzer_pin = buzzer_pin
#         self.mock = mock
#         self.pump_on = False
#         self.buzzer_on = False
        
#         if not self.mock:
#             try:
#                 # Normally use gpiozero.OutputDevice or LED class
#                 # from gpiozero import OutputDevice
#                 # self.pump = OutputDevice(self.pump_pin)
#                 # self.buzzer = OutputDevice(self.buzzer_pin)
#                 pass
#             except ImportError:
#                 logging.warning("No GPIO libraries found, falling back to mock actuator.")
#                 self.mock = True
                
#     def trigger_pump(self, duration=5):
#         if self.pump_on:
#             return
            
#         logging.critical("WATER PUMP ACTIVATED.")
#         self.pump_on = True
        
#         if not self.mock:
#             # self.pump.on()
#             pass
            
#         time.sleep(duration)
#         self.stop_pump()
        
#     def stop_pump(self):
#         logging.info("WATER PUMP DEACTIVATED.")
#         self.pump_on = False
#         if not self.mock:
#             # self.pump.off()
#             pass
            
#     def trigger_buzzer(self):
#         if self.buzzer_on:
#             return
            
#         logging.warning("ALARM BUZZER ACTIVATED.")
#         self.buzzer_on = True
#         if not self.mock:
#             # self.buzzer.on()
#             pass
            
#     def stop_buzzer(self):
#         logging.info("ALARM BUZZER DEACTIVATED.")
#         self.buzzer_on = False
#         if not self.mock:
#             # self.buzzer.off()
#             pass
            
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     ctrl = ActuatorController(mock=True)
#     ctrl.trigger_buzzer()
#     time.sleep(2)
#     ctrl.trigger_pump(duration=3)
#     ctrl.stop_buzzer()

### Revised for Headless ###

import logging
import time
from config import CONFIG

class ActuatorController:
    """
    Controls the water pump and buzzer via GPIO pins.
    Uses gpiozero.OutputDevice for real hardware, falls back to mock if unavailable.
    """
    def __init__(self, pump_pin=CONFIG["PUMP_PIN"], buzzer_pin=CONFIG["BUZZER_PIN"], mock=CONFIG["MOCK_HARDWARE"]):
        self.pump_pin = pump_pin
        self.buzzer_pin = buzzer_pin
        self.mock = mock
        self.pump_on = False
        self.buzzer_on = False
        self.pump = None
        self.buzzer = None

        if not self.mock:
            try:
                from gpiozero import OutputDevice
                # Initialize the GPIO pins as outputs, starting in the OFF (False) state
                self.pump = OutputDevice(self.pump_pin, initial_value=False)
                self.buzzer = OutputDevice(self.buzzer_pin, initial_value=False)
                logging.info(f"GPIO initialized: pump on pin {pump_pin}, buzzer on pin {buzzer_pin}")
            except ImportError:
                logging.warning("gpiozero not installed. Falling back to mock actuator.")
                self.mock = True
            except Exception as e:
                logging.error(f"GPIO initialization failed: {e}. Falling back to mock actuator.")
                self.mock = True

    def trigger_pump(self, duration=5):
        """Turn the pump on for `duration` seconds, then turn it off."""
        if self.pump_on:
            logging.debug("Pump already running, skipping duplicate trigger.")
            return

        logging.critical("WATER PUMP ACTIVATED.")
        self.pump_on = True

        if not self.mock and self.pump:
            self.pump.on()
        else:
            logging.debug("Mock mode: pump would be ON now.")

        time.sleep(duration)

        # Turn the pump off after the duration
        self.stop_pump()

    def stop_pump(self):
        """Deactivate the pump immediately."""
        if not self.pump_on:
            return

        logging.info("WATER PUMP DEACTIVATED.")
        self.pump_on = False

        if not self.mock and self.pump:
            self.pump.off()
        else:
            logging.debug("Mock mode: pump would be OFF now.")

    def trigger_buzzer(self):
        """Turn the buzzer on (continuous sound)."""
        if self.buzzer_on:
            logging.debug("Buzzer already on, skipping duplicate trigger.")
            return

        logging.warning("ALARM BUZZER ACTIVATED.")
        self.buzzer_on = True

        if not self.mock and self.buzzer:
            self.buzzer.on()
        else:
            logging.debug("Mock mode: buzzer would be ON now.")

    def stop_buzzer(self):
        """Turn the buzzer off immediately."""
        if not self.buzzer_on:
            return

        logging.info("ALARM BUZZER DEACTIVATED.")
        self.buzzer_on = False

        if not self.mock and self.buzzer:
            self.buzzer.off()
        else:
            logging.debug("Mock mode: buzzer would be OFF now.")

    def cleanup(self):
        """Explicit cleanup of GPIO resources (called automatically on exit)."""
        self.stop_buzzer()
        self.stop_pump()
        if self.pump:
            self.pump.close()
        if self.buzzer:
            self.buzzer.close()
        logging.debug("Actuator GPIO resources released.")


if __name__ == "__main__":
    # Quick test routine when running this file directly
    logging.basicConfig(level=logging.INFO)
    ctrl = ActuatorController(mock=CONFIG["MOCK_HARDWARE"])   # Change to mock=False to test real hardware
    ctrl.trigger_buzzer()
    time.sleep(2)
    ctrl.trigger_pump(duration=3)
    ctrl.stop_buzzer()
    ctrl.cleanup()