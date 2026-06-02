import time
import board
import adafruit_dht
import logging

logging.basicConfig(level=logging.INFO)

# Initialize the DHT11 on GPIO 4 (board.D4)
try:
    dht_device = adafruit_dht.DHT11(board.D4)
    logging.info("DHT11 initialized on GPIO 4.")
except Exception as e:
    logging.error(f"Failed to initialize DHT11: {e}")
    exit(1)

while True:
    try:
        temperature = dht_device.temperature
        humidity = dht_device.humidity
        if temperature is not None and humidity is not None:
            logging.info(f"Temp: {temperature}°C  Humidity: {humidity}%")
        else:
            logging.warning("Read None values from sensor.")
    except RuntimeError as error:
        # DHT sensors often have read errors; just retry
        logging.error(f"Read error: {error.args[0]}")
    except Exception as error:
        dht_device.exit()
        raise error
    time.sleep(2)