### Revised for Headless to reflect real GPIO Sensor inputs ###

import logging
import time
from collections import deque
from config import CONFIG

class TemperatureSensor:
    def __init__(self, pin=CONFIG["TEMP_PIN"], history_size=10, mock=CONFIG["MOCK_HARDWARE"]):
        """
        pin: GPIO pin number (BCM) where DHT11 data line is connected.
        mock: Set True for testing without real sensor.
        """
        self.pin = pin
        self.mock = mock
        self.history = deque(maxlen=history_size)
        self._device = None

        if not self.mock:
            try:
                import board
                import adafruit_dht
                # Convert BCM pin to board pin reference
                # Use getattr(board, f"D{pin}") - e.g., pin 4 becomes board.D4
                board_pin = getattr(board, f"D{self.pin}", None)
                if board_pin is None:
                    raise ValueError(f"Invalid GPIO pin {self.pin} for DHT11")
                self._device = adafruit_dht.DHT11(board_pin)
                logging.info(f"DHT11 initialized on GPIO {self.pin}")
            except ImportError:
                logging.warning("adafruit_dht not installed. Falling back to mock mode.")
                self.mock = True
            except Exception as e:
                logging.error(f"Failed to initialize DHT11: {e}. Using mock.")
                self.mock = True

    def _read_mock(self):
        """Simulate temperature readings for testing."""
        import random
        # Simulate room temperature (20–30°C) with occasional spikes
        return 25.0 + random.uniform(-3.0, 3.0)

    def _read_real(self):
        """Read temperature from DHT11 with retries."""
        if self._device is None:
            return None
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # DHT11 returns temperature in Celsius
                temperature = self._device.temperature
                if temperature is not None:
                    return temperature
                else:
                    logging.warning(f"DHT11 read returned None (attempt {attempt+1}/{max_retries})")
            except RuntimeError as e:
                # Common checksum or timing errors; retry
                logging.debug(f"DHT11 read error: {e}. Retrying...")
            except Exception as e:
                logging.error(f"Unexpected DHT11 error: {e}")
                break
            time.sleep(0.5)  # wait before retry
        logging.warning("Failed to read from DHT11 after multiple attempts")
        return None

    def read_temperature(self):
        """
        Returns the latest temperature reading (float).
        If reading fails, returns the last good value or a fallback.
        """
        if self.mock:
            temp = self._read_mock()
        else:
            temp = self._read_real()
            # Fallback to last known temperature if read fails
            if temp is None and self.history:
                temp = self.history[-1]
                logging.warning(f"Using last known temperature: {temp:.2f}°C")
            elif temp is None:
                temp = 25.0  # default fallback
                logging.warning("No previous temperature, using fallback 25.0°C")

        if temp is not None:
            self.history.append(temp)
        return temp

    def get_rolling_average(self):
        """Return average of last N readings (N = history_size)."""
        if not self.history:
            return None
        return sum(self.history) / len(self.history)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sensor = TemperatureSensor(mock=CONFIG["MOCK_HARDWARE"])
    for _ in range(5):
        t = sensor.read_temperature()
        avg = sensor.get_rolling_average()
        logging.info(f"Temp: {t:.2f}°C | Avg: {avg:.2f}°C")
        time.sleep(2)