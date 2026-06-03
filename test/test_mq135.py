import RPi.GPIO as GPIO
import time

GAS_SENSOR_DIGITAL_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(GAS_SENSOR_DIGITAL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

print("Monitoring MQ-135 digital output. Press Ctrl+C to stop.")
try:
    while True:
        sensor_state = GPIO.input(GAS_SENSOR_DIGITAL_PIN)
        if sensor_state == GPIO.HIGH:
            print("HIGH: Sensor threshold exceeded")
        else:
            print("LOW: Sensor reading normal")
        time.sleep(1)
except KeyboardInterrupt:
    print("Test stopped.")
finally:
    GPIO.cleanup()