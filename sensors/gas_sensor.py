import logging
import time
from config import CONFIG

class GasSensor:
    def __init__(self, pin=17, mock=CONFIG["MOCK_HARDWARE"], threshold=500):
        self.pin = pin
        self.mock = mock
        self.threshold = threshold
        self._gpio = None

        if not self.mock:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self._gpio = GPIO
                logging.info(f"Gas sensor (MQ-135 D0) initialized on GPIO {self.pin} (RPi.GPIO)")
            except Exception as e:
                logging.error(f"Failed to initialize gas sensor: {e}. Using mock.")
                self.mock = True

    def read_value(self):
        if self.mock:
            import random
            if random.random() > 0.95:
                return random.randint(600, 1023)
            return random.randint(0, 100)
        else:
            try:
                value = self._gpio.input(self.pin)
                # D0 is active HIGH (gas detected)
                return 1023 if value == 1 else 0
            except Exception as e:
                logging.error(f"Gas sensor read error: {e}")
                return 0

    def is_smoke_detected(self):
        val = self.read_value()
        detected = val > self.threshold
        if detected:
            logging.warning(f"Smoke/Gas detected! Value: {val} (Threshold: {self.threshold})")
        return detected

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gas_sensor = GasSensor(mock=CONFIG["MOCK_HARDWARE"])
    for _ in range(5):
        val = gas_sensor.read_value()
        detected = gas_sensor.is_smoke_detected()
        logging.info(f"Gas Value: {val} | Detected: {detected}")
        time.sleep(1)