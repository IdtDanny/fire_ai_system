import RPi.GPIO as GPIO
import time

BUZZER_PIN = 17   # Replace with your CONFIG["BUZZER_PIN"]
PUMP_PIN = 27     # Replace with your CONFIG["PUMP_PIN"]

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(PUMP_PIN, GPIO.OUT)

print("Buzzer on")
GPIO.output(BUZZER_PIN, 1)
time.sleep(1)
GPIO.output(BUZZER_PIN, 0)

print("Pump relay on")
GPIO.output(PUMP_PIN, 1)
time.sleep(1)
GPIO.output(PUMP_PIN, 0)

GPIO.cleanup()