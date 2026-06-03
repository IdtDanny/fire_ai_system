import serial
import logging
import time

class GSMAlerter:
    def __init__(self, port="/dev/ttyAMA0", baudrate=9600, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.available = False

        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.available = True
            logging.info(f"GSM Alerter initialized on {self.port}")
            # Flush any initial data
            self._send_command("AT")
        except Exception as e:
            logging.error(f"Failed to initialize GSM module: {e}")

    def _send_command(self, command, wait=0.5):
        """Send an AT command and return the response."""
        if not self.available:
            return None
        try:
            self.serial_conn.write(f"{command}\r\n".encode())
            time.sleep(wait)
            response = self.serial_conn.read(self.serial_conn.in_waiting or 100)
            return response.decode().strip()
        except Exception as e:
            logging.error(f"GSM communication error: {e}")
            return None

    def _setup_sms_mode(self):
        """Set the GSM module to SMS text mode."""
        if self._send_command("AT+CMGF=1") is not None:
            logging.info("GSM module set to SMS text mode")
            return True
        return False

    def send_sms(self, phone_number, message):
        """Send an SMS message."""
        if not self.available:
            logging.warning("GSM alerter not available")
            return False

        if not self._setup_sms_mode():
            return False

        # Send the command with the phone number
        response = self._send_command(f'AT+CMGS="{phone_number}"', wait=0.5)
        if ">" not in (response or ""):
            logging.error("GSM module not ready for SMS")
            return False

        # Send the message body followed by Ctrl+Z (chr(26))
        self.serial_conn.write(f"{message}\x1A".encode())
        time.sleep(2)

        # Read final response
        final_response = self.serial_conn.read(self.serial_conn.in_waiting or 100).decode().strip()
        if "+CMGS" in final_response:
            logging.info(f"SMS sent successfully to {phone_number}")
            return True
        else:
            logging.error(f"Failed to send SMS: {final_response}")
            return False

    def close(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("GSM serial connection closed")