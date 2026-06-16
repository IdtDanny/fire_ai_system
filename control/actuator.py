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

# import logging
# import time
# from config import CONFIG

# class ActuatorController:
#     """
#     Controls the water pump and buzzer via GPIO pins.
#     Uses gpiozero.OutputDevice for real hardware, falls back to mock if unavailable.
#     """
#     def __init__(self, pump_pin=CONFIG["PUMP_PIN"], buzzer_pin=CONFIG["BUZZER_PIN"], mock=CONFIG["MOCK_HARDWARE"]):
#         self.pump_pin = pump_pin
#         self.buzzer_pin = buzzer_pin
#         self.mock = mock
#         self.pump_on = False
#         self.buzzer_on = False
#         self.pump = None
#         self.buzzer = None

#         if not self.mock:
#             try:
#                 from gpiozero import OutputDevice
#                 # Initialize the GPIO pins as outputs, starting in the OFF (False) state
#                 self.pump = OutputDevice(self.pump_pin, initial_value=False)
#                 self.buzzer = OutputDevice(self.buzzer_pin, initial_value=False)
#                 logging.info(f"GPIO initialized: pump on pin {pump_pin}, buzzer on pin {buzzer_pin}")
#             except ImportError:
#                 logging.warning("gpiozero not installed. Falling back to mock actuator.")
#                 self.mock = True
#             except Exception as e:
#                 logging.error(f"GPIO initialization failed: {e}. Falling back to mock actuator.")
#                 self.mock = True

#     def trigger_pump(self, duration=5):
#         """Turn the pump on for `duration` seconds, then turn it off."""
#         if self.pump_on:
#             logging.debug("Pump already running, skipping duplicate trigger.")
#             return

#         logging.critical("WATER PUMP ACTIVATED.")
#         self.pump_on = True

#         if not self.mock and self.pump:
#             self.pump.on()
#         else:
#             logging.debug("Mock mode: pump would be ON now.")

#         time.sleep(duration)

#         # Turn the pump off after the duration
#         self.stop_pump()

#     def stop_pump(self):
#         """Deactivate the pump immediately."""
#         if not self.pump_on:
#             return

#         logging.info("WATER PUMP DEACTIVATED.")
#         self.pump_on = False

#         if not self.mock and self.pump:
#             self.pump.off()
#         else:
#             logging.debug("Mock mode: pump would be OFF now.")

#     def trigger_buzzer(self):
#         """Turn the buzzer on (continuous sound)."""
#         if self.buzzer_on:
#             logging.debug("Buzzer already on, skipping duplicate trigger.")
#             return

#         logging.warning("ALARM BUZZER ACTIVATED.")
#         self.buzzer_on = True

#         if not self.mock and self.buzzer:
#             self.buzzer.on()
#         else:
#             logging.debug("Mock mode: buzzer would be ON now.")

#     def stop_buzzer(self):
#         """Turn the buzzer off immediately."""
#         if not self.buzzer_on:
#             return

#         logging.info("ALARM BUZZER DEACTIVATED.")
#         self.buzzer_on = False

#         if not self.mock and self.buzzer:
#             self.buzzer.off()
#         else:
#             logging.debug("Mock mode: buzzer would be OFF now.")

#     def cleanup(self):
#         """Explicit cleanup of GPIO resources (called automatically on exit)."""
#         self.stop_buzzer()
#         self.stop_pump()
#         if self.pump:
#             self.pump.close()
#         if self.buzzer:
#             self.buzzer.close()
#         logging.debug("Actuator GPIO resources released.")


# if __name__ == "__main__":
#     # Quick test routine when running this file directly
#     logging.basicConfig(level=logging.INFO)
#     ctrl = ActuatorController(mock=CONFIG["MOCK_HARDWARE"])   # Change to mock=False to test real hardware
#     ctrl.trigger_buzzer()
#     time.sleep(2)
#     ctrl.trigger_pump(duration=3)
#     ctrl.stop_buzzer()
#     ctrl.cleanup()

### Revised for Headless with GSM support and pump back control ###

import logging
import time
from config import CONFIG

