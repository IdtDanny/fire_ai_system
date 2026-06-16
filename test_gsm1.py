import serial
import time

gsm = serial.Serial(
    port='/dev/serial0',
    baudrate=115200,
    timeout=1
)

time.sleep(2)

gsm.write(b'AT\r\n')
print(gsm.readline().decode())

gsm.write(b'ATI\r\n')
print(gsm.readline().decode())

gsm.close()