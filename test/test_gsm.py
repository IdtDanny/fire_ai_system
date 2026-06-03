import serial

# --- Use the correct serial port ---
# On a Raspberry Pi 3 (and later models) with Bluetooth enabled, the primary UART is often '/dev/ttyS0'.
# If you have disabled Bluetooth, it may be '/dev/ttyAMA0'.
# You may need to check which one works for your system.
SERIAL_PORT = "/dev/ttyS0"
BAUDRATE = 9600
TIMEOUT = 1

try:
    # Open the serial connection
    with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT) as ser:
        # Send the basic AT command to check communication
        ser.write(b'AT\r\n')
        # Read the response
        response = ser.read(100)
        print(f"Response: {response}")

except serial.SerialException as e:
    print(f"Could not open serial port: {e}")
except Exception as e:
    print(f"An error occurred: {e}")