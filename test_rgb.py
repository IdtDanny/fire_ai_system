#!/usr/bin/env python3
import time
from gpiozero import OutputDevice

# Define GPIO pins for RGB (BCM numbering)
RED_PIN = 13
GREEN_PIN = 26
BLUE_PIN = 19

# Initialize LED pins (common cathode – active HIGH)
red = OutputDevice(RED_PIN, initial_value=False)
green = OutputDevice(GREEN_PIN, initial_value=False)
blue = OutputDevice(BLUE_PIN, initial_value=False)

def all_off():
    red.off()
    green.off()
    blue.off()

def color(r, g, b):
    """r, g, b are booleans: True = on, False = off."""
    red.on() if r else red.off()
    green.on() if g else green.off()
    blue.on() if b else blue.off()

print("RGB LED Test (common cathode)")
print("Cycle: Red -> Green -> Blue -> Yellow -> Cyan -> Magenta -> White -> Off")
try:
    for _ in range(3):  # repeat 3 times
        color(1, 0, 0)    # Red
        time.sleep(1)
        color(0, 1, 0)    # Green
        time.sleep(1)
        color(0, 0, 1)    # Blue
        time.sleep(1)
        color(1, 1, 0)    # Yellow
        time.sleep(1)
        color(0, 1, 1)    # Cyan
        time.sleep(1)
        color(1, 0, 1)    # Magenta
        time.sleep(1)
        color(1, 1, 1)    # White
        time.sleep(1)
        all_off()
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    all_off()
    red.close()
    green.close()
    blue.close()
    print("Test finished.")