import logging
import time
import threading
from gpiozero import OutputDevice

class RGBIndicator:
    def __init__(self, red_pin=13, green_pin=26, blue_pin=19, mock=False):
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        self.mock = mock
        self.current_state = "normal"   # normal, warning, fire
        self.running = True
        self.thread = None

        if not self.mock:
            try:
                self.red = OutputDevice(red_pin, initial_value=False)
                self.green = OutputDevice(green_pin, initial_value=False)
                self.blue = OutputDevice(blue_pin, initial_value=False)
                logging.info(f"RGB LED initialized: R={red_pin}, G={green_pin}, B={blue_pin}")
            except Exception as e:
                logging.error(f"RGB LED init failed: {e}. Falling back to mock.")
                self.mock = True

        # Start background thread for blinking
        self.thread = threading.Thread(target=self._blink_loop, daemon=True)
        self.thread.start()

    def set_state(self, state):
        """state: 'normal', 'warning', 'fire'"""
        if state not in ("normal", "warning", "fire"):
            logging.warning(f"Invalid RGB state: {state}")
            return
        self.current_state = state

    def _blink_loop(self):
        """Background loop to handle blinking patterns."""
        blink_state = False
        last_toggle = time.time()
        interval = 0.5  # seconds per blink (on/off each 0.5s)

        while self.running:
            now = time.time()
            # Determine what the LEDs should do
            if self.current_state == "normal":
                # Green solid, others off
                if not self.mock:
                    self.green.on()
                    self.red.off()
                    self.blue.off()
                # No blinking, just sleep a bit
                time.sleep(0.2)
                continue

            elif self.current_state == "warning":
                # Blue blinking
                if now - last_toggle >= interval:
                    blink_state = not blink_state
                    last_toggle = now
                if not self.mock:
                    self.green.off()
                    self.red.off()
                    self.blue.value = blink_state
                time.sleep(0.05)

            elif self.current_state == "fire":
                # Red blinking
                if now - last_toggle >= interval:
                    blink_state = not blink_state
                    last_toggle = now
                if not self.mock:
                    self.green.off()
                    self.blue.off()
                    self.red.value = blink_state
                time.sleep(0.05)

            else:
                # Fallback: all off
                if not self.mock:
                    self.red.off()
                    self.green.off()
                    self.blue.off()
                time.sleep(0.2)

    def cleanup(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        if not self.mock:
            self.red.off()
            self.green.off()
            self.blue.off()
            self.red.close()
            self.green.close()
            self.blue.close()
        logging.info("RGB LED cleaned up")