class ActuatorController:
    """
    Controls:
      - Buzzer (GPIO)
      - Linear actuator via two relays: forward (pump_pin) and reverse (pump_back)
    Also maintains a mock mode for testing.
    """
    def __init__(self, pump_pin=CONFIG["PUMP_PIN"], pump_back=CONFIG["PUMP_BACK"],
                 buzzer_pin=CONFIG["BUZZER_PIN"], mock=CONFIG["MOCK_HARDWARE"]):
        self.pump_pin = pump_pin
        self.pump_back = pump_back
        self.buzzer_pin = buzzer_pin
        self.mock = mock

        # State flags
        self.forward_active = False
        self.reverse_active = False
        self.buzzer_on = False

        self.forward_relay = None
        self.reverse_relay = None
        self.buzzer = None

        if not self.mock:
            try:
                from gpiozero import OutputDevice
                # Forward relay (press extinguisher)
                self.forward_relay = OutputDevice(self.pump_pin, initial_value=False)
                # Reverse relay (retract)
                self.reverse_relay = OutputDevice(self.pump_back, initial_value=False)
                # Buzzer
                self.buzzer = OutputDevice(self.buzzer_pin, initial_value=False)
                logging.info(f"GPIO initialized: forward on pin {pump_pin}, "
                             f"reverse on pin {pump_back}, buzzer on {buzzer_pin}")
            except ImportError:
                logging.warning("gpiozero not installed. Falling back to mock actuator.")
                self.mock = True
            except Exception as e:
                logging.error(f"GPIO initialization failed: {e}. Falling back to mock.")
                self.mock = True

    # --- Buzzer methods (unchanged) ---
    def trigger_buzzer(self):
        if self.buzzer_on:
            return
        logging.warning("ALARM BUZZER ACTIVATED.")
        self.buzzer_on = True
        if not self.mock and self.buzzer:
            self.buzzer.on()
        else:
            logging.debug("Mock mode: buzzer would be ON now.")

    def stop_buzzer(self):
        if not self.buzzer_on:
            return
        logging.info("ALARM BUZZER DEACTIVATED.")
        self.buzzer_on = False
        if not self.mock and self.buzzer:
            self.buzzer.off()
        else:
            logging.debug("Mock mode: buzzer would be OFF now.")

    # --- Linear actuator control (forward + reverse with delays) ---
    def actuate_linear(self, duration_forward=5, duration_reverse=5, pause_between=0.5):
        """
        Moves the linear actuator forward (press extinguisher) for `duration_forward` seconds,
        then retracts (releases) for `duration_reverse` seconds.
        The two relays are never on at the same time.
        """
        if not self.mock and (self.forward_relay is None or self.reverse_relay is None):
            logging.error("Linear actuator not initialized (mock mode may be active).")
            return

        # --- Forward movement ---
        logging.critical("LINEAR ACTUATOR: EXTENDING (pressing extinguisher).")
        self.forward_active = True

        if not self.mock:
            self.forward_relay.on()
        else:
            logging.debug("Mock mode: forward relay would be ON now.")

        time.sleep(duration_forward)

        # Turn off forward relay
        if not self.mock:
            self.forward_relay.off()
        else:
            logging.debug("Mock mode: forward relay would be OFF now.")
        self.forward_active = False
        logging.info("Forward movement finished.")

        # Optional pause before reversing
        time.sleep(pause_between)

        # --- Reverse movement (retract) ---
        logging.info("LINEAR ACTUATOR: RETRACTING.")
        self.reverse_active = True

        if not self.mock:
            self.reverse_relay.on()
        else:
            logging.debug("Mock mode: reverse relay would be ON now.")

        time.sleep(duration_reverse)

        # Turn off reverse relay
        if not self.mock:
            self.reverse_relay.off()
        else:
            logging.debug("Mock mode: reverse relay would be OFF now.")
        self.reverse_active = False
        logging.info("Retraction finished. Actuator back to idle.")

    # --- Compatibility: if you still have a water pump, you can keep old method ---
    def trigger_pump(self, duration=5):
        """Legacy method – now calls actuate_linear with forward only? 
           We'll implement forward-only for backward compatibility."""
        self.actuate_linear(duration_forward=duration, duration_reverse=0)

    def stop_pump(self):
        """Emergency stop of all relays."""
        if not self.mock:
            if self.forward_relay:
                self.forward_relay.off()
            if self.reverse_relay:
                self.reverse_relay.off()
        self.forward_active = False
        self.reverse_active = False
        logging.info("All relays stopped.")

    # --- Cleanup ---
    def cleanup(self):
        self.stop_buzzer()
        self.stop_pump()
        if not self.mock:
            if self.forward_relay:
                self.forward_relay.close()
            if self.reverse_relay:
                self.reverse_relay.close()
            if self.buzzer:
                self.buzzer.close()
        logging.debug("Actuator GPIO resources released.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ctrl = ActuatorController(mock=CONFIG["MOCK_HARDWARE"])
    # Test buzzer
    ctrl.trigger_buzzer()
    time.sleep(2)
    ctrl.stop_buzzer()
    # Test linear actuator: extend 3 sec, retract 3 sec
    ctrl.actuate_linear(duration_forward=3, duration_reverse=3, pause_between=0.5)
    ctrl.cleanup()